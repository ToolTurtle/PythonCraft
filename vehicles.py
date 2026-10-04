"""Minecarts that run along rails, and boats that float on water. You can ride both:
right-click to get in, Shift to get out."""
import math

from ursina import Entity, Vec3, color, destroy, held_keys, time

from inventory import Stack

HEADINGS = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
SIDES = {(0, -1): 'N', (1, 0): 'E', (0, 1): 'S', (-1, 0): 'W'}


def _box(parent, scale, position, tint):
    return Entity(parent=parent, model='cube', scale=scale, position=position, color=tint)


class Vehicle(Entity):
    name = 'vehicle'
    item = None
    reach_width = 1.0
    reach_height = 0.8

    def __init__(self, world, position):
        super().__init__(position=position)
        self.world = world
        self.rider = None

    def hit_by_ray(self, origin, direction, reach):
        """Distance to this vehicle along a line, or None."""
        t_near, t_far = 0.0, math.inf
        centre = (self.x, self.y + self.reach_height / 2, self.z)
        half = (self.reach_width / 2, self.reach_height / 2, self.reach_width / 2)
        for i in range(3):
            low, high = centre[i] - half[i], centre[i] + half[i]
            if abs(direction[i]) < 1e-9:
                if not (low <= origin[i] <= high):
                    return None
            else:
                t1, t2 = (low - origin[i]) / direction[i], (high - origin[i]) / direction[i]
                t_near, t_far = max(t_near, min(t1, t2)), min(t_far, max(t1, t2))
        return t_near if t_near <= t_far and t_near <= reach else None


class Minecart(Vehicle):
    name = 'minecart'
    item = 'minecart'
    reach_width = 1.0
    reach_height = 0.7

    def __init__(self, world, position):
        super().__init__(world, position)
        grey = color.rgb32(115, 118, 125)
        dark = color.rgb32(70, 72, 78)
        _box(self, (0.9, 0.08, 0.7), (0, 0.25, 0), dark)
        for dx in (-0.45, 0.45):
            _box(self, (0.08, 0.4, 0.7), (dx, 0.45, 0), grey)
        for dz in (-0.35, 0.35):
            _box(self, (0.9, 0.4, 0.08), (0, 0.45, dz), grey)
        self.heading = None          # 'N', 'E', 'S' or 'W' while rolling
        self.speed = 0.0

    def rider_position(self):
        return Vec3(self.x, self.y + 0.1, self.z)

    # ---- the rails ------------------------------------------------------------------------------

    def _rail(self, cell):
        name = self.world.get(cell)
        return name if name and name.endswith(('rail', 'rail_on')) else None

    def _links(self, cell):
        """Which sides of this rail cell have another rail attached."""
        return [s for s, (dx, dz) in HEADINGS.items() if self._rail((cell[0] + dx, cell[1], cell[2] + dz))]

    def push(self, direction):
        """Give the cart a shove along (dx, dz)."""
        if abs(direction[0]) > abs(direction[1]):
            self.heading = 'E' if direction[0] > 0 else 'W'
        else:
            self.heading = 'S' if direction[1] > 0 else 'N'
        self.speed = max(self.speed, 2.5)

    def update(self):
        dt = min(time.dt, 0.05)
        cell = (round(self.x), math.floor(self.y + 0.5 + 0.1), round(self.z))      # the cell the rail is in
        on = self._rail(cell)
        if not on:
            if not self.world.is_solid((cell[0], cell[1] - 1, cell[2])) and self.world.get((cell[0], cell[1] - 1, cell[2])) is None:
                self.y -= 9 * dt                      # nothing under it: it falls
            self.speed *= 0.9
            return

        name = self._rail(cell) or ''
        if name == 'powered_rail_on':
            self.speed = min(self.speed + 12 * dt, 14)    # a boost
        elif name == 'powered_rail':
            self.speed = max(0.0, self.speed - 14 * dt)   # an unpowered rail brakes
        if self.rider is not None:
            forward = held_keys['w'] - held_keys['s']
            if forward and self.heading is None:
                look = self.rider.forward
                self.push((look[0], look[2]))
            self.speed = max(0.0, min(12.0, self.speed + forward * 5 * dt))
        self.speed = max(0.0, self.speed - 0.7 * dt)       # a little friction
        if self.speed <= 0.01 or self.heading is None:
            self.speed = 0.0
            self.y = cell[1] - 0.5 + 0.0625 + 0.0
            return

        # roll toward the next rail, always staying on the middle of the track
        dx, dz = HEADINGS[self.heading]
        links = self._links(cell)
        centre = (cell[0], cell[2])
        at_centre = (self.x - centre[0]) * dx + (self.z - centre[1]) * dz >= -0.001
        step = self.speed * dt
        if at_centre:
            # we have reached the middle of this piece of track: choose the way out
            options = [s for s in links if s != OPPOSITE[self.heading]]
            if self.heading in options:
                pass                                     # straight on
            elif options:
                self.heading = options[0]                # round a bend
                self.x, self.z = float(centre[0]), float(centre[1])
            else:
                self.speed = 0.0                         # end of the line
                self.heading = None
                return
        dx, dz = HEADINGS[self.heading]
        self.x += dx * step
        self.z += dz * step
        if dx:
            self.z += (centre[1] - self.z) * min(1.0, 10 * dt)
        else:
            self.x += (centre[0] - self.x) * min(1.0, 10 * dt)
        self.y = cell[1] - 0.5 + 0.0625
        self.rotation_y = {'N': 0, 'E': 90, 'S': 180, 'W': 270}[self.heading]


class Boat(Vehicle):
    name = 'boat'
    item = 'oak_boat'
    reach_width = 1.4
    reach_height = 0.6

    def __init__(self, world, position):
        super().__init__(world, position)
        wood = color.rgb32(140, 100, 55)
        _box(self, (1.2, 0.1, 1.7), (0, 0.1, 0), wood)
        for dx in (-0.55, 0.55):
            _box(self, (0.1, 0.35, 1.7), (dx, 0.3, 0), wood)
        for dz in (-0.8, 0.8):
            _box(self, (1.2, 0.35, 0.1), (0, 0.3, dz), wood)
        self.velocity = Vec3(0, 0, 0)
        self.heading = 0.0

    def rider_position(self):
        return Vec3(self.x, self.y + 0.2, self.z)

    def update(self):
        dt = min(time.dt, 0.05)
        cell = (round(self.x), math.floor(self.y + 0.5), round(self.z))
        in_water = self.world.get(cell) == 'water' or self.world.get((cell[0], cell[1] - 1, cell[2])) == 'water'
        if self.rider is not None:
            turn = held_keys['d'] - held_keys['a']
            self.heading += turn * 90 * dt
            drive = held_keys['w'] - 0.4 * held_keys['s']
            r = math.radians(self.heading)
            wanted = Vec3(math.sin(r), 0, math.cos(r)) * drive * 7
            self.velocity += (wanted - self.velocity) * min(1.0, 2.5 * dt)
        else:
            self.velocity *= 0.95
        if in_water:
            top = cell[1] if self.world.get(cell) == 'water' else cell[1] - 1
            above = (cell[0], top + 1, cell[2])
            surface = top + 0.5
            if self.world.get(above) == 'water':
                self.y += 3 * dt
            else:
                self.y += (surface - self.y) * min(1.0, 8 * dt)
        else:
            self.y -= 8 * dt
        # move, but stop at solid blocks and keep to the water
        nx, nz = self.x + self.velocity.x * dt, self.z + self.velocity.z * dt
        ahead = (round(nx), math.floor(self.y + 0.5), round(nz))
        if self.world.is_solid(ahead) or self.world.is_solid((ahead[0], ahead[1] + 1, ahead[2])):
            self.velocity = Vec3(0, 0, 0)
        elif self.world.get(ahead) == 'water' or self.world.get((ahead[0], ahead[1] - 1, ahead[2])) == 'water':
            self.x, self.z = nx, nz
        else:
            self.velocity *= 0.5                            # a boat cannot sail onto dry land
        self.rotation_y = self.heading


class Vehicles:
    def __init__(self, world, player, dropped, sound):
        self.world, self.player, self.dropped, self.sound = world, player, dropped, sound
        self.list = []

    def spawn(self, kind, position):
        v = (Minecart if kind == 'minecart' else Boat)(self.world, Vec3(*position))
        self.list.append(v)
        return v

    def hit_test(self, origin, direction, reach):
        best = None
        for v in self.list:
            t = v.hit_by_ray(origin, direction, reach)
            if t is not None and (best is None or t < best[1]):
                best = (v, t)
        return best

    def mount(self, vehicle):
        self.player.riding = vehicle
        vehicle.rider = self.player
        if isinstance(vehicle, Boat):
            vehicle.heading = self.player.rotation_y

    def dismount(self):
        v = self.player.riding
        if v is not None:
            v.rider = None
            self.player.riding = None
            self.player.position = (v.x, v.y + 0.9, v.z)
            self.player.velocity_y = 0

    def destroy_vehicle(self, vehicle, drop=True):
        if self.player.riding is vehicle:
            self.dismount()
        self.list.remove(vehicle)
        if drop and self.dropped is not None:
            self.dropped.drop(Stack(vehicle.item, 1), Vec3(vehicle.x, vehicle.y + 0.5, vehicle.z))
        destroy(vehicle)

    def update(self, dt):
        if self.player.riding is not None:
            if held_keys['left shift']:
                self.dismount()
        for v in self.list:
            v.enabled = (round(v.x) >> 4, round(v.z) >> 4) in self.world.chunk_entities
