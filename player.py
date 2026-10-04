"""The player: looking, walking, jumping, swimming, flying, health and game modes.

Game modes:
  survival   you can get hurt (falling, drowning, the void) and you heal slowly
  creative   you cannot be hurt, and you can fly (double-tap Space)
  spectator  you fly through everything and cannot touch anything"""
import math
from time import perf_counter

from ursina import Entity, Vec2, Vec3, camera, color, mouse, held_keys, clamp, time

from physics import Body

WIDTH = 0.6
HEIGHT = 1.95
EYE_HEIGHT = 1.62
WALK_SPEED = 4.3
SPRINT_SPEED = 5.6
SNEAK_SPEED = 1.3
SNEAK_EYE_HEIGHT = 1.27
GROUND_ACCELERATION = 22      # how quickly you reach full speed (higher = snappier)
AIR_ACCELERATION = 3.5        # in the air you keep your momentum
WATER_ACCELERATION = 6
SPRINT_JUMP_BOOST = 1.6       # extra forward push when you jump while sprinting
SPRINT_FOV = 1.12             # the view widens a little while sprinting
COYOTE_TIME = 0.1             # you can still jump this long after walking off an edge
JUMP_BUFFER = 0.12            # a jump pressed just before landing still counts
JUMP_COOLDOWN = 0.25
DOUBLE_TAP_TIME = 0.3
JUMP_SPEED = 9        # a little over one block high
SWIM_SPEED = 3.5      # how fast you rise while holding space in water
FLY_SPEED = 10
FLY_VERTICAL_SPEED = 7

MODES = ('survival', 'creative', 'spectator')
UNARMORED = ('void', 'starve', 'drown', 'fall')       # kinds of damage that armor does not stop
MAX_HEALTH = 20       # 2 health = 1 heart
MAX_AIR = 15.0        # seconds you can hold your breath
SAFE_FALL = 3         # blocks you can fall without getting hurt
INVULNERABLE_TIME = 0.5
MAX_FOOD = 20         # 2 food = 1 drumstick
SPRINT_FOOD = 6       # you cannot sprint when your food is this low or lower
REGEN_FOOD = 18       # you heal while your food is at least this full
REGEN_SECONDS = 4     # one health every 4 seconds
STARVE_SECONDS = 4    # one damage every 4 seconds with no food


class Player(Body):
    def __init__(self, world, position):
        super().__init__(world, position, WIDTH, HEIGHT)
        self.mouse_sensitivity = Vec2(40, 40)
        self.spawn = position

        self.mode = 'survival'
        self.health = MAX_HEALTH
        self.air = MAX_AIR
        self.food = MAX_FOOD
        self.saturation = 5.0       # a hidden buffer that is used up before your food drops
        self.exhaustion = 0.0       # builds up as you move, mine and fight; at 4 it costs some food
        self.dead = False
        self.flying = False
        self.armor_points = 0        # set by the game from the armor you wear
        self.build_locked = False    # adventure mode: cannot place or break blocks
        self.riding = None           # the minecart or boat you are sitting in
        self.xp = 0                  # experience points
        self.on_armor_hit = None     # called when armor should wear
        self.on_xp_gain = None

        self.camera_pivot = Entity(parent=self, y=EYE_HEIGHT)
        camera.parent = self.camera_pivot
        camera.position = Vec3.zero
        camera.rotation = Vec3.zero
        camera.fov = self.base_fov if hasattr(self, 'base_fov') else 90

        self.crosshair = Entity(parent=camera.ui, z=-1)
        Entity(parent=self.crosshair, model='quad', scale=(.02, .003), color=color.white)
        Entity(parent=self.crosshair, model='quad', scale=(.003, .02), color=color.white)

        mouse.locked = True

        # Functions main.py can set, so the player doesn't need to know about sound or the screen:
        self.on_step = None      # walking: called with the block we're walking on
        self.on_splash = None    # jumping into water
        self.on_swim = None      # now and then while swimming
        self.on_hurt = None      # called with (kind, amount)
        self.on_death = None
        self.on_mode_change = None

        self._step_timer = 0
        self._was_swimming = False
        self._peak_y = position[1]       # highest point since we last stood on something
        self._was_grounded = False
        self._invulnerable = 0
        self._since_damage = 0
        self._regen_timer = 0
        self._heal_timer = 0
        self._starve_timer = 0
        self._drown_timer = 1
        self._last_space_press = -1

        # Movement
        self.velocity_xz = Vec3(0, 0, 0)
        self.sprinting = False
        self.sneaking = False
        self.can_sprint = True            # (hunger turns this off when you are too hungry)
        self.base_fov = 90
        self._sprint_latched = False      # set by double-tapping W, cleared when W is let go
        self._last_w_press = -1
        self._coyote = 0
        self._jump_buffer = 0
        self._jump_cooldown = 0
        self._eye_height = EYE_HEIGHT

    def on_enable(self):
        self.crosshair.enabled = True

    def on_disable(self):
        self.crosshair.enabled = False

    # ---- health and modes ------------------------------------------------

    def damage(self, amount, kind='generic'):
        """Hurt the player. Only survival mode can be hurt."""
        if self.mode != 'survival' or self.dead or amount <= 0:
            return
        if self._invulnerable > 0 and kind != 'void':
            return
        if self.armor_points and kind not in UNARMORED:
            amount = max(1, round(amount * (1 - 0.04 * self.armor_points)))
            if self.on_armor_hit:
                self.on_armor_hit()
        self.health = max(0, self.health - amount)
        self._invulnerable = INVULNERABLE_TIME
        self._since_damage = 0
        self.add_exhaustion(0.3)
        if self.on_hurt:
            self.on_hurt(kind, amount)
        if self.health <= 0:
            self.dead = True
            if self.on_death:
                self.on_death()

    def add_xp(self, amount):
        from xp import level_for
        before = level_for(self.xp)[0]
        self.xp += amount
        if self.on_xp_gain:
            self.on_xp_gain(level_for(self.xp)[0] > before)

    def heal(self, amount):
        self.health = min(MAX_HEALTH, self.health + amount)

    def add_exhaustion(self, amount):
        """Doing things makes you hungry: running, jumping, mining, fighting, swimming..."""
        if self.mode == 'survival':
            self.exhaustion += amount

    def eat(self, food, saturation):
        self.food = min(MAX_FOOD, self.food + food)
        self.saturation = min(self.food, self.saturation + saturation)    # saturation can never top your food

    def _hunger(self, dt):
        if self.mode != 'survival':
            return
        if self.exhaustion >= 4:
            self.exhaustion -= 4
            if self.saturation > 0:
                self.saturation = max(0.0, self.saturation - 1)
            else:
                self.food = max(0, self.food - 1)
        self.can_sprint = self.food > SPRINT_FOOD

        if self.food >= REGEN_FOOD and self.health < MAX_HEALTH:           # well fed: heal
            self._heal_timer += dt
            if self._heal_timer >= REGEN_SECONDS:
                self._heal_timer = 0
                self.heal(1)
                self.add_exhaustion(3)
        else:
            self._heal_timer = 0
        if self.food <= 0:                                                  # starving: slowly lose health
            self._starve_timer += dt
            if self._starve_timer >= STARVE_SECONDS:
                self._starve_timer = 0
                if self.health > 1:
                    self.damage(1, 'starve')
        else:
            self._starve_timer = 0

    def respawn(self, position=None):
        self.position = position or self.spawn
        self.health, self.air = MAX_HEALTH, MAX_AIR
        self.food, self.saturation, self.exhaustion = MAX_FOOD, 5.0, 0.0
        self.velocity_y = 0
        self.dead = False
        self.flying = self.mode == 'spectator'
        self._invulnerable = 2
        self._peak_y = self.y
        self.camera_pivot.rotation_x = 0

    def set_mode(self, mode):
        was_noclip = self.noclip
        self.mode = mode
        self.flying = mode == 'spectator'
        self.noclip = mode == 'spectator'
        self.velocity_y = 0
        self._peak_y = self.y
        if was_noclip and not self.noclip:
            self._get_out_of_blocks()
        if self.on_mode_change:
            self.on_mode_change(mode)

    def _get_out_of_blocks(self):
        """If spectator mode left us inside the ground, move up until there is room."""
        for _ in range(60):
            if not self._hits_block(self.x, self.y, self.z):
                return
            self.y += 1

    # ---- looking and aiming ----------------------------------------------

    def eyes_in_water(self):
        eye = camera.world_position
        return self.world.get((round(eye[0]), math.floor(eye[1] + .5), round(eye[2]))) == 'water'

    def look_ray(self):
        """(start, direction) of the line from the eyes through the crosshair."""
        d = camera.forward
        return tuple(camera.world_position), (d[0], d[1], d[2])

    def block_underfoot(self):
        return self.world.get((round(self.x), math.floor(self.y - 0.5 + 1e-3), round(self.z)))

    # ---- every frame -----------------------------------------------------

    def input(self, key):
        if key == 'w':                     # double-tap W to sprint
            now = perf_counter()
            if now - self._last_w_press < DOUBLE_TAP_TIME:
                self._sprint_latched = True
            self._last_w_press = now
        elif key == 'w up':
            self._sprint_latched = False
        if key == 'space':
            self._jump_buffer = JUMP_BUFFER
        # Double-tap Space to start or stop flying (creative mode)
        if key == 'space' and self.mode == 'creative':
            now = perf_counter()
            if now - self._last_space_press < 0.3:
                self.flying = not self.flying
                self.velocity_y = 0
            self._last_space_press = now

    def update(self):
        if self.dead:
            return
        dt = min(time.dt, 0.05)

        # Look around
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity[1]
        self.camera_pivot.rotation_x = clamp(
            self.camera_pivot.rotation_x - mouse.velocity[1] * self.mouse_sensitivity[0], -90, 90)

        if self.riding is not None:                          # sitting in a vehicle: it carries you
            self.position = self.riding.rider_position()
            self.velocity_y = 0
            self.velocity_xz = Vec3(0, 0, 0)
            self.grounded = True
            return
        direction = (self.forward * (held_keys['w'] - held_keys['s'])
                     + self.right * (held_keys['d'] - held_keys['a']))
        direction = Vec3(direction[0], 0, direction[2]).normalized()

        swimming = self.in_water() and not self.flying
        if self.flying:
            self._fly(dt, direction)
        else:
            self._walk(dt, direction, swimming)
        self._survival(dt, swimming)

    def _fly(self, dt, direction):
        self.sprinting = self.sneaking = False
        self.velocity_xz = Vec3(0, 0, 0)
        camera.fov += (self.base_fov - camera.fov) * min(1.0, 9 * dt)
        self.camera_pivot.y = EYE_HEIGHT
        self.move(0, direction[0] * FLY_SPEED * dt)
        self.move(2, direction[2] * FLY_SPEED * dt)
        up_or_down = held_keys['space'] - held_keys['left shift']
        blocked = self.move(1, up_or_down * FLY_VERTICAL_SPEED * dt)
        self.velocity_y = 0
        self.grounded = False
        if blocked and up_or_down < 0 and self.mode == 'creative':
            self.flying = False        # touched the ground: stop flying

    def on_ladder(self):
        spots = [(round(self.x), math.floor(self.y + 0.5 + dy), round(self.z)) for dy in (0.1, 0.9, 1.5)]
        return any(self.world.get(s) == 'ladder' for s in spots)

    def _supported(self, x, z):
        """Is there a block under the player's feet if they stood at (x, z)? (For sneaking at edges.)"""
        half = self.width / 2 - 0.02
        below = math.floor(self.y - 0.05 + 0.5)
        return any(self.world.is_solid((round(x + dx), below, round(z + dz))) for dx in (-half, half) for dz in (-half, half))

    def _walk(self, dt, direction, swimming):
        moving_forward = held_keys['w'] and not held_keys['s']
        self.sneaking = bool(held_keys['left shift']) and not swimming
        wants_sprint = (held_keys['left control'] or self._sprint_latched) and moving_forward
        self.sprinting = bool(wants_sprint and not self.sneaking and self.can_sprint and not self.dead)
        if direction.length() == 0:
            self.sprinting = False

        if self.sneaking:
            speed = SNEAK_SPEED
        elif self.sprinting:
            speed = SPRINT_SPEED
        else:
            speed = WALK_SPEED
        if swimming:
            speed *= 0.6
        if self.world.get((round(self.x), math.floor(self.y + 0.5 + 0.2), round(self.z))) == 'cobweb':
            speed *= 0.15                        # stuck in a cobweb
            self.velocity_y = max(self.velocity_y, -1.0)

        if self.grounded and self.world.get((round(self.x), math.floor(self.y - 0.5 + 0.5), round(self.z))) == 'soul_sand':
            speed *= 0.4                         # soul sand drags at your feet

        # Accelerate toward the speed we want: quickly on the ground, slowly in the air
        acceleration = WATER_ACCELERATION if swimming else GROUND_ACCELERATION if self.grounded else AIR_ACCELERATION
        wanted = direction * speed
        self.velocity_xz += (wanted - self.velocity_xz) * min(1.0, acceleration * dt)

        before = self.x, self.z
        for axis in (0, 2):
            step = self.velocity_xz[axis] * dt
            if self.sneaking and self.grounded:        # sneaking never walks you off an edge
                target = [self.x, self.z]
                target[0 if axis == 0 else 1] += step
                if not self._supported(*target):
                    self.velocity_xz[axis] = 0
                    continue
            if self.move(axis, step):
                self.velocity_xz[axis] = 0             # bumped into something
        moved = math.dist(before, (self.x, self.z))
        self.add_exhaustion(moved * (0.1 if self.sprinting else 0.015 if swimming else 0.0))
        self._make_sounds(dt, swimming, moved / dt if dt else 0)

        # Jumping (or swimming up). A jump pressed just before landing, or just after leaving
        # an edge, still counts; holding Space keeps jumping.
        self._jump_cooldown = max(0.0, self._jump_cooldown - dt)
        self._coyote = COYOTE_TIME if self.grounded else self._coyote - dt
        self._jump_buffer = JUMP_BUFFER if held_keys['space'] else self._jump_buffer - dt
        if swimming:
            if held_keys['space']:
                self.velocity_y = SWIM_SPEED
        elif self._jump_buffer > 0 and self._coyote > 0 and self._jump_cooldown <= 0:
            self.velocity_y = JUMP_SPEED
            self._jump_cooldown = JUMP_COOLDOWN
            self._coyote = self._jump_buffer = 0
            self.add_exhaustion(0.8 if self.sprinting else 0.2)
            if self.sprinting:                         # sprint-jumping carries you further
                self.velocity_xz += direction * SPRINT_JUMP_BOOST
        if self.on_ladder() and not swimming:
            # Climb with W or Space, hold Shift to stay put, otherwise slide down slowly
            if held_keys['w'] or held_keys['space']:
                self.velocity_y = 2.6
            elif held_keys['left shift']:
                self.velocity_y = 0
            else:
                self.velocity_y = max(self.velocity_y, -2.0)
            self.move(1, self.velocity_y * dt)
            self.grounded = False
            self._peak_y = self.y
        else:
            self.fall(dt)

        # The camera: lower when sneaking, wider when sprinting
        target_eye = SNEAK_EYE_HEIGHT if self.sneaking else EYE_HEIGHT
        self._eye_height += (target_eye - self._eye_height) * min(1.0, 14 * dt)
        self.camera_pivot.y = self._eye_height
        target_fov = self.base_fov * (SPRINT_FOV if self.sprinting else 1.0)
        camera.fov += (target_fov - camera.fov) * min(1.0, 9 * dt)

    def _survival(self, dt, swimming):
        """Falling, drowning, the void, and healing. (Only survival can actually be hurt.)"""
        self._invulnerable = max(0, self._invulnerable - dt)
        self._since_damage += dt

        # Fall damage: how far did we drop before landing?
        if self.flying or swimming:
            self._peak_y = self.y
        elif self.grounded:
            if not self._was_grounded:
                fallen = self._peak_y - self.y
                if fallen > SAFE_FALL:
                    self.damage(math.ceil(fallen - SAFE_FALL), 'fall')
            self._peak_y = self.y
        else:
            self._peak_y = max(self._peak_y, self.y)
        self._was_grounded = self.grounded

        # Cactus pricks
        for dx, dz in ((0.35, 0), (-0.35, 0), (0, 0.35), (0, -0.35), (0, 0)):
            if self.world.get((round(self.x + dx), math.floor(self.y + 0.9), round(self.z + dz))) == 'cactus':
                self.damage(1, 'cactus')
                break

        # Magma blocks scorch bare feet
        if (self.mode == 'survival' and self.grounded and not self.sneaking
                and self.world.get((round(self.x), math.floor(self.y - 0.5 + 0.5), round(self.z))) == 'magma_block'):
            self._magma_timer = getattr(self, '_magma_timer', 0) - dt
            if self._magma_timer <= 0:
                self.damage(1, 'magma')
                self._magma_timer = 0.8

        # Lava burns
        feet = (round(self.x), math.floor(self.y + 0.3 + 0.5), round(self.z))
        if self.world.get(feet) == 'lava' or self.world.get((feet[0], feet[1] + 1, feet[2])) == 'lava':
            self._lava_timer = getattr(self, '_lava_timer', 0) - dt
            if self._lava_timer <= 0:
                self.damage(4, 'lava')
                self._lava_timer = 0.5
                self._invulnerable = 0
            self.velocity_y = max(self.velocity_y, -1)

        # Drowning
        if self.mode == 'survival' and self.eyes_in_water():
            self.air = max(0, self.air - dt)
            if self.air == 0:
                self._drown_timer -= dt
                if self._drown_timer <= 0:
                    self.damage(2, 'drown')
                    self._drown_timer = 1
        else:
            self.air = min(MAX_AIR, self.air + dt * 5)
            self._drown_timer = 1

        # Out of the world
        if self.y < -20:
            if self.mode == 'survival':
                self.damage(MAX_HEALTH, 'void')
            else:
                self.position = self.spawn
                self.velocity_y = 0

        self._hunger(dt)

    def _make_sounds(self, dt, swimming, ground_speed):
        if swimming and not self._was_swimming and self.on_splash:
            self.on_splash()
        self._was_swimming = swimming

        if ground_speed < 0.5:
            self._step_timer = 0.15          # standing still: the next step comes quickly
            return
        self._step_timer -= dt
        if self._step_timer > 0:
            return
        self._step_timer = 1.9 / ground_speed        # about two steps per block walked
        if swimming:
            if self.on_swim:
                self.on_swim()
        elif self.grounded and self.on_step:
            below = self.block_underfoot()
            if below:
                self.on_step(below)
