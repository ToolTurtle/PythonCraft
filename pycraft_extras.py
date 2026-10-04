"""Helpers for pycraftWorld that need no game window: a block font, a picture-to-blocks palette,
shape generators (trees, houses, mazes, villages, terrain), build challenges and share codes.

Everything here works on plain dictionaries {(x, y, z): block name}, so it can be tested without opening the game."""
import base64
import json
import math
import zlib
from pathlib import Path

HERE = Path(__file__).parent

# ---- a 5 x 7 block font ----------------------------------------------------------------------------------

_GLYPHS = {
    'A': (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11), 'B': (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    'C': (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E), 'D': (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    'E': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F), 'F': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    'G': (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F), 'H': (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'I': (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E), 'J': (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    'K': (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11), 'L': (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    'M': (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11), 'N': (0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11),
    'O': (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), 'P': (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    'Q': (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D), 'R': (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    'S': (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E), 'T': (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    'U': (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), 'V': (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'W': (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A), 'X': (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    'Y': (0x11, 0x11, 0x11, 0x0A, 0x04, 0x04, 0x04), 'Z': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    '0': (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E), '1': (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    '2': (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F), '3': (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    '4': (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02), '5': (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    '6': (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E), '7': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    '8': (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E), '9': (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    '!': (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04), '?': (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    '.': (0, 0, 0, 0, 0, 0x0C, 0x0C), ',': (0, 0, 0, 0, 0x0C, 0x04, 0x08), ':': (0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0),
    '-': (0, 0, 0, 0x1F, 0, 0, 0), '+': (0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0), '=': (0, 0, 0x1F, 0, 0x1F, 0, 0),
    '(': (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02), ')': (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    '/': (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10), '*': (0, 0x04, 0x15, 0x0E, 0x15, 0x04, 0),
    "'": (0x04, 0x04, 0x08, 0, 0, 0, 0), '<': (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02),
    '>': (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08), '#': (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
    ' ': (0, 0, 0, 0, 0, 0, 0),
}


def text_cells(message, size=1, spacing=1):
    """The cells of a line of block letters: [(across, up)], where `across` counts to the right and `up`
    counts up from the bottom of the letters. Each letter is 5 cells wide and 7 tall (times `size`)."""
    cells = []
    cursor = 0
    for ch in str(message).upper():
        glyph = _GLYPHS.get(ch)
        if glyph is None:
            raise ValueError(f"The block font has no letter {ch!r}. It knows A-Z, 0-9 and  ! ? . , : - + = ( ) / * ' < > #")
        width = 3 if ch == ' ' else 5
        for row, bits in enumerate(glyph):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    for dx in range(size):
                        for dy in range(size):
                            cells.append((cursor + col * size + dx, (6 - row) * size + dy))
        cursor += (width + spacing) * size
    return cells, max(0, cursor - spacing * size)


# ---- turning a picture into blocks -------------------------------------------------------------------------

_SKIP_FOR_PICTURES = {'bedrock', 'tnt', 'sponge', 'spawner', 'bookshelf', 'chest', 'furnace', 'crafting_table', 'grass', 'grass_snow',
                      'podzol', 'cactus', 'melon', 'pumpkin', 'jack_o_lantern', 'note_block', 'redstone_lamp', 'redstone_lamp_on',
                      'magma_block', 'nether_portal', 'redstone_ore'}
_palette_cache = {}


def _average_color(name):
    from PIL import Image
    image = Image.open(HERE / 'assets' / 'textures' / f'{name}.png').convert('RGBA')
    if image.height > image.width:
        image = image.crop((0, 0, image.width, image.width))
    pixels = [p for p in image.getdata() if p[3] > 128]
    if not pixels:
        return None
    return tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))


def palette(names=None):
    """[(block name, (r, g, b))] for blocks that look like one flat colour: used to turn pictures into blocks."""
    key = tuple(names) if names else None
    if key in _palette_cache:
        return _palette_cache[key]
    import blocks
    chosen = []
    for name, spec in blocks.BLOCKS.items():
        if names and name not in names:
            continue
        if not names and name.endswith('_ore'):
            continue
        if name in _SKIP_FOR_PICTURES or spec.get('transparent') or spec.get('shape') or spec.get('fluid') \
                or spec.get('placeable') is False or spec.get('gravity') and not names or not spec.get('solid', True):
            continue
        layers = spec.get('all') or spec.get('side')
        if not layers or not isinstance(layers[0], str):
            continue                                   # (grass and leaves are tinted: their picture is gray)
        try:
            color = _average_color(layers[0])
        except OSError:
            continue
        if color is not None:
            chosen.append((name, color))
    _palette_cache[key] = chosen
    return chosen


def nearest_block(rgb, colors):
    best, best_distance = None, 1e18
    r, g, b = rgb
    for name, (cr, cg, cb) in colors:
        distance = (r - cr) ** 2 * 0.3 + (g - cg) ** 2 * 0.59 + (b - cb) ** 2 * 0.11
        if distance < best_distance:
            best, best_distance = name, distance
    return best


def image_cells(path, width=None, height=None, names=None, max_size=48):
    """[(across, up, block name)] for a picture file, scaled to the size you ask for (or up to 48 across)."""
    from PIL import Image
    try:
        picture = Image.open(path).convert('RGBA')
    except OSError as error:
        raise ValueError(f'Could not open the picture {str(path)!r}: {error}') from None
    if width is None and height is None:
        width = min(max_size, picture.width)
    if width is None:
        width = max(1, round(picture.width * height / picture.height))
    if height is None:
        height = max(1, round(picture.height * width / picture.width))
    picture = picture.resize((width, height), Image.BILINEAR)
    colors = palette(names)
    if not colors:
        raise ValueError('No blocks to draw with. Check the names you gave in palette=[...].')
    cache = {}
    cells = []
    for row in range(height):
        for col in range(width):
            r, g, b, a = picture.getpixel((col, row))
            if a < 128:
                continue                                # see-through pixels stay empty
            key = (r >> 3, g >> 3, b >> 3)
            if key not in cache:
                cache[key] = nearest_block((r, g, b), colors)
            cells.append((col, height - 1 - row, cache[key]))
    return cells, width, height


# ---- turning a build 90 degrees ------------------------------------------------------------------------------

_TURN = {'north': 'east', 'east': 'south', 'south': 'west', 'west': 'north'}


def turn_facing(facing, turns):
    """A facing after `turns` quarter-turns clockwise (seen from above)."""
    if not facing:
        return facing
    open_mark = facing.endswith('+')                    # an open door keeps its '+'
    base = facing[:-1] if open_mark else facing
    for _ in range(turns % 4):
        if base in _TURN:
            base = _TURN[base]
        elif base == 'x':
            base = 'z'
        elif base == 'z':
            base = 'x'
    return base + ('+' if open_mark else '')


def mirror_facing(facing, axis):
    if not facing:
        return facing
    open_mark = facing.endswith('+')
    base = facing[:-1] if open_mark else facing
    flips = {'x': {'east': 'west', 'west': 'east'}, 'z': {'north': 'south', 'south': 'north'}}
    base = flips.get(axis, {}).get(base, base)
    return base + ('+' if open_mark else '')


# ---- generators: each returns {(x, y, z): block name} relative to (0, 0, 0) and {(x,y,z): facing} -----------------

def tree_blocks(kind='oak', height=None, rng=None):
    import random
    rng = rng or random
    from blocks import BLOCKS
    kind = kind if kind in ('oak', 'birch', 'spruce', 'jungle') or f'{kind}_log' in BLOCKS else 'oak'
    log, leaves = f'{kind}_log', f'{kind}_leaves'
    height = height or {'oak': 5, 'birch': 6, 'spruce': 8, 'jungle': 9}.get(kind, 5)
    out = {(0, y, 0): log for y in range(height)}
    if kind == 'spruce':                               # a cone
        for layer, y in enumerate(range(height - 1, 1, -1)):
            radius = min(3, 1 + (layer // 2))
            if layer == 0:
                radius = 0
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) + abs(dz) <= radius + 1 and (dx, dz) != (0, 0):
                        out[(dx, y, dz)] = leaves
        out[(0, height, 0)] = leaves
    else:                                              # a round crown
        for y, radius in ((height - 2, 2), (height - 1, 2), (height, 1), (height + 1, 1)):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) == radius and abs(dz) == radius and radius == 2 and rng.random() < 0.5:
                        continue
                    if (dx, dz) != (0, 0) or y >= height:
                        out[(dx, y, dz)] = leaves
    return out, {}


def house_blocks(width=7, depth=7, height=4, walls='oak_planks', roof='oak_planks', floor='cobblestone', door_side='north'):
    """A little house. The door is on the `door_side`; windows on the other sides."""
    out, facing = {}, {}
    for x in range(width):
        for z in range(depth):
            out[(x, 0, z)] = floor
    posts = {(0, 0), (width - 1, 0), (0, depth - 1), (width - 1, depth - 1)}
    for x in range(width):
        for z in range(depth):
            edge = x in (0, width - 1) or z in (0, depth - 1)
            if not edge:
                continue
            for y in range(1, height + 1):
                out[(x, y, z)] = walls
    for (x, z) in posts:
        for y in range(1, height + 1):
            out[(x, y, z)] = 'oak_log'
    # roof: steps getting smaller
    layers = (min(width, depth) + 1) // 2
    for i in range(layers):
        y = height + 1 + i
        for x in range(i - 1 if i == 0 else i, width - i + (1 if i == 0 else 0)):
            for z in range(i - 1 if i == 0 else i, depth - i + (1 if i == 0 else 0)):
                out[(x, y, z)] = roof
    # door and windows
    mid_x, mid_z = width // 2, depth // 2
    door = {'south': (mid_x, depth - 1), 'north': (mid_x, 0), 'west': (0, mid_z), 'east': (width - 1, mid_z)}[door_side]
    out[(door[0], 1, door[1])] = 'oak_door_b'
    out[(door[0], 2, door[1])] = 'oak_door_t'
    facing[(door[0], 1, door[1])] = facing[(door[0], 2, door[1])] = door_side
    for pos in ((mid_x, 0), (mid_x, depth - 1), (0, mid_z), (width - 1, mid_z)):
        if pos != door:
            out[(pos[0], 2, pos[1])] = 'glass_pane'
    out[(1, 1, 1)] = 'torch'
    return out, facing


def maze_cells(cols, rows, rng):
    """A random maze (recursive backtracker): a grid of (2 * cols + 1) x (2 * rows + 1) where True is wall."""
    width, depth = 2 * cols + 1, 2 * rows + 1
    wall = [[True] * depth for _ in range(width)]
    stack = [(0, 0)]
    wall[1][1] = False
    visited = {(0, 0)}
    while stack:
        cx, cz = stack[-1]
        options = [(cx + dx, cz + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= cx + dx < cols and 0 <= cz + dz < rows and (cx + dx, cz + dz) not in visited]
        if not options:
            stack.pop()
            continue
        nx, nz = rng.choice(options)
        wall[cx + nx + 1][cz + nz + 1] = False            # knock down the wall between the two cells
        wall[2 * nx + 1][2 * nz + 1] = False
        visited.add((nx, nz))
        stack.append((nx, nz))
    wall[1][0] = False                                     # an entrance at the front...
    wall[width - 2][depth - 1] = False                     # ...and an exit at the back
    return wall, width, depth


# ---- noise ------------------------------------------------------------------------------------------------------

_perlin = {}


def noise(x, z, scale=10.0, seed=0, detail=3):
    """Smooth random numbers from 0 to 1: nearby points give nearby numbers. Use it for hills."""
    from noise_np import Perlin
    if seed not in _perlin:
        _perlin[seed] = Perlin(int(seed) * 7919 + 13)
    value = float(_perlin[seed].layers(x / scale + 0.37, z / scale + 0.37, detail))
    return max(0.0, min(1.0, value * 1.15 + 0.5))


# ---- challenges -------------------------------------------------------------------------------------------------

_NON_SOLID = {'torch', 'ladder', 'redstone_wire', 'redstone_wire_on', 'lever', 'lever_on', 'stone_button', 'nether_portal',
              'sugar_cane', 'dandelion', 'poppy', 'red_mushroom', 'brown_mushroom', 'rail', 'powered_rail', 'fire', 'cobweb',
              'oak_door_b', 'oak_door_t', 'water', 'lava'}
_PLANTS = ('dandelion', 'poppy', 'oak_sapling', 'birch_sapling', 'spruce_sapling', 'red_mushroom', 'brown_mushroom',
           'sugar_cane', 'wheat_0', 'wheat_1', 'wheat_2', 'wheat_3', 'wheat_4', 'wheat_5', 'wheat_6', 'wheat_7', 'nether_wart_3')


def _solid(blocks_dict, pos):
    name = blocks_dict.get(pos)
    return name is not None and name not in _NON_SOLID and not name.endswith(('_pane',))


def check_house(blocks_dict, plot):
    problems = []
    solid = {p for p in blocks_dict if _solid(blocks_dict, p)}
    enclosed = 0
    xs, ys, zs = plot
    for x in range(xs):
        for z in range(zs):
            for y in range(1, ys - 2):
                p = (x, y, z)
                if p in solid or (x, y - 1, z) not in solid:
                    continue
                if not any((x, y + dy, z) in solid for dy in range(1, 6)):
                    continue                                 # no roof
                walls = 0
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if any(((x + dx * k, y, z + dz * k) in solid or (x + dx * k, y + 1, z + dz * k) in solid
                            or blocks_dict.get((x + dx * k, y, z + dz * k)) in ('oak_door_b', 'glass_pane')) for k in range(1, 8)):
                        walls += 1
                if walls == 4:
                    enclosed += 1
    if enclosed < 6:
        problems.append('Build a room: a floor, walls on all four sides, and a roof over it (at least 6 blocks of space inside).')
    if not any(n in ('oak_door_b', 'oak_door_t') for n in blocks_dict.values()):
        problems.append("Add a door: placeblock(x, y, z, 'oak_door_b') with 'oak_door_t' on top, or use door().")
    if not any(n in ('glass', 'glass_pane') for n in blocks_dict.values()):
        problems.append('Add a window (glass or glass_pane).')
    return problems


def check_tower(blocks_dict, plot):
    best = 0
    columns = {}
    for (x, y, z), name in blocks_dict.items():
        if name not in _NON_SOLID:
            columns.setdefault((x, z), set()).add(y)
    for ys in columns.values():
        run = 0
        for y in range(0, plot[1]):
            run = run + 1 if y in ys else 0
            best = max(best, run)
    if best < 12:
        return [f'Your tallest column is {best} blocks. Make a tower at least 12 blocks tall.']
    return []


def check_bridge(blocks_dict, plot):
    solid = {p for p in blocks_dict if _solid(blocks_dict, p)}
    best = 0
    for (x, y, z) in solid:
        for dx, dz in ((1, 0), (0, 1)):
            if (x - dx, y, z - dz) in solid:
                continue
            length = 0
            while (x + dx * length, y, z + dz * length) in solid:
                length += 1
            gap = sum(1 for i in range(length) if (x + dx * i, y - 1, z + dz * i) not in solid)
            if length >= 10 and gap >= 4:
                best = max(best, length)
    if not best:
        return ['Build a bridge: a straight path at least 10 blocks long, with empty air under at least 4 of them.']
    return []


def check_garden(blocks_dict, plot):
    problems = []
    if sum(1 for n in blocks_dict.values() if n in _PLANTS) < 8:
        problems.append('Plant at least 8 flowers or plants (dandelion, poppy, saplings, wheat...).')
    if sum(1 for n in blocks_dict.values() if n.endswith('_fence')) < 6:
        problems.append('Put a fence around it: at least 6 fence blocks.')
    if not any(n in ('grass', 'dirt', 'farmland') for n in blocks_dict.values()):
        problems.append('Add some grass or dirt for the plants to grow in.')
    return problems


def check_pyramid(blocks_dict, plot):
    layers = {}
    for (x, y, z), name in blocks_dict.items():
        layers.setdefault(y, set()).add((x, z))
    levels = sorted(layers)
    steps = 0
    for a, b in zip(levels, levels[1:]):
        if b == a + 1 and len(layers[b]) < len(layers[a]) and layers[b] <= {(x, z) for x in range(plot[0]) for z in range(plot[2])}:
            steps += 1
    if steps < 4:
        return ['Build a pyramid: layers that each get smaller as you go up (at least 5 layers).']
    return []


def check_portal(blocks_dict, plot):
    if sum(1 for n in blocks_dict.values() if n == 'nether_portal') < 6:
        return ['Build a portal with at least 6 glowing blocks inside an obsidian frame. (portal() does it for you.)']
    if sum(1 for n in blocks_dict.values() if n == 'obsidian') < 10:
        return ['A portal needs an obsidian frame around it.']
    return []


CHALLENGES = {
    'house': ('Build a house with a door, a window, walls and a roof.', check_house),
    'tower': ('Build a tower at least 12 blocks tall.', check_tower),
    'bridge': ('Build a bridge at least 10 blocks long with open air under it.', check_bridge),
    'garden': ('Make a fenced garden with at least 8 plants.', check_garden),
    'pyramid': ('Build a pyramid with at least 5 layers.', check_pyramid),
    'portal': ('Build a Nether portal.', check_portal),
}


# ---- share codes ---------------------------------------------------------------------------------------------------

CODE_PREFIX = 'PW1:'


def encode_build(data):
    raw = json.dumps(data, separators=(',', ':')).encode()
    return CODE_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode()


def decode_build(code):
    code = ''.join(str(code).split())
    if not code.startswith(CODE_PREFIX):
        raise ValueError('That is not a pycraftWorld share code. (They start with "PW1:".)')
    try:
        return json.loads(zlib.decompress(base64.urlsafe_b64decode(code[len(CODE_PREFIX):])))
    except Exception:
        raise ValueError('That share code is damaged: was it copied completely?') from None


# ---- challenge mode: levels ---------------------------------------------------------------------------------------

def _filled(blocks_dict, cells):
    return [c for c in cells if c not in blocks_dict]


def level_1(b, plot, extra):
    return [] if b.get((3, 0, 3)) == 'gold_block' else ["Put a 'gold_block' at (3, 0, 3) with placeblock(3, 0, 3, 'gold_block')."]


def level_2(b, plot, extra):
    missing = _filled(b, [(x, 0, 0) for x in range(10)])
    return [f'A line of 10 blocks along x at y = 0, z = 0. Missing {len(missing)}; the first gap is at {missing[0]}.'] if missing else []


def level_3(b, plot, extra):
    missing = _filled(b, [(x, y, 0) for x in range(6) for y in range(4)])
    return [f'A wall 6 wide and 4 tall at z = 0 (x 0-5, y 0-3). Missing {len(missing)} blocks, e.g. {missing[0]}.'] if missing else []


def level_4(b, plot, extra):
    problems = check_house(b, plot)
    return [p for p in problems if 'window' not in p]


def level_5(b, plot, extra):
    missing = [(i, i, 0) for i in range(8) if (i, i, 0) not in b]
    return [f'A staircase: step i goes at (i, i, 0) for i from 0 to 7. Missing step {missing[0][0]}.'] if missing else []


def level_6(b, plot, extra):
    cells = [(x, 0, z) for x in range(8) for z in range(8)]
    if _filled(b, cells):
        return ['Cover the 8 x 8 floor (x 0-7, z 0-7, y = 0) with blocks.']
    kinds = {b[c] for c in cells}
    if len(kinds) != 2:
        return [f'Use exactly two different blocks (you used {len(kinds)}).']
    first = b[(0, 0, 0)]
    for (x, y, z) in cells:
        if (b[(x, y, z)] == first) != ((x + z) % 2 == 0):
            return [f'Not a checkerboard: the block at ({x}, 0, {z}) should be {"the same as" if (x + z) % 2 == 0 else "different from"} the corner block.']
    return []


def level_7(b, plot, extra):
    problems = []
    for layer, width in enumerate((7, 5, 3, 1)):
        offset = layer
        cells = [(x + offset, layer, z + offset) for x in range(width) for z in range(width)]
        missing = _filled(b, cells)
        if missing:
            problems.append(f'Layer {layer} (y = {layer}) should be a {width} x {width} square starting at ({offset}, {layer}, {offset}).')
            break
    return problems


def level_8(b, plot, extra):
    problems = []
    for x, height in ((2, 4), (6, 6), (10, 8)):
        column = sum(1 for y in range(height) if (x, y, 2) in b)
        if column < height:
            problems.append(f'The tower at x = {x}, z = 2 should be {height} blocks tall (it is {column}).')
    return problems


def level_9(b, plot, extra):
    cells = list(b)
    if len(cells) < 30:
        return ['Write some words with text(). It needs at least 30 blocks.']
    xs = [c[0] for c in cells]
    if max(xs) - min(xs) < 15:
        return ['Write at least three letters: the writing should be at least 16 blocks wide.']
    return []


def level_10(b, plot, extra):
    levers = [p for p, n in b.items() if n in ('lever', 'lever_on')]
    lamps = [p for p, n in b.items() if n in ('redstone_lamp', 'redstone_lamp_on')]
    wires = {p for p, n in b.items() if n in ('redstone_wire', 'redstone_wire_on')}
    if not levers or not lamps or len(wires) < 3:
        return ['You need a lever, a redstone_lamp and at least 3 redstone dust (wire) between them.']
    steps = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0))
    for lever in levers:
        seen, todo = set(), [lever]
        while todo:
            x, y, z = todo.pop()
            for dx, dy, dz in steps:
                n = (x + dx, y + dy, z + dz)
                if n in lamps and (x, y, z) in wires:
                    return []
                if n in wires and n not in seen:
                    seen.add(n)
                    todo.append(n)
    return ['The lever, wire and lamp must touch in a line: lever next to the wire, the wire leading to the lamp.']


def level_11(b, plot, extra):
    hooks = extra.get('hooks', {})
    if not any(hooks.get(k) for k in ('enter', 'click', 'keys', 'every')):
        return ['Register something that happens: onenter(), onclick(), onkey() or every().']
    for pos in hooks.get('click', ()):
        if pos not in b:
            return [f'You used onclick at {pos} but there is no block there to click. Place one first.']
    return []


def level_12(b, plot, extra):
    problems = []
    if len(b) < 300:
        problems.append(f'A castle is big: at least 300 blocks (you have {len(b)}).')
    kinds = {}
    for n in b.values():
        kinds[n] = kinds.get(n, 0) + 1
    if sum(1 for c in kinds.values() if c >= 40) < 3:
        problems.append('Use at least 3 different building blocks (40 or more of each).')
    if not any(n in ('oak_door_b',) for n in b.values()):
        problems.append('Add a door.')
    if sum(1 for n in b.values() if n == 'torch') < 2:
        problems.append('Add at least 2 torches.')
    problems += [p for p in check_tower(b, plot)]
    return problems


# (title, plot size, what to do, a hint, the checking function, the teacher's solution)
LEVELS = [
    ('First block', (8, 8, 8), "Put a gold block at (3, 0, 3).",
     "placeblock(x, y, z, 'gold_block') puts one block. The numbers are x, y (up!) and z.", level_1,
     "w.placeblock(3, 0, 3, 'gold_block')"),
    ('A line', (12, 8, 12), "Make a line of 10 blocks along x, starting at (0, 0, 0).",
     "line(x1, y1, z1, x2, y2, z2, id) or fill(...) draws many blocks in one go.", level_2,
     "w.line(0, 0, 0, 9, 0, 0, 'stone')"),
    ('A wall', (12, 8, 12), "Build a solid wall 6 blocks wide and 4 tall at z = 0.",
     "fill(0, 0, 0, 5, 3, 0, 'bricks') fills a whole box. Corners are included.", level_3,
     "w.fill(0, 0, 0, 5, 3, 0, 'bricks')"),
    ('A little room', (14, 10, 14), "Build a room with a roof, four walls and a door.",
     "hollowbox(...) makes a room with a roof; then door(x, y, z, 'north') in one of the walls (remove a block there first with removeblock).", level_4,
     "w.hollowbox(2, 0, 2, 8, 4, 8, 'oak_planks')\nw.door(5, 1, 2, 'north')"),
    ('Stairs', (12, 12, 8), "Build a staircase of 8 steps: step i is at (i, i, 0).",
     "Use a loop: for i in range(8): placeblock(i, i, 0, 'cobblestone')", level_5,
     "for i in range(8):\n    w.placeblock(i, i, 0, 'cobblestone')"),
    ('Checkerboard', (10, 6, 10), "Cover the 8 x 8 floor with two blocks in a checkerboard pattern.",
     "Two loops (one for x, one for z). If (x + z) % 2 == 0 use one block, otherwise the other.", level_6,
     "for x in range(8):\n    for z in range(8):\n        w.placeblock(x, 0, z, 'stone' if (x + z) % 2 == 0 else 'white_wool')"),
    ('Pyramid', (12, 8, 12), "Build a pyramid of 4 layers: 7x7, 5x5, 3x3 and 1x1, each centred on the one below.",
     "Layer number i is (7 - 2 * i) wide and starts at (i, i, i). fill() once per layer in a loop.", level_7,
     "for i in range(4):\n    n = 7 - 2 * i\n    w.fill(i, i, i, i + n - 1, i, i + n - 1, 'sandstone')"),
    ('Three towers', (14, 12, 8), "Build three towers at z = 2: at x = 2 (4 tall), x = 6 (6 tall) and x = 10 (8 tall).",
     "Write a function: def tower(x, height): ... then call it three times.", level_8,
     "def tower(x, height):\n    w.fill(x, 0, 2, x, height - 1, 2, 'stone_bricks')\n\ntower(2, 4)\ntower(6, 6)\ntower(10, 8)"),
    ('Your name', (30, 12, 8), "Write words in blocks with text(). At least three letters.",
     "text(x, y, z, 'SAM', 'gold_block') writes block letters. Each letter is 5 wide.", level_9,
     "w.text(1, 1, 1, 'SAM', 'gold_block')"),
    ('Light it up', (12, 6, 12), "Make a lever turn on a lamp: lever, then redstone wire, then redstone_lamp, in a line.",
     "lever(2, 0, 2); wire(3, 0, 2, 6, 0, 2); lamp(7, 0, 2). The wire runs along the ground.", level_10,
     "w.lever(2, 0, 2)\nw.wire(3, 0, 2, 6, 0, 2)\nw.lamp(7, 0, 2)"),
    ('Make something happen', (12, 8, 12), "Make something happen when the player does something: onclick, onenter, onkey or every.",
     "def hello(): w.say('Hi!')   then   w.placeblock(3, 0, 3, 'gold_block')   and   w.onclick(3, 0, 3, hello)", level_11,
     "def hello():\n    w.say('Hi!')\n\nw.placeblock(3, 0, 3, 'gold_block')\nw.onclick(3, 0, 3, hello)"),
    ('Boss level: a castle', (40, 24, 40), "Build a castle: 300+ blocks, 3 materials, a door, 2 torches and a tower 12+ tall.",
     "Break it into functions: tower(), wall(), gate(). house() and hollowbox() save time.", level_12,
     "def tower(x, z):\n    w.fill(x, 0, z, x + 3, 13, z + 3, 'stone_bricks')\n    w.torch(x + 1, 14, z + 1)\n\n"
     "tower(2, 2); tower(30, 2)\nw.fill(6, 0, 2, 29, 5, 3, 'cobblestone')\nw.door(16, 0, 2, 'north')\n"
     "w.fill(6, 6, 2, 29, 6, 3, 'bricks')\nw.torch(10, 6, 2)"),
]


def stars_for(failures):
    return 3 if failures <= 2 else 2 if failures <= 6 else 1


# ---- turning a set of changed blocks into code ---------------------------------------------------------------------

def _runs(sorted_values):
    """[(first, last)] for runs of consecutive whole numbers in an ascending list."""
    out = []
    for value in sorted_values:
        if out and value == out[-1][1] + 1:
            out[-1][1] = value
        else:
            out.append([value, value])
    return [tuple(r) for r in out]


def merge_boxes(cells):
    """Cover a set of (x, y, z) cells with as few boxes as is easy: runs along x, then merged along z, then along y.
    Returns [(x1, y1, z1, x2, y2, z2)]."""
    rows = {}
    for x, y, z in cells:
        rows.setdefault((y, z), []).append(x)
    rects = {}                                       # (y, x1, x2) -> [z, ...]
    for (y, z), xs in rows.items():
        for x1, x2 in _runs(sorted(xs)):
            rects.setdefault((y, x1, x2), []).append(z)
    slabs = {}                                       # (x1, x2, z1, z2) -> [y, ...]
    for (y, x1, x2), zs in rects.items():
        for z1, z2 in _runs(sorted(zs)):
            slabs.setdefault((x1, x2, z1, z2), []).append(y)
    boxes = []
    for (x1, x2, z1, z2), ys in slabs.items():
        for y1, y2 in _runs(sorted(ys)):
            boxes.append((x1, y1, z1, x2, y2, z2))
    return sorted(boxes, key=lambda b: (b[1], b[2], b[0]))


def fill_code(cells, facings=None, plot='w'):
    """Code that makes these changes: `cells` is {(x, y, z): block name, or None for "removed"}; `facings` is
    {(x, y, z): facing}. Returns a list of lines using placeblock and fill."""
    facings = facings or {}
    by_name, singles = {}, []
    for pos, name in cells.items():
        if facings.get(pos):
            singles.append((pos, name, facings[pos]))
        else:
            by_name.setdefault(name or 'air', set()).add(pos)
    lines = []
    for name in sorted(by_name):
        for x1, y1, z1, x2, y2, z2 in merge_boxes(by_name[name]):
            if (x1, y1, z1) == (x2, y2, z2):
                lines.append(f"{plot}.placeblock({x1}, {y1}, {z1}, {name!r})")
            else:
                lines.append(f"{plot}.fill({x1}, {y1}, {z1}, {x2}, {y2}, {z2}, {name!r})")
    for (x, y, z), name, facing in sorted(singles):
        lines.append(f"{plot}.placeblock({x}, {y}, {z}, {(name or 'air')!r}, {facing!r})")
    return lines
