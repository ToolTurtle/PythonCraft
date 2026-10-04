"""Turning a chunk's blocks into meshes that hold only the faces you can see.

There are two meshes per chunk: one for normal blocks, one for water (which is
drawn semi-see-through, after everything else)."""
from ursina import Mesh

from blocks import BLOCKS
from cube import FACES
from facing import ORIENT, texture_key
from textures import atlas_uvs

TRANSPARENT = {name for name, spec in BLOCKS.items() if spec.get('transparent')}
TRANSLUCENT = {name for name, spec in BLOCKS.items() if spec.get('translucent')}


def face_is_visible(kind, neighbor):
    """Should we draw a block's face, given the block it touches?"""
    if neighbor is None:
        return True                      # open air
    if neighbor not in TRANSPARENT:
        return False                     # hidden behind a solid block
    return neighbor != kind              # see-through blocks: skip faces between two of the same


class _MeshData:
    def __init__(self):
        self.vertices, self.uvs, self.normals, self.quads = [], [], [], []

    def to_mesh(self):
        if not self.quads:
            return None
        return Mesh(vertices=self.vertices, triangles=self.quads, uvs=self.uvs, normals=self.normals)


def build_chunk_meshes(data, positions, facing=None):
    """`data` maps (x, y, z) to a block name; `positions` are this chunk's blocks;
    `facing` maps (x, y, z) to the way an oriented block (furnace, log...) is turned.
    Returns (solid_mesh, water_mesh); either can be None if it would be empty."""
    uv_table = atlas_uvs()
    facing = facing or {}
    solid, water = _MeshData(), _MeshData()

    for pos in positions:
        kind = data[pos]
        mesh = water if kind in TRANSLUCENT else solid
        x, y, z = pos
        orient = facing.get(pos) if kind in ORIENT else None
        for corners, _face, normal in FACES:
            neighbor = data.get((x + normal[0], y + normal[1], z + normal[2]))
            if not face_is_visible(kind, neighbor):
                continue
            first = len(mesh.vertices)
            for cx, cy, cz in corners:
                mesh.vertices.append((x + cx, y + cy, z + cz))
            key, turns = texture_key(kind, normal, orient)
            u0, v0, u1, v1 = uv_table.get((kind, key)) or uv_table[(kind, 'side')]
            corner_uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            if turns:                                    # a log lying down: turn the bark a quarter
                corner_uvs = corner_uvs[turns:] + corner_uvs[:turns]
            mesh.uvs += corner_uvs
            mesh.normals += [normal] * 4
            mesh.quads.append((first, first + 1, first + 2, first + 3))

    return solid.to_mesh(), water.to_mesh()
