"""The Nether: a hot, roofed cavern world of netherrack with a sea of lava.

Made the same way as the overworld (seeded noise, one chunk at a time), but the shape comes from one 3D
noise field with a push toward "solid" near the floor and the ceiling, so the middle stays open."""
import functools

import numpy as np

from blocks import ID
from chunk import CHUNK, HEIGHT, Chunk
from noise_np import Perlin

AIR, BEDROCK, NETHERRACK, LAVA = 0, ID['bedrock'], ID['netherrack'], ID['lava']
SOUL_SAND, GLOWSTONE, QUARTZ, MAGMA = ID['soul_sand'], ID['glowstone'], ID['nether_quartz_ore'], ID['magma_block']
RED_MUSHROOM, BROWN_MUSHROOM = ID['red_mushroom'], ID['brown_mushroom']
LAVA_SEA = 32          # air below this height is lava
STEP = 4


class NetherGenerator:
    def __init__(self, seed):
        self.shape_a = Perlin(seed * 53 + 101)
        self.shape_b = Perlin(seed * 53 + 102)
        self.soul = Perlin(seed * 53 + 103)
        self.patch = Perlin(seed * 53 + 104)


@functools.lru_cache(maxsize=2)
def generator(seed):
    return NetherGenerator(seed)


def _trilinear(grid, step, shape):
    out = grid
    for axis, size in enumerate(shape):
        idx = np.arange(size) // step
        frac = ((np.arange(size) % step) / step).reshape([-1 if i == axis else 1 for i in range(3)])
        out = np.take(out, idx, axis=axis) * (1 - frac) + np.take(out, idx + 1, axis=axis) * frac
    return out


def _solid_field(gen, cx, cz):
    """True where the ground is solid: a (16, 16, HEIGHT) array."""
    xs = cx * CHUNK + np.arange(0, CHUNK + STEP, STEP)
    zs = cz * CHUNK + np.arange(0, CHUNK + STEP, STEP)
    ys = np.arange(0, HEIGHT + STEP, STEP)
    X, Y, Z = xs[:, None, None], ys[None, None, :], zs[None, :, None]
    density = (gen.shape_a.noise3(X / 38, Y / 20, Z / 38) * 1.0
               + gen.shape_b.noise3(X / 17, Y / 11, Z / 17) * 0.45)
    floor_push = 1.8 * np.clip((24 - Y) / 14, 0, 1)            # solid near the bottom...
    roof_push = 1.8 * np.clip((Y - 88) / 18, 0, 1)             # ...and near the top
    field = density + floor_push + roof_push - 0.12
    return _trilinear(field, STEP, (CHUNK, CHUNK, HEIGHT)) > 0


def generate_chunk(seed, cx, cz):
    gen = generator(seed)
    rng = np.random.default_rng((seed & 0xFFFFFFFF, cx & 0xFFFFFFFF, cz & 0xFFFFFFFF, 11))
    solid = _solid_field(gen, cx, cz)
    Y = np.arange(HEIGHT)[None, None, :]
    solid |= Y >= HEIGHT - 4
    blocks = np.where(solid, NETHERRACK, AIR).astype(np.uint8)
    blocks[:, :, :LAVA_SEA + 1] = np.where(blocks[:, :, :LAVA_SEA + 1] == AIR, LAVA, blocks[:, :, :LAVA_SEA + 1])

    X, Z = np.meshgrid(np.arange(cx * CHUNK, cx * CHUNK + CHUNK), np.arange(cz * CHUNK, cz * CHUNK + CHUNK), indexing='ij')
    air_above = np.zeros(blocks.shape, dtype=bool)               # a floor: netherrack with open air above it
    air_above[:, :, :-1] = (blocks[:, :, 1:] == AIR) & (blocks[:, :, :-1] == NETHERRACK)
    soul_noise = gen.soul.noise(X / 9.0, Z / 9.0)[:, :, None]
    soul = air_above & (soul_noise > 0.28) & (Y > LAVA_SEA - 2) & (Y < 80)
    blocks[soul] = SOUL_SAND
    patch_noise = gen.patch.noise(X / 6.0 + 40, Z / 6.0 + 40)[:, :, None]
    magma = air_above & (patch_noise > 0.45) & (Y >= LAVA_SEA - 2) & (Y <= LAVA_SEA + 3) & ~soul
    blocks[magma] = MAGMA

    # glowstone blobs hanging from the ceiling, and quartz in the walls
    for _ in range(int(rng.integers(1, 4))):
        x, z = int(rng.integers(3, 13)), int(rng.integers(3, 13))
        column = blocks[x, z]
        ceiling = [y for y in range(60, HEIGHT - 6) if column[y] == NETHERRACK and column[y - 1] == AIR]
        if not ceiling:
            continue
        y = ceiling[0]
        for _step in range(int(rng.integers(8, 20))):
            for dx, dy, dz in ((0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
                nx, ny, nz = x + dx, y + dy, z + dz
                if 0 <= nx < CHUNK and 0 <= nz < CHUNK and blocks[nx, nz, ny] == AIR and rng.random() < 0.5:
                    blocks[nx, nz, ny] = GLOWSTONE
                    x, y, z = nx, ny, nz
        blocks[x, z, y] = GLOWSTONE
    for _ in range(14):
        x, y, z = int(rng.integers(0, CHUNK)), int(rng.integers(8, HEIGHT - 8)), int(rng.integers(0, CHUNK))
        for _step in range(int(rng.integers(3, 8))):
            if 0 <= x < CHUNK and 0 <= z < CHUNK and blocks[x, z, y] == NETHERRACK:
                blocks[x, z, y] = QUARTZ
            x, y, z = x + int(rng.integers(-1, 2)), y + int(rng.integers(-1, 2)), z + int(rng.integers(-1, 2))
    # mushrooms on the floors
    spots = np.argwhere(air_above & (blocks == NETHERRACK) & (rng.random(blocks.shape) < 0.004) & (Y > LAVA_SEA + 1) & (Y < 100))
    for x, z, y in spots:
        blocks[x, z, y + 1] = RED_MUSHROOM if rng.random() < 0.5 else BROWN_MUSHROOM

    import structures
    for rx, rz in structures.fortress_ids_near(seed, cx, cz):
        plan = structures.fortress_plan(seed, rx, rz)
        if plan is not None:
            structures.stamp(plan, blocks, cx, cz)

    blocks[:, :, 0] = BEDROCK
    for layer, chance in ((1, 0.55), (2, 0.25), (3, 0.1)):
        blocks[:, :, layer] = np.where(rng.random((CHUNK, CHUNK)) < chance, BEDROCK, blocks[:, :, layer])
    blocks[:, :, HEIGHT - 1] = BEDROCK
    for layer, chance in ((2, 0.55), (3, 0.25), (4, 0.1)):
        blocks[:, :, HEIGHT - layer] = np.where(rng.random((CHUNK, CHUNK)) < chance, BEDROCK, blocks[:, :, HEIGHT - layer])

    ground = (blocks != AIR) & (blocks != LAVA)
    heights = np.where(ground[:, :, :100].any(axis=2), 99 - np.argmax(ground[:, :, :100][:, :, ::-1], axis=2), 0).astype(np.int32)
    return Chunk(cx, cz, blocks, heights, np.zeros((CHUNK, CHUNK), dtype=np.int32))


def find_floor(world, x, z, y_high=110):
    """The height where something can stand (two free cells over a solid one), nearest the middle of the cave, or None."""
    for y in range(y_high, 33, -1):
        if (world.is_solid((x, y - 1, z)) and world.get((x, y - 1, z)) not in ('lava', 'magma_block')
                and world.get((x, y, z)) is None and world.get((x, y + 1, z)) is None
                and world.get((x, y + 2, z)) is None):
            return y
    return None
