"""Water and lava that flow.

A fluid cell is either a SOURCE (a bucket's worth, or the sea) or FLOWING with a level.
Water: a source is level 8 and spreads 7 blocks sideways, weaker each step; it always pours down.
Lava: a source is level 4, so it only creeps 3 blocks and flows more slowly.
Every few moments each active cell works out the level it ought to have, from the cell above
and the cells next to it, and changes if needed. Water meeting lava makes obsidian or cobblestone."""
import random

from blocks import BLOCKS, FLUID_TABLE, ID
from chunk import HEIGHT

SOURCE_LEVEL = {'water': 8, 'lava': 4}
TICK = {'water': 0.25, 'lava': 1.2}
MAX_CELLS_PER_TICK = 600
SIDE = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Fluids:
    def __init__(self, world, sound=None):
        self.world, self.sound = world, sound
        self.flowing = world.flowing          # (x, y, z) -> level of every flowing (non-source) fluid cell
        self.active = {'water': set(), 'lava': set()}
        self.timer = {'water': TICK['water'], 'lava': TICK['lava']}
        world.listeners.append(self._changed)

    # ---- what is where ---------------------------------------------------------

    def kind_at(self, pos):
        k = self.world.get(pos)
        return BLOCKS[k].get('fluid') if k else None

    def level_at(self, pos):
        kind = self.kind_at(pos)
        if not kind:
            return 0
        return self.flowing.get(pos, SOURCE_LEVEL[kind])

    def is_source(self, pos):
        return self.kind_at(pos) is not None and pos not in self.flowing

    def _free(self, pos):
        """Can a fluid flow into this cell? (Only empty air, or a plant that water would wash away.)"""
        k = self.world.get(pos)
        return k is None

    # ---- waking cells up --------------------------------------------------------

    def _changed(self, pos):
        """A block changed somewhere: any fluid next to it may need to move."""
        x, y, z = pos
        for dx, dy, dz in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            p = (x + dx, y + dy, z + dz)
            for kind in ('water', 'lava'):
                self.active[kind].add(p)

    def start(self, pos, kind):
        """Pour a source of `kind` at pos."""
        self.flowing.pop(pos, None)
        self.world.set_fluid(pos, kind)
        self._changed(pos)

    def take(self, pos):
        """Scoop up the source at pos (returns the fluid kind or None)."""
        kind = self.kind_at(pos)
        if kind is None or not self.is_source(pos):
            return None
        self.world.set_fluid(pos, None)
        self._changed(pos)
        return kind

    def absorb(self, pos, radius=6, limit=65):
        """A sponge soaks up the water around it (a limited amount, close by)."""
        from collections import deque
        seen, queue, taken = {pos}, deque([(pos, 0)]), 0
        while queue and taken < limit:
            cell, d = queue.popleft()
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (cell[0] + dx, cell[1] + dy, cell[2] + dz)
                if n in seen or d + 1 > radius:
                    continue
                seen.add(n)
                if self.kind_at(n) == 'water':
                    self.flowing.pop(n, None)
                    self.world.set_fluid(n, None)
                    taken += 1
                    queue.append((n, d + 1))
        self.world.flush_dirty(0.05)
        return taken

    # ---- running the flow ----------------------------------------------------------

    def update(self, dt):
        for kind in ('water', 'lava'):
            self.timer[kind] -= dt
            if self.timer[kind] <= 0:
                self.timer[kind] = TICK[kind]
                self._tick(kind)
        self.world.flush_dirty()

    def _tick(self, kind):
        cells = list(self.active[kind])[:MAX_CELLS_PER_TICK]
        for pos in cells:
            self.active[kind].discard(pos)
        for pos in cells:
            if (pos[0] >> 4, pos[2] >> 4) not in self.world.chunks or not 0 <= pos[1] < HEIGHT:
                continue
            self._update_cell(pos, kind)

    def _update_cell(self, pos, kind):
        x, y, z = pos
        here = self.kind_at(pos)
        if here is not None and here != kind:
            return
        if here is not None and self.is_source(pos):
            self._react(pos, kind)
            self._spread_from(pos, kind)
            return
        if here is None and not self._free(pos):
            return

        full = SOURCE_LEVEL[kind]
        up = (x, y + 1, z)
        wanted = full if self.kind_at(up) == kind else 0                    # falling fluid arrives at full strength
        for dx, dz in SIDE:
            n = (x + dx, y, z + dz)
            if self.kind_at(n) == kind:
                below_n = (n[0], n[1] - 1, n[2])
                supported = not self._free(below_n)                         # fluid only spreads sideways if it can't fall
                if supported or self.kind_at(below_n) == kind:
                    wanted = max(wanted, self.level_at(n) - 1)
        current = self.flowing.get(pos, 0) if here else 0
        if wanted == current:
            if here:
                self._react(pos, kind)
                self._spread_from(pos, kind)
            return
        if wanted <= 0:                                                      # nothing feeds this cell any more
            if here:
                self.flowing.pop(pos, None)
                self.world.set_fluid(pos, None)
                self._wake_around(pos)
            return
        if self._would_mix(pos, kind):
            return
        self.flowing[pos] = wanted
        self.world.set_fluid(pos, kind)
        self._wake_around(pos)
        self._react(pos, kind)

    def _spread_from(self, pos, kind):
        below = (pos[0], pos[1] - 1, pos[2])
        if self._free(below) or self.kind_at(below) == kind:
            self.active[kind].add(below)
        for dx, dz in SIDE:
            self.active[kind].add((pos[0] + dx, pos[1], pos[2] + dz))

    def _wake_around(self, pos):
        x, y, z = pos
        for dx, dy, dz in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            for kind in ('water', 'lava'):
                self.active[kind].add((x + dx, y + dy, z + dz))

    # ---- water meets lava ----------------------------------------------------------

    def _would_mix(self, pos, kind):
        return False

    def _react(self, pos, kind):
        """Where water and lava touch, the lava turns to stone."""
        x, y, z = pos
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            n = (x + dx, y + dy, z + dz)
            other = self.kind_at(n)
            if other and other != kind:
                lava = pos if kind == 'lava' else n
                solid = 'obsidian' if self.is_source(lava) else 'cobblestone'
                self.flowing.pop(lava, None)
                self.world.set_fluid(lava, solid)
                self._wake_around(lava)
                if self.sound:
                    self.sound.play('liquid/lavapop', 0.5)
                return
