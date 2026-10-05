"""Creatures: animals that wander and monsters that hunt you.

Every creature is a `Mob` built from a `MobType` (see mobtypes.py), which says
what its body looks like, how tough and fast it is, how it behaves and what it drops."""
import math
import random
from pathlib import Path

from ursina import Entity, Vec2, Vec3, color, destroy, time

from blocks import BLOCKS
from inventory import Stack
from items import ITEMS
from mobmodel import build_part, convert, load_skin
from mobtypes import ANIMALS, MONSTERS, TYPES

SEA_LEVEL = 48
from physics import Body
from shaders import entity_shader
from sound import distance_volume
from world import chunk_of

SKINS = Path(__file__).parent / 'assets' / 'textures' / 'entity'
HOP_SPEED = 9               # enough to rise a bit over one block (like the player's jump)
TURN_SPEED = 260            # degrees per second
DETECT_RANGE = 24
BURN_SECONDS = 8
TINT_HURT = color.rgb32(255, 110, 110)
TINT_FIRE = color.rgb32(255, 175, 110)


def _part(parent, mesh, texture, pivot):
    """A body part that can swing around its pivot point (pivot is in model units)."""
    x, y, z = convert((pivot[0], pivot[1] - 24, pivot[2]))     # 24 units = ground level
    return Entity(parent=parent, model=mesh, texture=texture, shader=entity_shader,
                  double_sided=True, position=(x, y, z))


def _angle_to(dx, dz):
    """The heading (degrees) that points toward an offset (dx, dz)."""
    return math.degrees(math.atan2(dx, dz))


class Mob(Body):
    def __init__(self, manager, kind, position, size=1):
        dim = {1: 0.5, 2: 1.0, 4: 2.0}.get(size) if kind.splits else None      # slimes come in three sizes
        super().__init__(manager.world, position, dim or kind.width, dim or kind.height)
        self.manager, self.kind = manager, kind
        self.size = size
        self.home = Vec3(*position)
        self.tamed = False
        self.angry = False
        self.owner_hit = None
        self.offers = None
        self.enemy = None
        self.order = None             # a command from a pycraftWorld script: ('goto', x, z), ('follow',) or ('stay',)
        self.script_click = None      # a function to call when the player right-clicks it (pycraftWorld)
        self.arrived = False
        self.hop_timer = random.uniform(0.5, 2)
        self.sound, self.player = manager.sound, manager.player

        skins = {name: load_skin(SKINS / file) for name, file in kind.textures.items()}
        self.skins = skins
        self.parts = []                                    # (spec, entity)
        for spec in kind.parts:
            texture, skin_size = skins[spec['texture']]
            skin_size = (skin_size[0] / kind.skin_scale, skin_size[1] / kind.skin_scale)
            mesh = build_part(spec['boxes'], skin_size, rotate_x=spec['rotate_x'], rotate=spec['rotate'])
            self.parts.append((spec, _part(self, mesh, texture, spec['pivot'])))

        self.health = kind.health if not kind.splits else {1: 1, 2: 4, 4: 16}[size]
        if kind.splits:
            for _spec, _entity in self.parts:
                _entity.scale = size                      # the model is half a block wide: x1, x2 or x4
        elif kind.scale != 1:
            for _spec, _entity in self.parts:
                _entity.scale = kind.scale
        self.walking = False
        self.timer = random.uniform(0.5, 3)
        self.heading = random.uniform(0, 360)
        self.rotation_y = self.heading
        self.wish_speed = 0.0
        self.stuck_for = 0.0
        self.side_step = 0.0
        self.knockback = Vec3(0, 0, 0)
        self.flash = 0.0
        self.fire = 0.0
        self.fire_tick = 1.0
        self.panic = 0.0
        self.panic_from = None
        self.provoked = False
        self.say_timer = random.uniform(3, 12)
        self.attack_cooldown = 0.0
        self.shoot_timer = random.uniform(1, 2)
        self.fuse = 0.0                  # creepers: how close to blowing up (0 to 1)
        self.target = None
        self.cycle = 0.0
        self.moving = False
        self.arms_up = 0.0

    def set_skin(self, name):
        """Switch the picture the body is painted with (a tame wolf wears a collar, an angry one has red eyes)."""
        if name in self.skins:
            for spec, entity in self.parts:
                if spec['texture'] == 'main':
                    entity.texture = self.skins[name][0]

    # ---- being hurt ------------------------------------------------------------

    def hurt(self, from_position, damage=1):
        away = Vec3(self.x - from_position[0], 0, self.z - from_position[2]).normalized()
        self.knockback = away * 6
        self.velocity_y = 6
        self.flash = 0.3
        self.provoked = True
        self.health -= damage
        if self.kind.base == 'wolf' and not self.tamed:
            self.angry = True
            self.set_skin('angry')
        if self.kind.behavior == 'pigman':                 # the whole herd turns on you
            for other in self.manager.mobs:
                if other.kind.behavior == 'pigman' and math.dist(other.position, self.position) < 24:
                    other.provoked = True
        if not self.kind.monster:
            self.panic = 4.0
            self.panic_from = Vec3(*from_position)
        self._say('hurt' if self.health > 0 else 'death', loud=True)
        if self.health <= 0:
            self.manager.mob_died(self)

    def _say(self, group, loud=False):
        """Make a noise, quieter if the player is far away."""
        if not self.sound or not self.player:
            return
        folder = f'mob/{self.kind.sound}'
        for name in (group, 'say') if group != 'say' else ('say',):
            if self.sound.has(f'{folder}/{name}'):
                distance = math.dist(self.player.position, self.position)
                self.sound.play(f'{folder}/{name}', distance_volume(distance) * (1.3 if loud else 1.0))
                return

    # ---- every frame -------------------------------------------------------------

    def update(self):
        dt = min(time.dt, 0.05)
        self._timers(dt)
        if self not in self.manager.mobs:
            return                        # died from fire this frame
        self.target = self._find_target()
        self.wish_direction = None
        self.wish_speed = 0.0
        if self.order is not None:
            self._follow_order(dt)
        else:
            getattr(self, f'_behave_{self.kind.behavior}')(dt)
        if self not in self.manager.mobs:
            return                        # died or blew up this frame (a creeper)
        self._move(dt)
        self._animate(dt)

    def _timers(self, dt):
        self.say_timer -= dt
        if self.say_timer <= 0:
            self._say('say')
            self.say_timer = random.uniform(6, 16)
        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        self.flash = max(0.0, self.flash - dt)
        self.panic = max(0.0, self.panic - dt)
        self.side_step = max(0.0, self.side_step - dt)

        # Zombies and skeletons burn in sunlight
        if self.kind.burns and self.manager.sky is not None:
            sky_light = self.world.light_at((round(self.x), round(self.y + self.height - 0.1), round(self.z)))[0]
            if self.manager.sky.daylight > 0.7 and sky_light > 0.95 and not self.in_water():
                self.fire = BURN_SECONDS
        if self.kind.fire_immune:
            self.fire = 0
        elif self.in_lava():
            self.fire = BURN_SECONDS
            self.lava_tick = getattr(self, 'lava_tick', 0) - dt
            if self.lava_tick <= 0:
                self.lava_tick = 0.5
                self.hurt_by_fire(3)
                if self not in self.manager.mobs:
                    return                      # burned to death
        if self.fire > 0:
            self.fire -= dt
            if self.in_water():
                self.fire = 0
            self.fire_tick -= dt
            if self.fire_tick <= 0:
                self.fire_tick = 1.0
                self.hurt_by_fire()

    def in_lava(self):
        spot = (round(self.x), math.floor(self.y + self.height / 2 + .5), round(self.z))
        return self.world.get(spot) == 'lava'

    def hurt_by_fire(self, amount=1):
        if self.kind.fire_immune:
            return
        self.health -= amount
        self.flash = 0.2
        if self.health <= 0:
            self.manager.mob_died(self)

    def _find_enemy(self):
        """The nearest hostile creature, for wolves and golems that defend their friends."""
        best, best_distance = None, 14.0
        for other in self.manager.mobs:
            if other is self or not other.kind.monster:
                continue
            d = math.hypot(other.x - self.x, other.z - self.z)
            if d < best_distance and abs(other.y - self.y) < 5:
                best, best_distance = other, d
        return best

    def _find_target(self):
        """The player, if this monster can see... well, sense them."""
        p = self.player
        if not self.kind.monster or p is None or p.dead or p.mode != 'survival':
            return None
        dx, dz = p.x - self.x, p.z - self.z
        if math.hypot(dx, dz) > DETECT_RANGE or abs(p.y - self.y) > 14:
            return None
        if self.kind.behavior == 'pigman' and not self.provoked:
            return None                      # zombie pigmen leave you alone until you hit one
        if self.kind.behavior == 'spider' and self.manager.sky is not None:
            if self.manager.sky.daylight > 0.5 and not self.provoked:
                return None                  # spiders ignore you in daylight, unless you hit them
        return p

    # ---- behaviors: each decides which way to go and how fast ---------------------------

    def _follow_order(self, dt):
        """Obey a command from a script: walk somewhere, follow the player, or stand still."""
        kind = self.order[0]
        if kind == 'stay':
            return
        if kind == 'follow':
            p = self.player
            if p is None or p.dead:
                return
            tx, tz, stop = p.x, p.z, 2.5
        else:
            tx, tz, stop = self.order[1], self.order[2], 0.6
        distance = math.hypot(tx - self.x, tz - self.z)
        if distance <= stop:
            if kind == 'goto':
                self.order, self.arrived = ('stay',), True
            return
        self._go(_angle_to(tx - self.x, tz - self.z), self.kind.speed * 1.2)

    def _wander(self, dt, speed_scale=1.0):
        self.timer -= dt
        if self.timer <= 0:
            self.walking = not self.walking
            if self.walking:
                self.heading = random.uniform(0, 360)
                self.timer = random.uniform(2, 5)
                self.stuck_for = 0
            else:
                self.timer = random.uniform(1, 4)
        if self.walking:
            self._go(self.heading, self.kind.speed * speed_scale)

    def _go(self, heading, speed):
        self.heading = heading
        self.wish_speed = speed
        r = math.radians(heading)
        self.wish_direction = Vec3(math.sin(r), 0, math.cos(r))

    def _behave_passive(self, dt):
        if self.panic > 0 and self.panic_from is not None:               # run from whatever hit us
            away = _angle_to(self.x - self.panic_from.x, self.z - self.panic_from.z)
            self._go(away + 25 * math.sin(self.cycle * 0.5), self.kind.speed * 2.2)
        else:
            self._wander(dt)

    def _chase(self, dt, speed_scale=1.0):
        p = self.target
        toward = _angle_to(p.x - self.x, p.z - self.z)
        if self.side_step > 0:                                           # walked into something: go around it
            toward += 70
        self._go(toward, self.kind.speed * speed_scale)

    def _behave_zombie(self, dt):
        p = self.target
        if p is None:
            return self._wander(dt, 0.6)
        self._chase(dt)
        near = math.hypot(p.x - self.x, p.z - self.z) < 1.2 and abs(p.y - self.y) < 1.6
        if near and self.attack_cooldown <= 0:
            self.attack_cooldown = 1.0
            self.manager.attack_player(self, self.kind.attack)

    _behave_spider = _behave_zombie
    _behave_pigman = _behave_zombie

    def _behave_blaze(self, dt):
        p = self.target
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(2, 5)
            self.heading = random.uniform(0, 360)
            self.walking = random.random() < 0.6
        want_y = self.y
        if p is None:
            if self.walking:
                self._go(self.heading, self.kind.speed * 0.5)
        else:
            d = math.hypot(p.x - self.x, p.z - self.z)
            toward = _angle_to(p.x - self.x, p.z - self.z)
            if d > 9:
                self._go(toward, self.kind.speed)
            elif d < 4:
                self._go(toward + 180, self.kind.speed)
            else:
                self.heading = toward
            want_y = p.y + 1.5
            self.shoot_timer -= dt
            if self.shoot_timer <= 0 and d < 22:
                self.burst = getattr(self, 'burst', 0) or 3
                self.shoot_timer = 0.35 if self.burst > 1 else random.uniform(3.0, 4.5)
                self.burst -= 1
                origin = Vec3(self.x, self.y + 1.0, self.z)
                self.manager.projectiles.shoot_fireball(origin, Vec3(p.x, p.y + 1.0, p.z) - origin, speed=14, small=True)
        self.velocity_y = max(-2.0, min(2.0, want_y - self.y))
        if self.world.is_solid((round(self.x), math.floor(self.y - 0.5), round(self.z))):
            self.velocity_y = 1.0                                 # float a little above the floor

    def _behave_ghast(self, dt):
        p = self.player
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(3, 7)
            self.heading = random.uniform(0, 360)
            self.walking = random.random() < 0.7
            self.swim_rise = random.uniform(-1.5, 1.5)
        near = (p is not None and not p.dead and p.mode == 'survival' and math.hypot(p.x - self.x, p.z - self.z) < 46
                and abs(p.y - self.y) < 40)
        want_y = self.y + getattr(self, 'swim_rise', 0) * 3
        if near:
            d = math.hypot(p.x - self.x, p.z - self.z)
            toward = _angle_to(p.x - self.x, p.z - self.z)
            if d > 24:
                self._go(toward, self.kind.speed)
            elif d < 12:
                self._go(toward + 180, self.kind.speed)
            else:
                self.heading = toward
            want_y = p.y + 5
            self.shoot_timer -= dt
            if self.shoot_timer < 1.0 and self.shoot_timer > 0:
                self.set_skin('shooting')                        # the mouth opens just before it shoots
            elif self.shoot_timer <= 0:
                self.shoot_timer = random.uniform(3.0, 5.0)
                self.set_skin('main')
                self.manager.shoot_fireball(self)
        else:
            self.set_skin('main')
            if self.walking:
                self._go(self.heading, self.kind.speed * 0.6)
        want_y = max(4 if self.world.flat else 36, min(104, want_y))
        self.velocity_y = max(-2.0, min(2.0, want_y - self.y))
        if self.world.is_solid((round(self.x), math.floor(self.y + self.height + 1.5), round(self.z))):
            self.velocity_y = -1.5                               # do not bump the ceiling
        elif self.world.is_solid((round(self.x), math.floor(self.y - 0.5), round(self.z))):
            self.velocity_y = 1.5

    def _behave_skeleton(self, dt):
        p = self.target
        if p is None:
            return self._wander(dt, 0.6)
        distance = math.hypot(p.x - self.x, p.z - self.z)
        toward = _angle_to(p.x - self.x, p.z - self.z)
        if distance > 10:
            self._go(toward, self.kind.speed)
        elif distance < 5:
            self._go(toward + 180, self.kind.speed)               # keep a bit of distance
        else:
            self.heading = toward
        self.shoot_timer -= dt
        if self.shoot_timer <= 0 and distance < 18:
            self.shoot_timer = 2.0
            self.manager.shoot_at_player(self)

    def _behave_creeper(self, dt):
        p = self.target
        if p is None:
            self.fuse = max(0.0, self.fuse - dt)
            return self._wander(dt, 0.6)
        distance = math.hypot(p.x - self.x, p.z - self.z)
        if distance < 3.0 and abs(p.y - self.y) < 2.5:
            self.fuse += dt / 1.5                                         # hissing... three, two, one
            if self.fuse >= 1.0:
                self.manager.mob_died(self, exploded=True)
                return
        else:
            self.fuse = max(0.0, self.fuse - dt * 1.5)
            self._chase(dt)
        if 0 < self.fuse < 1 and distance < 3.0:
            self.heading = _angle_to(p.x - self.x, p.z - self.z)          # stand still and swell

    def _behave_wolf(self, dt):
        p = self.player
        self.enemy = self._find_enemy() if (self.tamed or self.angry) else None
        if self.angry and not self.tamed and p is not None and not p.dead and p.mode == 'survival':
            if math.hypot(p.x - self.x, p.z - self.z) < 20:                 # an angry wild wolf goes for you
                self._go(_angle_to(p.x - self.x, p.z - self.z), self.kind.speed * 1.4)
                if math.hypot(p.x - self.x, p.z - self.z) < 1.3 and self.attack_cooldown <= 0:
                    self.attack_cooldown = 1.0
                    self.manager.attack_player(self, 4)
                return
            self.angry = False
            self.set_skin('main')
        if self.enemy is not None:                                           # a pet fights monsters
            e = self.enemy
            self._go(_angle_to(e.x - self.x, e.z - self.z), self.kind.speed * 1.5)
            if math.hypot(e.x - self.x, e.z - self.z) < 1.4 and self.attack_cooldown <= 0:
                self.attack_cooldown = 0.8
                e.hurt(self.position, 4)
            return
        if self.tamed and p is not None and not p.dead:                      # a pet follows its owner
            d = math.hypot(p.x - self.x, p.z - self.z)
            if d > 24:
                self.position = (p.x + random.uniform(-2, 2), p.y + 0.5, p.z + random.uniform(-2, 2))
            elif d > 5:
                self._go(_angle_to(p.x - self.x, p.z - self.z), self.kind.speed * (1.5 if d > 10 else 1.0))
            return
        self._wander(dt)

    def _behave_skittish(self, dt):
        p = self.player
        if p is not None and not p.dead and math.hypot(p.x - self.x, p.z - self.z) < 7:
            self._go(_angle_to(self.x - p.x, self.z - p.z), self.kind.speed * 1.8)       # runs from you
        else:
            self._wander(dt)

    def _behave_swimmer(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(2, 5)
            self.heading = random.uniform(0, 360)
            self.walking = random.random() < 0.8
            self.swim_rise = random.uniform(-0.6, 0.6)
        if self.walking and self.in_water():
            self._go(self.heading, self.kind.speed)
            self.velocity_y = getattr(self, 'swim_rise', 0)
        elif self.in_water():
            self.velocity_y *= 0.9

    def _behave_slime(self, dt):
        p = self.target
        self.hop_timer -= dt
        if self.grounded and self.hop_timer <= 0:
            self.hop_timer = random.uniform(0.7, 1.6)
            self.velocity_y = 6.5 + self.size * 0.3
            if p is not None:
                self.heading = _angle_to(p.x - self.x, p.z - self.z)
            else:
                self.heading = random.uniform(0, 360)
            self.walking = True
            self.timer = 0.5
            self.sound and self._say('say')
        if not self.grounded or self.timer > 0:
            self.timer -= dt
            self._go(self.heading, self.kind.speed)
        if p is not None and math.hypot(p.x - self.x, p.z - self.z) < 0.7 * (self.width + 0.6) \
                and abs(p.y - self.y) < 1.5 and self.attack_cooldown <= 0:
            self.attack_cooldown = 1.0
            self.manager.attack_player(self, {1: 1, 2: 2, 4: 4}[self.size])

    def _behave_villager(self, dt):
        far = math.hypot(self.x - self.home.x, self.z - self.home.z)
        zombie = next((o for o in self.manager.mobs if o.kind.behavior == 'zombie' and math.hypot(o.x - self.x, o.z - self.z) < 10), None)
        if zombie is not None:                                               # run from zombies
            self._go(_angle_to(self.x - zombie.x, self.z - zombie.z), self.kind.speed * 2.2)
        elif far > 16:
            self._go(_angle_to(self.home.x - self.x, self.home.z - self.z), self.kind.speed)
        else:
            self._wander(dt, 0.8)

    def _behave_golem(self, dt):
        self.enemy = self._find_enemy()
        if self.provoked and self.player is not None and not self.player.dead and self.player.mode == 'survival' \
                and math.hypot(self.player.x - self.x, self.player.z - self.z) < 16:
            self.enemy = None
            p = self.player
            self._go(_angle_to(p.x - self.x, p.z - self.z), self.kind.speed * 1.4)
            if math.hypot(p.x - self.x, p.z - self.z) < 2.0 and self.attack_cooldown <= 0:
                self.attack_cooldown = 1.2
                self.manager.attack_player(self, 8)
            return
        if self.enemy is not None:
            e = self.enemy
            self._go(_angle_to(e.x - self.x, e.z - self.z), self.kind.speed * 1.3)
            if math.hypot(e.x - self.x, e.z - self.z) < 2.0 and self.attack_cooldown <= 0:
                self.attack_cooldown = 1.0
                away = Vec3(e.x - self.x, 0, e.z - self.z).normalized() * 8
                e.hurt(self.position, 12)
                if e in self.manager.mobs:
                    e.knockback = away                 # (it may already be gone)
            return
        far = math.hypot(self.x - self.home.x, self.z - self.home.z)
        if far > 20:
            self._go(_angle_to(self.home.x - self.x, self.home.z - self.z), self.kind.speed)
        else:
            self._wander(dt, 0.7)

    # ---- moving ----------------------------------------------------------------------

    def _move(self, dt):
        # turn smoothly toward the way we are heading
        turn = (self.heading - self.rotation_y + 180) % 360 - 180
        self.rotation_y += max(-TURN_SPEED * dt, min(TURN_SPEED * dt, turn))

        step = Vec3(0, 0, 0)
        if self.wish_direction is not None and self.fuse < 0.01:
            step += self.wish_direction * self.wish_speed
        step += self.knockback
        self.knockback *= 0.9 ** (dt * 60)

        before = (self.x, self.z)
        blocked = self.move(0, step.x * dt)
        blocked = self.move(2, step.z * dt) or blocked
        self.moving = math.dist(before, (self.x, self.z)) / max(dt, 1e-6) > 0.4

        if blocked and self.wish_speed > 0:
            self.stuck_for += dt
            if self.grounded:
                self.velocity_y = HOP_SPEED                     # hop up a one-block step
            if self.stuck_for > 0.8:
                self.stuck_for = 0
                if self.kind.monster and self.target is not None:
                    self.side_step = 0.7
                else:
                    self.heading += random.uniform(90, 270)      # a wall: turn around
        elif not blocked:
            self.stuck_for = 0

        if self.kind.flying:
            if self.move(1, self.velocity_y * dt):             # a ghast floats and drifts up and down
                self.velocity_y = 0
        elif self.kind.behavior == 'swimmer' and self.in_water():
            self.move(1, self.velocity_y * dt)                 # a squid floats and swims up and down
        elif self.in_water() or (self.kind.fire_immune and self.in_lava()):
            self.velocity_y = max(self.velocity_y, 1.5)        # paddle back up to the surface
            self.fall(dt)
        else:
            self.fall(dt)

    # ---- how it looks -------------------------------------------------------------------

    def _animate(self, dt):
        if self.moving:
            self.cycle += dt * (7 + self.wish_speed)
        swing = math.sin(self.cycle) * (35 if self.kind.behavior != 'spider' else 14)
        aggressive = self.target is not None and self.kind.behavior in ('zombie', 'skeleton')
        look = None
        if self.target is not None:
            look = max(-50.0, min(50.0, (_angle_to(self.target.x - self.x, self.target.z - self.z)
                                         - self.rotation_y + 180) % 360 - 180))

        tint = color.white
        if self.fuse > 0:
            blink = 1.0 + (0.9 if int(self.fuse * 14) % 2 == 0 else 0.0)
            tint = color.Color(blink, blink, blink, 1)
        elif self.flash > 0:
            tint = TINT_HURT
        elif self.fire > 0:
            tint = TINT_FIRE
        self.scale = 1 + 0.25 * self.fuse if self.kind.behavior == 'creeper' else 1

        for spec, entity in self.parts:
            role = spec['role']
            if role == 'leg':
                target = swing * (1 if spec['phase'] else -1)
                entity.rotation_x += (target - entity.rotation_x) * min(1, dt * 15)
            elif role == 'arm':
                if aggressive:
                    target = -85 + swing * 0.1 if self.kind.behavior == 'zombie' or self.shoot_timer < 0.5 else -20
                else:
                    target = swing * 0.7 * (1 if spec['phase'] else -1)
                entity.rotation_x += (target - entity.rotation_x) * min(1, dt * 10)
            elif role == 'head':
                entity.rotation_y += ((look or 0) - entity.rotation_y) * min(1, dt * 8)
            elif role == 'orbit':
                entity.rotation_y += dt * (150 if spec['phase'] % 2 == 0 else -190)
            elif role == 'wing':
                entity.rotation_z = (45 * math.sin(self.cycle * 4 + id(entity) % 7) if not self.grounded else 5)
            entity.color = tint


class Mobs:
    """Keeps track of all the creatures, spawns new ones near the player and removes far ones."""

    def __init__(self, world, sound, player):
        self.world, self.sound, self.player = world, sound, player
        self.mobs = []
        self.dropped = None          # set by game.py, so mobs can drop things
        self.particles = None
        self.sky = None
        self.xp_orbs = None
        self.projectiles = None
        self.tnt = None
        self._animal_timer = 3.0
        self._monster_timer = 6.0

    # ---- making and removing -------------------------------------------------------

    def add(self, kind_name, position, rotation_y=None, health=None, size=1):
        mob = Mob(self, TYPES[kind_name], position, size)
        mob.get_out_of_blocks()                                       # (never start inside the ground: it would fall right through)
        if rotation_y is not None:
            mob.rotation_y = mob.heading = rotation_y
        if health is not None:
            mob.health = health
        self.mobs.append(mob)
        return mob

    def remove(self, mob):
        if mob in self.mobs:
            self.mobs.remove(mob)
            destroy(mob)

    def mob_died(self, mob, exploded=False):
        """A creature dies (or a creeper blows up): drop its loot."""
        center = (mob.x, mob.y + mob.height / 2, mob.z)
        if not exploded and self.xp_orbs is not None:
            self.xp_orbs.spawn(Vec3(*center), 5 if mob.kind.monster else random.randint(1, 3))
        if exploded:
            self.explode(center, 3.0)
        elif self.dropped is not None:
            for entry in mob.kind.drops:
                item, least, most = entry[:3]
                chance = entry[3] if len(entry) > 3 else 1.0
                count = random.randint(least, most) if random.random() < chance else 0
                if count:
                    name = item if item in ITEMS else None
                    if name:
                        self.dropped.drop(Stack(name, count), (mob.x, mob.y + 0.5, mob.z))
        if mob.kind.splits and mob.size > 1 and not exploded:
            for _ in range(random.randint(2, 3)):
                self.add(mob.kind.name, (mob.x + random.uniform(-0.4, 0.4), mob.y + 0.3, mob.z + random.uniform(-0.4, 0.4)), size=mob.size // 2)
        self.remove(mob)

    # ---- fighting ------------------------------------------------------------------------

    def attack_player(self, mob, damage):
        p = self.player
        p.damage(damage, 'mob')
        away = Vec3(p.x - mob.x, 0, p.z - mob.z).normalized()
        p.velocity_xz += away * 5
        if p.grounded:
            p.velocity_y = 4

    def shoot_at_player(self, mob):
        p = self.player
        origin = Vec3(mob.x, mob.y + 1.5, mob.z)
        target = Vec3(p.x, p.y + 1.2, p.z)
        distance = (target - origin).length()
        target.y += distance * 0.06                                # aim a little high: arrows drop
        self.projectiles.shoot(origin, target - origin, 22, 'monster', 3, spread=0.05)

    def shoot_fireball(self, mob):
        p = self.player
        origin = Vec3(mob.x, mob.y + 1.8, mob.z)
        self.projectiles.shoot_fireball(origin, Vec3(p.x, p.y + 1.0, p.z) - origin)

    def explode(self, center, power=3.0):
        """A big bang: holes in the ground, damage to everything close, and a few dropped blocks."""
        destroyed = self.world.explode(center, power)
        for (pos, kind) in destroyed:
            if kind == 'tnt' and self.tnt is not None:
                self.tnt.prime(pos, random.uniform(0.4, 1.3))        # chain reaction
        for (pos, kind) in destroyed:
            if self.dropped is not None and random.random() < 0.25:
                name = BLOCKS[kind].get('drops', kind) if 'drops' in BLOCKS[kind] else kind
                if name in ITEMS:
                    self.dropped.drop(Stack(name, 1), pos)
        if self.particles is not None:
            self.particles.emit('stone', center, count=40, speed=4)
        if self.sound is not None:
            self.sound.play('random/explode', 1.0)
        reach = power * 2
        p = self.player
        distance = math.dist(center, (p.x, p.y + 1, p.z))
        if distance < reach and not p.dead:
            p.damage(max(1, round((1 - distance / reach) * 22)), 'explosion')
            away = Vec3(p.x - center[0], 0, p.z - center[2]).normalized()
            p.velocity_xz += away * 8
            p.velocity_y = 6
        for mob in self.mobs[:]:
            d = math.dist(center, (mob.x, mob.y + mob.height / 2, mob.z))
            if d < reach and mob.health > 0:
                mob.hurt(center, damage=max(1, round((1 - d / reach) * 22)))

    # ---- queries ---------------------------------------------------------------------------

    def hit_test(self, origin, direction, reach):
        """The nearest creature along a line: (creature, distance) or None."""
        best = None
        for mob in self.mobs:
            t = _ray_box(origin, direction, (mob.x, mob.y + mob.height / 2, mob.z),
                         (mob.width / 2, mob.height / 2, mob.width / 2))
            if t is not None and t <= reach and (best is None or t < best[1]):
                best = (mob, t)
        return best

    def use_on(self, mob, held, give_item):
        """The player right-clicked a creature holding `held` (a Stack or None). Returns what happened:
        'tamed', 'fed', 'trade' or None."""
        name = held.name if held is not None else None
        if mob.script_click is not None:
            return 'scripted'
        if mob.kind.base == 'wolf':
            if not mob.tamed and name == 'bone':
                give_item()
                if random.random() < 0.34:
                    mob.tamed, mob.angry = True, False
                    mob.set_skin('tame')
                    return 'tamed'
                return 'fed'
            if mob.tamed and name in ('porkchop', 'cooked_porkchop', 'beef', 'cooked_beef', 'rotten_flesh', 'chicken',
                                      'cooked_chicken'):
                give_item()
                mob.health = min(mob.kind.health, mob.health + 4)
                return 'fed'
        if mob.kind.base == 'villager':
            return 'trade'
        return None

    def overlaps_block(self, block):
        """Is a creature standing where this block would go?"""
        return any(mob.overlaps_block(block) for mob in self.mobs)

    def update_lighting(self):
        """Light each creature the way the air around it is lit."""
        for mob in self.mobs:
            sky, block = self.world.light_at((round(mob.x), round(mob.y + mob.height / 2), round(mob.z)))
            if mob.kind.base == 'magma_cube':
                block = max(block, 0.75)                      # (it glows)
            mob.set_shader_input('entity_light', Vec2(sky, block))

    def update_visibility(self):
        """Creatures in chunks that are not shown stand still and are hidden."""
        for mob in self.mobs:
            show = chunk_of((round(mob.x), 0, round(mob.z))) in self.world.chunk_entities
            if mob.enabled != show:
                mob.enabled = show                     # (switching is slow: only do it when it changes)

    # ---- spawning ---------------------------------------------------------------------------

    def spawn_initial(self, count, around, radius=30):
        """Start the game with a few animals near a point."""
        tries = 0
        while len([m for m in self.mobs if not m.kind.monster]) < count and tries < 600:
            tries += 1
            self._try_spawn_animal(int(around[0] + random.uniform(-radius, radius)),
                                   int(around[2] + random.uniform(-radius, radius)))

    def _try_spawn_animal(self, x, z):
        if (x >> 4, z >> 4) not in self.world.chunk_entities:
            return False                               # only where the land is shown
        ground = self.world.height_at(x, z)
        if self.world.get((x, ground, z)) != 'grass':
            return False                               # animals live on grass
        if self.world.is_solid((x, ground + 1, z)) or self.world.is_solid((x, ground + 2, z)):
            return False                               # under a tree
        biome = self.world.biome_at(x, z).name
        kinds, weights = [ANIMALS[0], ANIMALS[1], ANIMALS[2], ANIMALS[3]], [3, 3, 3, 2]
        if biome in ('Forest', 'Taiga'):
            kinds.append(TYPES['wolf']); weights.append(3)
        if biome == 'Jungle':
            kinds.append(TYPES['ocelot']); weights.append(5)
        kind = random.choices(kinds, weights=weights)[0]
        placed = 0
        for _ in range(random.randint(2, 4) if kind.base == 'wolf' else random.randint(1, 3)):          # animals come in small groups
            ax, az = x + random.uniform(-2, 2), z + random.uniform(-2, 2)
            cx, cz = round(ax), round(az)
            surface = self.world.height_at(cx, cz)                  # (each animal stands on the ground where IT is: on a hillside the
            if self.world.get((cx, surface, cz)) != 'grass' or self.world.is_solid((cx, surface + 1, cz)):     # next column is higher or lower)
                continue
            self.add(kind.name, (ax, surface + 0.6, az))
            placed += 1
        return placed > 0

    def _try_spawn_squid(self):
        p = self.player
        angle, distance = random.uniform(0, 2 * math.pi), random.uniform(20, 50)
        x, z = int(p.x + math.cos(angle) * distance), int(p.z + math.sin(angle) * distance)
        if (x >> 4, z >> 4) not in self.world.chunk_entities:
            return False
        y = SEA_LEVEL - 3
        if all(self.world.get((x, y + dy, z)) == 'water' for dy in (-1, 0, 1)):
            for _ in range(random.randint(1, 3)):
                self.add('squid', (x + random.uniform(-1.5, 1.5), y, z + random.uniform(-1.5, 1.5)))
            return True
        return False

    def _find_floor(self, x, z, start_y):
        """Scan down from start_y for a cell with a solid floor and two free cells above."""
        for y in range(start_y, max(2, start_y - 24), -1):
            if (self.world.is_solid((x, y - 1, z)) and not self.world.is_solid((x, y, z))
                    and not self.world.is_solid((x, y + 1, z)) and self.world.get((x, y, z)) != 'water'):
                return y
        return None

    def _try_spawn_monster(self):
        p = self.player
        angle, distance = random.uniform(0, 2 * math.pi), random.uniform(22, 46)
        x, z = int(p.x + math.cos(angle) * distance), int(p.z + math.sin(angle) * distance)
        if (x >> 4, z >> 4) not in self.world.chunk_entities:
            return False
        start = self.world.height_at(x, z) + 2 if random.random() < 0.5 else int(p.y + random.uniform(-10, 8))
        y = self._find_floor(x, z, min(start, 120))
        if y is None:
            return False
        sky, block = self.world.light_at((x, y, z))
        daylight = self.sky.daylight if self.sky is not None else 0.0
        if max(sky * daylight, block) > 0.47:          # too bright (Minecraft: light level 7 or less)
            return False
        kind = random.choices(MONSTERS, weights=(4, 3, 3, 2))[0]
        if self.world.biome_at(x, z).name == 'Swamp' and random.random() < 0.6:
            self.add('slime', (x + 0.5, y + 0.1, z + 0.5), size=random.choice((1, 2, 2, 4)))
            return True
        self.add(kind.name, (x + 0.5, y + 0.1, z + 0.5))
        return True

    def _try_spawn_nether_mob(self):
        """Zombie pigmen and magma cubes on the floors of the Nether."""
        p = self.player
        angle, distance = random.uniform(0, 2 * math.pi), random.uniform(18, 44)
        x, z = int(p.x + math.cos(angle) * distance), int(p.z + math.sin(angle) * distance)
        if (x >> 4, z >> 4) not in self.world.chunk_entities:
            return False
        y = self._find_floor(x, z, min(118, int(p.y + random.uniform(-14, 14))))
        if y is None or self.world.get((x, y, z)) is not None or self.world.get((x, y - 1, z)) in ('lava', 'magma_block'):
            return False
        if y < 34 and random.random() < 0.6 or random.random() < 0.2:
            self.add('magma_cube', (x + 0.5, y + 0.1, z + 0.5), size=random.choice((1, 2, 2, 4)))
            return True
        for _ in range(random.randint(1, 3)):
            self.add('zombie_pigman', (x + random.uniform(0, 1), y + 0.1, z + random.uniform(0, 1)), random.uniform(0, 360))
        return True

    def _try_spawn_ghast(self):
        p = self.player
        angle, distance = random.uniform(0, 2 * math.pi), random.uniform(24, 48)
        x, z = int(p.x + math.cos(angle) * distance), int(p.z + math.sin(angle) * distance)
        y = int(random.uniform(45, 100))
        if (x >> 4, z >> 4) not in self.world.chunk_entities:
            return False
        if any(self.world.get((x + dx, y + dy, z + dz)) is not None
               for dx in (-3, 0, 3) for dz in (-3, 0, 3) for dy in (-1, 2, 5)):
            return False                                              # ghasts need a big open space
        self.add('ghast', (x + 0.5, y, z + 0.5), random.uniform(0, 360))
        return True

    def update_villages(self, dt):
        """Put villagers and an iron golem into villages as the player gets near them."""
        self._village_timer = getattr(self, '_village_timer', 0) - dt
        if self._village_timer > 0:
            return
        self._village_timer = 1.5
        for entry in list(self.world.village_queue):
            key, villagers, golems = entry
            spots = villagers + golems
            if not all((s[0] >> 4, s[2] >> 4) in self.world.chunk_entities for s in spots):
                continue                                              # wait until the whole village is on screen
            for x, y, z in villagers:
                self.add('villager', (x + 0.5, y + 0.1, z + 0.5), random.uniform(0, 360))
            for x, y, z in golems:
                self.add('iron_golem', (x + 0.5, y + 0.1, z + 0.5))
            self.world.villages_done.add(key)
            self.world.village_queue.remove(entry)

    def update_spawners(self, dt):
        """A monster spawner makes zombies, skeletons or spiders around itself while you are close."""
        self._spawner_timer = getattr(self, '_spawner_timer', 0) - dt
        if self._spawner_timer > 0:
            return
        self._spawner_timer = 4.0
        p = self.player
        for pos in list(self.world.spawners):
            if self.world.get(pos) != 'spawner':
                self.world.spawners.discard(pos)
                continue
            if math.dist(pos, (p.x, p.y, p.z)) > 16 or p.mode != 'survival':
                continue
            if sum(1 for m in self.mobs if m.kind.monster and math.dist((m.x, m.y, m.z), pos) < 8) >= 6:
                continue
            kind = 'blaze' if self.world.nether else ('zombie', 'skeleton', 'spider', 'zombie')[hash(pos) % 4]
            for _ in range(random.randint(1, 3)):
                x, z = pos[0] + random.randint(-3, 3), pos[2] + random.randint(-3, 3)
                if self.world.get((x, pos[1], z)) is None and self.world.is_solid((x, pos[1] - 1, z)):
                    self.add(kind, (x + 0.5, pos[1] + 0.1, z + 0.5))

    def update_spawning(self, dt):
        """Keep creatures around the player as they explore: new ones appear nearby (monsters in the
        dark), ones left far behind disappear."""
        p = self.player
        for mob in self.mobs[:]:
            if mob.kind.base in ('villager', 'iron_golem'):
                continue                                              # villagers stay in their village
            if math.hypot(mob.x - p.x, mob.z - p.z) > (110 if not mob.kind.monster else 80):
                self.remove(mob)

        if self.world.nether:
            self._monster_timer -= dt
            if self._monster_timer <= 0 and p.mode == 'survival' and not p.dead:
                self._monster_timer = 2.5
                near = [m for m in self.mobs if math.hypot(m.x - p.x, m.z - p.z) < 64]
                if sum(1 for m in near if m.kind.base != 'ghast') < 12:
                    for _ in range(6):
                        if self._try_spawn_nether_mob():
                            break
                if sum(1 for m in near if m.kind.base == 'ghast') < 2 and random.random() < 0.25:
                    self._try_spawn_ghast()
            return

        self._animal_timer -= dt
        if self._animal_timer <= 0:
            self._animal_timer = 4.0
            near = sum(1 for m in self.mobs if not m.kind.monster and math.hypot(m.x - p.x, m.z - p.z) < 70)
            if near < 14:
                angle, distance = random.uniform(0, 2 * math.pi), random.uniform(24, 56)
                self._try_spawn_animal(int(p.x + math.cos(angle) * distance), int(p.z + math.sin(angle) * distance))

        self._squid_timer = getattr(self, '_squid_timer', 5.0) - dt
        if self._squid_timer <= 0:
            self._squid_timer = 6.0
            if sum(1 for m in self.mobs if m.kind.base == 'squid') < 6:
                self._try_spawn_squid()

        self._monster_timer -= dt
        if self._monster_timer <= 0 and p.mode == 'survival' and not p.dead:
            self._monster_timer = 2.0
            near = sum(1 for m in self.mobs if m.kind.monster and math.hypot(m.x - p.x, m.z - p.z) < 64)
            if near < 10:
                for _ in range(6):
                    if self._try_spawn_monster():
                        break

    # ---- saving ------------------------------------------------------------------------------

    def snapshot(self, mobs=None):
        return [{'type': m.kind.name, 'position': list(m.position), 'rotation_y': m.rotation_y, 'health': m.health,
                 'size': m.size, 'tamed': m.tamed, 'home': list(m.home), 'offers': m.offers}
                for m in (self.mobs if mobs is None else mobs)]

    def restore(self, data):
        for d in data:
            if d['type'] in TYPES:
                mob = self.add(d['type'], tuple(d['position']), d['rotation_y'], d['health'], d.get('size', 1))
                if d.get('tamed'):
                    mob.tamed = True
                    mob.set_skin('tame')
                if d.get('home'):
                    mob.home = Vec3(*d['home'])
                mob.offers = d.get('offers')


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
