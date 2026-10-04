"""Builds the tile sheet (atlas) with the picture of every block face."""
import math
import os
from pathlib import Path
from PIL import Image, ImageChops
from ursina import Texture

from blocks import BLOCKS

TEXTURE_DIR = Path(__file__).parent / 'assets' / 'textures'
TILE = 16  # pixels per block face

_atlas = None
_tints = {'grass': (255, 255, 255), 'foliage': (255, 255, 255), 'water': (255, 255, 255),
          'birch': (128, 167, 85), 'spruce': (97, 153, 97),
          'rs_off': (110, 0, 0), 'rs_on': (255, 30, 30)}      # birch and spruce leaves never change color


def set_biome(biome):
    """Use the biome's colors to tint the grass and leaves."""
    global _atlas
    _tints.update(biome.tints)
    _atlas = None


def set_tint(name, rgb):
    """Change one tint ('grass' or 'foliage'); textures made afterwards use it."""
    global _atlas
    _tints[name] = tuple(rgb)
    _atlas = None


def get_tint(name):
    return _tints[name]


def reset_atlas():
    """Make the tile sheet again the next time it is needed (a block was added)."""
    global _atlas
    _atlas = None


from blocks import ON_REGISTER as _ON_REGISTER
_ON_REGISTER.append(lambda name: reset_atlas())


def _load_layer(name):
    if isinstance(name, Image.Image):                  # a picture made by a mod
        image = name.convert('RGBA')
    else:
        path = Path(name) if (isinstance(name, Path) or os.path.isabs(str(name))) else TEXTURE_DIR / f'{name}.png'
        if not path.exists():
            return None
        image = Image.open(path).convert('RGBA')
    if image.height > image.width:                     # animated textures are a tall strip: use frame 1
        image = image.crop((0, 0, image.width, image.width))
    return image.resize((TILE, TILE), Image.NEAREST)


def _tint(layer, rgb):
    """Multiply a gray texture by a color, keeping its see-through parts."""
    r, g, b, a = layer.split()
    tinted = ImageChops.multiply(Image.merge('RGB', (r, g, b)), Image.new('RGB', layer.size, rgb))
    return Image.merge('RGBA', (*tinted.split(), a))


def _make_face(layers, fallback):
    """Stack the layers; a missing file is replaced by the fallback color."""
    face = None
    for entry in layers:
        name, tint = entry if isinstance(entry, tuple) else (entry, None)
        layer = _load_layer(name)
        if layer is None:
            layer = Image.new('RGBA', (TILE, TILE), tuple(int(c * 255) for c in fallback))
        elif tint:
            layer = _tint(layer, _tints[tint])
        face = layer if face is None else Image.alpha_composite(face, layer)
    return face


def tile_texture(name):
    """A plain texture of one file, for repeating backgrounds."""
    return Texture(_load_layer(name))


def _face_layers(kind, face):
    spec = BLOCKS[kind]
    if face in spec:
        return spec[face]
    if 'all' in spec:
        return spec['all']
    if 'side' in spec:
        return spec['side']
    return spec.get('front') or spec.get('top')


def _atlas_tiles():
    """Every (block, face) pair that needs a tile, in a fixed order."""
    from facing import extra_sides
    return [(kind, face) for kind in BLOCKS for face in ('top', 'bottom', 'side', *extra_sides(kind))]


def _columns():
    return math.ceil(math.sqrt(len(_atlas_tiles())))


def atlas_uvs():
    """Where each (block, face) lives in the atlas: (u0, v0, u1, v1)."""
    n = _columns()
    inset = 0.01 / (n * TILE)     # stay a hair inside the tile so neighbors don't bleed in
    uvs = {}
    for i, key in enumerate(_atlas_tiles()):
        col, row = i % n, i // n
        # Row 0 is the TOP of the picture, which is v = 1 in texture space.
        uvs[key] = (col / n + inset, 1 - (row + 1) / n + inset,
                    (col + 1) / n - inset, 1 - row / n - inset)
    return uvs


def atlas_texture():
    """One picture holding every block face (a 'tile sheet'). Cached."""
    global _atlas
    if _atlas is None:
        n = _columns()
        sheet = Image.new('RGBA', (n * TILE, n * TILE), (0, 0, 0, 0))
        for i, (kind, face) in enumerate(_atlas_tiles()):
            tile = _make_face(_face_layers(kind, face), BLOCKS[kind]['fallback'])
            sheet.paste(tile, ((i % n) * TILE, (i // n) * TILE))
        _atlas = Texture(sheet)  # pixel-art look: no smoothing by default
    return _atlas


def icon_texture(kind):
    """A small picture of a block for the hotbar (its side, or its top if it has no side)."""
    spec = BLOCKS[kind]
    face = next((f for f in ('front', 'south', 'side') if f in spec), 'side' if 'all' in spec else 'top')
    return Texture(_make_face(_face_layers(kind, face), spec['fallback']))


_item_icons = {}


def item_icon_texture(item):
    """The picture of an item: a block's icon, or the sprite from assets/textures/item."""
    if item.name not in _item_icons:
        kind, name = item.icon
        if kind == 'block':
            _item_icons[item.name] = icon_texture(name)
        else:
            path = Path(name) if os.path.isabs(str(name)) else TEXTURE_DIR / 'item' / f'{name}.png'
            image = Image.open(path).convert('RGBA') if path.exists() else Image.new('RGBA', (TILE, TILE), (255, 0, 255, 255))
            _item_icons[item.name] = Texture(image)
    return _item_icons[item.name]


def refresh_item_icons():
    """Forget block icons (the grass and leaf colors may have changed)."""
    for name in [n for n in _item_icons if _item_icons[n] is not None]:
        del _item_icons[name]
