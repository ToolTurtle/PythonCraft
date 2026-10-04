"""Crafting recipes and smelting recipes.

A shaped recipe is a little picture of the crafting grid: each letter stands for
an ingredient (see `key`), and a space is an empty cell. It works anywhere on
the grid, and mirrored. A shapeless recipe just needs the right ingredients."""
from items import ITEMS

LOGS = ('oak_log', 'birch_log', 'spruce_log', 'jungle_log')
PLANKS = ('oak_planks', 'birch_planks', 'spruce_planks', 'jungle_planks')
TAGS = {'#planks': PLANKS, '#logs': LOGS, '#coal': ('coal', 'charcoal')}      # an ingredient starting with # accepts any of these

SHAPED = []        # (rows, key, result, count)
SHAPELESS = []     # (ingredients, result, count)


def shaped(rows, key, result, count=1):
    SHAPED.append((rows, key, result, count))


def shapeless(ingredients, result, count=1):
    SHAPELESS.append((ingredients, result, count))


# ---- wood
for _log, _planks in zip(LOGS, PLANKS):
    shapeless([_log], _planks, 4)
shaped(['P', 'P'], {'P': '#planks'}, 'stick', 4)
shaped(['PP', 'PP'], {'P': '#planks'}, 'crafting_table')

# ---- tools
for _material, _head in (('wooden', '#planks'), ('stone', 'cobblestone'), ('iron', 'iron_ingot'),
                         ('diamond', 'diamond')):
    key = {'M': _head, 'S': 'stick'}
    shaped(['MMM', ' S ', ' S '], key, f'{_material}_pickaxe')
    shaped(['MM', 'MS', ' S'], key, f'{_material}_axe')
    shaped(['M', 'S', 'S'], key, f'{_material}_shovel')
    shaped(['M', 'M', 'S'], key, f'{_material}_sword')
    shaped(['MM', ' S', ' S'], key, f'{_material}_hoe')

# ---- bow and arrows
shaped([' SX', 'S X', ' SX'], {'S': 'stick', 'X': 'string'}, 'bow')
shaped(['F', 'S', 'E'], {'F': 'flint', 'S': 'stick', 'E': 'feather'}, 'arrow', 4)

# ---- armor
for _m, _ingredient in (('leather', 'leather'), ('golden', 'gold_ingot'), ('iron', 'iron_ingot'), ('diamond', 'diamond')):
    shaped(['XXX', 'X X'], {'X': _ingredient}, f'{_m}_helmet')
    shaped(['X X', 'XXX', 'XXX'], {'X': _ingredient}, f'{_m}_chestplate')
    shaped(['XXX', 'X X', 'X X'], {'X': _ingredient}, f'{_m}_leggings')
    shaped(['X X', 'X X'], {'X': _ingredient}, f'{_m}_boots')
shaped(['SSS'], {'S': 'sugar_cane'}, 'paper', 3)
shapeless(['paper', 'paper', 'paper', 'leather'], 'book')
shaped(['BBB', 'XXX', 'BBB'], {'B': '#planks', 'X': 'book'}, 'bookshelf')

# ---- transport
shaped(['I I', 'ISI', 'I I'], {'I': 'iron_ingot', 'S': 'stick'}, 'rail', 16)
shaped(['G G', 'GSG', 'GRG'], {'G': 'gold_ingot', 'S': 'stick', 'R': 'redstone'}, 'powered_rail', 6)
shaped(['I I', 'III'], {'I': 'iron_ingot'}, 'minecart')
shaped(['P P', 'PPP'], {'P': '#planks'}, 'oak_boat')

# ---- redstone
shaped(['R', 'S'], {'R': 'redstone', 'S': 'stick'}, 'redstone_torch')
shaped(['S', 'C'], {'S': 'stick', 'C': 'cobblestone'}, 'lever')
shaped(['S'], {'S': 'stone'}, 'stone_button')
shaped(['SS'], {'S': 'stone'}, 'stone_pressure_plate')
shaped(['PP'], {'P': '#planks'}, 'oak_pressure_plate')
shaped([' R ', 'RGR', ' R '], {'R': 'redstone', 'G': 'glowstone'}, 'redstone_lamp')
shaped(['PPP', 'CIC', 'CRC'], {'P': '#planks', 'C': 'cobblestone', 'I': 'iron_ingot', 'R': 'redstone'}, 'piston')
shapeless(['slime_ball', 'piston'], 'sticky_piston')
shaped(['RRR', 'RRR', 'RRR'], {'R': 'redstone'}, 'redstone_block')
shapeless(['redstone_block'], 'redstone', 9)
shaped(['PPP', 'PRP', 'PPP'], {'P': '#planks', 'R': 'redstone'}, 'note_block')

# ---- enchanting
shaped([' B ', 'DOD', 'OOO'], {'B': 'book', 'D': 'diamond', 'O': 'obsidian'}, 'enchanting_table')

# ---- misc
shaped(['I', 'F'], {'I': 'iron_ingot', 'F': 'flint'}, 'flint_and_steel')
shaped(['W', 'W', 'W'], {'W': 'wheat'}, 'bread')
shaped(['SGS', 'GSG', 'SGS'], {'S': 'sand', 'G': 'gunpowder'}, 'tnt')
shaped(['PPP', 'P P', 'PPP'], {'P': '#planks'}, 'chest')
shaped(['I I', ' I '], {'I': 'iron_ingot'}, 'bucket')

# ---- building blocks
for _slab, _source in (('oak_slab', '#planks'), ('cobblestone_slab', 'cobblestone'), ('stone_slab', 'stone'),
                       ('sandstone_slab', 'sandstone'), ('brick_slab', 'bricks'), ('stone_brick_slab', 'stone_bricks')):
    shaped(['XXX'], {'X': _source}, _slab, 6)
for _stairs, _source in (('oak_stairs', '#planks'), ('cobblestone_stairs', 'cobblestone'), ('brick_stairs', 'bricks'),
                         ('stone_brick_stairs', 'stone_bricks'), ('sandstone_stairs', 'sandstone')):
    shaped(['X  ', 'XX ', 'XXX'], {'X': _source}, _stairs, 4)
shaped(['PSP', 'PSP'], {'P': '#planks', 'S': 'stick'}, 'oak_fence', 3)
shaped(['GGG', 'GGG'], {'G': 'glass'}, 'glass_pane', 16)
shaped(['PP', 'PP', 'PP'], {'P': '#planks'}, 'oak_door', 3)
shaped(['S S', 'SSS', 'S S'], {'S': 'stick'}, 'ladder', 3)
shaped(['SS', 'SS'], {'S': 'string'}, 'white_wool')
shaped(['WWW', 'PPP'], {'W': 'white_wool', 'P': '#planks'}, 'bed')

# ---- blocks
shaped(['C', 'S'], {'C': '#coal', 'S': 'stick'}, 'torch', 4)
shaped(['CCC', 'C C', 'CCC'], {'C': 'cobblestone'}, 'furnace')
shaped(['SS', 'SS'], {'S': 'stone'}, 'stone_bricks', 4)
shaped(['SS', 'SS'], {'S': 'sand'}, 'sandstone')
shaped(['CC', 'CC'], {'C': 'clay_ball'}, 'clay')
for _ingredient, _block in (('lapis_lazuli', 'lapis_block'), ('emerald', 'emerald_block'), ('coal', 'coal_block'), ('iron_ingot', 'iron_block'),
                            ('gold_ingot', 'gold_block'), ('diamond', 'diamond_block')):
    shaped(['III', 'III', 'III'], {'I': _ingredient}, _block)
    shapeless([_block], _ingredient, 9)


def _accepts(requirement, name):
    if requirement is None:
        return name is None
    if name is None:
        return False
    if requirement in TAGS:
        return name in TAGS[requirement]
    return requirement == name


def find(names, width, height):
    """Which recipe fits this grid? `names` is a list (row by row) of item names or None.
    Returns (result_name, count) or None."""
    filled = [(i % width, i // width, n) for i, n in enumerate(names) if n is not None]
    if not filled:
        return None

    # Shapeless: same ingredients in any places
    given = sorted(n for _, _, n in filled)
    for ingredients, result, count in SHAPELESS:
        if len(ingredients) == len(given) and _same_ingredients(ingredients, given):
            return result, count

    # Shaped: cut away the empty edges, then compare with the picture
    x0, x1 = min(f[0] for f in filled), max(f[0] for f in filled)
    y0, y1 = min(f[1] for f in filled), max(f[1] for f in filled)
    cut = [[names[y * width + x] for x in range(x0, x1 + 1)] for y in range(y0, y1 + 1)]
    for rows, key, result, count in SHAPED:
        if len(rows) != len(cut) or len(rows[0]) != len(cut[0]):
            continue
        for flip in (False, True):
            if all(_accepts(key.get(rows[y][x if not flip else len(rows[0]) - 1 - x]), cut[y][x])
                   for y in range(len(rows)) for x in range(len(rows[0]))):
                return result, count
    return None


def _same_ingredients(ingredients, given):
    remaining = list(given)
    for requirement in ingredients:
        for name in remaining:
            if _accepts(requirement, name):
                remaining.remove(name)
                break
        else:
            return False
    return not remaining


# ---- the Nether
shaped(['BB', 'BB'], {'B': 'nether_brick'}, 'nether_bricks')
shaped(['BBB'], {'B': 'nether_bricks'}, 'nether_brick_slab', 6)
shaped(['B  ', 'BB ', 'BBB'], {'B': 'nether_bricks'}, 'nether_brick_stairs', 4)
shaped(['BIB', 'BIB'], {'B': 'nether_bricks', 'I': 'nether_brick'}, 'nether_brick_fence', 6)
shaped(['QQ', 'QQ'], {'Q': 'nether_quartz'}, 'quartz_block')
shaped(['Q', 'Q'], {'Q': 'quartz_block'}, 'chiseled_quartz')
shaped(['Q', 'Q'], {'Q': 'chiseled_quartz'}, 'quartz_pillar', 2)
shaped(['DD', 'DD'], {'D': 'glowstone_dust'}, 'glowstone')
shapeless(['blaze_rod'], 'blaze_powder', 2)
shapeless(['blaze_powder', 'slime_ball'], 'magma_cream')
shapeless(['blaze_powder', 'coal'], 'fire_charge', 3)
shaped(['NNN', 'NNN', 'NNN'], {'N': 'gold_nugget'}, 'gold_ingot')
shapeless(['gold_ingot'], 'gold_nugget', 9)

# ---- smelting: input -> output
SMELTING = {
    'iron_ore': 'iron_ingot',
    'netherrack': 'nether_brick',
    'gold_ore': 'gold_ingot',
    'sand': 'glass',
    'cobblestone': 'stone',
    'clay_ball': 'brick',
    'porkchop': 'cooked_porkchop',
    'beef': 'cooked_beef',
    'chicken': 'cooked_chicken',
    'oak_log': 'charcoal',
    'birch_log': 'charcoal',
    'spruce_log': 'charcoal',
    'jungle_log': 'charcoal',
}
COOK_TIME = 10.0     # seconds per item


def fuel_value(name):
    return ITEMS[name].fuel
