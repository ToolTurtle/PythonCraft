"""Redstone: power flowing from levers, buttons, plates, torches and redstone blocks, through dust wire,
to lamps, doors, TNT and pistons.

Every 0.1 seconds, when something has changed (or something might be clocking), the whole circuit is
worked out again from scratch:
  1. Sources give off power: a lever that is on, a pressed button or plate, a redstone block, a lit torch.
  2. Wire carries power, one step weaker for each piece of wire it travels through (15 down to 1).
  3. Things that use power (lamps, pistons, doors, TNT) check whether they are being powered.
  4. A redstone torch goes out when the block it is stuck on is powered.
Block names carry the on/off state: 'redstone_lamp' / 'redstone_lamp_on', 'lever' / 'lever_on'..."""
import math

from blocks import BLOCKS, ID, NAMES, REDSTONE_ROLE
from facing import SUPPORT_OFFSET, VECTOR, support_of
from inventory import Stack

TICK = 0.1
BUTTON_SECONDS = 1.0
PUSH_LIMIT = 12
NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
UNMOVABLE = {'bedrock', 'obsidian', 'chest', 'furnace', 'enchanting_table', 'spawner', 'piston_extended',
             'sticky_piston_extended', 'piston_head', 'water', 'lava'}


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


class Redstone:
    def __init__(self, world, player, mobs, dropped, tnt, sound):
        self.world, self.player, self.mobs, self.dropped, self.tnt, self.sound = world, player, mobs, dropped, tnt, sound
        self.timer = TICK
        self.dirty = True
        self.button_timers = {}
        self.door_power = {}          # door position -> whether it was powered last time we looked
        world.listeners.append(self._changed)

    def _changed(self, pos):
        self.dirty = True

    # ---- reading blocks -------------------------------------------------------------------

    def role(self, pos):
        name = self.world.get(pos)
        return BLOCKS[name].get('redstone') if name else None

    def _solid_block(self, pos):
        name = self.world.get(pos)
        return bool(name) and self.world.is_solid(pos) and not BLOCKS[name].get('redstone') in ('wire', 'torch', 'torch_off')

    # ---- what the player does with the controls ---------------------------------------------

    def toggle_lever(self, pos):
        name = self.world.get(pos)
        new = 'lever_on' if name == 'lever' else 'lever'
        self.world.replace(pos, new, self.world.facing.get(pos))
        self.sound.play('random/lever', 0.7)
        self.dirty = True

    def press_button(self, pos):
        if self.world.get(pos) == 'stone_button':
            self.world.replace(pos, 'stone_button_on', self.world.facing.get(pos))
            self.button_timers[pos] = BUTTON_SECONDS
            self.sound.play('random/click', 0.7)
            self.dirty = True

    # ---- every frame ----------------------------------------------------------------------------

    def update(self, dt):
        for pos in list(self.button_timers):
            self.button_timers[pos] -= dt
            if self.button_timers[pos] <= 0:
                del self.button_timers[pos]
                if self.world.get(pos) == 'stone_button_on':
                    self.world.replace(pos, 'stone_button', self.world.facing.get(pos))
                    self.dirty = True
        self.timer -= dt
        if self.timer > 0:
            return
        self.timer = TICK
        comps = [p for p in self.world.circuit if (p[0] >> 4, p[2] >> 4) in self.world.chunks]
        if not comps:
            return
        if self._update_plates(comps):
            self.dirty = True
        has_torch = any(self.role(p) in ('torch', 'torch_off') for p in comps)
        if self.dirty or has_torch:
            self.dirty = False
            self._compute(comps)
        self.world.flush_dirty()

    # ---- pressure plates ---------------------------------------------------------------------------

    def _occupied(self, pos):
        x, y, z = pos
        things = [(self.player.x, self.player.y, self.player.z)] if not self.player.dead else []
        things += [(m.x, m.y, m.z) for m in self.mobs.mobs]
        things += [(d.x, d.y, d.z) for d in self.dropped.items]
        return any(abs(tx - x) < 0.55 and abs(tz - z) < 0.55 and y - 0.6 < ty < y + 0.8 for tx, ty, tz in things)

    def _update_plates(self, comps):
        changed = False
        for pos in comps:
            r = self.role(pos)
            if r not in ('plate', 'plate_on'):
                continue
            pressed = self._occupied(pos)
            name = self.world.get(pos)
            if pressed and r == 'plate':
                self.world.replace(pos, name + '_on')
                self.sound.play('random/click', 0.5)
                changed = True
            elif not pressed and r == 'plate_on':
                self.world.replace(pos, name[:-3])
                changed = True
        return changed

    # ---- working out the power ---------------------------------------------------------------------

    def _compute(self, comps):
        w = self.world
        receiving = set()          # cells that get power straight from a source
        hard = set()               # solid blocks that are powered by something attached to them (they power their neighbors)

        def emit_neighbors(cell):
            for d in NEIGHBORS:
                receiving.add(add(cell, d))

        for pos in comps:
            r = self.role(pos)
            if r in ('lever_on', 'button_on'):
                support = support_of(pos, w.facing.get(pos))
                emit_neighbors(pos)
                hard.add(support)
                emit_neighbors(support)
            elif r == 'plate_on':
                emit_neighbors(pos)
                below = (pos[0], pos[1] - 1, pos[2])
                hard.add(below)
                emit_neighbors(below)
            elif r == 'block':
                emit_neighbors(pos)
            elif r == 'torch':
                orient = w.facing.get(pos)
                support = support_of(pos, orient)
                for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0)):
                    c = add(pos, d)
                    if c != support:
                        receiving.add(c)
                above = (pos[0], pos[1] + 1, pos[2])
                hard.add(above)
                emit_neighbors(above)

        # wire: levels from 15 down to 1
        wires = [p for p in comps if self.role(p) == 'wire']
        level = {p: 0 for p in wires}
        frontier = []
        for p in wires:
            if p in receiving:
                level[p] = 15
                frontier.append(p)
        while frontier:
            nxt = []
            for p in frontier:
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    for dy in (0, 1, -1):
                        q = (p[0] + dx, p[1] + dy, p[2] + dz)
                        if q in level and level[q] < level[p] - 1:
                            level[q] = level[p] - 1
                            nxt.append(q)
            frontier = nxt

        soft = set()                              # solid blocks powered by a neighboring wire
        for p, lv in level.items():
            if lv > 0:
                for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
                    c = add(p, d)
                    if self.role(c) in ('lamp', 'lamp_on', 'piston', 'piston_out', 'door', 'tnt', 'note', 'prail', 'prail_on'):
                        receiving.add(c)                  # something that uses power: it is powered by the wire
                    elif self._solid_block(c):
                        soft.add(c)
        block_power = hard | soft

        def powered(pos):
            if pos in receiving:
                return True
            return any(add(pos, d) in block_power for d in NEIGHBORS)

        # apply to the world
        for p in wires:
            want = 'redstone_wire_on' if level[p] > 0 else 'redstone_wire'
            if w.get(p) != want:
                w.set_fluid(p, want)
        for pos in comps:
            r = self.role(pos)
            if r in ('lamp', 'lamp_on'):
                on = powered(pos)
                if on and r == 'lamp':
                    w.set_fluid(pos, 'redstone_lamp_on')
                elif not on and r == 'lamp_on':
                    w.set_fluid(pos, 'redstone_lamp')
            elif r in ('torch', 'torch_off'):
                support = support_of(pos, w.facing.get(pos))
                out = support in block_power or support in receiving and self.role(support) not in ('torch',)
                if out and r == 'torch':
                    w.set_fluid(pos, 'redstone_torch_off')
                elif not out and r == 'torch_off':
                    w.set_fluid(pos, 'redstone_torch')
            elif r in ('prail', 'prail_on'):
                on = powered(pos)
                if on and r == 'prail':
                    w.set_fluid(pos, 'powered_rail_on')
                elif not on and r == 'prail_on':
                    w.set_fluid(pos, 'powered_rail')
            elif r == 'tnt':
                if powered(pos):
                    w.remove(pos)
                    self.tnt.prime(pos, 4.0)
            elif r == 'door':
                if w.get(pos) == 'oak_door_b':
                    now = powered(pos)
                    before = self.door_power.get(pos)
                    self.door_power[pos] = now
                    if before is not None and now != before:             # only react when the power CHANGES,
                        for q in (pos, (pos[0], pos[1] + 1, pos[2])):    # so a door opened by hand stays open
                            s = w.facing.get(q) or 'south'
                            if now and not s.endswith('+'):
                                w.facing[q] = s + '+'
                            elif not now and s.endswith('+'):
                                w.facing[q] = s[:-1]
                        w.dirty.add((pos[0] >> 4, pos[2] >> 4))
                        self.sound.play('random/door_open' if now else 'random/door_close', 0.6)
            elif r in ('piston', 'piston_out'):
                on = powered(pos)
                if on and r == 'piston':
                    self._extend(pos)
                elif not on and r == 'piston_out':
                    self._retract(pos)

    # ---- pistons ---------------------------------------------------------------------------------------

    def _extend(self, pos):
        w = self.world
        direction = VECTOR[w.facing.get(pos, 'up')]
        start = add(pos, direction)
        chain = []
        for i in range(PUSH_LIMIT + 1):
            cell = add(start, tuple(c * i for c in direction))
            k = w.get(cell)
            if k is None or BLOCKS[k].get('fluid') or BLOCKS[k].get('shape') in ('cross',):
                break
            if k in UNMOVABLE or BLOCKS[k].get('hardness') is None:
                return                                    # something is in the way that cannot be pushed
            chain.append(cell)
        else:
            return                                        # too many blocks to push
        for cell in reversed(chain):                      # move the far ones first
            target = add(cell, direction)
            w._set(target, w.get(cell))
            if cell in w.facing:
                w.facing[target] = w.facing.pop(cell)
            w._set(cell, None)
        name = w.get(pos)
        w._set(start, 'piston_head')
        w.facing[start] = w.facing.get(pos, 'up')
        w._set(pos, name + '_extended')
        self._dirty_chunks(pos, chain, direction)
        self.sound.play('random/piston_out', 0.6)

    def _retract(self, pos):
        w = self.world
        direction = VECTOR[w.facing.get(pos, 'up')]
        head = add(pos, direction)
        sticky = w.get(pos).startswith('sticky')
        if w.get(head) == 'piston_head':
            w._set(head, None)
            w.facing.pop(head, None)
        beyond = add(head, direction)
        if sticky and w.get(beyond) is not None and w.get(beyond) not in UNMOVABLE \
                and BLOCKS[w.get(beyond)].get('hardness') is not None:
            w._set(head, w.get(beyond))
            if beyond in w.facing:
                w.facing[head] = w.facing.pop(beyond)
            w._set(beyond, None)
        w._set(pos, w.get(pos).replace('_extended', ''))
        self._dirty_chunks(pos, [head, beyond], direction)
        self.sound.play('random/piston_in', 0.6)

    def _dirty_chunks(self, pos, cells, direction):
        for c in [pos] + list(cells) + [add(cells[-1], direction)] if cells else [pos]:
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    key = ((c[0] + dx) >> 4, (c[2] + dz) >> 4)
                    if key in self.world.wanted:
                        self.world.dirty.add(key)
