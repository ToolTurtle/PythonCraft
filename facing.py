"""Which way a block faces, and which texture goes on which side.

A block's textures can be given per side in blocks.py:
    top, bottom           up and down
    north, south, east, west   fixed sides of the world  (north is -z, east is +x)
    front, back, left, right   sides RELATIVE to the way the block faces (for orient='horizontal')
    side                  every side you did not name
Blocks with orient='horizontal' (furnace, pumpkin) turn their front toward you when placed.
Blocks with orient='axis' (logs) lie along whichever face you click."""
from blocks import BLOCKS

NAMES = {(0, 1, 0): 'top', (0, -1, 0): 'bottom', (0, 0, -1): 'north', (0, 0, 1): 'south',
         (1, 0, 0): 'east', (-1, 0, 0): 'west'}
DIRECTION = {'up': 'top', 'down': 'bottom', 'north': 'north', 'south': 'south', 'east': 'east', 'west': 'west'}
OPPOSITE6 = {'top': 'bottom', 'bottom': 'top', 'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}
VECTOR = {'up': (0, 1, 0), 'down': (0, -1, 0), 'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0)}
OPPOSITE = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}
RIGHT_OF = {'north': 'east', 'east': 'south', 'south': 'west', 'west': 'north'}
EXTRA_SIDES = ('front', 'back', 'left', 'right', 'north', 'south', 'east', 'west', 'corner')
DEFAULT_FACING = 'south'

ORIENT = {name: spec['orient'] for name, spec in BLOCKS.items() if spec.get('orient')}


def _block_added(name):
    if BLOCKS[name].get('orient'):
        ORIENT[name] = BLOCKS[name]['orient']


from blocks import ON_REGISTER as _ON_REGISTER
_ON_REGISTER.append(_block_added)


def extra_sides(kind):
    """The optional per-side textures a block defines."""
    spec = BLOCKS[kind]
    return [s for s in EXTRA_SIDES if s in spec]


def texture_key(kind, normal, orient):
    """Which tile ('top', 'bottom', 'side', 'front', 'north'...) covers the face of `kind`
    that points along `normal`, when the block is oriented `orient`. Also returns how many
    quarter-turns the picture needs (for logs lying on their side)."""
    spec = BLOCKS[kind]
    world = NAMES[normal]
    kind_of_orient = spec.get('orient')

    if kind_of_orient == 'axis':
        axis = orient if orient in ('x', 'y', 'z') else 'y'          # (a facing that does not fit is ignored)
        ends = {'y': ('top', 'bottom'), 'x': ('east', 'west'), 'z': ('south', 'north')}[axis]
        if world in ends:
            return ('top' if world == ends[0] else 'bottom'), 0
        turns = 0 if axis == 'y' or (axis == 'z' and world in ('top', 'bottom')) else 1
        return 'side', turns

    if kind_of_orient == 'facing6':
        pointing = DIRECTION.get(orient, 'top')
        if world == pointing:
            return ('front' if 'front' in spec else 'side'), 0
        if world == OPPOSITE6[pointing]:
            return ('back' if 'back' in spec else 'side'), 0
        return 'side', 0

    if world in ('top', 'bottom'):
        return world, 0

    if kind_of_orient == 'horizontal':
        facing = orient if orient in OPPOSITE else DEFAULT_FACING
        if world == facing:
            local = 'front'
        elif world == OPPOSITE[facing]:
            local = 'back'
        elif world == RIGHT_OF[facing]:
            local = 'right'
        else:
            local = 'left'
        return (local if local in spec else 'side'), 0

    return (world if world in spec else 'side'), 0


def placement_orient(kind, face, player_position, block_position, look6=None):
    """The orientation a newly placed block should get (or None if it has none)."""
    kind_of_orient = BLOCKS[kind].get('orient')
    if kind_of_orient == 'horizontal':               # the front turns toward the player
        dx = player_position[0] - block_position[0]
        dz = player_position[2] - block_position[2]
        if abs(dx) > abs(dz):
            return 'east' if dx > 0 else 'west'
        return 'south' if dz > 0 else 'north'
    if kind_of_orient == 'facing6':                  # a piston: the front points where you are looking
        return look6
    if kind_of_orient == 'attach':                   # a torch: remember which side it hangs on
        if face[1] < 0:
            return None                                  # you cannot hang one from a ceiling
        return 'down' if face[1] > 0 else NAMES[(-face[0], 0, -face[2])]
    if kind_of_orient == 'axis':                     # lies along the face that was clicked
        if face[0]:
            return 'x'
        if face[2]:
            return 'z'
        return 'y'
    return None


SUPPORT_OFFSET = {'down': (0, -1, 0), 'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0)}


def support_of(position, orient):
    """The block an attached block (torch) hangs on."""
    dx, dy, dz = SUPPORT_OFFSET[orient or 'down']
    return (position[0] + dx, position[1] + dy, position[2] + dz)
