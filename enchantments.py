"""Enchantments: what each one does and which items can have it.

An enchantment is stored on an item stack as a small dictionary: {'efficiency': 3}.
They change how tools mine, how weapons hit, how armor protects and how bows shoot."""
import random

from items import ITEMS

# name: (title, highest level, which kinds of item can have it)
ENCHANTMENTS = {
    'efficiency': ('Efficiency', 5, ('pickaxe', 'axe', 'shovel', 'hoe')),
    'unbreaking': ('Unbreaking', 3, ('pickaxe', 'axe', 'shovel', 'hoe', 'sword', 'bow', 'armor')),
    'fortune': ('Fortune', 3, ('pickaxe', 'axe', 'shovel')),
    'silk_touch': ('Silk Touch', 1, ('pickaxe', 'axe', 'shovel')),
    'sharpness': ('Sharpness', 5, ('sword',)),
    'knockback': ('Knockback', 2, ('sword',)),
    'protection': ('Protection', 4, ('armor',)),
    'power': ('Power', 5, ('bow',)),
}
ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V'}


def category(item):
    """What sort of thing is it? 'pickaxe', 'sword', 'bow', 'armor'... or None if it cannot be enchanted."""
    if item.armor is not None:
        return 'armor'
    if item.tool is not None and item.tool.kind in ('pickaxe', 'axe', 'shovel', 'hoe', 'sword', 'bow'):
        return item.tool.kind
    return None


def level_of(stack, name):
    return stack.enchants.get(name, 0) if stack is not None else 0


def describe(enchants):
    return [f'{ENCHANTMENTS[n][0]} {ROMAN.get(l, l)}' for n, l in enchants.items() if n in ENCHANTMENTS]


def roll(stack, power, rng=None):
    """Pick enchantments for an item. `power` (1-30) says how strong they can get."""
    rng = rng or random
    kind = category(stack.item)
    options = [n for n, (_t, _m, kinds) in ENCHANTMENTS.items() if kind in kinds or (kind == 'armor' and 'armor' in kinds)]
    if not options:
        return {}
    result = {}
    count = 1 + (1 if power >= 12 and rng.random() < 0.6 else 0) + (1 if power >= 22 and rng.random() < 0.4 else 0)
    for _ in range(count):
        name = rng.choice(options)
        if name in result or (name == 'silk_touch' and 'fortune' in result) or (name == 'fortune' and 'silk_touch' in result):
            continue
        top = ENCHANTMENTS[name][1]
        result[name] = max(1, min(top, round(power / 30 * top + rng.uniform(0, 1))))
    return result
