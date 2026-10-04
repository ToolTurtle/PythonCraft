"""The world: an endless map made of chunks, made on demand from the seed.

Blocks live in per-chunk numpy arrays (one small number per block). A chunk is
generated the first time something needs it. Changes the player makes are
remembered separately (`modified`) and re-applied whenever a chunk is made
again, so nothing is lost when far-away chunks are forgotten."""
import math
import time

from ursina import Entity, color, destroy

import lighting
import numpy as np
import terrain
from blocks import DOOR_IDS, EMIT_TABLE, FLUID_TABLE, REDSTONE_ROLE, ID, NAMES, SOLID_TABLE, TARGET_TABLE, TOP_TABLE
import numpy as _np
from shapes import OPEN_MARK
from chunk import CHUNK, HEIGHT
from chunkmesh import build_chunk_meshes
from shaders import block_shader
from textures import atlas_texture, set_biome, set_tint

# World state that belongs to one dimension. These are swapped in place when you change dimension
# (other parts of the game hold on to the same dictionaries and sets).
PER_DIMENSION = ('chunks', 'wanted', 'build_queue', 'furnaces', 'chests', 'crops', 'flowing', 'dirty', 'spawners',
                 'circuit', 'fires', 'village_queue', 'modified', 'facing', 'changes_by_chunk')


class NetherBiome:
    name = 'Nether Wastes'


NETHER_BIOME = NetherBiome()
BUILD_TIME_PER_FRAME = 0.008   # seconds spent building chunk meshes each frame
FORGET_DISTANCE = 3            # chunks this far beyond the view distance are forgotten


def chunk_of(pos):
    return (pos[0] >> 4, pos[2] >> 4)


class World:
    def __init__(self, biome, seed=None, render_distance=5, modified=None, tints=None, facing=None, flat_spawn=None,
                 dimension='overworld'):
        self.biome = biome                  # the biome whose colors tint grass, leaves and water
        self.seed = seed if seed is not None else int(time.time() * 1000) % 1_000_000
        self.render_distance = render_distance    # in chunks

        self.chunks = {}              # (cx, cz) -> Chunk: the blocks themselves
        self.chunk_entities = {}      # (cx, cz) -> list of Entities showing that chunk
        self.wanted = set()           # chunks that should be shown
        self.build_queue = []         # chunks waiting for their mesh
        self._view_chunk = None
        self.on_retint = []           # functions to call after the tint colors change
        self.furnaces = {}            # (x, y, z) -> Furnace, for every furnace block
        self.chests = {}              # (x, y, z) -> list of 27 stacks, for every chest
        self.crops = set()            # positions of growing wheat
        self.flowing = {}             # (x, y, z) -> level of every flowing (not source) water or lava cell
        self.dirty = set()            # chunks whose picture must be remade
        self.spawners = set()         # positions of monster spawners
        self.circuit = set()          # positions of every redstone part (wire, lever, lamp, piston...)
        self.fires = set()            # positions of every fire block
        self.village_queue = []       # villages seen but not yet populated: (key, villager spots, golem spots)
        self.villages_done = set()    # villages that already got their villagers (saved)
        self.listeners = []           # functions called with a position whenever a block there changes
        self.modified = dict(modified or {})      # (x, y, z) -> block name or None: everything the player changed
        unknown = {kind for kind in self.modified.values() if kind and kind not in ID}
        if unknown:                                # blocks from a mod that is not loaded now
            print('Note: this world has blocks from a mod that is not loaded:', ', '.join(sorted(unknown)), '(they are left out)')
            self.modified = {pos: kind for pos, kind in self.modified.items() if not kind or kind in ID}
        self.facing = dict(facing or {})          # (x, y, z) -> which way an oriented block is turned
        self.changes_by_chunk = {}
        self.crops = {p for p, k in self.modified.items() if k and k.startswith(('wheat_', 'nether_wart_'))}
        self.circuit = {p for p, k in self.modified.items() if k and ID[k] in REDSTONE_ROLE}
        for pos, kind in self.modified.items():
            self.changes_by_chunk.setdefault(chunk_of(pos), {})[pos] = kind

        self.dimension = dimension              # 'overworld' or 'nether'
        self._other_dimensions = {}             # name -> saved per-dimension state (see PER_DIMENSION)

        set_biome(biome)
        for name, rgb in (tints or {}).items():
            set_tint(name, rgb)

        self.flat = flat_spawn is not None          # a flat, empty world (used by the pycraftWorld library)
        self.spawn = flat_spawn if self.flat else terrain.find_spawn(self.seed)
        self._first_view()

    # ---- dimensions --------------------------------------------------------

    @property
    def nether(self):
        return self.dimension == 'nether'

    def _grab_state(self):
        return {key: (list(c) if isinstance(c, list) else c.copy()) for key in PER_DIMENSION for c in (getattr(self, key),)}

    def _put_state(self, state):
        for key in PER_DIMENSION:
            container = getattr(self, key)
            new = state[key]
            if isinstance(container, list):
                container[:] = new
            else:
                container.clear()
                container.update(new)

    @staticmethod
    def _blank_state(modified=None, facing=None, flowing=None):
        modified = dict(modified or {})
        by_chunk = {}
        for pos, kind in modified.items():
            by_chunk.setdefault(chunk_of(pos), {})[pos] = kind
        return {'chunks': {}, 'wanted': set(), 'build_queue': [], 'furnaces': {}, 'chests': {}, 'flowing': dict(flowing or {}),
                'crops': {p for p, k in modified.items() if k and k.startswith(('wheat_', 'nether_wart_'))},
                'dirty': set(), 'spawners': set(), 'fires': set(), 'village_queue': [], 'modified': modified,
                'circuit': {p for p, k in modified.items() if k and ID[k] in REDSTONE_ROLE},
                'facing': dict(facing or {}), 'changes_by_chunk': by_chunk}

    def load_dimension(self, name, modified, facing, flowing, furnaces=None, chests=None):
        """Hand over the saved blocks of a dimension we are not in right now (when a game is loaded)."""
        state = self._blank_state(modified, facing, flowing)
        state['furnaces'].update(furnaces or {})
        state['chests'].update(chests or {})
        if name == self.dimension:
            self._put_state(state)
        else:
            self._other_dimensions[name] = state

    def dimension_data(self):
        """{dimension name: state} for every dimension, the current one included."""
        data = dict(self._other_dimensions)
        data[self.dimension] = self._grab_state()
        return data

    def switch_dimension(self, name):
        """Go to the other dimension: hide this one's land and bring the other one's back."""
        if name == self.dimension:
            return
        for entities in self.chunk_entities.values():
            for entity in entities:
                destroy(entity)
        self.chunk_entities.clear()
        self._other_dimensions[self.dimension] = self._grab_state()
        self.dimension = name
        self._put_state(self._other_dimensions.pop(name, None) or self._blank_state())
        self.build_queue.clear()
        self.wanted.clear()
        self._view_chunk = None

    def _first_view(self):
        """Make the land around the spawn point right away, so the game starts with ground to stand on."""
        self.preload(self.spawn[0], self.spawn[2])

    def preload(self, x, z):
        """Make and draw the land around a point right now."""
        wanted_distance = self.render_distance
        self.render_distance = min(3, wanted_distance)
        self.update_view(x, z)
        self.build_step(budget=float('inf'))
        self.render_distance = wanted_distance
        self._view_chunk = None          # the next frame will start loading the rest

    def spawn_point(self):
        return self.spawn

    # ---- chunks ------------------------------------------------------------

    def chunk_at(self, cx, cz):
        """The chunk at these chunk coordinates, made now if it does not exist yet."""
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            if self.flat:
                chunk = terrain.generate_flat_chunk(self.nether)
                chunk.cx, chunk.cz = cx, cz
            elif self.nether:
                import nether
                chunk = nether.generate_chunk(self.seed, cx, cz)
            else:
                chunk = terrain.generate_chunk(self.seed, cx, cz)
            for (x, y, z), kind in self.changes_by_chunk.get((cx, cz), {}).items():
                if 0 <= y < HEIGHT:
                    chunk.blocks[x & 15, z & 15, y] = ID[kind] if kind else 0
            self.chunks[(cx, cz)] = chunk
            self._after_generate(chunk)
        return chunk

    def _after_generate(self, chunk):
        """A chunk was just made: give its chests something inside, note its spawners, and remember villages."""
        if self.flat:
            return
        import random
        from blocks import ID as _ID
        x0, z0 = chunk.cx * CHUNK, chunk.cz * CHUNK
        for lx, lz, y in zip(*np.nonzero(chunk.blocks == _ID['chest'])):
            pos = (x0 + int(lx), int(y), z0 + int(lz))
            if pos not in self.chests:
                rng = random.Random(f'{self.seed},{pos}')
                village = y > 45
                self.chests[pos] = _nether_loot(rng) if self.nether else _loot(rng, village)
        from furnace import Furnace
        for lx, lz, y in zip(*np.nonzero(chunk.blocks == _ID['furnace'])):
            pos = (x0 + int(lx), int(y), z0 + int(lz))
            self.furnaces.setdefault(pos, Furnace())                 # (villages have furnaces too)
        for lx, lz, y in zip(*np.nonzero(chunk.blocks == _ID['spawner'])):
            self.spawners.add((x0 + int(lx), int(y), z0 + int(lz)))
        if self.nether:
            return
        import structures
        for rx, rz in structures.village_ids_near(self.seed, chunk.cx, chunk.cz):
            key = (rx, rz)
            plan = structures.village_plan(self.seed, rx, rz)
            if plan is not None and key not in self.villages_done and not any(q[0] == key for q in self.village_queue):
                self.village_queue.append((key, plan.villagers, plan.golems))

    def height_at(self, x, z):
        """The height of the land at a spot (before anything was built on it)."""
        chunk = self.chunks.get((x >> 4, z >> 4))
        if chunk is not None:
            return int(chunk.heights[x & 15, z & 15])
        if self.flat:
            return terrain.FLAT_TOP
        if self.nether:
            return 64
        import numpy as np
        return int(terrain.column_info(terrain.generator(self.seed), np.array([x]), np.array([z]))['height'][0])

    def biome_at(self, x, z):
        if self.nether:
            return NETHER_BIOME
        chunk = self.chunks.get((math.floor(x) >> 4, math.floor(z) >> 4))
        if chunk is None:
            return self.biome
        return terrain.BIOMES[chunk.biomes[math.floor(x) & 15, math.floor(z) & 15]]

    # ---- which chunks are shown --------------------------------------------

    def set_render_distance(self, chunks):
        self.render_distance = chunks
        self._view_chunk = None      # forces update_view to look again

    def update_view(self, x, z):
        """Show the chunks near (x, z), hide the far ones. Call every frame."""
        here = (math.floor(x) >> 4, math.floor(z) >> 4)
        if here == self._view_chunk:
            return
        self._view_chunk = here
        r = self.render_distance
        self.wanted = {(here[0] + dx, here[1] + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1)
                       if dx * dx + dz * dz <= r * r}

        for key in list(self.chunk_entities):
            if key not in self.wanted:
                for entity in self.chunk_entities.pop(key):
                    destroy(entity)
        far = r + FORGET_DISTANCE
        for key in list(self.chunks):          # forget far chunks (they can always be made again)
            if abs(key[0] - here[0]) > far or abs(key[1] - here[1]) > far:
                del self.chunks[key]

        def distance(key):
            return (key[0] - here[0]) ** 2 + (key[1] - here[1]) ** 2
        self.build_queue = sorted((k for k in self.wanted if k not in self.chunk_entities), key=distance)

    def build_step(self, budget=BUILD_TIME_PER_FRAME):
        """Make and mesh waiting chunks until the time budget is used. Call every frame."""
        start = time.perf_counter()
        while self.build_queue and time.perf_counter() - start < budget:
            key = self.build_queue.pop(0)
            if key in self.wanted:
                self._build(key)

    def _build(self, key):
        for entity in self.chunk_entities.pop(key, ()):
            destroy(entity)
        solid, water, portal = build_chunk_meshes(self, self.chunk_at(*key))
        entities = []
        if solid is not None:
            entities.append(Entity(model=solid, texture=atlas_texture(), shader=block_shader))
        if water is not None:
            entities.append(Entity(model=water, texture=atlas_texture(), shader=block_shader,
                                   color=color.rgba32(255, 255, 255, 175), double_sided=True))
        if portal is not None:
            entities.append(Entity(model=portal, texture=atlas_texture(), shader=block_shader,
                                   color=color.rgba32(255, 255, 255, 80), double_sided=True))
        self.chunk_entities[key] = entities      # (an empty list still means "built")

    # ---- asking about blocks -------------------------------------------------

    def get(self, pos):
        """The name of the block at pos, or None for air (or a place that has not been made yet)."""
        x, y, z = pos
        if y < 0 or y >= HEIGHT:
            return None
        chunk = self.chunks.get((x >> 4, z >> 4))
        if chunk is None:
            return None
        block = chunk.blocks[x & 15, z & 15, y]
        return NAMES[block] if block else None

    def is_solid(self, pos):
        return self.solid_top(pos) > 0

    def solid_top(self, pos):
        """How much of this cell is solid, from the bottom: 0 = none (air, water, an open door),
        1 = a full block, 0.5 = a slab or stair, and so on."""
        x, y, z = pos
        if y < 0 or y >= HEIGHT:
            return 0.0
        chunk = self.chunks.get((x >> 4, z >> 4))
        if chunk is None:
            return 0.0
        block = chunk.blocks[x & 15, z & 15, y]
        if not SOLID_TABLE[block]:
            return 0.0
        if block in DOOR_IDS and (self.facing.get(pos) or '').endswith(OPEN_MARK):
            return 0.0
        return float(TOP_TABLE[block])

    def light_at(self, pos):
        """(sky light, block light) at a cell, each 0 to 1. (Full sky light where nothing is known.)"""
        x, y, z = pos
        chunk = self.chunks.get((x >> 4, z >> 4))
        if chunk is None or chunk.skylight is None or y < 0 or y >= HEIGHT:
            return 1.0, 0.0
        return chunk.skylight[x & 15, z & 15, y] / 15, chunk.blocklight[x & 15, z & 15, y] / 15

    def _id_at(self, pos):
        x, y, z = pos
        chunk = self.chunks.get((x >> 4, z >> 4))
        if chunk is None or not 0 <= y < HEIGHT:
            return 0
        return int(chunk.blocks[x & 15, z & 15, y])

    def is_targetable(self, pos):
        """Can you point at (and mine) the block here? Solid blocks and torches, but not water or air."""
        x, y, z = pos
        if y < 0 or y >= HEIGHT:
            return False
        chunk = self.chunks.get((x >> 4, z >> 4))
        return chunk is not None and bool(TARGET_TABLE[chunk.blocks[x & 15, z & 15, y]])

    def get_orient(self, pos):
        return self.facing.get(pos)

    # ---- changing blocks -----------------------------------------------------

    def _set(self, pos, kind):
        x, y, z = pos
        self.chunk_at(x >> 4, z >> 4).blocks[x & 15, z & 15, y] = ID[kind] if kind else 0
        self.modified[pos] = kind
        if kind and kind.startswith(('wheat_', 'nether_wart_')):
            self.crops.add(pos)
        else:
            self.crops.discard(pos)
        if kind == 'chest':
            self.chests.setdefault(pos, [None] * 27)         # a chest always has somewhere to keep things
        elif kind == 'furnace' and pos not in self.furnaces:
            from furnace import Furnace
            self.furnaces[pos] = Furnace()
        if kind == 'fire':
            self.fires.add(pos)
        else:
            self.fires.discard(pos)
        if kind and ID[kind] in REDSTONE_ROLE:
            self.circuit.add(pos)
        else:
            self.circuit.discard(pos)
        self.changes_by_chunk.setdefault(chunk_of(pos), {})[pos] = kind

    def _rebuild_around(self, pos, glow=False):
        """After a change, rebuild its chunk and any chunk the changed light could reach."""
        reach = lighting.BLOCK_SPREAD if glow else lighting.SKY_SPREAD
        for cx in range((pos[0] - reach) >> 4, ((pos[0] + reach) >> 4) + 1):
            for cz in range((pos[2] - reach) >> 4, ((pos[2] + reach) >> 4) + 1):
                if (cx, cz) in self.wanted:
                    self._build((cx, cz))

    def place(self, pos, kind, orient=None, notify=True):
        if not 0 <= pos[1] < HEIGHT:
            return
        self.chunk_at(pos[0] >> 4, pos[2] >> 4)
        if self.get(pos) in (None, 'water'):
            self._set(pos, kind)
            if orient:
                self.facing[pos] = orient
            else:
                self.facing.pop(pos, None)
            self._rebuild_around(pos, glow=bool(EMIT_TABLE[ID[kind]]))
            if notify:
                for listener in self.listeners:
                    listener(pos)

    def remove(self, pos, notify=True):
        old = self.get(pos)
        if old is not None:
            self._set(pos, None)
            self.facing.pop(pos, None)
            self._rebuild_around(pos, glow=bool(EMIT_TABLE[ID[old]]))
            if notify:
                for listener in self.listeners:
                    listener(pos)

    def explode(self, center, power=3.0):
        """Blow a round hole in the world. Returns [(position, block name)] for every block destroyed.
        (Bedrock, water and ice-hard things survive. Stronger explosions dig deeper.)"""
        import random
        cx, cy, cz = center
        reach = math.ceil(power)
        destroyed = []
        for x in range(round(cx) - reach, round(cx) + reach + 1):
            for y in range(max(1, round(cy) - reach), min(HEIGHT - 1, round(cy) + reach + 1)):
                for z in range(round(cz) - reach, round(cz) + reach + 1):
                    kind = self.get((x, y, z))
                    if kind is None or kind in ('bedrock', 'water'):
                        continue
                    distance = math.dist((x, y, z), center)
                    if distance > power:
                        continue
                    if random.random() < (1.15 - distance / power) * 1.1:
                        self._set((x, y, z), None)
                        self.facing.pop((x, y, z), None)
                        destroyed.append(((x, y, z), kind))
        reach_blocks = lighting.BLOCK_SPREAD
        chunks = set()
        for (x, y, z), _kind in destroyed:
            for cx_ in range((x - reach_blocks) >> 4, ((x + reach_blocks) >> 4) + 1):
                for cz_ in range((z - reach_blocks) >> 4, ((z + reach_blocks) >> 4) + 1):
                    chunks.add((cx_, cz_))
        for key in chunks:
            if key in self.wanted:
                self._build(key)
        for (pos, _kind) in destroyed:
            for listener in self.listeners:
                listener(pos)
        return destroyed

    def set_fluid(self, pos, kind):
        """Set a cell to a fluid (or air, or obsidian...) quickly: the chunk pictures are remade later in one go."""
        self.chunk_at(pos[0] >> 4, pos[2] >> 4)
        self._set(pos, kind)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                key = ((pos[0] + dx) >> 4, (pos[2] + dz) >> 4)
                if key in self.wanted:
                    self.dirty.add(key)

    def flush_dirty(self, budget=0.006):
        """Remake a few of the chunk pictures that fluids changed."""
        start = time.perf_counter()
        while self.dirty and time.perf_counter() - start < budget:
            self._build(self.dirty.pop())

    def replace(self, pos, kind, orient=None):
        """Change a block to something else (farmland, a growing crop, an opened door) and redraw it."""
        self.chunk_at(pos[0] >> 4, pos[2] >> 4)
        self._set(pos, kind)
        if orient is not None:
            self.facing[pos] = orient
        self._rebuild_around(pos, glow=bool(EMIT_TABLE[ID[kind]]))
        for listener in self.listeners:
            listener(pos)

    def retint(self):
        """Use the newly colored tile sheet on every chunk (after a color change)."""
        texture = atlas_texture()
        for entities in self.chunk_entities.values():
            for entity in entities:
                entity.texture = texture
        for callback in self.on_retint:
            callback()

    # ---- looking along a line --------------------------------------------------

    def raycast(self, origin, direction, reach=6, fluids=False):
        """Walk along a line through the blocks. Returns (block, face_direction, distance)
        for the first solid block hit within `reach`, or None."""
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
            if self.is_targetable(tuple(cell)) or (fluids and FLUID_TABLE[self._id_at(tuple(cell))]):
                normal = [0, 0, 0]
                normal[axis] = -step[axis]
                return tuple(cell), tuple(normal), distance


def _nether_loot(rng):
    """What is inside a chest in a Nether fortress."""
    from inventory import Stack
    from items import ITEMS
    table = [('gold_ingot', 1, 3, 0.6), ('iron_ingot', 1, 4, 0.5), ('diamond', 1, 3, 0.3), ('nether_wart', 3, 7, 0.5),
             ('saddle', 1, 1, 0.1), ('golden_helmet', 1, 1, 0.1), ('iron_sword', 1, 1, 0.1), ('obsidian', 2, 4, 0.2),
             ('flint_and_steel', 1, 1, 0.2), ('gold_nugget', 3, 9, 0.4)]
    slots = [None] * 27
    for name, low, high, chance in table:
        if name in ITEMS and rng.random() < chance:
            slots[rng.randrange(27)] = Stack(name, rng.randint(low, high))
    return slots


def _loot(rng, village):
    """What is inside a freshly generated chest (a list of 27 slots)."""
    from inventory import Stack
    if village:
        table = [('bread', 1, 4, 0.7), ('wheat_seeds', 2, 6, 0.6), ('wheat', 2, 6, 0.5), ('apple', 1, 3, 0.4),
                 ('iron_ingot', 1, 3, 0.45), ('coal', 2, 6, 0.4), ('oak_sapling', 1, 3, 0.3), ('emerald', 1, 2, 0.2),
                 ('gold_ingot', 1, 2, 0.15), ('diamond', 1, 1, 0.05)]
    else:
        table = [('iron_ingot', 1, 4, 0.5), ('gold_ingot', 1, 3, 0.35), ('bone', 2, 6, 0.6), ('gunpowder', 2, 5, 0.5),
                 ('string', 2, 6, 0.5), ('bread', 1, 3, 0.4), ('coal', 3, 8, 0.4), ('redstone', 2, 8, 0.0),
                 ('diamond', 1, 2, 0.12), ('wheat_seeds', 2, 5, 0.3), ('saddle', 1, 1, 0.0)]
    slots = [None] * 27
    from items import ITEMS
    for name, low, high, chance in table:
        if name in ITEMS and rng.random() < chance:
            slots[rng.randrange(27)] = Stack(name, rng.randint(low, high))
    return slots
