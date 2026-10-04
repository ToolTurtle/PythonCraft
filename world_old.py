"""The world: which block is where, and the chunk meshes that show them.

Every block is stored in `data`. To keep the game fast we do NOT make one
object per block. Instead the world is cut into chunks (16x16 columns), and
each chunk becomes a single mesh that only contains the faces you could see."""
import math
import time

from ursina import Entity, color, destroy
from blocks import SOLID
from chunkmesh import build_chunk_meshes
from textures import atlas_texture, set_biome, set_tint
from shaders import block_shader
import terrain

CHUNK = 16
BUILD_TIME_PER_FRAME = 0.008   # seconds spent building chunk meshes each frame


def chunk_of(pos):
    return (pos[0] // CHUNK, pos[2] // CHUNK)


class World:
    def __init__(self, biome, size=128, seed=None, render_distance=4, modified=None, tints=None, facing=None):
        self.biome = biome
        self.size = size
        self.render_distance = render_distance    # in chunks
        self.data = {}            # (x, y, z) -> block name
        self.chunks = {}          # (cx, cz) -> set of block positions in that chunk
        self.chunk_entities = {}  # (cx, cz) -> list of Entities showing that chunk
        self.wanted = set()       # chunks that should be shown
        self.build_queue = []     # chunks waiting for their mesh
        self._view_chunk = None
        self.on_retint = []       # functions to call after the tint colors change
        self.furnaces = {}        # (x, y, z) -> Furnace, for every furnace block
        self.modified = {}        # (x, y, z) -> block name or None: everything the player changed
        self.facing = dict(facing or {})     # (x, y, z) -> which way an oriented block is turned

        set_biome(biome)
        for name, rgb in (tints or {}).items():
            set_tint(name, rgb)
        terrain.generate(self, seed)    # fills data, heights, biome_map and spawn
        for pos, kind in (modified or {}).items():      # a loaded game: redo the player's changes
            if kind is None:
                self.data.pop(pos, None)
            else:
                self.data[pos] = kind
        self.modified = dict(modified or {})
        for pos in self.data:
            self.chunks.setdefault(chunk_of(pos), set()).add(pos)

        self.update_view(self.spawn[0], self.spawn[2])
        self.build_step(budget=float('inf'))    # the first view is built right away

    def spawn_point(self):
        return self.spawn

    def biome_at(self, x, z):
        return self.biome_map.get((round(x), round(z)), self.biome)

    # ---- which chunks are shown ------------------------------------------

    def set_render_distance(self, chunks):
        self.render_distance = chunks
        self._view_chunk = None      # forces update_view to look again

    def update_view(self, x, z):
        """Show the chunks near (x, z), hide the far ones. Call every frame."""
        here = (math.floor((x + .5) / CHUNK), math.floor((z + .5) / CHUNK))
        if here == self._view_chunk:
            return
        self._view_chunk = here

        def distance_squared(chunk):
            return (chunk[0] - here[0]) ** 2 + (chunk[1] - here[1]) ** 2

        self.wanted = {c for c in self.chunks if distance_squared(c) <= self.render_distance ** 2}
        for chunk in list(self.chunk_entities):
            if chunk not in self.wanted:
                for entity in self.chunk_entities.pop(chunk):
                    destroy(entity)
        self.build_queue = sorted(self.wanted - set(self.chunk_entities), key=distance_squared)

    def build_step(self, budget=BUILD_TIME_PER_FRAME):
        """Build waiting chunk meshes until the time budget is used. Call every frame."""
        start = time.perf_counter()
        while self.build_queue and time.perf_counter() - start < budget:
            self._build(self.build_queue.pop(0))

    def _build(self, chunk):
        for entity in self.chunk_entities.pop(chunk, ()):
            destroy(entity)
        solid, water = build_chunk_meshes(self.data, self.chunks.get(chunk, ()), self.facing)
        entities = []
        if solid is not None:
            entities.append(Entity(model=solid, texture=atlas_texture(), shader=block_shader))
        if water is not None:
            entities.append(Entity(model=water, texture=atlas_texture(), shader=block_shader,
                                   color=color.rgba32(255, 255, 255, 175), double_sided=True))
        self.chunk_entities[chunk] = entities      # (an empty list still means "built")

    # ---- changing blocks -------------------------------------------------

    def _rebuild_around(self, pos):
        """After a change, rebuild its chunk (and a neighbor chunk if it is on the edge)."""
        cx, cz = chunk_of(pos)
        affected = {(cx, cz)}
        if pos[0] % CHUNK == 0: affected.add((cx - 1, cz))
        if pos[0] % CHUNK == CHUNK - 1: affected.add((cx + 1, cz))
        if pos[2] % CHUNK == 0: affected.add((cx, cz - 1))
        if pos[2] % CHUNK == CHUNK - 1: affected.add((cx, cz + 1))
        for chunk in affected:
            if chunk in self.wanted:
                self._build(chunk)

    def place(self, pos, kind, orient=None):
        if self.data.get(pos) in (None, 'water'):
            self.data[pos] = kind
            self.modified[pos] = kind
            if orient:
                self.facing[pos] = orient
            else:
                self.facing.pop(pos, None)
            self.chunks.setdefault(chunk_of(pos), set()).add(pos)
            self._rebuild_around(pos)

    def remove(self, pos):
        if self.data.pop(pos, None) is not None:
            self.modified[pos] = None
            self.facing.pop(pos, None)
            self.chunks[chunk_of(pos)].discard(pos)
            self._rebuild_around(pos)

    def retint(self):
        """Use the newly colored tile sheet on every chunk (after a color change)."""
        texture = atlas_texture()
        for entities in self.chunk_entities.values():
            for entity in entities:
                entity.texture = texture
        for callback in self.on_retint:
            callback()

    # ---- asking questions about blocks -----------------------------------

    def get(self, pos):
        return self.data.get(pos)

    def get_orient(self, pos):
        return self.facing.get(pos)

    def is_solid(self, pos):
        return self.data.get(pos) in SOLID

    def raycast(self, origin, direction, reach=6):
        """Walk along a line through the blocks. Returns (block, face_direction, distance)
        for the first block hit within `reach`, or None."""
        cell = [math.floor(c + .5) for c in origin]      # blocks are centered on whole numbers
        step = [1 if d > 0 else -1 for d in direction]
        t_delta = [abs(1 / d) if d else math.inf for d in direction]
        t_max = [((cell[i] + .5 * step[i]) - origin[i]) / direction[i] if direction[i] else math.inf
                 for i in range(3)]
        while True:
            axis = t_max.index(min(t_max))
            distance = t_max[axis]
            if distance > reach:
                return None
            cell[axis] += step[axis]
            t_max[axis] += t_delta[axis]
            if self.is_solid(tuple(cell)):
                normal = [0, 0, 0]
                normal[axis] = -step[axis]
                return tuple(cell), tuple(normal), distance
