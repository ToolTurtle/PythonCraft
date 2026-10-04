"""Nether portals: light an obsidian frame with flint and steel, walk in, wait a moment, and you arrive
in the other dimension. One block in the Nether is eight blocks in the overworld."""
import math

import numpy as np
from ursina import Entity, camera, color

from blocks import ID

PORTAL = 'nether_portal'
TRAVEL_SECONDS = 3.0           # standing in a portal in survival mode
MAX_SIZE = 21                  # the biggest portal interior (width or height)
SEARCH_RADIUS = 3              # chunks around the destination searched for an existing portal


class Portals:
    def __init__(self, world, player, change_dimension, sound=None):
        self.world, self.player, self.sound = world, player, sound
        self.change_dimension = change_dimension          # function(name): switch to another dimension
        self.timer = 0.0
        self.cooldown = 0.0
        self.must_leave = False
        self.overlay = Entity(parent=camera.ui, model='quad', scale=(3, 2), z=1.5, enabled=False,
                              color=color.rgba32(110, 20, 200, 0))
        world.listeners.append(self.on_change)

    # ---- lighting a portal ----------------------------------------------------------

    def try_light(self, spot):
        """Flint and steel was used on an empty cell: if it sits inside an obsidian frame, fill the frame."""
        for axis in (0, 2):
            cells = self._interior(spot, axis)
            if cells:
                for cell in cells:
                    self.world.set_fluid(cell, PORTAL)
                    self.world.fires.discard(cell)
                    self.world.facing.pop(cell, None)
                self.world.flush_dirty(budget=float('inf'))
                if self.sound:
                    self.sound.play('random/fire', 0.7)
                return True
        return False

    def _interior(self, spot, axis):
        """The empty cells of an obsidian frame in the plane through `spot` (along x if axis == 0, along z if 2),
        or None if there is no complete rectangular frame there."""
        world = self.world
        horizontal = (1, 0, 0) if axis == 0 else (0, 0, 1)

        def free(cell):
            return world.get(cell) in (None, 'fire')

        if not free(spot):
            return None
        found, todo = {spot}, [spot]
        while todo:
            x, y, z = todo.pop()
            for dh, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dh * horizontal[0], y + dy, z + dh * horizontal[2])
                if n in found:
                    continue
                if free(n):
                    found.add(n)
                    if len(found) > MAX_SIZE * MAX_SIZE:
                        return None
                    todo.append(n)
                elif world.get(n) != 'obsidian':
                    return None
        h = [c[0] if axis == 0 else c[2] for c in found]
        ys = [c[1] for c in found]
        width, height = max(h) - min(h) + 1, max(ys) - min(ys) + 1
        if width * height != len(found) or not (2 <= width <= MAX_SIZE and 3 <= height <= MAX_SIZE):
            return None
        return sorted(found)

    # ---- a frame breaks ----------------------------------------------------------

    def on_change(self, pos):
        """A block changed: if it was part of a portal's frame, the portal fades away."""
        if self.world.get(pos) in ('obsidian', PORTAL):
            return
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
            if self.world.get(n) == PORTAL:
                self._collapse(n)

    def _collapse(self, start):
        world = self.world
        todo, seen = [start], {start}
        while todo:
            x, y, z = todo.pop()
            world.set_fluid((x, y, z), None)
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + dx, y + dy, z + dz)
                if n not in seen and world.get(n) == PORTAL:
                    seen.add(n)
                    todo.append(n)
        world.flush_dirty(budget=float('inf'))

    # ---- walking into one ---------------------------------------------------------

    def in_portal(self):
        p = self.player
        feet = (round(p.x), math.floor(p.y + 0.5), round(p.z))
        return self.world.get(feet) == PORTAL or self.world.get((feet[0], feet[1] + 1, feet[2])) == PORTAL

    def update(self, dt, active=True):
        self.cooldown = max(0.0, self.cooldown - dt)
        inside = active and self.in_portal()
        here = (round(self.player.x) >> 4, round(self.player.z) >> 4)
        if here not in self.world.chunks:
            return                                    # (the land is not here yet)
        if not inside:
            self.must_leave = False
            self.timer = max(0.0, self.timer - dt * 2)
        elif not self.must_leave and self.cooldown <= 0:
            self.timer += dt
            need = 0.2 if self.player.mode == 'creative' else TRAVEL_SECONDS
            if self.timer >= need:
                self.timer = 0.0
                self.travel()
        alpha = min(1.0, self.timer / TRAVEL_SECONDS) * 0.7
        self.overlay.enabled = alpha > 0.01
        self.overlay.color = color.rgba(0.43, 0.08, 0.78, alpha)

    # ---- the journey ----------------------------------------------------------------

    def travel(self):
        p, world = self.player, self.world
        going_to = 'nether' if world.dimension == 'overworld' else 'overworld'
        scale = 1 / 8 if going_to == 'nether' else 8
        tx, tz = math.floor(p.x * scale), math.floor(p.z * scale)
        self.change_dimension(going_to)
        for cx in range((tx >> 4) - SEARCH_RADIUS, (tx >> 4) + SEARCH_RADIUS + 1):       # make the land there
            for cz in range((tz >> 4) - SEARCH_RADIUS, (tz >> 4) + SEARCH_RADIUS + 1):
                world.chunk_at(cx, cz)
        spot = self.find_portal(tx, tz) or self.build_portal(tx, tz)
        p.position = (spot[0], spot[1] - 0.5 + 0.01, spot[2])
        p.velocity_y = 0
        self.must_leave = True
        self.cooldown = 1.0
        world._view_chunk = None

    def find_portal(self, tx, tz):
        """The nearest existing portal block to (tx, tz), or None."""
        best, best_distance = None, 1e18
        for (cx, cz), chunk in world_chunks(self.world, tx, tz):
            for lx, lz, y in zip(*np.nonzero(chunk.blocks == ID[PORTAL])):
                x, z = cx * 16 + int(lx), cz * 16 + int(lz)
                distance = (x - tx) ** 2 + (z - tz) ** 2
                if distance < best_distance or (distance == best_distance and best is not None and y < best[1]):
                    best, best_distance = (x, int(y), z), distance
        return best

    def build_portal(self, tx, tz):
        """Make a new portal frame (with a platform and room to step out) near (tx, tz). Returns the cell you arrive in."""
        world = self.world
        if world.nether:
            import nether
            y = None
            for radius in range(0, 17, 2):
                for dx, dz in ((0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius), (radius, radius), (-radius, -radius)):
                    y = nether.find_floor(world, tx + dx, tz + dz, 100)
                    if y is not None:
                        tx, tz = tx + dx, tz + dz
                        break
                if y is not None:
                    break
            if y is None:
                y = 70
        else:
            y = max(world.height_at(tx, tz), 49) + 1
        z = tz
        for dx in range(-1, 3):                                       # room: air around and above
            for dz in (-1, 0, 1):
                for dy in range(0, 5):
                    if world.get((tx + dx, y + dy, z + dz)) is not None:
                        world.set_fluid((tx + dx, y + dy, z + dz), None)
                world.set_fluid((tx + dx, y - 1, z + dz), 'obsidian')    # a platform
        for dx in range(-1, 3):
            for dy in range(-1, 4):
                edge = dx in (-1, 2) or dy in (-1, 3)
                cell = (tx + dx, y + dy, z)
                world.set_fluid(cell, 'obsidian' if edge else PORTAL)
        world.flush_dirty(budget=float('inf'))
        return (tx, y, tz)


def world_chunks(world, tx, tz):
    for cx in range((tx >> 4) - SEARCH_RADIUS, (tx >> 4) + SEARCH_RADIUS + 1):
        for cz in range((tz >> 4) - SEARCH_RADIUS, (tz >> 4) + SEARCH_RADIUS + 1):
            chunk = world.chunks.get((cx, cz))
            if chunk is not None:
                yield (cx, cz), chunk
