"""Crops that grow, and plants that drop when the ground under them goes."""
import random

from ursina import Vec3

from blocks import BLOCKS
from inventory import Stack

CROP_PREFIXES = ('wheat_', 'nether_wart_')
GROW_CHANCE = 0.05        # chance per second that a crop grows one stage (wheat has 8 stages)


class Plants:
    def __init__(self, world, dropped):
        self.world, self.dropped = world, dropped
        self.timer = 1.0
        self.decaying = []            # [position, seconds left] of leaves that are about to fall off
        self.sapling_timer = 2.0
        world.listeners.append(self.check)

    def update(self, dt):
        self.timer -= dt
        if self.timer > 0:
            return
        self.timer = 1.0
        for pos in list(self.world.crops):
            kind = self.world.get(pos)
            if kind is None or not kind.startswith(CROP_PREFIXES):
                self.world.crops.discard(pos)
                continue
            wart = kind.startswith('nether_wart_')
            stage = BLOCKS[kind]['nether_crop' if wart else 'crop']
            if stage < (3 if wart else 7) and (pos[0] >> 4, pos[2] >> 4) in self.world.chunks and random.random() < GROW_CHANCE:
                self.world.replace(pos, f'{"nether_wart" if wart else "wheat"}_{stage + 1}')

    def update_trees(self, dt):
        """Saplings turn into trees; leaves with no log nearby wither away."""
        self.sapling_timer -= dt
        if self.sapling_timer <= 0:
            self.sapling_timer = 2.0
            for pos in [p for p, k in self.world.modified.items() if k and BLOCKS[k].get('sapling')]:
                kind = self.world.get(pos)
                if kind and BLOCKS[kind].get('sapling') and (pos[0] >> 4, pos[2] >> 4) in self.world.chunks \
                        and random.random() < 0.02:
                    self.grow_tree(pos, BLOCKS[kind]['sapling'])
        for entry in self.decaying[:]:
            entry[1] -= dt
            if entry[1] <= 0:
                self.decaying.remove(entry)
                pos = entry[0]
                kind = self.world.get(pos)
                if kind and kind.endswith('_leaves') and not self._log_near(pos):
                    self.world.set_fluid(pos, None)
                    for listener in self.world.listeners:
                        listener(pos)
                    if random.random() < 0.05 and self.dropped is not None:
                        self.dropped.drop(Stack(kind.replace('_leaves', '_sapling'), 1), Vec3(*pos))
        self.world.flush_dirty()

    def _log_near(self, pos, reach=4):
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for dz in range(-reach, reach + 1):
                    if abs(dx) + abs(dy) + abs(dz) <= reach:
                        k = self.world.get((pos[0] + dx, pos[1] + dy, pos[2] + dz))
                        if k and k.endswith('_log'):
                            return True
        return False

    def schedule_decay(self, pos, reach=5):
        """A log was removed: leaves around it may need to die."""
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for dz in range(-reach, reach + 1):
                    p = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
                    k = self.world.get(p)
                    if k and k.endswith('_leaves') and not self._log_near(p):
                        self.decaying.append([p, random.uniform(0.5, 8)])

    def grow_tree(self, pos, kind):
        """Replace a sapling with a full tree (if there is room)."""
        height = {'oak': 5, 'birch': 6, 'spruce': 7, 'jungle': 8}.get(kind, 5)
        for dy in range(1, height + 3):
            k = self.world.get((pos[0], pos[1] + dy, pos[2]))
            if k not in (None,) and not (k.endswith('_leaves')):
                return
        log, leaves = f'{kind}_log', f'{kind}_leaves'
        for dy in range(0, height):
            self.world.set_fluid((pos[0], pos[1] + dy, pos[2]), log)
        for dy, radius in ((height - 2, 2), (height - 1, 2), (height, 1), (height + 1, 1)):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) == radius and abs(dz) == radius and radius == 2 and random.random() < 0.5:
                        continue
                    p = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
                    if self.world.get(p) is None:
                        self.world.set_fluid(p, leaves)
        self.world.flush_dirty(0.05)

    def check(self, pos):
        """A block changed: a plant standing on it may no longer have anywhere to grow."""
        above = (pos[0], pos[1] + 1, pos[2])
        kind = self.world.get(above)
        if not kind:
            return
        wanted = BLOCKS[kind].get('plant_on')
        if wanted == 'solid':
            ok = self.world.is_solid(pos)
        else:
            ok = not wanted or self.world.get(pos) in wanted
        if wanted and not ok:
            self.world.remove(above, notify=False)
            if self.dropped is not None:
                from drops import drops_for
                for name, count in drops_for(kind, None) or ([(kind, 1)] if BLOCKS[kind].get('placeable', True) else []):
                    if count:
                        self.dropped.drop(Stack(name, count), Vec3(*above))
