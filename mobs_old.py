"""Animals that wander around the world."""
import math
import random
from pathlib import Path

from ursina import Entity, Vec2, Vec3, color, destroy, time

from mobmodel import build_part, convert, load_skin
from physics import Body
from sound import distance_volume
from shaders import entity_shader
from world import chunk_of

SKINS = Path(__file__).parent / 'assets' / 'textures' / 'entity'


def _part(parent, mesh, texture, pivot):
    """A body part that can swing around its pivot point (pivot is in model units)."""
    x, y, z = convert((pivot[0], pivot[1] - 24, pivot[2]))     # 24 units = ground level
    return Entity(parent=parent, model=mesh, texture=texture, shader=entity_shader,
                  double_sided=True, position=(x, y, z))


class Pig(Body):
    WALK_SPEED = 1.4
    HOP_SPEED = 9          # enough to rise a bit over one block (like the player's jump)
    MAX_HEALTH = 10

    def __init__(self, world, position, sound=None, player=None):
        super().__init__(world, position, width=0.9, height=0.9)
        self.sound = sound
        self.player = player
        self.oink_timer = random.uniform(3, 12)
        texture, size = load_skin(SKINS / 'pig_temperate.png')

        # Each part: boxes as (skin offset, box corner, box size), then where it pivots.
        head = build_part([((0, 0), (-4, -4, -8), (8, 8, 8)),        # head
                           ((16, 16), (-2, 0, -9), (4, 3, 1))], size)  # snout
        body = build_part([((28, 8), (-5, -10, -7), (10, 16, 8))], size, rotate_x=90)

        self.head = _part(self, head, texture, (0, 12, -6))
        self.body = _part(self, body, texture, (0, 11, 2))
        # Every leg needs its OWN mesh: an Entity takes the mesh it is given away from
        # any other Entity, so sharing one mesh would leave only a single leg.
        self.legs = [_part(self, build_part([((0, 16), (-2, 0, -2), (4, 6, 4))], size), texture, pivot)
                     for pivot in ((-3, 18, 7), (3, 18, 7), (-3, 18, -5), (3, 18, -5))]
        self.parts = [self.head, self.body, *self.legs]

        self.health = self.MAX_HEALTH
        self.walking = False
        self.timer = random.uniform(0.5, 3)
        self.heading = random.uniform(0, 360)
        self.stuck_for = 0
        self.knockback = Vec3(0, 0, 0)
        self.flash = 0           # seconds left of turning red after being hit
        self.walk_cycle = 0
        self.rotation_y = self.heading

    # ---- behavior --------------------------------------------------------

    def hurt(self, from_position, damage=1):
        """Called when the player hits the pig."""
        away = Vec3(self.x - from_position[0], 0, self.z - from_position[2]).normalized()
        self.knockback = away * 6
        self.velocity_y = 6
        self.flash = 0.3
        self.health -= damage
        self._say('mob/pig/death' if self.health <= 0 else 'mob/pig/say', loudness=1.3)
        if self.health <= 0:
            self.die()

    def _say(self, group, loudness=1.0):
        """Make a noise, quieter if the player is far away."""
        if self.sound and self.player:
            distance = math.dist(self.player.position, self.position)
            self.sound.play(group, distance_volume(distance) * loudness)

    def die(self):
        self.world_mobs.pig_died(self)

    def _choose_next_action(self):
        self.walking = not self.walking
        if self.walking:
            self.heading = random.uniform(0, 360)
            self.timer = random.uniform(2, 5)
            self.stuck_for = 0
        else:
            self.timer = random.uniform(1, 4)

    def update(self):
        dt = min(time.dt, 0.05)

        self.oink_timer -= dt
        if self.oink_timer <= 0:
            self._say('mob/pig/say')
            self.oink_timer = random.uniform(6, 16)

        self.timer -= dt
        if self.timer <= 0:
            self._choose_next_action()

        # Walk in the direction we are heading (turning smoothly)
        turn = (self.heading - self.rotation_y + 180) % 360 - 180
        self.rotation_y += max(-240 * dt, min(240 * dt, turn))
        move = Vec3(0, 0, 0)
        if self.walking:
            move += self.forward * self.WALK_SPEED
        move += self.knockback
        self.knockback *= 0.9 ** (dt * 60)

        blocked = self.move(0, move[0] * dt)
        blocked = self.move(2, move[2] * dt) or blocked
        if blocked and self.walking:
            self.stuck_for += dt
            if self.grounded:
                self.velocity_y = self.HOP_SPEED   # hop up a one-block step
            if self.stuck_for > 1.0:           # a wall: turn around
                self.heading += random.uniform(90, 270)
                self.stuck_for = 0
        if self.in_water():
            self.velocity_y = max(self.velocity_y, 1.5)   # paddle back up to the surface
        self.fall(dt)

        self._animate(dt)

    def _animate(self, dt):
        moving = self.walking or self.knockback.length() > 0.5
        if moving:
            self.walk_cycle += dt * 9
        swing = math.sin(self.walk_cycle) * 35 if moving else 0
        for i, leg in enumerate(self.legs):
            leg.rotation_x += (swing * (1 if i in (0, 3) else -1) - leg.rotation_x) * min(1, dt * 15)

        self.flash = max(0, self.flash - dt)
        tint = color.rgb32(255, 110, 110) if self.flash > 0 else color.white
        for part in self.parts:
            part.color = tint


class Mobs:
    """Keeps track of all the animals."""

    def __init__(self, world, sound=None, player=None):
        self.world = world
        self.sound = sound
        self.player = player
        self.pigs = []
        self.dropped = None      # set by main.py, so pigs can drop food
        self._spawn_timer = 3.0

    def _try_spawn_pig(self, x, z):
        """Place a pig on the grass at (x, z) if that is a good spot. Returns True if it did."""
        if (x >> 4, z >> 4) not in self.world.chunk_entities:
            return False                               # only where the land is shown
        ground = self.world.height_at(x, z)
        if self.world.get((x, ground, z)) != 'grass':
            return False                               # pigs live on grass (not sand, water, snow or rock)
        if self.world.is_solid((x, ground + 1, z)) or self.world.is_solid((x, ground + 2, z)):
            return False                               # under a tree
        self.add_pig((x, ground + 0.6, z))
        return True

    def spawn_pigs(self, count, around, radius=30):
        """Start with a few pigs near a point."""
        tries = 0
        while len(self.pigs) < count and tries < 500:
            tries += 1
            self._try_spawn_pig(int(around[0] + random.uniform(-radius, radius)),
                                int(around[2] + random.uniform(-radius, radius)))

    def update_spawning(self, dt):
        """Keep some pigs around the player as they explore: new ones appear nearby,
        pigs left far behind disappear."""
        self._spawn_timer -= dt
        if self._spawn_timer > 0:
            return
        self._spawn_timer = 3.0
        px, pz = self.player.x, self.player.z
        for pig in self.pigs[:]:
            if math.hypot(pig.x - px, pig.z - pz) > 110:
                self.remove(pig)
        nearby = sum(1 for pig in self.pigs if math.hypot(pig.x - px, pig.z - pz) < 70)
        if nearby < 8:
            angle, distance = random.uniform(0, 2 * math.pi), random.uniform(24, 56)
            self._try_spawn_pig(int(px + math.cos(angle) * distance), int(pz + math.sin(angle) * distance))

    def add_pig(self, position, rotation_y=None, health=None):
        pig = Pig(self.world, position, self.sound, self.player)
        pig.world_mobs = self
        if rotation_y is not None:
            pig.rotation_y = pig.heading = rotation_y
        if health is not None:
            pig.health = health
        self.pigs.append(pig)
        return pig

    def pig_died(self, pig):
        if self.dropped is not None:
            from inventory import Stack
            self.dropped.drop(Stack('porkchop', random.randint(1, 3)), (pig.x, pig.y + 0.5, pig.z))
        self.remove(pig)

    def remove(self, pig):
        self.pigs.remove(pig)
        destroy(pig)

    def overlaps_block(self, block):
        """Is an animal standing where this block would go?"""
        return any(pig.overlaps_block(block) for pig in self.pigs)

    def update_lighting(self):
        """Light each animal the way the air around it is lit."""
        for pig in self.pigs:
            sky, block = self.world.light_at((round(pig.x), round(pig.y + 0.45), round(pig.z)))
            pig.set_shader_input('entity_light', Vec2(sky, block))

    def update_visibility(self):
        """Animals in chunks that are not shown stand still and are hidden."""
        for pig in self.pigs:
            pig.enabled = chunk_of((round(pig.x), 0, round(pig.z))) in self.world.chunk_entities

    def hit_test(self, origin, direction, reach):
        """The nearest animal along a line: (animal, distance) or None."""
        best = None
        for pig in self.pigs:
            t = _ray_box(origin, direction, (pig.x, pig.y + pig.height / 2, pig.z),
                         (pig.width / 2, pig.height / 2, pig.width / 2))
            if t is not None and t <= reach and (best is None or t < best[1]):
                best = (pig, t)
        return best


def _ray_box(origin, direction, center, half):
    """Distance along a ray to a box, or None if it misses."""
    t_near, t_far = 0.0, math.inf
    for i in range(3):
        low, high = center[i] - half[i], center[i] + half[i]
        if abs(direction[i]) < 1e-9:
            if not (low <= origin[i] <= high):
                return None
        else:
            t1, t2 = (low - origin[i]) / direction[i], (high - origin[i]) / direction[i]
            t_near, t_far = max(t_near, min(t1, t2)), min(t_far, max(t1, t2))
    return t_near if t_near <= t_far else None
