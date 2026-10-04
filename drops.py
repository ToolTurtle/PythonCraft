"""Mining rules: how long a block takes to break, and what it drops."""
import random

from blocks import BLOCKS
from items import ITEMS

MINING_SCALE = 0.6        # 1.0 would be exactly like Minecraft; lower is quicker


def held_tool(stack):
    """The Tool in a stack, or None (bare hands, or holding something that is not a tool)."""
    return stack.item.tool if stack is not None else None


def can_harvest(kind, stack):
    """Does this tool make the block drop its item? (Stone gives nothing if you punch it.)"""
    needed = BLOCKS[kind].get('tier')
    if needed is None:
        return True
    tool = held_tool(stack)
    return tool is not None and tool.kind == BLOCKS[kind].get('tool') and tool.tier >= needed


def mining_time(kind, stack):
    """Seconds of holding the mouse button to break the block, or None if it can't be broken."""
    spec = BLOCKS[kind]
    hardness = spec.get('hardness')
    if hardness is None:
        return None
    tool = held_tool(stack)
    speed = tool.speed if tool is not None and tool.kind == spec.get('tool') else 1.0
    if speed > 1.0 and stack is not None:
        from enchantments import level_of
        efficiency = level_of(stack, 'efficiency')
        if efficiency:
            speed += efficiency * efficiency + 1
    factor = 1.5 if can_harvest(kind, stack) else 5.0
    return hardness * factor / speed * MINING_SCALE


def drops_for(kind, stack):
    """A list of (item_name, count) the block drops when broken with this tool."""
    spec = BLOCKS[kind]
    if not can_harvest(kind, stack):
        return []
    from enchantments import level_of
    if stack is not None and level_of(stack, 'silk_touch') and kind in ITEMS and not kind.startswith('wheat_'):
        return [(kind, 1)]                         # Silk Touch: the block itself
    fortune = level_of(stack, 'fortune') if stack is not None else 0
    result = []
    if kind.startswith('wheat_'):
        return [('wheat', 1), ('wheat_seeds', random.randint(0, 3))] if kind == 'wheat_7' else [('wheat_seeds', 1)]
    if kind.startswith('nether_wart_'):
        return [('nether_wart', random.randint(2, 4) if kind == 'nether_wart_3' else 1)]
    if kind == 'glowstone':
        return [('glowstone_dust', random.randint(2, 4))]
    if kind == 'gravel' and random.random() < 0.1:       # now and then gravel gives flint instead
        return [('flint', 1)]
    if kind == 'grass' and random.random() < 0.12:
        result_seed = ('wheat_seeds', 1)
    else:
        result_seed = None
    name = spec.get('drops', kind) if 'drops' in spec else (kind if spec.get('placeable', True) else None)
    if name is not None and name in ITEMS:
        count = 1
        if fortune and name != kind:                  # Fortune: ores can give more
            count = random.randint(1, fortune + 1)
        result.append((name, count))
    if result_seed:
        result.append(result_seed)
    if kind.endswith('_leaves'):
        if random.random() < 0.1:
            result.append(('stick', random.randint(1, 2)))
        if kind == 'oak_leaves' and random.random() < 0.01:
            result.append(('apple', 1))
        if random.random() < 0.06:
            result.append((kind.replace('_leaves', '_sapling'), 1))
    return result
