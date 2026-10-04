"""Making the land from layers of Perlin noise.

Each noise layer answers one question about a spot on the map:
  continents    -> is this ocean or land? (very big, slow shapes)
  ridges        -> where are the mountain ranges?
  erosion       -> where are the mountains allowed to be tall?
  rolling hills -> gentle bumps, everywhere
  detail        -> tiny bumps, so the ground isn't smooth
  temperature, humidity -> which biome grows here?"""
import math
import random

from biomes import PLAINS, FOREST, DESERT, SNOWY
from noise import Perlin

BOTTOM = 0        # the lowest layer (bedrock)
SEA = 12          # water fills every low spot up to this height
ROCK_LINE = 24    # above this the ground is bare stone
SNOW_LINE = 29    # and above this it is snow-capped


def smoothstep(low, high, x):
    t = min(1.0, max(0.0, (x - low) / (high - low)))
    return t * t * (3 - 2 * t)


def coarse(function, size, step=4):
    """Slow-changing noise is the same for neighboring columns, so work it out
    only every `step` blocks and blend in between. Much faster."""
    count = size // step + 2
    grid = [[function(i * step, j * step) for j in range(count)] for i in range(count)]

    def lookup(x, z):
        fx, fz = x / step, z / step
        i, j = int(fx), int(fz)
        tx, tz = fx - i, fz - j
        a = grid[i][j] * (1 - tz) + grid[i][j + 1] * tz
        b = grid[i + 1][j] * (1 - tz) + grid[i + 1][j + 1] * tz
        return a * (1 - tx) + b * tx
    return lookup


def generate(world, seed=None):
    """Fill world.data with blocks. Sets world.heights, world.biome_map, world.spawn."""
    seed = random.randrange(1_000_000) if seed is None else seed
    world.seed = seed
    size = world.size
    rng = random.Random(seed)

    continents = Perlin(seed + 1)
    ridges = Perlin(seed + 2)
    erosion = Perlin(seed + 3)
    rolling = Perlin(seed + 4)
    detail = Perlin(seed + 5)
    temperature = Perlin(seed + 6)
    humidity = Perlin(seed + 7)
    seabed = Perlin(seed + 8)

    # The big, slow layers (each scaled to roughly -1..1)
    continent_at = coarse(lambda x, z: continents.layers(x / 90, z / 90, 4) * 3, size)
    ridge_at = coarse(lambda x, z: ridges.layers(x / 85, z / 85, 3) * 3, size)
    erosion_at = coarse(lambda x, z: erosion.layers(x / 60, z / 60, 3) * 3, size)
    temperature_at = coarse(lambda x, z: temperature.layers(x / 65, z / 65, 3) * 3, size)
    humidity_at = coarse(lambda x, z: humidity.layers(x / 55, z / 55, 3) * 3, size)

    world.heights, world.biome_map = {}, {}
    for x in range(size):
        for z in range(size):
            c = continent_at(x, z)
            land = SEA + 3 + c * 9                                   # ocean floor up to low hills

            # Mountains: ridge lines, but only on land, and only where erosion allows
            ridge = max(0.0, 1 - abs(ridge_at(x, z))) ** 1.5
            allowed = smoothstep(0.0, 0.5, c) * smoothstep(-0.3, 0.4, erosion_at(x, z))
            mountains = ridge * 22 * allowed

            bumps = rolling.layers(x / 40, z / 40, 3) * 3 * 3 + detail.layers(x / 12, z / 12, 2) * 3 * 1.2
            height = max(BOTTOM + 3, round(land + mountains + bumps * (0.4 + allowed)))

            biome = _pick_biome(temperature_at(x, z), humidity_at(x, z))
            world.heights[(x, z)] = height
            world.biome_map[(x, z)] = biome
            _fill_column(world, x, z, height, biome, seabed.noise(x / 9, z / 9), detail.noise(x / 5, z / 5), rng)

    _scatter_ores(world, rng)
    _plant_trees(world, rng)
    world.spawn = _find_spawn(world)


def _pick_biome(temperature, humidity):
    if temperature > 0.3 and humidity < 0.1:
        return DESERT
    if temperature < -0.3:
        return SNOWY
    if humidity > 0.15:
        return FOREST
    return PLAINS


def _fill_column(world, x, z, height, biome, seabed_noise, rock_noise, rng):
    """Stack the blocks of one column, from bedrock up to the surface."""
    data = world.data

    if height < SEA:                                   # under the sea
        top = filler = 'clay' if seabed_noise > 0.45 else 'gravel' if seabed_noise > 0.25 else 'sand'
    elif height <= SEA + (1 if rock_noise > 0 else 0):  # beach
        top = filler = 'sand'
    elif height >= SNOW_LINE + rock_noise * 2:         # snowy peaks
        top, filler = 'snow', 'stone'
    elif height >= ROCK_LINE + rock_noise * 2:         # bare mountain rock
        top = filler = 'stone'
    else:
        top, filler = biome.surface, biome.filler

    for y in range(BOTTOM, height + 1):
        depth = height - y
        if y == BOTTOM or (y == BOTTOM + 1 and rng.random() < 0.5):
            kind = 'bedrock'
        elif depth == 0:
            kind = top
        elif depth <= 3:
            kind = filler
        elif depth <= 6 and filler == 'sand' and top == 'sand' and biome is DESERT:
            kind = 'sandstone'
        else:
            kind = 'stone'
        data[(x, y, z)] = kind

    for y in range(height + 1, SEA + 1):               # fill the low spots with water
        data[(x, y, z)] = 'ice' if (biome.frozen_water and y == SEA) else 'water'


def _scatter_ores(world, rng):
    """Veins of ore: a short random walk through the stone."""
    for kind, veins, low, high, length in (('coal_ore', 700, 3, 30, 8),
                                           ('iron_ore', 350, 2, 20, 5),
                                           ('gold_ore', 60, 2, 9, 4),
                                           ('diamond_ore', 45, 1, 8, 3)):
        for _ in range(veins):
            x, z = rng.randrange(world.size), rng.randrange(world.size)
            y = rng.randrange(low, high)
            for _ in range(rng.randint(2, length)):
                if world.data.get((x, y, z)) == 'stone':
                    world.data[(x, y, z)] = kind
                x += rng.choice((-1, 0, 1))
                y += rng.choice((-1, 0, 1))
                z += rng.choice((-1, 0, 1))


def _plant_trees(world, rng):
    taken = set()    # a coarse grid so trees don't grow too close together
    for (x, z), ground in world.heights.items():
        biome = world.biome_map[(x, z)]
        if not biome.trees or ground <= SEA + 1 or rng.random() > biome.tree_chance:
            continue
        cell = (x // 4, z // 4)
        if any((cell[0] + dx, cell[1] + dz) in taken for dx in (-1, 0, 1) for dz in (-1, 0, 1)):
            continue
        below = world.data.get((x, ground, z))
        inside = 3 <= x < world.size - 3 and 3 <= z < world.size - 3
        kind = rng.choice(biome.trees)
        if kind in ('oak', 'birch', 'spruce') and below in ('grass', 'grass_snow') and inside:
            {'oak': _grow_oak, 'birch': _grow_birch, 'spruce': _grow_spruce}[kind](world, x, ground, z, rng)
        elif kind == 'cactus' and below == 'sand' and ground > SEA + 2:
            for y in range(ground + 1, ground + 1 + rng.randint(1, 3)):
                world.data[(x, y, z)] = 'cactus'
        else:
            continue
        taken.add(cell)


def _round_leaves(world, x, ground, z, rng, height, leaves):
    """Two wide layers around the top of a trunk, two small ones above."""
    for dy, radius in ((height - 1, 2), (height, 2), (height + 1, 1), (height + 2, 1)):
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                corner = abs(dx) == radius and abs(dz) == radius
                if corner and (radius == 1 or rng.random() < 0.5):
                    continue
                world.data.setdefault((x + dx, ground + dy, z + dz), leaves)


def _grow_oak(world, x, ground, z, rng):
    height = rng.choice((4, 5))
    for y in range(ground + 1, ground + height + 1):
        world.data[(x, y, z)] = 'oak_log'
    _round_leaves(world, x, ground, z, rng, height, 'oak_leaves')


def _grow_birch(world, x, ground, z, rng):
    height = rng.choice((5, 6))
    for y in range(ground + 1, ground + height + 1):
        world.data[(x, y, z)] = 'birch_log'
    _round_leaves(world, x, ground, z, rng, height, 'birch_leaves')


def _grow_spruce(world, x, ground, z, rng):
    """A pointy tree: leaf layers get narrower toward the top."""
    height = rng.choice((6, 7))
    for y in range(ground + 1, ground + height + 1):
        world.data[(x, y, z)] = 'spruce_log'
    for dy in range(2, height + 2):
        radius = max(0, min(2, (height + 1 - dy) // 2 + (1 if dy % 2 == 0 else 0)))
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if abs(dx) + abs(dz) <= radius + 1 and not (dx == 0 and dz == 0 and dy <= height):
                    world.data.setdefault((x + dx, ground + dy, z + dz), 'spruce_leaves')


def _find_spawn(world):
    """A grassy, dry spot as near the middle of the map as we can find."""
    middle = world.size // 2
    for radius in range(0, middle - 4):
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if max(abs(dx), abs(dz)) != radius:
                    continue
                x, z = middle + dx, middle + dz
                ground = world.heights[(x, z)]
                if SEA + 2 <= ground <= SEA + 8 and world.data.get((x, ground, z)) in ('grass', 'sand'):
                    return (x, ground + 3, z)
    return (middle, world.heights[(middle, middle)] + 3, middle)
