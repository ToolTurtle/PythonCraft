"""Items lying on the ground: they pop out of broken blocks and fly into your pockets."""
import math
import random

from ursina import Entity, Texture, Vec2, Vec3, destroy, time

from chunkmesh import single_block_mesh
from physics import Body
from shaders import entity_shader
from textures import atlas_texture, item_icon_texture
from world import chunk_of

PICKUP_RANGE = 1.5
PICKUP_DELAY = 0.6
LIFETIME = 300


class DroppedItem(Body):
    def __init__(self, world, position, stack, velocity=None):
        super().__init__(world, position, 0.25, 0.25)
        self.stack = stack
        self.age = 0
        self.velocity = velocity or Vec3(random.uniform(-1.5, 1.5), 0, random.uniform(-1.5, 1.5))
        self.velocity_y = random.uniform(3, 5)

        kind, name = stack.item.icon
        if kind == 'block':      # a little spinning block
            mesh = single_block_mesh(name)
            self.visual = Entity(parent=self, model=mesh, texture=atlas_texture(), shader=entity_shader,
                                 scale=0.25, y=0.2)
        else:                    # a little spinning picture
            self.visual = Entity(parent=self, model='quad', texture=item_icon_texture(stack.item),
                                 shader=entity_shader, double_sided=True, scale=0.4, y=0.25)

    def update(self):
        dt = min(time.dt, 0.05)
        self.age += dt
        self.move(0, self.velocity[0] * dt)
        self.move(2, self.velocity[2] * dt)
        self.velocity *= 0.92 ** (dt * 60) if self.grounded else 0.995
        self.fall(dt)
        self.visual.rotation_y += 90 * dt
        self.visual.y = 0.25 + 0.05 * math.sin(self.age * 3)


class DroppedItems:
    def __init__(self, world, sound):
        self.world = world
        self.sound = sound
        self.items = []

    def drop(self, stack, position, velocity=None):
        entity = DroppedItem(self.world, Vec3(*position), stack, velocity)
        self.items.append(entity)
        return entity

    def update(self, player, inventory, dt):
        """Hide items in chunks you cannot see, and pick up the ones next to you."""
        for entity in self.items[:]:
            sky, block = self.world.light_at((round(entity.x), round(entity.y + 0.2), round(entity.z)))
            entity.set_shader_input('entity_light', Vec2(sky, block))
            show = chunk_of((round(entity.x), 0, round(entity.z))) in self.world.chunk_entities
            if entity.enabled != show:
                entity.enabled = show
            if entity.age > LIFETIME or entity.y < -20:
                self._remove(entity)
                continue
            if entity.age < PICKUP_DELAY or player.dead or player.mode == 'spectator':
                continue
            dx, dz = player.x - entity.x, player.z - entity.z
            across = math.hypot(dx, dz)
            height_ok = player.y - 1.2 <= entity.y <= player.y + 2.3          # near our feet, body or head
            if across < PICKUP_RANGE and height_ok:
                left = inventory.add_stack(entity.stack)
                if left < entity.stack.count:
                    self.sound.play('random/pop', 0.5)
                if left == 0:
                    self._remove(entity)
                else:
                    entity.stack.count = left
            elif across < 3 and height_ok:                                     # drift toward the player
                entity.velocity = entity.velocity * 0.9 + Vec3(dx, 0, dz).normalized() * 1.2

    def _remove(self, entity):
        self.items.remove(entity)
        destroy(entity)

    def clear(self):
        for entity in self.items[:]:
            self._remove(entity)
