"""Anything that walks around and bumps into blocks (the player, the animals).

The world is made of blocks on a grid, so we don't need physics colliders.
We just ask the world "is there a block here?"."""
import math

from ursina import Entity

GRAVITY = 32
MAX_FALL_SPEED = 50
WATER_GRAVITY = 6
WATER_SINK_SPEED = 3
EPSILON = 1e-4


class Body(Entity):
    """An entity with a box-shaped body whose position is the middle of its feet."""

    def __init__(self, world, position, width, height):
        super().__init__(position=position)
        self.world = world
        self.width = width
        self.height = height
        self.velocity_y = 0
        self.grounded = False
        self.noclip = False      # True: pass through blocks (spectator mode)
        self.step_height = 0.5625   # how high a step can be climbed without jumping

    def _hits_block(self, x, y, z):
        """Would the body overlap a block if standing at (x, y, z)?"""
        if self.noclip:
            return False
        half = self.width / 2
        solid_top = self.world.solid_top
        for bx in range(math.floor(x - half + .5 + EPSILON), math.floor(x + half + .5 - EPSILON) + 1):
            for by in range(math.floor(y + .5 + EPSILON), math.floor(y + self.height + .5 - EPSILON) + 1):
                for bz in range(math.floor(z - half + .5 + EPSILON), math.floor(z + half + .5 - EPSILON) + 1):
                    top = solid_top((bx, by, bz))
                    if top > 0 and y < by - 0.5 + top - EPSILON:       # (a slab is only solid in its lower half)
                        return True
        return False

    def _surface_below(self, x, y, z):
        """The height of the highest solid surface under the feet around (x, y, z)."""
        half = self.width / 2
        best = -1e9
        row = math.floor(y + .5)
        for bx in range(math.floor(x - half + .5 + EPSILON), math.floor(x + half + .5 - EPSILON) + 1):
            for bz in range(math.floor(z - half + .5 + EPSILON), math.floor(z + half + .5 - EPSILON) + 1):
                top = self.world.solid_top((bx, row, bz))
                if top > 0:
                    best = max(best, row - 0.5 + top)
        return best

    def overlaps_block(self, block):
        """Is this block position inside the body? (Used to stop you walling yourself in.)"""
        half = self.width / 2 + .5
        return (abs(block[0] - self.x) < half and abs(block[2] - self.z) < half
                and block[1] + .5 > self.y and block[1] - .5 < self.y + self.height)

    def move(self, axis, amount):
        """Move along one axis (0=x, 1=y, 2=z) in small steps. Returns True if a block stopped us."""
        if amount == 0:
            return False
        if self._hits_block(self.x, self.y, self.z):
            # Already stuck inside a block (it was built around us?): move freely to get out,
            # instead of being pushed around by the collision code.
            pos = [self.x, self.y, self.z]
            pos[axis] += amount
            self.position = pos
            return False
        steps = max(1, math.ceil(abs(amount) / 0.2))
        step = amount / steps
        for _ in range(steps):
            pos = [self.x, self.y, self.z]
            pos[axis] += step
            if not self._hits_block(*pos):
                self.position = pos
                continue
            # Walking into a step (a slab, a stair, farmland)? Climb it if it is low enough.
            if axis != 1 and self.grounded and self.step_height:
                for lift in (0.0625, 0.125, 0.25, 0.5, 0.5625):
                    if lift <= self.step_height and not self._hits_block(pos[0], self.y + lift, pos[2]):
                        pos[1] = self.y + lift
                        self.position = pos
                        break
                else:
                    lift = None
                if lift is not None and self.position[1] == pos[1]:
                    continue
            # Blocked: line up exactly against the block we hit.
            if axis == 1:
                if step < 0:
                    surface = self._surface_below(pos[0], pos[1], pos[2])
                    self.y = (surface if surface > -1e8 else math.floor(pos[1] + .5) + .5) + EPSILON
                else:
                    self.y = math.floor(pos[1] + self.height + .5) - .5 - self.height - EPSILON
            else:
                half = self.width / 2
                if step > 0:
                    pos[axis] = math.floor(pos[axis] + half + .5) - .5 - half - EPSILON
                else:
                    pos[axis] = math.floor(pos[axis] - half + .5) + .5 + half + EPSILON
                self.position = pos
            return True
        return False

    def in_water(self):
        """Is the middle of the body under water?"""
        spot = (round(self.x), math.floor(self.y + self.height / 2 + .5), round(self.z))
        return self.world.get(spot) == 'water'

    def fall(self, dt):
        """Let gravity pull us down for one frame; updates `grounded`."""
        if self.in_water():
            self.velocity_y = max(self.velocity_y - WATER_GRAVITY * dt, -WATER_SINK_SPEED)   # sink slowly
        else:
            self.velocity_y = max(self.velocity_y - GRAVITY * dt, -MAX_FALL_SPEED)
        blocked = self.move(1, self.velocity_y * dt)
        self.grounded = blocked and self.velocity_y < 0
        if blocked:
            self.velocity_y = 0
