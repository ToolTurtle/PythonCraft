"""Buildings that appear in the world by themselves: villages and dungeons.

Like everything else in world generation, a structure depends only on the seed and where it is,
so the same village appears in the same place every time, and each chunk draws just the part of it
that falls inside the chunk."""
import functools

import numpy as np

import terrain
from blocks import ID
from chunk import CHUNK, HEIGHT

REGION = 96              # the map is cut into squares this big, and each may hold one village
VILLAGE_CHANCE = 0.9
VILLAGE_RADIUS = 34


def _hash(seed, a, b, salt=0):
    h = (seed * 374761393 + a * 668265263 + b * 2147483647 + salt * 1274126177) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


class _Plan:
    """The blocks of one structure, collected in a dictionary: (x, y, z) -> block name."""

    def __init__(self):
        self.blocks = {}
        self.villagers = []        # where villagers start
        self.golems = []
        self.base = (0, 0)
        self.ground = lambda x, z: None      # the terrain height at a spot (set when the plan is made)

    def put(self, x, y, z, name):
        self.blocks[(x, y, z)] = name

    def level(self, x0, z0, x1, z1, gy):
        """Make the ground flat at height gy under a rectangle: fill hollows with dirt and cut away hills."""
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                h = self.ground(x, z)
                if h is None:
                    continue
                if h < gy:
                    for y in range(h, gy):
                        self.blocks[(x, y, z)] = 'dirt'
                elif h > gy:
                    for y in range(gy + 1, h + 9):
                        self.blocks[(x, y, z)] = 'air'
                self.blocks.setdefault((x, gy, z), 'dirt')

    def box(self, x0, y0, z0, x1, y1, z1, name):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    self.blocks[(x, y, z)] = name


# ---- villages -----------------------------------------------------------------------------------

def _cottage(plan, x0, z0, gy, rng, kind):
    """A small house with its floor at gy. (x0, z0) is the north-west corner; it is 5 wide and 7 long."""
    w, d = 5, 7
    plan.level(x0 - 1, z0 - 2, x0 + w, z0 + d, gy)
    plan.box(x0, gy - 1, z0, x0 + w - 1, gy, z0 + d - 1, 'cobblestone')                  # foundation and floor
    plan.box(x0, gy + 1, z0, x0 + w - 1, gy + 8, z0 + d - 1, 'air')                      # clear the space
    plan.box(x0 + 1, gy, z0 + 1, x0 + w - 2, gy, z0 + d - 2, 'oak_planks')
    for (cx, cz) in ((x0, z0), (x0 + w - 1, z0), (x0, z0 + d - 1), (x0 + w - 1, z0 + d - 1)):
        plan.box(cx, gy + 1, cz, cx, gy + 3, cz, 'oak_log')                             # corner posts
    for x in range(x0 + 1, x0 + w - 1):
        for y in (gy + 1, gy + 2, gy + 3):
            plan.put(x, y, z0, 'oak_planks'); plan.put(x, y, z0 + d - 1, 'oak_planks')
    for z in range(z0 + 1, z0 + d - 1):
        for y in (gy + 1, gy + 2, gy + 3):
            plan.put(x0, y, z, 'oak_planks'); plan.put(x0 + w - 1, y, z, 'oak_planks')
    for z in (z0 + 2, z0 + 4):                                                          # windows
        plan.put(x0, gy + 2, z, 'glass_pane'); plan.put(x0 + w - 1, gy + 2, z, 'glass_pane')
    plan.put(x0 + 2, gy + 2, z0 + d - 1, 'glass_pane')
    plan.put(x0 + 2, gy + 1, z0, 'oak_door_b'); plan.put(x0 + 2, gy + 2, z0, 'oak_door_t')   # the door (north side)
    plan.box(x0 - 1, gy + 4, z0 - 1, x0 + w, gy + 4, z0 + d, 'oak_planks')               # a flat roof with a lip
    plan.box(x0, gy + 5, z0, x0 + w - 1, gy + 5, z0 + d - 1, 'oak_slab')
    plan.put(x0 + 1, gy + 3, z0 + d - 2, 'torch')
    plan.put(x0 + 1, gy + 1, z0 + d - 2, 'bed')
    if kind == 'library':
        for z in range(z0 + 2, z0 + d - 1):
            plan.put(x0 + 1, gy + 1, z, 'bookshelf'); plan.put(x0 + 1, gy + 2, z, 'bookshelf')
        plan.put(x0 + w - 2, gy + 1, z0 + 2, 'crafting_table')
    elif kind == 'smithy':
        plan.put(x0 + w - 2, gy + 1, z0 + 2, 'furnace')
        plan.put(x0 + w - 2, gy + 1, z0 + 3, 'furnace')
        plan.put(x0 + w - 2, gy + 1, z0 + d - 2, 'chest')
    else:
        plan.put(x0 + w - 2, gy + 1, z0 + d - 2, 'chest') if rng.random() < 0.5 else plan.put(x0 + w - 2, gy + 1, z0 + 2, 'crafting_table')
    plan.villagers.append((x0 + 2, gy + 1, z0 + 3))


def _farm(plan, x0, z0, gy, rng):
    plan.level(x0 - 1, z0 - 1, x0 + 7, z0 + 9, gy)
    plan.box(x0 - 1, gy, z0 - 1, x0 + 7, gy, z0 + 9, 'dirt')
    plan.box(x0 - 1, gy + 1, z0 - 1, x0 + 7, gy + 3, z0 + 9, 'air')
    for z in range(z0, z0 + 9):
        for x in range(x0, x0 + 7):
            if x == x0 + 3:
                plan.put(x, gy, z, 'water')
            else:
                plan.put(x, gy, z, 'farmland')
                plan.put(x, gy + 1, z, f'wheat_{int(rng.integers(3, 8))}')
    for x in range(x0 - 1, x0 + 8):
        for z in (z0 - 1, z0 + 9):
            plan.put(x, gy + 1, z, 'oak_fence')
    for z in range(z0 - 1, z0 + 10):
        for x in (x0 - 1, x0 + 7):
            plan.put(x, gy + 1, z, 'oak_fence')


def _well(plan, x0, z0, gy):
    plan.level(x0 - 2, z0 - 2, x0 + 4, z0 + 4, gy)
    plan.box(x0 - 1, gy - 4, z0 - 1, x0 + 3, gy, z0 + 3, 'cobblestone')
    plan.box(x0, gy - 3, z0, x0 + 2, gy, z0 + 2, 'water')
    plan.box(x0 - 1, gy + 1, z0 - 1, x0 + 3, gy + 6, z0 + 3, 'air')
    plan.box(x0, gy + 1, z0, x0 + 2, gy + 1, z0 + 2, 'air')
    plan.box(x0, gy + 1, z0, x0, gy + 3, z0, 'oak_fence')
    plan.box(x0 + 2, gy + 1, z0 + 2, x0 + 2, gy + 3, z0 + 2, 'oak_fence')
    plan.box(x0 + 2, gy + 1, z0, x0 + 2, gy + 3, z0, 'oak_fence')
    plan.box(x0, gy + 1, z0 + 2, x0, gy + 3, z0 + 2, 'oak_fence')
    plan.box(x0 - 1, gy + 4, z0 - 1, x0 + 3, gy + 4, z0 + 3, 'oak_planks')


@functools.lru_cache(maxsize=64)
def village_plan(seed, rx, rz):
    """The village in region (rx, rz), or None if that region has none. Returns a _Plan."""
    if _hash(seed, rx, rz, 5) % 1000 >= VILLAGE_CHANCE * 1000:
        return None
    gen = terrain.generator(seed)
    r = VILLAGE_RADIUS
    for attempt in range(5):                                                   # try a few places in the region
        rng = np.random.default_rng((seed & 0xFFFFFFFF, rx & 0xFFFFFFFF, rz & 0xFFFFFFFF, 99 + attempt))
        cx = rx * REGION + 36 + int(rng.integers(0, REGION - 72))
        cz = rz * REGION + 36 + int(rng.integers(0, REGION - 72))
        X, Z = np.meshgrid(np.arange(cx - r, cx + r + 1), np.arange(cz - r, cz + r + 1), indexing='ij')
        info = terrain.column_info(gen, X, Z)
        heights, biomes = info['height'], info['biome']
        biome = terrain.BIOMES[biomes[r, r]]
        nearby = heights[r - 20:r + 21, r - 20:r + 21]
        gy = int(np.median(nearby))
        if biome.name not in ('Plains', 'Desert', 'Forest') or gy < terrain.SEA + 2 or gy > terrain.SEA + 18:
            continue
        if np.percentile(nearby, 95) - np.percentile(nearby, 5) > 9 or (nearby < terrain.SEA).mean() > 0.04:
            continue                                                           # too hilly, or too much water
        break
    else:
        return None
    plan = _Plan()
    plan.base = (cx, cz)
    plan.ground = lambda x, z: int(heights[x - (cx - r), z - (cz - r)]) if abs(x - cx) <= r and abs(z - cz) <= r else None
    _well(plan, cx - 1, cz - 1, gy)
    spots = []
    for i in range(int(rng.integers(5, 9))):                                    # houses around the well
        angle = 2 * np.pi * i / 7 + rng.uniform(-0.3, 0.3)
        distance = rng.uniform(11, 20)
        spots.append((int(cx + np.cos(angle) * distance) - 2, int(cz + np.sin(angle) * distance) - 3))
    kinds = ['library', 'smithy'] + ['house'] * 7
    for n, (hx, hz) in enumerate(spots):
        if any(abs(hx - ox) < 8 and abs(hz - oz) < 10 for ox, oz in spots[:n]):
            continue
        _cottage(plan, hx, hz, gy, rng, kinds[n % len(kinds)])
    fx, fz = cx + 14, cz - 6
    _farm(plan, fx, fz, gy, rng)
    plan.villagers.append((cx, gy + 1, cz + 3))
    plan.golems.append((cx + 3, gy + 1, cz))
    # gravel paths from the well to every house door
    for (hx, hz) in spots:
        x, z = cx, cz
        tx, tz = hx + 2, hz - 1
        for _ in range(60):
            if plan.ground(x, z) is not None:
                plan.level(x, z, x, z, gy)
            plan.put(x, gy, z, 'gravel')
            if x == tx and z == tz:
                break
            if abs(tx - x) > abs(tz - z):
                x += 1 if tx > x else -1
            else:
                z += 1 if tz > z else -1
    return plan


def village_ids_near(seed, cx, cz):
    """The (rx, rz) of every region whose village might touch chunk (cx, cz)."""
    x0, z0 = cx * CHUNK - VILLAGE_RADIUS, cz * CHUNK - VILLAGE_RADIUS
    out = []
    for rx in range(x0 // REGION, (cx * CHUNK + CHUNK + VILLAGE_RADIUS) // REGION + 1):
        for rz in range(z0 // REGION, (cz * CHUNK + CHUNK + VILLAGE_RADIUS) // REGION + 1):
            out.append((rx, rz))
    return out


# ---- dungeons --------------------------------------------------------------------------------------

def dungeon_plan(seed, cx, cz):
    """A small underground room with a monster spawner and chests, or None. It always fits inside its chunk."""
    if _hash(seed, cx, cz, 17) % 100 >= 7:
        return None
    rng = np.random.default_rng((seed & 0xFFFFFFFF, cx & 0xFFFFFFFF, cz & 0xFFFFFFFF, 31))
    w = int(rng.choice((5, 7)))
    x0 = cx * CHUNK + int(rng.integers(2, CHUNK - w - 1))
    z0 = cz * CHUNK + int(rng.integers(2, CHUNK - w - 1))
    y0 = int(rng.integers(14, 40))
    plan = _Plan()
    plan.box(x0 - 1, y0 - 1, z0 - 1, x0 + w, y0 + 4, z0 + w, 'cobblestone')
    plan.box(x0, y0, z0, x0 + w - 1, y0 + 3, z0 + w - 1, 'air')
    for x in range(x0, x0 + w):
        for z in range(z0, z0 + w):
            plan.put(x, y0 - 1, z, 'mossy_cobblestone' if rng.random() < 0.4 else 'cobblestone')
    mid = w // 2
    plan.put(x0 + mid, y0, z0 + mid, 'spawner')
    for _ in range(2):
        side = int(rng.integers(0, 4))
        if side == 0: pos = (x0, z0 + int(rng.integers(1, w - 1)))
        elif side == 1: pos = (x0 + w - 1, z0 + int(rng.integers(1, w - 1)))
        elif side == 2: pos = (x0 + int(rng.integers(1, w - 1)), z0)
        else: pos = (x0 + int(rng.integers(1, w - 1)), z0 + w - 1)
        plan.put(pos[0], y0, pos[1], 'chest')
    return plan


# ---- putting a plan into a chunk ---------------------------------------------------------------------

def stamp(plan, blocks, cx, cz):
    """Copy the part of a plan that is inside chunk (cx, cz) into the chunk's block array."""
    x_low, z_low = cx * CHUNK, cz * CHUNK
    for (x, y, z), name in plan.blocks.items():
        lx, lz = x - x_low, z - z_low
        if 0 <= lx < CHUNK and 0 <= lz < CHUNK and 0 <= y < HEIGHT:
            blocks[lx, lz, y] = ID[name] if name != 'air' else 0


_TREE_IDS = None


def clear_trees(plan, blocks, cx, cz, radius=26):
    """Take away any tree that grew inside a village (so the houses are not hidden in a forest)."""
    global _TREE_IDS
    if _TREE_IDS is None:
        _TREE_IDS = np.array([ID[n] for n in ID if n.endswith(('_log', '_leaves'))], dtype=np.uint8)
    bx, bz = plan.base
    for lx in range(CHUNK):
        for lz in range(CHUNK):
            x, z = cx * CHUNK + lx, cz * CHUNK + lz
            if (x - bx) ** 2 + (z - bz) ** 2 <= radius * radius:
                column = blocks[lx, lz]
                column[np.isin(column, _TREE_IDS)] = 0


# ---- Nether fortresses ----------------------------------------------------------------------------------

FORTRESS_REGION = 160        # the Nether map is cut into squares this big, and each may hold one fortress
FORTRESS_CHANCE = 0.7
FORTRESS_REACH = 80          # no piece is farther than this from the middle of its fortress


@functools.lru_cache(maxsize=64)
def fortress_plan(seed, rx, rz):
    """A Nether fortress for region (rx, rz) (or None): long covered bridges that turn corners, with a room
    for a blaze spawner and one with a nether wart garden. It depends only on the seed and the region."""
    if _hash(seed, rx, rz, 71) % 100 >= FORTRESS_CHANCE * 100:
        return None
    rng = np.random.default_rng((seed & 0xFFFFFFFF, rx & 0xFFFFFFFF, rz & 0xFFFFFFFF, 73))
    x = rx * FORTRESS_REGION + int(rng.integers(50, FORTRESS_REGION - 50))
    z = rz * FORTRESS_REGION + int(rng.integers(50, FORTRESS_REGION - 50))
    y0 = int(rng.integers(58, 70))
    plan = _Plan()
    plan.base = (x, z)
    heading = [(1, 0), (0, 1), (-1, 0), (0, -1)][int(rng.integers(0, 4))]
    shells, interiors, pillars, lamps = [], [], [], []
    px, pz = x, z
    stops = []                                                      # where each corridor ends
    for _ in range(int(rng.integers(5, 8))):
        length = int(rng.integers(2, 5)) * 6
        ex, ez = px + heading[0] * length, pz + heading[1] * length
        lo_x, hi_x = sorted((px, ex))
        lo_z, hi_z = sorted((pz, ez))
        reach = 3
        shells.append((lo_x - reach if heading[0] == 0 else lo_x - reach, y0, lo_z - reach, hi_x + reach, y0 + 5, hi_z + reach))
        interiors.append((lo_x - (2 if heading[0] == 0 else 0), y0 + 1, lo_z - (2 if heading[1] == 0 else 0),
                          hi_x + (2 if heading[0] == 0 else 0), y0 + 4, hi_z + (2 if heading[1] == 0 else 0), heading))
        for t in range(0, length + 1, 8):
            pillars.append((px + heading[0] * t, pz + heading[1] * t))
        for t in range(3, length, 9):                                  # glowstone lamps in the roof
            lamps.append((px + heading[0] * t, pz + heading[1] * t))
        stops.append((ex, ez))
        px, pz = ex, ez
        heading = (-heading[1], heading[0]) if rng.random() < 0.5 else (heading[1], -heading[0])
    # shells first, so every interior can be carved out of the overlaps afterwards
    for x0, ya, z0, x1, yb, z1 in shells:
        plan.box(x0, ya, z0, x1, yb, z1, 'nether_bricks')
    for x0, ya, z0, x1, yb, z1, heading in interiors:
        plan.box(x0, ya, z0, x1, yb, z1, 'air')
    for x0, ya, z0, x1, yb, z1 in shells:                          # railings with gaps to look out of
        for xx in range(x0, x1 + 1):
            for zz in range(z0, z1 + 1):
                on_edge = xx in (x0, x1) or zz in (z0, z1)
                if on_edge and (xx + zz) % 2 == 0 and plan.blocks.get((xx, y0 + 2, zz)) == 'nether_bricks' \
                        and plan.blocks.get((xx, y0 + 1, zz)) == 'nether_bricks':
                    plan.put(xx, y0 + 2, zz, 'nether_brick_fence')
    for lx, lz in lamps:
        plan.put(lx, y0 + 4, lz, 'glowstone')
    for pxx, pzz in pillars:                                       # pillars down to the lava
        for dx in (0, 1):
            for dz in (0, 1):
                for yy in range(34, y0):
                    plan.put(pxx + dx, yy, pzz + dz, 'nether_bricks')
    # the last stop is a blaze room, the one before a nether wart garden
    bx, bz = stops[-1]
    plan.box(bx - 5, y0, bz - 5, bx + 5, y0 + 6, bz + 5, 'nether_bricks')
    plan.box(bx - 4, y0 + 1, bz - 4, bx + 4, y0 + 5, bz + 4, 'air')
    plan.box(bx - 1, y0 + 1, bz - 1, bx + 1, y0 + 1, bz + 1, 'nether_bricks')
    plan.put(bx, y0 + 2, bz, 'spawner')
    for dx, dz in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
        plan.put(bx + dx, y0 + 2, bz + dz, 'nether_brick_fence')
    plan.put(bx, y0 + 2, bz, 'spawner')
    for dx, dz in ((3, 3), (-3, 3), (3, -3), (-3, -3), (0, 3), (0, -3)):
        plan.put(bx + dx, y0 + 5, bz + dz, 'glowstone')
    plan.put(bx + 3, y0 + 1, bz + 3, 'chest')
    plan.put(bx - 3, y0 + 1, bz - 3, 'chest')
    wx, wz = stops[-2] if len(stops) > 1 else (x, z)
    plan.box(wx - 4, y0, wz - 4, wx + 4, y0 + 6, wz + 4, 'nether_bricks')
    plan.box(wx - 3, y0 + 1, wz - 3, wx + 3, y0 + 5, wz + 3, 'air')
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            if abs(dx) + abs(dz) < 6:
                plan.put(wx + dx, y0, wz + dz, 'soul_sand')
                plan.put(wx + dx, y0 + 1, wz + dz, f'nether_wart_{int(rng.integers(1, 4))}')
    for dx, dz in ((0, 0), (2, 2), (-2, -2), (2, -2), (-2, 2)):
        plan.put(wx + dx, y0 + 5, wz + dz, 'glowstone')
    plan.put(x, y0 + 1, z + 1, 'chest')
    return plan


def fortress_ids_near(seed, cx, cz):
    """The fortress regions that might reach into chunk (cx, cz)."""
    x, z = cx * CHUNK + 8, cz * CHUNK + 8
    rx0, rz0 = x // FORTRESS_REGION, z // FORTRESS_REGION
    return [(rx, rz) for rx in (rx0 - 1, rx0, rx0 + 1) for rz in (rz0 - 1, rz0, rz0 + 1)]
