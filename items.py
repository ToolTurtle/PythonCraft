"""Everything you can hold: blocks, tools and materials.

Every placeable block is automatically an item. Tools and materials are listed here."""
from dataclasses import dataclass
from typing import Optional

from blocks import BLOCKS, PLACEABLE


@dataclass(frozen=True)
class Tool:
    kind: str          # 'pickaxe', 'axe', 'shovel' or 'sword'
    tier: int          # 1 wood, 2 stone, 3 iron, 4 diamond
    speed: float       # how many times faster than bare hands it mines the right blocks
    durability: int    # how many blocks it can break
    attack: float      # damage to animals


@dataclass(frozen=True)
class Armor:
    slot: str          # 'helmet', 'chestplate', 'leggings' or 'boots'
    points: int        # how much protection it gives (each point stops 4% of damage)
    durability: int


@dataclass(frozen=True)
class Item:
    name: str
    title: str
    icon: tuple                       # ('block', block_name) or ('file', texture_name)
    max_stack: int = 64
    tool: Optional[Tool] = None
    food: int = 0                     # hunger points restored when eaten (2 = one drumstick)
    saturation: float = 0.0           # how long that food keeps you from getting hungry again
    fuel: float = 0.0                 # seconds it burns in a furnace
    places: Optional[str] = None      # the block it puts down
    armor: Optional[Armor] = None


def _title(name):
    return name.replace('_', ' ').title()


ITEMS = {}


def _add(item):
    ITEMS[item.name] = item


# Blocks
for _name in PLACEABLE:
    fuel = 15.0 if _name.endswith(('_log', '_planks')) or _name in ('crafting_table', 'bookshelf') else 0.0
    if _name == 'coal_block':
        fuel = 800.0
    _add(Item(_name, _title(_name), ('block', _name), fuel=fuel, places=_name))



def register_block_item(name):
    """A block was added by a mod: make the item that places it."""
    if name in ITEMS or not BLOCKS[name].get('placeable', True):
        return
    fuel = 15.0 if name.endswith(('_log', '_planks')) else 0.0
    _add(Item(name, _title(name), ('block', name), fuel=fuel, places=name))
    if 'CREATIVE_ORDER' in globals():
        CREATIVE_ORDER.insert(sum(1 for n in CREATIVE_ORDER if n in BLOCKS), name)


from blocks import ON_REGISTER as _ON_REGISTER
_ON_REGISTER.append(register_block_item)

# Materials
_add(Item('stick', 'Stick', ('file', 'stick'), fuel=5.0))
_add(Item('coal', 'Coal', ('file', 'coal'), fuel=80.0))
_add(Item('charcoal', 'Charcoal', ('file', 'charcoal'), fuel=80.0))
_add(Item('iron_ingot', 'Iron Ingot', ('file', 'iron_ingot')))
_add(Item('gold_ingot', 'Gold Ingot', ('file', 'gold_ingot')))
_add(Item('diamond', 'Diamond', ('file', 'diamond')))
_add(Item('clay_ball', 'Clay Ball', ('file', 'clay_ball')))
_add(Item('brick', 'Brick', ('file', 'brick')))

# Food
_add(Item('porkchop', 'Raw Porkchop', ('file', 'porkchop'), food=3, saturation=1.8))
_add(Item('cooked_porkchop', 'Cooked Porkchop', ('file', 'cooked_porkchop'), food=8, saturation=12.8))
_add(Item('apple', 'Apple', ('file', 'apple'), food=4, saturation=2.4))
_add(Item('bread', 'Bread', ('file', 'bread'), food=5, saturation=6.0))

_add(Item('beef', 'Raw Beef', ('file', 'beef'), food=3, saturation=1.8))
_add(Item('cooked_beef', 'Steak', ('file', 'cooked_beef'), food=8, saturation=12.8))
_add(Item('chicken', 'Raw Chicken', ('file', 'chicken'), food=2, saturation=1.2))
_add(Item('cooked_chicken', 'Cooked Chicken', ('file', 'cooked_chicken'), food=6, saturation=7.2))
_add(Item('rotten_flesh', 'Rotten Flesh', ('file', 'rotten_flesh'), food=4, saturation=0.8))
_add(Item('spider_eye', 'Spider Eye', ('file', 'spider_eye'), food=2, saturation=3.2))
for _name, _title_text in (('leather', 'Leather'), ('bone', 'Bone'), ('arrow', 'Arrow'), ('gunpowder', 'Gunpowder'),
                           ('string', 'String'), ('feather', 'Feather'), ('flint', 'Flint')):
    _add(Item(_name, _title_text, ('file', _name)))
for _name, _title_text in (('wheat', 'Wheat'), ('bucket', 'Bucket'), ('bowl', 'Bowl')):
    _add(Item(_name, _title_text, ('file', _name), max_stack=16 if _name == 'bucket' else 64))
_add(Item('wheat_seeds', 'Wheat Seeds', ('file', 'wheat_seeds'), places='wheat_0'))
_add(Item('oak_door', 'Oak Door', ('file', 'oak_door'), places='oak_door_b'))
_add(Item('water_bucket', 'Water Bucket', ('file', 'water_bucket'), max_stack=1))
_add(Item('lava_bucket', 'Lava Bucket', ('file', 'lava_bucket'), max_stack=1, fuel=1000.0))
_add(Item('flint_and_steel', 'Flint and Steel', ('file', 'flint_and_steel'), max_stack=1, tool=Tool('lighter', 0, 1, 64, 0)))
_add(Item('mushroom_stew', 'Mushroom Stew', ('file', 'mushroom_stew'), max_stack=1, food=6, saturation=7.2))
_add(Item('bow', 'Bow', ('file', 'bow'), max_stack=1, tool=Tool('bow', 0, 1, 385, 0)))

# Tools: material -> (tier, speed, durability)
TOOL_MATERIALS = {
    'wooden': (1, 2, 59),
    'stone': (2, 4, 131),
    'iron': (3, 6, 250),
    'diamond': (4, 8, 1561),
}
for _material, (_tier, _speed, _durability) in TOOL_MATERIALS.items():
    for _kind in ('pickaxe', 'axe', 'shovel', 'sword'):
        _attack = _tier + (3 if _kind == 'sword' else 2 if _kind == 'axe' else 1)
        _name = f'{_material}_{_kind}'
        _add(Item(_name, _title(_name), ('file', _name), max_stack=1,
                  tool=Tool(_kind, _tier, _speed, _durability, _attack),
                  fuel=10.0 if _material == 'wooden' else 0.0))

for _material, (_tier, _speed, _durability) in TOOL_MATERIALS.items():
    _name = f'{_material}_hoe'
    _add(Item(_name, _title(_name), ('file', _name), max_stack=1, tool=Tool('hoe', _tier, _speed, _durability, 1)))

# Armor: material -> (points for helmet, chestplate, leggings, boots) and durability multiplier
ARMOR_MATERIALS = {'leather': ((1, 3, 2, 1), 5), 'golden': ((2, 5, 3, 1), 7), 'iron': ((2, 6, 5, 2), 15),
                   'diamond': ((3, 8, 6, 3), 33)}
ARMOR_BASE = {'helmet': 11, 'chestplate': 16, 'leggings': 15, 'boots': 13}
for _material, (_points, _mult) in ARMOR_MATERIALS.items():
    for _slot, _p in zip(('helmet', 'chestplate', 'leggings', 'boots'), _points):
        _name = f'{_material}_{_slot}'
        _add(Item(_name, _title(_name), ('file', _name), max_stack=1, armor=Armor(_slot, _p, ARMOR_BASE[_slot] * _mult)))
_add(Item('paper', 'Paper', ('file', 'paper')))
_add(Item('emerald', 'Emerald', ('file', 'emerald')))
_add(Item('minecart', 'Minecart', ('file', 'minecart'), max_stack=1))
_add(Item('oak_boat', 'Oak Boat', ('file', 'oak_boat'), max_stack=1))
_add(Item('redstone', 'Redstone Dust', ('file', 'redstone'), places='redstone_wire'))
_add(Item('lapis_lazuli', 'Lapis Lazuli', ('file', 'lapis_lazuli')))
_add(Item('slime_ball', 'Slime Ball', ('file', 'slime_ball')))
_add(Item('book', 'Book', ('file', 'book')))
_add(Item('nether_quartz', 'Nether Quartz', ('file', 'quartz')))
_add(Item('nether_wart', 'Nether Wart', ('file', 'nether_wart'), places='nether_wart_0'))
_add(Item('nether_brick', 'Nether Brick', ('file', 'nether_brick')))
_add(Item('ghast_tear', 'Ghast Tear', ('file', 'ghast_tear')))
_add(Item('magma_cream', 'Magma Cream', ('file', 'magma_cream')))
_add(Item('gold_nugget', 'Gold Nugget', ('file', 'gold_nugget')))
_add(Item('blaze_rod', 'Blaze Rod', ('file', 'blaze_rod'), fuel=120.0))
_add(Item('blaze_powder', 'Blaze Powder', ('file', 'blaze_powder'), fuel=60.0))
_add(Item('fire_charge', 'Fire Charge', ('file', 'fire_charge')))
_add(Item('glowstone_dust', 'Glowstone Dust', ('file', 'glowstone_dust')))

# Items that are in the creative inventory, in a sensible order
CREATIVE_ORDER = (
    [n for n in PLACEABLE]
    + ['stick', 'coal', 'charcoal', 'iron_ingot', 'gold_ingot', 'diamond', 'clay_ball', 'brick',
       'porkchop', 'cooked_porkchop', 'apple', 'bread', 'beef', 'cooked_beef', 'chicken', 'cooked_chicken',
       'rotten_flesh', 'spider_eye', 'wheat', 'wheat_seeds', 'oak_door', 'flint_and_steel', 'bucket', 'water_bucket', 'lava_bucket', 'leather', 'bone', 'arrow', 'gunpowder', 'string', 'feather', 'flint', 'bow']
    + [f'{m}_{k}' for k in ('pickaxe', 'axe', 'shovel', 'sword', 'hoe') for m in TOOL_MATERIALS]
    + [f'{m}_{s}' for m in ('leather', 'golden', 'iron', 'diamond') for s in ('helmet', 'chestplate', 'leggings', 'boots')]
    + ['paper', 'book', 'nether_quartz', 'nether_wart', 'nether_brick', 'ghast_tear', 'magma_cream', 'gold_nugget', 'blaze_rod', 'blaze_powder', 'glowstone_dust', 'emerald', 'lapis_lazuli', 'redstone', 'slime_ball', 'minecart', 'oak_boat']
)


def get(name):
    return ITEMS[name]


def title(name):
    return ITEMS[name].title
