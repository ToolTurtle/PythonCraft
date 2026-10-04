"""Fire: it burns on wood, leaves, wool and other things that can burn, spreads to them, and goes out
when nothing is left to burn (or when water gets to it)."""
import random

from ursina import Vec3

from blocks import BLOCKS, flammability
from inventory import Stack

TICK = 0.6
NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


class Fire:
    def __init__(self, world, player, mobs, tnt, sound):
        self.world, self.player, self.mobs, self.tnt, self.sound = world, player, mobs, tnt, sound
        self.fires = {}            # position -> seconds it has been burning
        self.timer = TICK
        self.hurt_timer = 0.5

    def start(self, pos):
        """Light a fire in an empty cell (if it can burn there)."""
        if self.world.get(pos) is not None:
            return False
        self.world.place(pos, 'fire')
        self.fires[pos] = 0.0
        self.sound.play('random/fire', 0.5)
        return True

    def update(self, dt):
        self._burn_creatures(dt)
        self.timer -= dt
        if self.timer > 0:
            return
        dt = TICK
        self.timer = TICK
        for pos in [p for p in self.world.fires]:
            if self.world.get(pos) != 'fire':
                self.world.fires.discard(pos)
                self.fires.pop(pos, None)
                continue
            if (pos[0] >> 4, pos[2] >> 4) not in self.world.chunks:
                continue
            self.fires[pos] = self.fires.get(pos, 0) + dt
            self._step(pos)
        self.world.flush_dirty()

    def _step(self, pos):
        w = self.world
        neighbors = [add(pos, d) for d in NEIGHBORS]
        if any(w.get(n) == 'water' for n in neighbors) or w.get(add(pos, (0, 1, 0))) == 'water':
            self._put_out(pos)
            return
        fuel = [(n, flammability(w.get(n))) for n in neighbors if flammability(w.get(n)) > 0]
        under = flammability(w.get(add(pos, (0, -1, 0))))
        for n, chance in fuel:                                       # burn the things next to the fire
            if random.random() < chance * 0.25:
                kind = w.get(n)
                if kind == 'tnt':
                    w.remove(n)
                    self.tnt.prime(n, 1.0)
                    continue
                w.set_fluid(n, 'fire')
                w.fires.add(n)
                self.fires[n] = 0.0
                w.facing.pop(n, None)
                for listener in w.listeners:
                    listener(n)
        if fuel:                                                     # and sometimes jump to a nearby empty cell
            if random.random() < 0.5:
                target = add(pos, random.choice(((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0))))
                if w.get(target) is None and any(flammability(w.get(add(target, d))) > 0 for d in NEIGHBORS):
                    w.set_fluid(target, 'fire')
                    w.fires.add(target)
                    self.fires[target] = 0.0
        elif w.get(add(pos, (0, -1, 0))) != 'netherrack':
            # nothing to burn: this fire dies out soon
            if self.fires.get(pos, 0) > random.uniform(1.5, 4.0):
                self._put_out(pos)
                return
        if w.get(add(pos, (0, -1, 0))) == 'netherrack':
            return                                                   # fire on netherrack burns forever
        if not fuel and under == 0 and not w.is_solid(add(pos, (0, -1, 0))):
            self._put_out(pos)                                       # fire needs something to stand on
        # a fire eventually burns down its own fuel base
        if under > 0 and random.random() < under * 0.15:
            w.set_fluid(add(pos, (0, -1, 0)), 'fire')
            w.fires.add(add(pos, (0, -1, 0)))
            w.set_fluid(pos, None)
            w.fires.discard(pos)
            self.fires.pop(pos, None)

    def _put_out(self, pos):
        self.world.set_fluid(pos, None)
        self.world.fires.discard(pos)
        self.fires.pop(pos, None)
        for listener in self.world.listeners:
            listener(pos)

    def _burn_creatures(self, dt):
        self.hurt_timer -= dt
        if self.hurt_timer > 0:
            return
        self.hurt_timer = 0.5
        p = self.player
        cells = {(round(p.x), int(p.y + 0.5), round(p.z)), (round(p.x), int(p.y + 1.5), round(p.z))}
        if any(self.world.get(c) == 'fire' for c in cells):
            p.damage(1, 'fire')
        for mob in self.mobs.mobs[:]:
            if self.world.get((round(mob.x), int(mob.y + 0.5), round(mob.z))) == 'fire':
                mob.hurt_by_fire()
