"""Turning a chunk into meshes that hold only the faces you can see.

All the work is done on whole arrays at once (numpy): for each of the six
directions we find every block face that is not hidden by a neighbor, then fill
a vertex buffer straight into Panda3D. There are two meshes per chunk: one for
normal blocks, one for water (which is drawn semi-see-through, after everything else)."""
import numpy as np
from panda3d.core import Geom, GeomEnums, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, NodePath


from blocks import BLOCKS, ID, NAMES, ON_REGISTER, SHAPED_TABLE, SHAPE_OF, TRANSLUCENT_TABLE, TRANSPARENT_TABLE

PORTAL_ID = ID['nether_portal']
from chunk import CHUNK, HEIGHT
from cube import FACES
from facing import ORIENT, texture_key
import lighting
import shapes
from textures import atlas_uvs

_tables = {}
ON_REGISTER.append(lambda name: _tables.clear())            # a block was added: the picture lookup must be made again


def _oriented_ids():
    return np.array([ID[name] for name in ORIENT], dtype=np.int64)


def _lookup_tables():
    """For each direction and block: where its picture is in the atlas."""
    if not _tables:
        uv = atlas_uvs()
        table = np.zeros((6, len(NAMES), 4), dtype=np.float32)
        for d, (_corners, _face, normal) in enumerate(FACES):
            for kind in BLOCKS:
                key, _turns = texture_key(kind, normal, None)
                table[d, ID[kind]] = uv.get((kind, key)) or uv[(kind, 'side')]
        _tables['uv'] = table
        _tables['uv_dict'] = uv
        _tables['corners'] = [np.array(corners, dtype=np.float32) for corners, _f, _n in FACES]
    return _tables


def _neighbor(P, normal):
    """The padded array shifted one block in the direction of `normal`: element by element,
    the block that touches each block's face on that side."""
    nx, ny, nz = normal
    return P[1 + nx:CHUNK + 1 + nx, 1 + nz:CHUNK + 1 + nz, 1 + ny:HEIGHT + 1 + ny]


def build_chunk_meshes(world, chunk):
    """Returns (solid_nodepath, water_nodepath); either can be None if it would be empty."""
    tables = _lookup_tables()
    big = lighting.padded_blocks(world, chunk)                    # this chunk and the ones around it
    sky18, block18 = lighting.compute(big, sky_light=not world.nether)
    chunk.skylight, chunk.blocklight = sky18[1:17, 1:17], block18[1:17, 1:17]
    P = np.zeros((CHUNK + 2, CHUNK + 2, HEIGHT + 2), dtype=np.uint8)           # blocks with a one-block rim
    P[:, :, 1:HEIGHT + 1] = big[lighting.RING - 1:lighting.RING + CHUNK + 1, lighting.RING - 1:lighting.RING + CHUNK + 1]
    P[:, :, 0] = ID['bedrock']          # below the world counts as solid, so the bottom is never drawn
    sky_pad = np.full((CHUNK + 2, CHUNK + 2, HEIGHT + 2), 15, dtype=np.uint8)       # above the world: full sky
    sky_pad[:, :, 0] = 0
    sky_pad[:, :, 1:HEIGHT + 1] = sky18
    block_pad = np.zeros((CHUNK + 2, CHUNK + 2, HEIGHT + 2), dtype=np.uint8)
    block_pad[:, :, 1:HEIGHT + 1] = block18
    cur = P[1:17, 1:17, 1:HEIGHT + 1]
    shaped = SHAPED_TABLE[cur]
    present = (cur != 0) & ~shaped        # (torches and plants are not cubes: they are drawn separately below)
    base = np.array([chunk.cx * CHUNK, 0, chunk.cz * CHUNK], dtype=np.float32)

    parts = {0: ([], [], [], []), 1: ([], [], [], []), 2: ([], [], [], [])}      # translucent? -> (vertices, uvs, normals, lights)
    for d, (_corners, _face, normal) in enumerate(FACES):
        nb = _neighbor(P, normal)
        visible = present & ((nb == 0) | (TRANSPARENT_TABLE[nb] & (nb != cur)))
        sx, sz, sy = np.nonzero(visible)
        if len(sx) == 0:
            continue
        ids = cur[sx, sz, sy]
        rects = tables['uv'][d][ids]                                   # (n, 4): u0 v0 u1 v1
        corner_uvs = np.stack([rects[:, [0, 1]], rects[:, [2, 1]], rects[:, [2, 3]], rects[:, [0, 3]]], axis=1)

        oriented = np.nonzero(np.isin(ids, _oriented_ids()))[0]          # furnaces, logs...: look at which way they face
        for i in oriented:
            pos = (int(sx[i]) + chunk.cx * CHUNK, int(sy[i]), int(sz[i]) + chunk.cz * CHUNK)
            kind = NAMES[ids[i]]
            key, turns = texture_key(kind, normal, world.facing.get(pos))
            u0, v0, u1, v1 = tables['uv_dict'].get((kind, key)) or tables['uv_dict'][(kind, 'side')]
            quad = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            quad = quad[turns:] + quad[:turns]
            corner_uvs[i] = quad

        positions = np.stack([sx, sy, sz], axis=1).astype(np.float32) + base
        vertices = positions[:, None, :] + tables['corners'][d][None, :, :]
        normals = np.broadcast_to(np.array(normal, dtype=np.float32), vertices.shape)
        # Each face is as bright as the air cell it faces
        nx, ny, nz = normal
        face_sky = sky_pad[sx + 1 + nx, sz + 1 + nz, sy + 1 + ny]
        face_block = block_pad[sx + 1 + nx, sz + 1 + nz, sy + 1 + ny]
        lights = np.empty((len(sx), 4, 2), dtype=np.uint8)               # (sky light, block light) per vertex
        lights[:, :, 0] = (face_sky.astype(np.uint16) * 17)[:, None]
        lights[:, :, 1] = (face_block.astype(np.uint16) * 17)[:, None]
        category = np.where(ids == PORTAL_ID, 2, np.where(TRANSLUCENT_TABLE[ids], 1, 0))       # solid, water, portal
        for is_water in (0, 1, 2):
            chosen = category == is_water
            if chosen.any():
                parts[is_water][0].append(vertices[chosen])
                parts[is_water][1].append(corner_uvs[chosen])
                parts[is_water][2].append(normals[chosen])
                parts[is_water][3].append(lights[chosen])

    if shaped.any():
        extra = _shaped_geometry(world, chunk, cur, shaped, sky_pad, block_pad, tables['uv_dict'])
        if extra is not None:
            for slot, array in zip(parts[0], extra):
                slot.append(array)

    return tuple(_make_node(*(np.concatenate(p) for p in parts[w])) if parts[w][0] else None for w in (0, 1, 2))


def _make_node(vertices, uvs, normals, lights):
    """Fill a Panda3D vertex buffer straight from numpy arrays."""
    quads = len(vertices)
    count = quads * 4
    # One record per vertex, laid out exactly as Panda3D wants it: position, normal, packed color, uv.
    # (Ursina runs Panda3D with y pointing up, so positions go in just as they are.)
    record = np.dtype([('position', '<f4', 3), ('normal', '<f4', 3), ('color', 'u1', 4), ('uv', '<f4', 2)])
    data = np.empty(count, dtype=record)
    data['position'] = vertices.reshape(count, 3)
    data['normal'] = normals.reshape(count, 3)
    data['uv'] = uvs.reshape(count, 2)
    # Panda3D keeps packed colors as blue, green, red, alpha. The shader reads red as the sky light
    # and green as the block light.
    flat = lights.reshape(count, 2)
    data['color'] = np.stack([np.zeros(count, np.uint8), flat[:, 1], flat[:, 0], np.full(count, 255, np.uint8)], axis=1)

    vdata = GeomVertexData('chunk', GeomVertexFormat.get_v3n3cpt2(), Geom.UH_static)
    vdata.unclean_set_num_rows(count)
    memoryview(vdata.modify_array(0)).cast('B')[:] = data.tobytes()

    first = np.arange(quads, dtype=np.uint32) * 4
    indices = np.stack([first, first + 1, first + 2, first + 2, first + 3, first], axis=1).ravel()
    triangles = GeomTriangles(Geom.UH_static)
    triangles.set_index_type(GeomEnums.NT_uint32)
    index_data = triangles.modify_vertices()
    index_data.unclean_set_num_rows(len(indices))
    memoryview(index_data).cast('B')[:] = indices.tobytes()

    geom = Geom(vdata)
    geom.add_primitive(triangles)
    node = GeomNode('chunk')
    node.add_geom(geom)
    return NodePath(node)


# ---- blocks that are not cubes (slabs, stairs, fences, doors, ladders, torches, plants) ----

def _tiles_for(uv_dict, kind):
    """The picture rectangles a shaped block can use."""
    def get(face):
        return uv_dict.get((kind, face)) or uv_dict[(kind, 'side')]
    side = get('side')
    tiles = {'top': get('top'), 'bottom': get('bottom'), 'side': side, 'torch': side}
    if (kind, 'corner') in uv_dict:
        tiles['corner'] = uv_dict[(kind, 'corner')]
    return tiles


def _torch_pixels(side):
    """Rectangles for the parts of the torch picture (the stick is only 2 pixels wide)."""
    u0, v0, u1, v1 = side
    px, py = (u1 - u0) / 16, (v1 - v0) / 16
    def rect(left, top, right, bottom):
        return (u0 + left * px, v1 - bottom * py, u0 + right * px, v1 - top * py)
    return {'side': rect(7, 6, 9, 16), 'top': rect(7, 6, 9, 8), 'bottom': rect(7, 14, 9, 16)}


def _shaped_geometry(world, chunk, cur, shaped, sky_pad, block_pad, uv_dict):
    """Vertices for every non-cube block in this chunk. Returns (vertices, uvs, normals, lights)
    arrays like the cube faces, or None."""
    vertices, uvs, normals, lights = [], [], [], []
    for sx, sz, sy in zip(*np.nonzero(shaped)):
        block = int(cur[sx, sz, sy])
        kind = NAMES[block]
        shape = SHAPE_OF[block]
        pos = (int(sx) + chunk.cx * CHUNK, int(sy), int(sz) + chunk.cz * CHUNK)
        sky = int(sky_pad[sx + 1, sz + 1, sy + 1]) * 17          # lit by the cell it stands in
        glow = int(block_pad[sx + 1, sz + 1, sy + 1]) * 17
        tiles = _tiles_for(uv_dict, kind)
        orient = world.facing.get(pos)
        quads = []
        if shape == 'cross':                                     # two diagonal sheets, seen from both sides
            u0, v0, u1, v1 = tiles['side']
            a, b = 0.45, 0.5
            for (x0, z0, x1, z1) in ((-a, -a, a, a), (-a, a, a, -a)):
                for flip in (False, True):
                    corners = [(x0, -b, z0), (x1, -b, z1), (x1, b, z1), (x0, b, z0)]
                    quads.append((corners[::-1] if flip else corners, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], (0, 1, 0)))
        else:
            if shape == 'torch':
                tiles = dict(tiles, **{'torch': tiles['side']})
                pieces = _torch_pixels(tiles['side'])
                tiles = {'top': pieces['top'], 'bottom': pieces['bottom'], 'side': pieces['side'], 'torch': pieces['side']}
            def neighbors(dx, dz, pos=pos):
                return world.get((pos[0] + dx, pos[1], pos[2] + dz))
            for box in shapes.boxes_for(kind, shape, orient, neighbors):
                quads += shapes.quads_for(box, tiles)
                # (quads_for gives corners relative to the block; fixed up below)
        for corners, quv, normal in quads:
            vertices.append([[pos[0] + c[0], pos[1] + c[1], pos[2] + c[2]] for c in corners])
            uvs.append(quv)
            normals.append([normal] * 4)
            lights.append([(sky, glow)] * 4)
    if not vertices:
        return None
    return (np.array(vertices, dtype=np.float32), np.array(uvs, dtype=np.float32),
            np.array(normals, dtype=np.float32), np.array(lights, dtype=np.uint8))


# ---- one single block (for items lying on the ground) -------------------------------

def single_block_mesh(kind):
    """A mesh of one block at the origin, built the plain way (it is tiny)."""
    from ursina import Mesh
    tables = _lookup_tables()
    vertices, uvs, normals, quads = [], [], [], []
    for d, (corners, _face, normal) in enumerate(FACES):
        first = len(vertices)
        vertices += [tuple(c) for c in corners]
        u0, v0, u1, v1 = tables['uv'][d][ID[kind]]
        uvs += [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        normals += [normal] * 4
        quads.append((first, first + 1, first + 2, first + 3))
    return Mesh(vertices=vertices, triangles=quads, uvs=uvs, normals=normals)
