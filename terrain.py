"""Making the land, one chunk at a time, from layers of Perlin noise.

Each noise layer answers one question about a spot on the map:
  continents    -> is this ocean or land? (very big, slow shapes)
  ridges        -> where are the mountain ranges?
  erosion       -> where are the mountains allowed to be tall?
  rolling hills -> gentle bumps, everywhere
  detail        -> tiny bumps, so the ground isn't smooth
  temperature, humidity -> which biome grows here?
  caves         -> 3D noise: tunnels and caverns underground

Every number depends only on the seed and the position, never on what was made
before, so any chunk can be (re)made at any time and always comes out the same."""
import functools

import numpy as np

from biomes import DESERT, FOREST, JUNGLE, PLAINS, SNOWY, SWAMP, TAIGA
from blocks import ID
from chunk import CHUNK, HEIGHT, Chunk
from noise_np import Perlin, smoothstep

BIOMES = [PLAINS, FOREST, DESERT, SNOWY, JUNGLE, SWAMP, TAIGA]
SEA = 48          # water fills every low spot up to this height
ROCK_LINE = SEA + 14    # above this the ground is bare stone
SNOW_LINE = SEA + 20    # and above this it is snow-capped
TREE_CELL = 6           # one tree at most in each 6x6 square
LEAF_REACH = 3          # trees from the next chunk can reach this far in

AIR, STONE, BEDROCK, WATER, ICE = (ID[n] for n in ('air', 'stone', 'bedrock', 'water', 'ice'))
LAVA = ID['lava']
LAVA_LEVEL = 10
SAND, GRAVEL, CLAY, SNOW, SANDSTONE = (ID[n] for n in ('sand', 'gravel', 'clay', 'snow', 'sandstone'))
DIRT, GRASS, GRASS_SNOW = ID['dirt'], ID['grass'], ID['grass_snow']

SURFACE = np.array([ID[b.surface] for b in BIOMES], dtype=np.uint8)
FILLER = np.array([ID[b.filler] for b in BIOMES], dtype=np.uint8)
FROZEN = np.array([b.frozen_water for b in BIOMES])
DESERT_INDEX = BIOMES.index(DESERT)
SWAMP_INDEX = BIOMES.index(SWAMP)

# ore: block, veins per chunk, lowest and highest layer, length of a vein
ORES = (('coal_ore', 16, 5, 90, 8), ('iron_ore', 9, 5, 56, 5), ('gold_ore', 2, 5, 30, 4),
        ('diamond_ore', 1, 3, 16, 3), ('emerald_ore', 1, 5, 28, 1), ('lapis_ore', 2, 5, 32, 4), ('redstone_ore', 8, 5, 16, 5))


class Generator:
    """All the noise layers for one world seed."""

    def __init__(self, seed):
        self.seed = seed
        names = ('continents', 'ridges', 'erosion', 'rolling', 'detail', 'temperature', 'humidity', 'seabed',
                 'cave_a', 'cave_b', 'cavern')
        for i, name in enumerate(names):
            setattr(self, name, Perlin(seed * 31 + i + 1))


@functools.lru_cache(maxsize=4)
def generator(seed):
    return Generator(seed)


def column_info(gen, X, Z):
    """Everything about the ground at the given map points (arrays of x and z):
    the height, the biome, and which blocks make the top and the layers under it."""
    c = coarse_layers(gen.continents, X, Z, 160, 4) * 3
    land = SEA + 3 + c * 10

    # Mountains: ridge lines, but only on land, and only where erosion allows
    ridge = np.maximum(0.0, 1 - np.abs(coarse_layers(gen.ridges, X, Z, 110, 3) * 3)) ** 1.5
    allowed = smoothstep(0.0, 0.5, c) * smoothstep(-0.3, 0.4, coarse_layers(gen.erosion, X, Z, 120, 3) * 3)
    mountains = ridge * 26 * allowed

    bumps = coarse_layers(gen.rolling, X, Z, 48, 3) * 9 + gen.detail.layers(X / 14, Z / 14, 2) * 3.6
    height = np.maximum(4, np.rint(land + mountains + bumps * (0.4 + allowed))).astype(np.int32)
    temperature = coarse_layers(gen.temperature, X, Z, 200, 3) * 3
    humidity = coarse_layers(gen.humidity, X, Z, 160, 3) * 3
    swampy = (temperature > -0.1) & (temperature < 0.3) & (humidity > 0.55) & (c > -0.2)
    height = np.where(swampy, SEA - 1 + np.rint(gen.detail.layers(X / 9, Z / 9, 2) * 3 + 0.4).astype(np.int32), height)   # low, boggy land

    biome = np.zeros(height.shape, dtype=np.int32)                  # plains
    biome[humidity > 0.12] = BIOMES.index(FOREST)
    biome[(temperature < -0.2) & (humidity > -0.2)] = BIOMES.index(TAIGA)           # cool and not dry: taiga
    biome[(temperature > -0.1) & (temperature < 0.3) & (humidity > 0.55)] = SWAMP_INDEX
    biome[(temperature > 0.3) & (humidity > 0.35)] = BIOMES.index(JUNGLE)
    biome[temperature < -0.6] = BIOMES.index(SNOWY)
    biome[(temperature > 0.35) & (humidity < 0.0)] = DESERT_INDEX

    rock_noise = gen.detail.noise(X / 5, Z / 5)
    seabed = gen.seabed.noise(X / 9, Z / 9)

    ocean = height < SEA
    beach = ~ocean & (height <= SEA + np.where(rock_noise > 0, 1, 0))
    peak = height >= SNOW_LINE + rock_noise * 2
    rock = height >= ROCK_LINE + rock_noise * 2
    seabed_id = np.where(seabed > 0.45, CLAY, np.where(seabed > 0.25, GRAVEL, SAND)).astype(np.uint8)

    top = SURFACE[biome]
    filler = FILLER[biome]
    top = np.where(rock, STONE, top)
    filler = np.where(rock, STONE, filler)
    top = np.where(peak, SNOW, top)
    top = np.where(beach, SAND, top)
    filler = np.where(beach, SAND, filler)
    top = np.where(ocean, seabed_id, top)
    filler = np.where(ocean, seabed_id, filler)
    return {'height': height, 'biome': biome, 'top': top.astype(np.uint8), 'filler': filler.astype(np.uint8)}


def coarse_layers(perlin, X, Z, scale, count, step=4):
    """Like perlin.layers(X / scale, Z / scale, count) but worked out only every `step` blocks and blended in
    between. Slow, big shapes look the same, and it is many times faster."""
    x0, z0 = int(np.floor(X.min() / step)) * step, int(np.floor(Z.min() / step)) * step
    xs = np.arange(x0, X.max() + 2 * step, step)
    zs = np.arange(z0, Z.max() + 2 * step, step)
    grid = perlin.layers(xs[:, None] / scale, zs[None, :] / scale, count)
    fx, fz = (X - x0) / step, (Z - z0) / step
    ix, iz = np.floor(fx).astype(np.int64), np.floor(fz).astype(np.int64)
    tx, tz = fx - ix, fz - iz
    a = grid[ix, iz] * (1 - tx) + grid[ix + 1, iz] * tx
    b = grid[ix, iz + 1] * (1 - tx) + grid[ix + 1, iz + 1] * tx
    return a * (1 - tz) + b * tz


def _hash(seed, a, b, salt=0):
    """A repeatable pseudo-random whole number for a place on the map."""
    h = (seed * 374761393 + a * 668265263 + b * 2147483647 + salt * 1274126177) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def generate_chunk(seed, cx, cz):
    gen = generator(seed)
    reach = LEAF_REACH
    size = CHUNK + 2 * reach
    X, Z = np.meshgrid(np.arange(cx * CHUNK - reach, cx * CHUNK - reach + size),
                       np.arange(cz * CHUNK - reach, cz * CHUNK - reach + size), indexing='ij')
    info = column_info(gen, X, Z)                     # a little bigger than the chunk, for the trees
    inner = (slice(reach, reach + CHUNK), slice(reach, reach + CHUNK))
    height, biome, top, filler = (info[k][inner] for k in ('height', 'biome', 'top', 'filler'))

    Y = np.arange(HEIGHT, dtype=np.int32)[None, None, :]
    depth = height[:, :, None] - Y                    # how far below the surface each block is
    blocks = np.where(depth >= 0, STONE, AIR).astype(np.uint8)
    blocks = np.where((depth >= 1) & (depth <= 3), filler[:, :, None], blocks)
    sandy = (biome == DESERT_INDEX)[:, :, None] & (filler == SAND)[:, :, None] & (depth >= 4) & (depth <= 6)
    blocks = np.where(sandy, SANDSTONE, blocks)
    blocks = np.where(depth == 0, top[:, :, None], blocks).astype(np.uint8)

    _carve_caves(gen, cx, cz, X[inner], Z[inner], height, blocks)
    _scatter_ores(seed, cx, cz, blocks)

    rng = np.random.default_rng((seed & 0xFFFFFFFF, cx & 0xFFFFFFFF, cz & 0xFFFFFFFF, 7))
    blocks[:, :, 0] = BEDROCK
    blocks[:, :, 1] = np.where(rng.random((CHUNK, CHUNK)) < 0.5, BEDROCK, blocks[:, :, 1])

    water = (Y > height[:, :, None]) & (Y <= SEA)     # fill the low spots with water
    blocks = np.where(water, WATER, blocks).astype(np.uint8)
    freezes = FROZEN[biome]
    surface_water = blocks[:, :, SEA] == WATER
    blocks[:, :, SEA] = np.where(freezes & surface_water, ICE, blocks[:, :, SEA])

    _plant_trees(seed, cx, cz, info, blocks)
    _scatter_small_plants(seed, cx, cz, info, blocks, height, biome)
    _build_structures(seed, cx, cz, blocks)
    return Chunk(cx, cz, blocks, height, biome)


def _trilinear(grid, step, shape):
    """Blow a coarse 3D grid (a point every `step` blocks) up to full size by blending."""
    out = grid
    for axis, size in enumerate(shape):
        idx = np.arange(size) // step
        frac = ((np.arange(size) % step) / step).reshape([-1 if i == axis else 1 for i in range(3)])
        lo = np.take(out, idx, axis=axis)
        hi = np.take(out, idx + 1, axis=axis)
        out = lo * (1 - frac) + hi * frac
    return out


def _carve_caves(gen, cx, cz, X, Z, height, blocks):
    """Dig tunnels where two noise fields are both close to zero, and a few big caverns.
    The noise is worked out on a coarse grid (every 4 blocks) and blended: caves are big, smooth shapes."""
    low, high, step = 6, 102, 4
    xs = cx * CHUNK + np.arange(0, CHUNK + step, step)
    zs = cz * CHUNK + np.arange(0, CHUNK + step, step)
    ys = np.arange(low, high + step, step)
    Xg, Yg, Zg = xs[:, None, None], ys[None, None, :], zs[None, :, None]
    a = _trilinear(gen.cave_a.noise3(Xg / 34, Yg / 22, Zg / 34), step, (CHUNK, CHUNK, high - low))
    b = _trilinear(gen.cave_b.noise3(Xg / 34, Yg / 22, Zg / 34), step, (CHUNK, CHUNK, high - low))
    caverns = _trilinear(gen.cavern.noise3(Xg / 55, Yg / 30, Zg / 55), step, (CHUNK, CHUNK, high - low)) > 0.46
    tunnels = (a * a + b * b) < 0.0125
    Yc = np.arange(low, high)[None, None, :]
    carve = (tunnels | caverns) & (Yc < height[:, :, None] - 5)        # keep a roof over the cave
    region = blocks[:, :, low:high]
    dig = carve & (region != WATER)
    region[dig] = AIR
    deep = Yc <= LAVA_LEVEL
    region[dig & deep] = LAVA                       # caves down deep are flooded with lava


def _scatter_ores(seed, cx, cz, blocks):
    """Veins of ore: a short random walk through the stone."""
    rng = np.random.default_rng((seed & 0xFFFFFFFF, cx & 0xFFFFFFFF, cz & 0xFFFFFFFF, 11))
    for name, veins, low, high, length in ORES:
        ore = ID[name]
        for _ in range(veins):
            x, z = int(rng.integers(0, CHUNK)), int(rng.integers(0, CHUNK))
            y = int(rng.integers(low, high))
            for _ in range(int(rng.integers(min(2, length), length + 1))):
                if 0 <= x < CHUNK and 0 <= z < CHUNK and 0 <= y < HEIGHT and blocks[x, z, y] == STONE:
                    blocks[x, z, y] = ore
                x += int(rng.integers(-1, 2))
                y += int(rng.integers(-1, 2))
                z += int(rng.integers(-1, 2))


def _plant_trees(seed, cx, cz, info, blocks):
    """Each 6x6 square of the map may have a tree, placed from the seed alone.
    Because that doesn't depend on the chunk, a tree on a chunk's edge is built
    correctly by both chunks."""
    reach = LEAF_REACH
    x0, z0 = cx * CHUNK - reach, cz * CHUNK - reach
    size = CHUNK + 2 * reach
    for cell_x in range(x0 // TREE_CELL - 1, (x0 + size) // TREE_CELL + 2):
        for cell_z in range(z0 // TREE_CELL - 1, (z0 + size) // TREE_CELL + 2):
            h = _hash(seed, cell_x, cell_z)
            tx = cell_x * TREE_CELL + 1 + (h % 4)
            tz = cell_z * TREE_CELL + 1 + ((h >> 3) % 4)
            ix, iz = tx - x0, tz - z0
            if not (0 <= ix < size and 0 <= iz < size):
                continue
            biome = BIOMES[info['biome'][ix, iz]]
            ground = int(info['height'][ix, iz])
            chance = min(0.9, biome.tree_chance * TREE_CELL * TREE_CELL)
            if not biome.trees or ground <= SEA + 1 or ((h >> 8) % 1000) / 1000 >= chance:
                continue
            kind = biome.trees[(h >> 18) % len(biome.trees)]
            surface = info['top'][ix, iz]
            if kind == 'cactus':
                if surface == SAND and ground > SEA + 2:
                    for dy in range(1, 2 + (h >> 20) % 3):
                        _put(blocks, cx, cz, tx, ground + dy, tz, ID['cactus'])
            elif surface in (GRASS, GRASS_SNOW):
                _grow_tree(blocks, cx, cz, tx, ground, tz, kind, h)


def _put(blocks, cx, cz, x, y, z, block, only_air=False):
    """Set one block (if it is inside this chunk)."""
    lx, lz = x - cx * CHUNK, z - cz * CHUNK
    if 0 <= lx < CHUNK and 0 <= lz < CHUNK and 0 <= y < HEIGHT:
        if not only_air or blocks[lx, lz, y] == AIR:
            blocks[lx, lz, y] = block


def _grow_tree(blocks, cx, cz, x, ground, z, kind, h):
    log, leaves = ID[f'{kind}_log'], ID[f'{kind}_leaves']
    if kind == 'spruce':
        height = 6 + (h >> 22) % 2
    elif kind == 'birch':
        height = 5 + (h >> 22) % 2
    elif kind == 'jungle':
        height = 8 + (h >> 22) % 4
    else:
        height = 4 + (h >> 22) % 2
    for dy in range(1, height + 1):
        _put(blocks, cx, cz, x, ground + dy, z, log)

    if kind == 'spruce':           # a pointy tree: leaf layers get narrower toward the top
        for dy in range(2, height + 2):
            radius = max(0, min(2, (height + 1 - dy) // 2 + (1 if dy % 2 == 0 else 0)))
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) + abs(dz) <= radius + 1 and not (dx == 0 and dz == 0 and dy <= height):
                        _put(blocks, cx, cz, x + dx, ground + dy, z + dz, leaves, only_air=True)
        return
    # Two wide layers around the top of the trunk, two small ones above
    layers = ((height - 1, 3), (height, 3), (height + 1, 2), (height + 2, 1)) if kind == 'jungle' \
        else ((height - 1, 2), (height, 2), (height + 1, 1), (height + 2, 1))
    for dy, radius in layers:
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                corner = abs(dx) == radius and abs(dz) == radius
                if corner and (radius == 1 or _hash(h, x + dx, z + dz, dy) % 2):
                    continue
                _put(blocks, cx, cz, x + dx, ground + dy, z + dz, leaves, only_air=True)


def find_spawn(seed):
    """A grassy, dry spot near the middle of the map."""
    gen = generator(seed)
    R = 96
    X, Z = np.meshgrid(np.arange(-R, R + 1), np.arange(-R, R + 1), indexing='ij')
    info = column_info(gen, X, Z)
    h = info['height']
    good = (h >= SEA + 2) & (h <= SEA + 8) & np.isin(info['top'], (GRASS, SAND, GRASS_SNOW))
    good &= (X > -R + 4) & (X < R - 4) & (Z > -R + 4) & (Z < R - 4)
    distance = np.where(good, X * X + Z * Z, 10 ** 9)
    i = np.unravel_index(np.argmin(distance), distance.shape)
    return int(X[i]), int(h[i]) + 3, int(Z[i])


def _scatter_small_plants(seed, cx, cz, info, blocks, height, biome):
    """Flowers on the grass, mushrooms in dark caves, and sugar cane at the water's edge."""
    rng = np.random.default_rng((seed & 0xFFFFFFFF, cx & 0xFFFFFFFF, cz & 0xFFFFFFFF, 23))
    flower_ids = (ID['dandelion'], ID['poppy'])
    for _ in range(14):                                               # flowers (a few per chunk, in groups)
        x, z = int(rng.integers(0, CHUNK)), int(rng.integers(0, CHUNK))
        if BIOMES[biome[x, z]] not in (PLAINS, FOREST):
            continue
        flower = flower_ids[int(rng.integers(0, 2))]
        for _ in range(int(rng.integers(2, 6))):
            fx, fz = x + int(rng.integers(-2, 3)), z + int(rng.integers(-2, 3))
            if 0 <= fx < CHUNK and 0 <= fz < CHUNK:
                ground = int(height[fx, fz])
                if ground > SEA and blocks[fx, fz, ground] == GRASS and blocks[fx, fz, ground + 1] == AIR:
                    blocks[fx, fz, ground + 1] = flower
    for _ in range(10):                                               # mushrooms underground
        x, z, y = int(rng.integers(0, CHUNK)), int(rng.integers(0, CHUNK)), int(rng.integers(12, 45))
        if blocks[x, z, y] == AIR and blocks[x, z, y - 1] == STONE:
            blocks[x, z, y] = ID['brown_mushroom'] if rng.random() < 0.6 else ID['red_mushroom']
    for x in range(CHUNK):                                            # sugar cane beside water
        for z in range(CHUNK):
            ground = int(height[x, z])
            if ground == SEA and blocks[x, z, ground] in (SAND, GRASS) and rng.random() < 0.12:
                near_water = any(0 <= x + dx < CHUNK and 0 <= z + dz < CHUNK and blocks[x + dx, z + dz, SEA] == WATER
                                 for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if near_water and blocks[x, z, ground + 1] == AIR:
                    for dy in range(1, int(rng.integers(2, 4))):
                        blocks[x, z, ground + dy] = ID['sugar_cane']


FLAT_TOP = 3        # in a flat world the grass is at this height


def generate_flat_chunk(nether=False):
    """A chunk of an empty flat world: bedrock, a little dirt, and grass on top (netherrack in the Nether)."""
    blocks = np.zeros((CHUNK, CHUNK, HEIGHT), dtype=np.uint8)
    blocks[:, :, 0] = BEDROCK
    blocks[:, :, 1:FLAT_TOP] = ID['netherrack'] if nether else DIRT
    blocks[:, :, FLAT_TOP] = ID['netherrack'] if nether else GRASS
    return Chunk(0, 0, blocks, np.full((CHUNK, CHUNK), FLAT_TOP, dtype=np.int32), np.zeros((CHUNK, CHUNK), dtype=np.int32))


def _build_structures(seed, cx, cz, blocks):
    """Villages and dungeons that reach into this chunk."""
    import structures
    plan = structures.dungeon_plan(seed, cx, cz)
    if plan is not None:
        structures.stamp(plan, blocks, cx, cz)
    for rx, rz in structures.village_ids_near(seed, cx, cz):
        village = structures.village_plan(seed, rx, rz)
        if village is not None:
            structures.clear_trees(village, blocks, cx, cz)
            structures.stamp(village, blocks, cx, cz)
