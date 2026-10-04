"""Things that are made of blocks but move or hold things: falling sand and gravel, lit TNT, and chests."""
import random

from ursina import Entity, Vec3, destroy, time

from blocks import BLOCKS, GRAVITY_TABLE, ID
from chunkmesh import single_block_mesh
from inventory import Stack
from shaders import entity_shader
from textures import atlas_texture

GRAVITY = 28


class FallingBlocks:
    """Sand and gravel that drop when the block under them goes away."""

    def __init__(self, world):
        self.world = world
        self.falling = []
        world.listeners.append(self.check)

    def check(self, pos):
        """A block at `pos` changed: anything that can fall there or just above it might start to."""
        for p in (pos, (pos[0], pos[1] + 1, pos[2])):
            kind = self.world.get(p)
            if kind and BLOCKS[kind].get('gravity') and not self.world.is_solid((p[0], p[1] - 1, p[2])):
                self.world.remove(p, notify=False)
                entity = Entity(model=single_block_mesh(kind), texture=atlas_texture(), shader=entity_shader,
                                position=(p[0], p[1], p[2]))
                entity.kind, entity.vy = kind, 0.0
                self.falling.append(entity)
                self.check((p[0], p[1] + 1, p[2]))        # whatever was on top falls too

    def update(self, dt):
        dt = min(dt, 0.05)
        for e in self.falling[:]:
            e.vy -= GRAVITY * dt
            e.y += e.vy * dt
            below = (round(e.x), round(e.y - 0.5 + 1e-3), round(e.z))
            if self.world.is_solid(below) or e.y < 1:
                spot = (round(e.x), below[1] + 1, round(e.z))
                self.falling.remove(e)
                destroy(e)
                if self.world.get(spot) in (None, 'water') or not self.world.is_solid(spot):
                    self.world.place(spot, e.kind)


class PrimedTNT:
    """TNT that has been lit: it flashes, then explodes."""

    def __init__(self, world, mobs):
        self.world, self.mobs = world, mobs
        self.lit = []

    def prime(self, pos, fuse=4.0):
        entity = Entity(model=single_block_mesh('tnt'), texture=atlas_texture(), shader=entity_shader,
                        position=(pos[0], pos[1], pos[2]), scale=0.98)
        entity.fuse, entity.vy = fuse, 3.0           # (a little hop when lit)
        self.lit.append(entity)

    def update(self, dt):
        dt = min(dt, 0.05)
        for e in self.lit[:]:
            e.fuse -= dt
            e.vy -= GRAVITY * dt
            e.y += e.vy * dt
            if self.world.is_solid((round(e.x), round(e.y - 0.5 + 1e-3), round(e.z))) and e.vy < 0:
                e.y, e.vy = round(e.y - 0.5) + 0.5 + 1e-3 + 0.5, 0
            white = int(e.fuse * 6) % 2 == 0
            e.color = (1.6, 1.6, 1.6, 1) if white else (1, 1, 1, 1)
            e.scale = 0.98 + (0.12 if white else 0)
            if e.fuse <= 0:
                self.lit.remove(e)
                center = (e.x, e.y, e.z)
                destroy(e)
                self.mobs.explode(center, 4.0)


class Chests:
    """The contents of every chest block, by position."""

    def __init__(self, world):
        self.world = world
        self.contents = world.chests

    def create(self, pos):
        self.contents[pos] = [None] * 27

    def stacks(self, pos):
        return [s for s in self.contents.get(pos, []) if s is not None]
