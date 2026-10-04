"""mods - add your own blocks, wood, items, recipes and creatures to PythonCraft.

    import pycraft as pc

    m = pc.mod('my-mod')
    m.addblock('snad', 'snad.png', like='sand')                 # a new block that falls like sand
    m.addwood((150, 60, 120), 'leaves.png', name='plum')        # a whole family: plum_log, plum_planks, plum_leaves...
    m.additem('vine', 'vine.png')

    golem = pc.mob(pc.golem, 'vine_golem')                      # a new creature made from the iron golem
    golem.texture('vine_golem.png').health(60)
    golem.spawncondition(pc.block_placement('vinegolem_spawn.pcschem'))   # build the pattern and it appears

Everything is added the moment you call it. Blocks work in plots (`w.placeblock(0, 0, 0, 'snad')`) and in the full game;
the full game loads every mod file in the `mods/` folder when it starts. See docs/README_mods.md.

This module needs no game window to make blocks and creatures, only to run them."""
import colorsys
import dataclasses
import difflib
import json
import math
import os
import random
import re
import runpy
import sys
import traceback
from pathlib import Path

from PIL import Image

import blocks
import crafting
import items
import mobtypes
import pcplot
import sound

TEXTURE_DIR = Path(__file__).parent / 'assets' / 'textures'
SKINS = TEXTURE_DIR / 'entity'
HERE = Path(__file__).parent

ACTIVE = []              # every Mod that has been made
SPAWN_RULES = []         # [(creature name, condition)] from .spawncondition()
REFRESH_HOOKS = []       # functions to call when a block is added while a game is running (they redraw the world)

_COLORS = {'red': (200, 40, 40), 'orange': (230, 130, 30), 'yellow': (230, 210, 60), 'green': (60, 160, 60),
           'blue': (50, 90, 200), 'purple': (130, 60, 170), 'pink': (230, 130, 180), 'brown': (120, 80, 45),
           'white': (240, 240, 240), 'black': (30, 30, 30), 'gray': (128, 128, 128), 'grey': (128, 128, 128),
           'cyan': (50, 190, 200), 'lime': (130, 220, 60), 'magenta': (200, 50, 180), 'gold': (230, 190, 50)}

_TEXTURE_KEYS = ('all', 'top', 'bottom', 'side', 'front', 'back', 'left', 'right', 'north', 'south', 'east', 'west', 'corner')
_BLOCK_PROPS = ('hardness', 'tool', 'tier', 'light', 'solid', 'transparent', 'translucent', 'gravity', 'drops', 'placeable',
                'sound', 'shape', 'orient')


def parse_color(value):
    """(r, g, b) from a name ('purple'), '#aa3355', a tuple of 0-255 (or of 0-1), or an ursina color."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _COLORS:
            return _COLORS[text]
        if re.fullmatch(r'#?[0-9a-f]{6}', text):
            text = text.lstrip('#')
            return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
        close = difflib.get_close_matches(text, list(_COLORS), n=2)
        raise ValueError(f'I do not know the colour {value!r}.' + (f' Did you mean {" or ".join(close)}?' if close else
                         ' Use a name like "purple", a hex code like "#aa3355", or (red, green, blue) numbers.'))
    if hasattr(value, 'r') and hasattr(value, 'g') and hasattr(value, 'b'):      # an ursina Color (0 to 1)
        return tuple(round(c * 255) for c in (value.r, value.g, value.b))
    try:
        r, g, b = value[:3]
    except (TypeError, ValueError):
        raise ValueError('A colour is a name, "#rrggbb", or three numbers (red, green, blue).') from None
    if all(isinstance(c, float) and 0 <= c <= 1 for c in (r, g, b)):
        return tuple(round(c * 255) for c in (r, g, b))
    return tuple(max(0, min(255, int(c))) for c in (r, g, b))


def _caller_dir():
    """The folder of the file that is calling pycraft (so 'snad.png' means the snad.png next to your program)."""
    frame = sys._getframe(1)
    while frame is not None:
        filename = frame.f_code.co_filename
        if os.path.basename(filename) not in ('mods.py', 'pycraft.py') and not filename.startswith('<'):
            return Path(filename).resolve().parent
        frame = frame.f_back
    return Path.cwd()


def _slug(name, what='name'):
    text = str(name).strip().lower().replace(' ', '_').replace('-', '_')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,40}', text):
        raise ValueError(f'A {what} uses small letters, digits and _ (starting with a letter), like "snad" or "vine_golem". '
                         f'{name!r} will not do.')
    return text


# ---- pictures --------------------------------------------------------------------------------------------------------

def _square(image):
    image = image.convert('RGBA')
    if image.height > image.width:                                 # an animated strip: use the first frame
        image = image.crop((0, 0, image.width, image.width))
    return image


def _recolor(base_name, rgb, brightness=1.0):
    """A copy of a game texture painted in the colour `rgb`: the shading of the picture is kept."""
    image = _square(Image.open(TEXTURE_DIR / f'{base_name}.png'))
    gray = image.convert('L')
    pixels = [gray.getpixel((x, y)) for x in range(image.width) for y in range(image.height) if image.getpixel((x, y))[3] > 0]
    average = (sum(pixels) / len(pixels)) if pixels else 128
    out = image.copy()
    for x in range(image.width):
        for y in range(image.height):
            alpha = image.getpixel((x, y))[3]
            factor = gray.getpixel((x, y)) / max(average, 1) * brightness
            out.putpixel((x, y), tuple(max(0, min(255, int(c * factor))) for c in rgb) + (alpha,))
    return out


class Mod:
    """A set of additions to the game. Make one with pc.mod('name'), then call addblock, addwood, additem, recipe..."""

    def __init__(self, name='mod', folder=None):
        self.name = _slug(name, 'mod name')
        self.folder = Path(folder) if folder else _caller_dir()
        self.blocks, self.items, self.mobs = [], [], []
        ACTIVE.append(self)

    def __repr__(self):
        return f'<Mod {self.name!r}: {len(self.blocks)} blocks, {len(self.items)} items, {len(self.mobs)} creatures>'

    # ---- files -------------------------------------------------------------------------------------------------------

    def _path(self, path, what='picture'):
        """The full path of a file you named. Relative names are looked for next to your program, then where you ran it."""
        if isinstance(path, Image.Image):
            return path
        candidates = [Path(path)] if os.path.isabs(str(path)) else [self.folder / str(path), Path.cwd() / str(path)]
        for candidate in candidates:
            if candidate.is_file():
                try:
                    Image.open(candidate).verify()
                except Exception:
                    raise ValueError(f'The {what} {str(path)!r} is not a picture file I can read (use a .png).') from None
                return candidate
        raise ValueError(f'I cannot find the {what} {str(path)!r}. I looked in {candidates[0].parent}. '
                         f'Put the .png next to your program, or give the whole path.')

    def _faces(self, texture):
        """Turn the texture argument of addblock into {'all': [...]} or {'top': ..., 'side': ..., 'bottom': ...}."""
        if isinstance(texture, dict):
            faces = {}
            for key, value in texture.items():
                if key not in _TEXTURE_KEYS:
                    raise ValueError(f'Unknown side {key!r}. Use: {", ".join(_TEXTURE_KEYS)}.')
                faces[key] = [str(self._path(value)) if not isinstance(value, Image.Image) else value]
            return faces
        if isinstance(texture, (tuple, list)):
            if not 2 <= len(texture) <= 3:
                raise ValueError('Give (top, side) or (top, side, bottom) pictures, or one picture for every side.')
            top, side = texture[0], texture[1]
            bottom = texture[2] if len(texture) == 3 else texture[0]
            return {name: [str(self._path(p)) if not isinstance(p, Image.Image) else p] for name, p in
                    (('top', top), ('side', side), ('bottom', bottom))}
        path = self._path(texture)
        return {'all': [str(path) if not isinstance(path, Image.Image) else path]}

    # ---- blocks -----------------------------------------------------------------------------------------------------------

    def addblock(self, name, texture, like=None, **props):
        """Add a block. `texture` is a picture file (.png) for every side, or (top, side) / (top, side, bottom), or a dict like
        {'top': 'a.png', 'side': 'b.png'}.  like='sand' makes it behave like an existing block (falls like sand...).
        Options: hardness, tool ('pickaxe', 'axe', 'shovel'), tier, light (0-15), solid, transparent, gravity, drops,
        placeable, sound ('stone', 'wood', 'gravel', 'sand', 'grass', 'glass', 'cloth', 'snow'). Returns the name."""
        name = _slug(name, 'block name')
        if name in blocks.BLOCKS or name in items.ITEMS:
            raise ValueError(f'There is already a block or item called {name!r}.')
        for key in props:
            if key not in _BLOCK_PROPS:
                close = difflib.get_close_matches(key, _BLOCK_PROPS, n=2)
                raise ValueError(f'Unknown option {key!r} for a block.' + (f' Did you mean {" or ".join(close)}?' if close else
                                 f' The options are: {", ".join(_BLOCK_PROPS)}.'))
        spec = {'hardness': 1.0, 'fallback': _fallback_color()}
        material = None
        if like is not None:
            if like not in blocks.BLOCKS:
                close = difflib.get_close_matches(str(like), list(blocks.BLOCKS), n=3)
                raise ValueError(f'There is no block called {like!r} to copy.' + (f' Did you mean {", ".join(close)}?' if close else ''))
            spec = {k: v for k, v in blocks.BLOCKS[like].items() if k not in _TEXTURE_KEYS and k != 'placeable'}
            material = sound.MATERIAL.get(like, 'stone')
        spec.update(self._faces(texture))
        material = props.pop('sound', material or 'stone')
        spec.update(props)
        blocks.register_block(name, spec)
        sound.MATERIAL[name] = material
        self.blocks.append(name)
        _refresh()
        return name

    def addwood(self, color, leaves=None, name=None, sapling=True):
        """Add a whole kind of wood from one colour: <name>_log, _planks, _leaves, _sapling, _slab, _stairs and _fence, with
        crafting recipes (a log makes 4 planks; planks make slabs, stairs, fences and tools like oak). The saplings grow into trees.
        `leaves` is a picture for the leaves (without it they look like oak leaves). Returns the name."""
        rgb = parse_color(color)
        wood = _slug(name or f'{self.name}_wood', 'wood name')
        for suffix in ('log', 'planks', 'leaves', 'sapling', 'slab', 'stairs', 'fence'):
            if f'{wood}_{suffix}' in blocks.BLOCKS:
                raise ValueError(f'There is already a wood called {wood!r}.')
        planks = _recolor('oak_planks', rgb)
        bark = _recolor('oak_log', tuple(int(c * 0.6) for c in rgb))
        rings = _recolor('oak_log_top', rgb)
        fallback = _fallback_color(rgb)
        leaf_layers = [str(self._path(leaves, 'leaves picture'))] if leaves is not None else [('oak_leaves', 'foliage')]
        made = [
            (f'{wood}_log', dict(hardness=2.0, tool='axe', orient='axis', top=[rings], bottom=[rings], side=[bark], fallback=fallback), 'wood'),
            (f'{wood}_planks', dict(hardness=2.0, tool='axe', all=[planks], fallback=fallback), 'wood'),
            (f'{wood}_leaves', dict(hardness=0.2, drops=None, all=leaf_layers, transparent=True, fallback=fallback), 'grass'),
            (f'{wood}_slab', dict(hardness=1.5, tool='axe', shape='slab', transparent=True, all=[planks], fallback=fallback), 'wood'),
            (f'{wood}_stairs', dict(hardness=1.5, tool='axe', shape='stairs', orient='horizontal', transparent=True, all=[planks],
                                    fallback=fallback), 'wood'),
            (f'{wood}_fence', dict(hardness=2.0, tool='axe', shape='fence', transparent=True, all=[planks], fallback=fallback), 'wood'),
        ]
        if sapling:
            made.append((f'{wood}_sapling', dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['oak_sapling'],
                                                 plant_on=('grass', 'dirt', 'farmland'), sapling=wood, fallback=fallback), 'grass'))
        for block, spec, material in made:
            blocks.register_block(block, spec)
            sound.MATERIAL[block] = material
            self.blocks.append(block)
        crafting.TAGS['#planks'] = crafting.TAGS['#planks'] + (f'{wood}_planks',)
        crafting.TAGS['#logs'] = crafting.TAGS['#logs'] + (f'{wood}_log',)
        crafting.shapeless([f'{wood}_log'], f'{wood}_planks', 4)
        crafting.shaped(['XXX'], {'X': f'{wood}_planks'}, f'{wood}_slab', 6)
        crafting.shaped(['X  ', 'XX ', 'XXX'], {'X': f'{wood}_planks'}, f'{wood}_stairs', 4)
        crafting.shaped(['PSP', 'PSP'], {'P': f'{wood}_planks', 'S': 'stick'}, f'{wood}_fence', 3)
        crafting.SMELTING[f'{wood}_log'] = 'charcoal'
        _refresh()
        return wood

    # ---- items and recipes ---------------------------------------------------------------------------------------------------

    def additem(self, name, texture, food=0, saturation=0.0, stack=64, fuel=0.0, title=None):
        """Add an item (a material, or food if food > 0) with a picture. Returns the name."""
        name = _slug(name, 'item name')
        if name in items.ITEMS or name in blocks.BLOCKS:
            raise ValueError(f'There is already a block or item called {name!r}.')
        path = self._path(texture, 'item picture')
        icon = path if not isinstance(path, Image.Image) else path
        if isinstance(icon, Image.Image):                           # (an image made in code: keep it as a file in memory)
            raise ValueError('An item picture has to be a .png file.')
        item = items.Item(name, title or name.replace('_', ' ').title(), ('file', str(icon)), max_stack=int(stack), food=int(food),
                          saturation=float(saturation), fuel=float(fuel))
        items.ITEMS[name] = item
        if hasattr(items, 'CREATIVE_ORDER'):
            items.CREATIVE_ORDER.append(name)
        self.items.append(name)
        return name

    def _known(self, name):
        if name in items.ITEMS or name in crafting.TAGS:
            return
        close = difflib.get_close_matches(str(name), list(items.ITEMS), n=3)
        raise ValueError(f'There is no item or block called {name!r}.' + (f' Did you mean {", ".join(close)}?' if close else ''))

    def recipe(self, rows, key, result, count=1):
        """A crafting recipe shaped like a picture of the grid: recipe(['SS', 'SS'], {'S': 'snad'}, 'sandstone')."""
        for ingredient in key.values():
            self._known(ingredient)
        self._known(result)
        crafting.shaped(list(rows), dict(key), result, count)

    def shapeless(self, ingredients, result, count=1):
        """A recipe where only the ingredients matter, not their places: shapeless(['snad', 'vine'], 'snad_block')."""
        for ingredient in ingredients:
            self._known(ingredient)
        self._known(result)
        crafting.shapeless(list(ingredients), result, count)

    def smelt(self, source, result):
        """Cooking in a furnace: smelt('snad', 'glass')."""
        self._known(source)
        self._known(result)
        crafting.SMELTING[source] = result


def _fallback_color(rgb=None):
    from ursina import color
    return color.rgb32(*rgb) if rgb else color.gray


def _refresh():
    for hook in list(REFRESH_HOOKS):
        try:
            hook()
        except Exception:
            traceback.print_exc()


# ---- creatures --------------------------------------------------------------------------------------------------------------

ALIASES = {'golem': 'iron_golem', 'pigman': 'zombie_pigman', 'lava_slime': 'magma_cube', 'cat': 'ocelot', 'dog': 'wolf'}
_mob_counter = [0]


def mob_name_for(base):
    """A creature's real name from an alias like `golem` (or from the name itself)."""
    if isinstance(base, MobBuilder):                # a creature you made: base another on it
        base = base.kind.name
    name = ALIASES.get(base, base)
    if name not in mobtypes.TYPES:
        close = difflib.get_close_matches(str(base), list(mobtypes.TYPES) + list(ALIASES), n=3)
        raise ValueError(f'There is no creature called {base!r} to make yours from.' +
                         (f' Did you mean {", ".join(close)}?' if close else ' pc.moblist() shows them all.'))
    return name


class MobBuilder:
    """A creature you are making: change it with .texture(), .health(), .speed()... (each returns the builder, so they chain)."""

    def __init__(self, base, name=None, folder=None):
        base_name = mob_name_for(base)
        if name is None:
            _mob_counter[0] += 1
            name = f'{base_name}_mod{_mob_counter[0]}'
        name = _slug(name, 'creature name')
        if name in mobtypes.TYPES:
            raise ValueError(f'There is already a creature called {name!r}.')
        source = mobtypes.TYPES[base_name]
        self.kind = dataclasses.replace(source, name=name, title=name.replace('_', ' ').title(), base=source.base,
                                        textures=dict(source.textures), parts=list(source.parts), drops=list(source.drops))
        self.folder = Path(folder) if folder else _caller_dir()
        self._base_skin = source.textures.get('main')
        mobtypes.TYPES[name] = self.kind

    def __repr__(self):
        return f'<creature {self.kind.name!r} made from {self.kind.base!r}>'

    @property
    def name(self):
        return self.kind.name

    def title(self, text):
        """The name people see."""
        self.kind.title = str(text)
        return self

    def texture(self, path):
        """Paint it with your own skin (a .png laid out like the original creature's skin: pycraft.export_skin() makes a copy to paint on)."""
        candidates = [Path(path)] if os.path.isabs(str(path)) else [self.folder / str(path), Path.cwd() / str(path)]
        file = next((c for c in candidates if c.is_file()), None)
        if file is None:
            raise ValueError(f'I cannot find the skin {str(path)!r}. I looked in {candidates[0].parent}.')
        try:
            width, height = Image.open(file).size
        except Exception:
            raise ValueError(f'The skin {str(path)!r} is not a picture file I can read (use a .png).') from None
        if self._base_skin:
            base_w, base_h = Image.open(SKINS / self._base_skin).size
            if (width, height) != (base_w, base_h) and (width % base_w or height * base_w != base_h * width):
                raise ValueError(f'The skin is {width} x {height} but this creature needs {base_w} x {base_h} (or the same shape, '
                                 f'bigger). Start from a copy: pycraft.export_skin({self.kind.base!r}, "skin.png").')
            self.kind.skin_scale = max(1.0, width / base_w) * (self.kind.skin_scale if width == base_w else 1.0)
        self.kind.textures['main'] = str(file)
        return self

    def health(self, points):
        """Hit points (a player's heart is 2 points)."""
        self.kind.health = max(1, int(points))
        return self

    def speed(self, blocks_per_second):
        self.kind.speed = float(blocks_per_second)
        return self

    def attack(self, damage):
        self.kind.attack = float(damage)
        return self

    def scale(self, factor):
        """Make it bigger (2 = twice as big) or smaller (0.5): its body and its hitbox."""
        factor = float(factor)
        if not 0.2 <= factor <= 6:
            raise ValueError('The size can be from 0.2 to 6.')
        self.kind.scale *= factor
        self.kind.width *= factor
        self.kind.height *= factor
        return self

    def drops(self, drops):
        """What it drops: [('vine', 1, 3), ('iron_ingot', 0, 2, 0.5)] (item, least, most, chance)."""
        checked = []
        for entry in drops:
            if len(entry) < 3 or entry[0] not in items.ITEMS:
                close = difflib.get_close_matches(str(entry[0]), list(items.ITEMS), n=3)
                raise ValueError(f'Each drop is (item, least, most): {entry!r} is not. ' +
                                 (f'There is no item {entry[0]!r}. Did you mean {", ".join(close)}?' if entry[0] not in items.ITEMS and close else ''))
            checked.append(tuple(entry))
        self.kind.drops = checked
        return self

    def hostile(self, yes=True):
        """Hostile creatures go after the player (and other creatures defend against them)."""
        self.kind.monster = bool(yes)
        return self

    def fire_immune(self, yes=True):
        self.kind.fire_immune = bool(yes)
        return self

    def sound(self, folder):
        """Use the noises of another creature (a folder in assets/sounds/mob like 'zombie')."""
        self.kind.sound = str(folder)
        return self

    def spawncondition(self, condition):
        """When it appears: pc.block_placement('pattern.pcschem'), pc.near_block('vine_block'), pc.at_night(), pc.on_block('grass'),
        pc.anywhere(). Call it more than once for more ways."""
        if not isinstance(condition, Condition):
            raise ValueError('A spawn condition comes from pc.block_placement(...), pc.near_block(...), pc.at_night(), pc.on_block(...) '
                             'or pc.anywhere().')
        SPAWN_RULES.append((self.kind.name, condition))
        return self


# ---- when a creature appears -------------------------------------------------------------------------------------------------

class Condition:
    natural = False                         # True: the game keeps trying to spawn it near the player


class BlockPlacement(Condition):
    """Build the pattern (from a .pcschem file, a Clip or a Plot) anywhere and the blocks turn into the creature."""

    def __init__(self, source, consume=True, rotate=True):
        self.source, self.consume, self.rotate = source, consume, rotate
        self._rotations = None
        if isinstance(source, (str, os.PathLike)) and not os.path.isabs(str(source)):
            for base in (_caller_dir(), Path.cwd()):                # (the game moves to its own folder, so find the file now)
                if (base / str(source)).is_file():
                    self.source = str(base / str(source))
                    break

    def rotations(self):
        if self._rotations is None:
            cells = load_pattern(self.source)
            if not cells:
                raise ValueError('The spawn pattern has no blocks in it.')
            variants, seen = [], set()
            for turns in range(4 if self.rotate else 1):
                turned = _turn_cells(cells, turns)
                key = frozenset(turned.items())
                if key not in seen:
                    seen.add(key)
                    variants.append(turned)
            self._rotations = variants
        return self._rotations

    def names(self):
        return {name for cells in self.rotations()[:1] for name in cells.values()}

    def find(self, world, pos):
        """If building a block at `pos` completes the pattern, the cells it covers (in world coordinates), else None."""
        block = world.get(pos)
        if block is None:
            return None
        for cells in self.rotations():
            for cell, name in cells.items():
                if name != block:
                    continue
                origin = (pos[0] - cell[0], pos[1] - cell[1], pos[2] - cell[2])
                if all(world.get((origin[0] + dx, origin[1] + dy, origin[2] + dz)) == n for (dx, dy, dz), n in cells.items()):
                    return {(origin[0] + dx, origin[1] + dy, origin[2] + dz): n for (dx, dy, dz), n in cells.items()}
        return None


def _turn_cells(cells, turns):
    out = dict(cells)
    for _ in range(turns):
        turned = {(-dz, dy, dx): name for (dx, dy, dz), name in out.items()}
        low_x = min(p[0] for p in turned)
        low_z = min(p[2] for p in turned)
        out = {(dx - low_x, dy, dz - low_z): name for (dx, dy, dz), name in turned.items()}
    return out


def load_pattern(source):
    """{(dx, dy, dz): block name} from a .pcschem / .pcplot file, a Clip (from copy()) or a Plot."""
    if isinstance(source, dict):
        return dict(source)
    if hasattr(source, 'blocks') and isinstance(source.blocks, dict):               # a Clip: {(dx, dy, dz): (name, facing)}
        return {pos: (value[0] if isinstance(value, tuple) else value) for pos, value in source.blocks.items()}
    if hasattr(source, '_blocks'):                                                  # a Plot
        cells = dict(source._blocks)
    else:
        path = Path(source)
        if not path.is_file():
            alt = Path.cwd() / path
            if not alt.is_file():
                raise ValueError(f'I cannot find the pattern {str(source)!r}. Make one with: w.copy(x1, y1, z1, x2, y2, z2).save("name.pcschem")')
            path = alt
        try:
            data = json.loads(path.read_text())
            if data.get('format') == 'pcschem':
                cells = pcplot.unpack_blocks(data['blocks'])
            else:
                data, warnings = pcplot.read_plot(path, None, None)
                cells = pcplot.unpack_blocks(data['blocks'])
        except (ValueError, KeyError, AttributeError, OSError):
            raise ValueError(f'{str(source)!r} is not a pattern file (make one with Clip.save("name.pcschem")).') from None
        missing = sorted({n for n in cells.values() if n not in blocks.BLOCKS})
        if missing:
            raise ValueError(f'The pattern {path.name} uses blocks that do not exist yet: {", ".join(missing)}. '
                             f'Add them with your mod before using the pattern.')
    cells = {pos: name for pos, name in cells.items() if name != 'air'}
    low = (min(p[0] for p in cells), min(p[1] for p in cells), min(p[2] for p in cells)) if cells else (0, 0, 0)
    return {(x - low[0], y - low[1], z - low[2]): name for (x, y, z), name in cells.items()}


def save_pattern(clip, path):
    """Write a Clip's blocks to a .pcschem file (the shape of a build, used by block_placement)."""
    cells = {pos: (v[0] if isinstance(v, tuple) else v) for pos, v in clip.blocks.items()}
    Path(path).write_text(json.dumps({'format': 'pcschem', 'version': 1, 'blocks': pcplot.pack_blocks(cells)}))
    return str(path)


class NearBlock(Condition):
    natural = True

    def __init__(self, block, radius=6, chance=0.15, limit=3):
        self.blocks = {block} if isinstance(block, str) else set(block)
        self.radius, self.chance, self.limit = int(radius), float(chance), int(limit)

    def accepts(self, runtime, x, y, z):
        world, r = runtime.game.world, self.radius
        return any(world.get((x + dx, y + dy, z + dz)) in self.blocks
                   for dx in range(-r, r + 1) for dy in range(-2, 4) for dz in range(-r, r + 1))


class OnBlock(Condition):
    natural = True

    def __init__(self, block, chance=0.1, limit=3):
        self.blocks = {block} if isinstance(block, str) else set(block)
        self.chance, self.limit = float(chance), int(limit)

    def accepts(self, runtime, x, y, z):
        return runtime.game.world.get((x, y - 1, z)) in self.blocks


class AtNight(Condition):
    natural = True

    def __init__(self, chance=0.15, limit=4):
        self.chance, self.limit = float(chance), int(limit)

    def accepts(self, runtime, x, y, z):
        sky = runtime.game.sky
        return sky is not None and sky.daylight < 0.3


class Anywhere(Condition):
    natural = True

    def __init__(self, chance=0.1, limit=4):
        self.chance, self.limit = float(chance), int(limit)

    def accepts(self, runtime, x, y, z):
        return True


def block_placement(pattern, consume=True, rotate=True):
    """Spawn when blocks are built in the shape of `pattern` (a .pcschem file, a Clip from copy(), or a Plot). consume=False
    leaves the blocks. rotate=False only matches it facing one way."""
    return BlockPlacement(pattern, consume, rotate)


def near_block(block, radius=6, chance=0.15, limit=3):
    """Appears now and then near these blocks (a name or a list), up to `limit` at a time."""
    return NearBlock(block, radius, chance, limit)


def on_block(block, chance=0.1, limit=3):
    """Appears now and then standing on these blocks (a name or a list)."""
    return OnBlock(block, chance, limit)


def at_night(chance=0.15, limit=4):
    """Appears in the dark, like zombies."""
    return AtNight(chance, limit)


def anywhere(chance=0.1, limit=4):
    return Anywhere(chance, limit)


# ---- running it in a game -----------------------------------------------------------------------------------------------------

class ModRuntime:
    """Makes mods work in a running game: watches for patterns being built and spawns creatures near the player."""

    def __init__(self, game, schedule=None):
        self.game = game
        self.schedule = schedule or (lambda function: function())      # how to run something on the game's own thread
        self.on_remove = None                                          # called with the cells a pattern used up
        self.timer = 3.0
        self.placements = [(name, cond) for name, cond in SPAWN_RULES if isinstance(cond, BlockPlacement)]
        self.natural = [(name, cond) for name, cond in SPAWN_RULES if cond.natural]
        game.world.listeners.append(self._changed)
        REFRESH_HOOKS.append(self._on_new_blocks)
        self._scan_start()

    def close(self):
        if self._on_new_blocks in REFRESH_HOOKS:
            REFRESH_HOOKS.remove(self._on_new_blocks)

    def refresh_rules(self):
        """Pick up rules added while the game runs."""
        self.placements = [(name, cond) for name, cond in SPAWN_RULES if isinstance(cond, BlockPlacement)]
        self.natural = [(name, cond) for name, cond in SPAWN_RULES if cond.natural]

    # ---- blocks added while the game is open ---------------------------------------------------------------------------------

    def _on_new_blocks(self):
        self.schedule(self.redraw_all)

    def redraw_all(self):
        """The picture sheet changed: make every chunk again."""
        world = self.game.world
        world.retint()
        for key in list(world.chunk_entities):
            world._build(key)

    # ---- patterns --------------------------------------------------------------------------------------------------------------

    def _scan_start(self):
        """Patterns that are already built when the game starts count too."""
        self.refresh_rules()
        if not self.placements:
            return
        wanted = set()
        for _name, cond in self.placements:
            try:
                wanted |= cond.names()
            except ValueError as error:
                print('Mod problem:', error)
        for pos, kind in list(self.game.world.modified.items()):
            if kind in wanted:
                self._changed(pos)

    def _changed(self, pos):
        self.refresh_rules()
        if not self.placements:
            return
        world = self.game.world
        block = world.get(pos)
        if block is None:
            return
        for kind_name, cond in self.placements:
            try:
                if block not in cond.names():
                    continue
                cells = cond.find(world, pos)
            except ValueError as error:
                print('Mod problem:', error)
                continue
            if cells:
                self._build_creature(kind_name, cond, cells)
                return

    def _build_creature(self, kind_name, cond, cells):
        world, game = self.game.world, self.game
        xs = [p[0] for p in cells]
        zs = [p[2] for p in cells]
        feet = (sum((min(xs), max(xs))) / 2, min(p[1] for p in cells) - 0.5 + 0.05, sum((min(zs), max(zs))) / 2)
        if cond.consume:
            for cell in sorted(cells, key=lambda p: -p[1]):
                world.remove(cell, notify=False)
            if self.on_remove:
                self.on_remove(list(cells))
            for cell in cells:
                for listener in world.listeners:
                    if listener != self._changed:
                        listener(cell)
        game.mobs.add(kind_name, feet, random.uniform(0, 360))
        if game.particles is not None:
            game.particles.emit('stone', feet, 24, speed=3)
        game.sound.play('random/pop', 0.8)

    # ---- spawning near the player -----------------------------------------------------------------------------------------------

    def update(self, dt):
        self.timer -= dt
        if self.timer > 0 or not self.natural:
            return
        self.timer = 3.0
        game = self.game
        player = game.player
        if player.dead:
            return
        for kind_name, cond in self.natural:
            near = sum(1 for m in game.mobs.mobs if m.kind.name == kind_name and math.hypot(m.x - player.x, m.z - player.z) < 48)
            if near >= cond.limit:
                continue
            for _ in range(8):
                angle, distance = random.uniform(0, 2 * math.pi), random.uniform(10, 30)
                x, z = int(player.x + math.cos(angle) * distance), int(player.z + math.sin(angle) * distance)
                if (x >> 4, z >> 4) not in game.world.chunk_entities:
                    continue
                y = game.mobs._find_floor(x, z, int(player.y + 8))
                if y is None or not cond.accepts(self, x, y, z):
                    continue
                if random.random() < cond.chance:
                    game.mobs.add(kind_name, (x + 0.5, y - 0.4, z + 0.5), random.uniform(0, 360))
                break


# ---- the game's own mods folder ----------------------------------------------------------------------------------------------------

def load_folder(folder=None):
    """Run every mod file (*.py, not starting with _ or .) in the mods folder. Returns the names that loaded."""
    folder = Path(folder) if folder else HERE / 'mods'
    loaded = []
    if not folder.is_dir():
        return loaded
    for path in sorted(folder.glob('*.py')):
        if path.name.startswith(('_', '.')):
            continue
        try:
            runpy.run_path(str(path), run_name='__mod__')
            loaded.append(path.stem)
        except Exception as error:                                  # one broken mod must not stop the game
            print(f'Mod {path.name} could not load: {type(error).__name__}: {error}')
    return loaded


def export_skin(creature, path):
    """Copy a creature's skin so you can paint your own: export_skin('iron_golem', 'my_golem.png')."""
    name = mob_name_for(creature)
    file = mobtypes.TYPES[name].textures.get('main')
    if file is None:
        raise ValueError(f'{creature!r} has no skin to copy.')
    source = Path(file) if os.path.isabs(str(file)) else SKINS / file
    Image.open(source).convert('RGBA').save(path)
    return str(path)


def export_texture(block, path):
    """Copy a block's picture so you can paint your own: export_texture('sand', 'snad.png') (16 x 16)."""
    if block not in blocks.BLOCKS:
        close = difflib.get_close_matches(str(block), list(blocks.BLOCKS), n=3)
        raise ValueError(f'There is no block called {block!r}.' + (f' Did you mean {", ".join(close)}?' if close else ''))
    spec = blocks.BLOCKS[block]
    layers = spec.get('all') or spec.get('side') or spec.get('top')
    entry = layers[0] if layers else None
    name = entry if isinstance(entry, str) else (entry[0] if isinstance(entry, tuple) else None)
    if name is None:
        raise ValueError(f'{block!r} has no simple picture to copy.')
    source = Path(name) if os.path.isabs(name) else TEXTURE_DIR / f'{name}.png'
    _square(Image.open(source)).resize((16, 16), Image.NEAREST).save(path)
    return str(path)
