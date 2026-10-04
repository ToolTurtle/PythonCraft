"""Little bits of block that fly off when you break one (or splash in water)."""
import math
import random

from ursina import Entity, Mesh, Vec2, Vec3, destroy

from cube import FACES
from shaders import entity_shader
from textures import atlas_texture, atlas_uvs

GRAVITY = 22


def _bit_of_block_mesh(uv_rect):
    """A tiny cube whose every face shows the same small piece of a block texture."""
    u0, v0, u1, v1 = uv_rect
    vertices, uvs, normals, quads = [], [], [], []
    for corners, _face, normal in FACES:
        first = len(vertices)
        vertices += corners
        uvs += [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        normals += [normal] * 4
        quads.append((first, first + 1, first + 2, first + 3))
    return Mesh(vertices=vertices, triangles=quads, uvs=uvs, normals=normals)


class Particle:
    def __init__(self, entity, velocity, life, size):
        self.entity = entity
        self.velocity = velocity
        self.life = life
        self.age = 0
        self.size = size


class Particles:
    def __init__(self, world):
        self.world = world
        self.live = []

    def emit(self, kind, position, count=16, speed=2.5, face=None):
        """Spray `count` bits of block `kind` from `position`.
        If `face` is given (a direction like (0, 1, 0)) they fly out of that side."""
        uv_table = atlas_uvs()
        texture = atlas_texture()
        for _ in range(count):
            tile = uv_table[(kind, random.choice(('top', 'side', 'side')))]
            # Pick a random 4x4 pixel square out of the 16x16 tile
            u0, v0, u1, v1 = tile
            step_u, step_v = (u1 - u0) / 4, (v1 - v0) / 4
            i, j = random.randint(0, 3), random.randint(0, 3)
            rect = (u0 + i * step_u, v0 + j * step_v, u0 + (i + 1) * step_u, v0 + (j + 1) * step_v)

            size = random.uniform(0.07, 0.15)
            offset = Vec3(random.uniform(-.4, .4), random.uniform(-.4, .4), random.uniform(-.4, .4))
            velocity = Vec3(random.uniform(-1, 1), random.uniform(0.2, 1.4), random.uniform(-1, 1)) * speed
            if face:
                velocity += Vec3(*face) * speed * 0.8
                offset = offset * 0.5 + Vec3(*face) * 0.5
            entity = Entity(model=_bit_of_block_mesh(rect), texture=texture, shader=entity_shader,
                            position=Vec3(*position) + offset, scale=size)
            sky, block = self.world.light_at((round(position[0]), round(position[1]), round(position[2])))
            entity.set_shader_input('entity_light', Vec2(sky, block))
            self.live.append(Particle(entity, velocity, random.uniform(0.5, 1.0), size))

    def update(self, dt):
        for particle in self.live[:]:
            particle.age += dt
            if particle.age >= particle.life:
                destroy(particle.entity)
                self.live.remove(particle)
                continue

            particle.velocity.y -= GRAVITY * dt
            entity = particle.entity
            new_position = entity.position + particle.velocity * dt
            spot = (round(new_position.x), round(new_position.y), round(new_position.z))
            if self.world.is_solid(spot):                 # hit the ground or a wall: stop sliding
                particle.velocity = Vec3(0, 0, 0)
            else:
                entity.position = new_position
            entity.rotation_y += 200 * dt
            entity.scale = particle.size * (1 - 0.6 * particle.age / particle.life)   # shrink as it fades

    def clear(self):
        for particle in self.live:
            destroy(particle.entity)
        self.live.clear()
