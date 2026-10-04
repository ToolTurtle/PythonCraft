"""Blocks that are not full cubes: slabs, stairs, fences, panes, doors, ladders, farmland, torches, plants.

Each shape is a list of small boxes, in block-local coordinates from -0.5 to 0.5.
A box is (x0, y0, z0, x1, y1, z1, texture), where `texture` names which tile of the block to paint on it.
Boxes are painted with the matching part of the block's picture, so a slab shows half a texture."""
from cube import FACES

H = 0.5
OPEN_MARK = '+'          # a door's facing text ends with this when the door is open


def _turn(box, facing):
    """Rotate a box (built facing south, +z) so that it faces `facing`."""
    x0, y0, z0, x1, y1, z1, tex = box
    maps = {'south': lambda x, z: (x, z), 'north': lambda x, z: (-x, -z),
            'east': lambda x, z: (z, -x), 'west': lambda x, z: (-z, x)}
    f = maps[facing]
    (a, b), (c, d) = f(x0, z0), f(x1, z1)
    return (min(a, c), y0, min(b, d), max(a, c), y1, max(b, d), tex)


_HORIZONTAL = ('north', 'south', 'east', 'west')


def _clean(shape, orient):
    """A facing that does not suit the shape is replaced by a sensible one instead of crashing."""
    o = orient or ''
    if shape == 'door':
        base = o.rstrip(OPEN_MARK)
        return (base if base in _HORIZONTAL else 'south') + (OPEN_MARK if o.endswith(OPEN_MARK) else '')
    if shape in ('torch', 'lever', 'button'):
        return o if o in _HORIZONTAL + ('down',) else 'down'
    if shape == 'ladder':
        return o if o in _HORIZONTAL else 'south'
    return o if o in _HORIZONTAL else 'south'


def boxes_for(kind, shape, orient, neighbors):
    """The boxes that make up this block. `neighbors` is a function (dx, dz) -> block name or None."""
    o = _clean(shape, orient)
    if shape == 'slab':
        return [(-H, -H, -H, H, 0.0, H, 'main')]
    if shape == 'rail':
        link = {d: (neighbors(dx, dz) or '').endswith('rail') or (neighbors(dx, dz) or '').endswith('rail_on')
                for d, (dx, dz) in {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}.items()}
        joined = [d for d in 'NESW' if link[d]]
        powered = kind.startswith('powered')
        spin = 0
        tile = 'main'
        if len(joined) >= 2 and not powered and not (link['N'] and link['S']) and not (link['E'] and link['W']):
            tile = 'corner'                                    # a bend joins two sides that are at right angles
            spin = {('E', 'S'): 0, ('S', 'W'): 1, ('W', 'N'): 2, ('N', 'E'): 3}.get(
                next(((a, b) for a, b in (('E', 'S'), ('S', 'W'), ('W', 'N'), ('N', 'E')) if link[a] and link[b]), ('E', 'S')), 0)
        elif (link['E'] or link['W']) and not (link['N'] or link['S']):
            spin = 1                                           # runs east-west
        elif link['E'] and link['W'] and not (link['N'] and link['S']):
            spin = 1
        return [(-H, -H, -H, H, -H + 1 / 16, H, f'{tile}@{spin}')]
    if shape == 'plate':
        return [(-7 / 16, -H, -7 / 16, 7 / 16, -H + 1 / 16, 7 / 16, 'main')]
    if shape == 'button':
        sink = 0 if not o.endswith(OPEN_MARK) else 0
        return [_hang((-3 / 16, -2 / 16, -H + (0.5 / 16), 3 / 16, 2 / 16, -H + 2 / 16, 'main'), o)]
    if shape == 'lever':
        base = _hang((-3 / 16, -2 / 16, -H, 3 / 16, 2 / 16, -H + 3 / 16, 'main'), o)
        stick = _hang((-1 / 16, -1 / 16, -H + 3 / 16, 1 / 16, 1 / 16 + 0.28, -H + 5 / 16, 'main'), o)
        return [base, stick]
    if shape == 'wire':
        arms = []
        y0, y1 = -H, -H + 1 / 16
        for dx, dz, box in ((0, -1, (-1 / 16, -H, -H, 1 / 16, -H + 1 / 16, 0)), (0, 1, (-1 / 16, -H, 0, 1 / 16, -H + 1 / 16, H)),
                            (1, 0, (0, -H, -1 / 16, H, -H + 1 / 16, 1 / 16)), (-1, 0, (-H, -H, -1 / 16, 0, -H + 1 / 16, 1 / 16))):
            other = neighbors(dx, dz)
            if other and (other.startswith(('redstone', 'lever', 'stone_button', 'piston', 'sticky', 'oak_pressure', 'stone_pressure'))
                          or other in ('tnt', 'note_block')):
                arms.append(box + ('main',))
        return [(-2 / 16, y0, -2 / 16, 2 / 16, y1, 2 / 16, 'main')] + arms
    if shape == 'sign':                                      # a post with a board on top, facing `o` (built facing south)
        post = (-1 / 16, -H, -1 / 16, 1 / 16, 0.05, 1 / 16, 'main')
        board = (-7 / 16, 0.05, -1 / 16, 7 / 16, 0.45, 1 / 16, 'main')
        return [post, _turn(board, o)]
    if shape == 'enchtable':
        return [(-H, -H, -H, H, 0.25, H, 'main')]
    if shape == 'farmland':
        return [(-H, -H, -H, H, 0.4375, H, 'main')]
    if shape == 'stairs':
        low = (-H, -H, -H, H, 0.0, H, 'main')
        high = (-H, 0.0, -H, H, H, 0.0, 'main')            # the tall back half (back = north when facing south)
        return [low, _turn(high, o)]
    if shape == 'torch':
        lean = {'down': (0, 0), 'north': (0, 0.4), 'south': (0, -0.4), 'east': (-0.4, 0), 'west': (0.4, 0)}
        ox, oz = lean[o]
        base = -0.5 + (0.1 if o != 'down' else 0)
        return [(ox - 1 / 16, base, oz - 1 / 16, ox + 1 / 16, base + 10 / 16, oz + 1 / 16, 'torch')]
    if shape == 'ladder':                                   # a flat panel against the wall it hangs on
        panel = (-H, -H, -H, H, H, -H + 1 / 16, 'main')     # (built against north)
        return [_turn(panel, {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}[o])]
    if shape == 'door':
        is_open = o.endswith(OPEN_MARK)
        facing = o.rstrip(OPEN_MARK)
        if not is_open:
            panel = (-H, -H, -H, H, H, -H + 3 / 16, 'main')         # closed: across the north side
        else:
            panel = (-H, -H, -H, -H + 3 / 16, H, H, 'main')         # open: swung back along the west side
        return [_turn(panel, facing)]
    if shape in ('fence', 'pane'):
        arms = []
        thin = 1 / 16 if shape == 'pane' else 2 / 16
        post = (-thin, -H, -thin, thin, H, thin, 'main')
        for (dx, dz, box) in ((0, -1, (-thin, -H, -H, thin, H, thin)), (0, 1, (-thin, -H, -thin, thin, H, H)),
                              (1, 0, (-thin, -H, -thin, H, H, thin)), (-1, 0, (-H, -H, -thin, thin, H, thin))):
            other = neighbors(dx, dz)
            if other and (other == kind or other in SOLID_FULL):
                if shape == 'fence':
                    x0, y0, z0, x1, y1, z1 = box
                    arms.append((x0, -0.125, z0, x1, 0.0625, z1, 'main'))
                    arms.append((x0, 0.25, z0, x1, 0.4375, z1, 'main'))
                else:
                    arms.append(box + ('main',))
        return [post] + arms
    return []


def _hang(box, support):
    """Put a box built against the NORTH wall onto the wall (or floor) it really hangs on. `support` is the
    side of the cell the block hangs on ('down' = the floor)."""
    x0, y0, z0, x1, y1, z1, tex = box
    if support == 'down':                         # lying on the floor: a box built on the north wall, tipped onto the floor
        return (x0, z0, y0, x1, z1, y1, tex)         # width stays, depth becomes height, height becomes depth
    return _turn(box, {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}.get(support, 'south'))


SOLID_FULL = set()          # set by blocks at start up: names of ordinary full cubes (fences and panes join to them)


def quads_for(box, tiles, local_light=None):
    """Turn a box into drawable quads: a list of (corners, uvs, normal).
    `tiles` maps the texture name ('main', 'torch'...) to its picture rectangle (u0, v0, u1, v1)."""
    x0, y0, z0, x1, y1, z1, tex = box
    spin = 0
    if '@' in tex:
        tex, spin = tex.split('@')
        spin = int(spin)
    out = []
    for corners, _name, normal in FACES:
        if tex == 'corner':
            tile = tiles.get('corner') or tiles['top']
        elif tex != 'main':
            tile = tiles[tex]
        else:
            tile = tiles['top' if normal[1] > 0 else 'bottom' if normal[1] < 0 else 'side']
        u0, v0, u1, v1 = tile
        pts = []
        for cx, cy, cz in corners:
            pts.append((x0 if cx < 0 else x1, y0 if cy < 0 else y1, z0 if cz < 0 else z1))
        # work out which part of the picture this face covers, from where the box really is
        a, b, c, _d = pts
        def span(p, q, axis):
            return (p[axis], q[axis])
        # direction of picture-u (corner0 -> corner1) and picture-v (corner1 -> corner2)
        du = [i for i in range(3) if abs(b[i] - a[i]) > 1e-9 or abs(corners[1][i] - corners[0][i]) > 1e-9][0]
        dv = [i for i in range(3) if abs(c[i] - b[i]) > 1e-9 or abs(corners[2][i] - corners[1][i]) > 1e-9][0]
        u_positive = corners[1][du] > corners[0][du]
        v_positive = corners[2][dv] > corners[1][dv]
        lo = (x0, y0, z0)
        hi = (x1, y1, z1)
        uvs = []
        for i, p in enumerate(pts):
            su = p[du] + 0.5 if u_positive else 0.5 - p[du]
            sv = p[dv] + 0.5 if v_positive else 0.5 - p[dv]
            uvs.append((u0 + su * (u1 - u0), v0 + sv * (v1 - v0)))
        if spin and normal[1] > 0:                          # turn the picture on the top face by quarter turns
            uvs = uvs[spin:] + uvs[:spin]
        out.append((pts, uvs, normal))
    return out
