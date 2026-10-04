"""The sky: time of day, sky color, sun, moon, stars and clouds.

Time is counted in "ticks" like Minecraft: a day is 24000 ticks.
    0 = sunrise    6000 = noon    12000 = sunset    18000 = midnight
The sun rises in the east (+x), crosses the sky, and sets in the west (-x)."""
import math
from pathlib import Path

import numpy as np
from panda3d.core import ColorBlendAttrib
from PIL import Image
from ursina import Entity, Mesh, Texture, Vec2, Vec3, camera, color, window, application, Vec4

TICKS_PER_DAY = 24000
DAY_SECONDS = 720            # how long a whole day lasts in real time (Minecraft: 1200)
SKY_DIR = Path(__file__).parent / 'assets' / 'textures' / 'sky'

DAY_COLOR = np.array([135, 206, 235], dtype=float)
NETHER_COLOR = np.array([46, 10, 10], dtype=float)
NIGHT_COLOR = np.array([8, 9, 22], dtype=float)
GLOW_COLOR = np.array([255, 105, 50], dtype=float)
SUN_DISTANCE = 220
CLOUD_HEIGHT = 135
CLOUD_CELL = 12              # a cloud pixel is this many blocks wide
CLOUD_REPEAT = 256 * CLOUD_CELL
MOON_PHASES = ['full_moon', 'waning_gibbous', 'third_quarter', 'waning_crescent',
               'new_moon', 'waxing_crescent', 'first_quarter', 'waxing_gibbous']

PHASES = {'Morning': 1000, 'Noon': 6000, 'Evening': 12000, 'Midnight': 18000}


def smoothstep(low, high, x):
    t = min(1.0, max(0.0, (x - low) / (high - low)))
    return t * t * (3 - 2 * t)


def _sprite_texture(name):
    """A sun or moon picture. (Its black background disappears because we draw it additively.)"""
    return Texture(Image.open(SKY_DIR / f'{name}.png').convert('RGBA'))


def _behind_everything(entity, glowing=False):
    entity.setBin('background', 0)
    if glowing:                      # add the picture's light to the sky, so black adds nothing
        entity.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one, ColorBlendAttrib.O_one))
    entity.setDepthWrite(False)
    entity.setDepthTest(False)
    entity.setLightOff()


class Sky:
    def __init__(self, time=1000.0, days=0):
        self.time = float(time)          # ticks since this morning began
        self.days = days                 # whole days gone by (for the moon's phase)
        self.speed = TICKS_PER_DAY / DAY_SECONDS
        self.frozen = False

        self.sun = Entity(model='quad', texture=_sprite_texture('sun'), scale=70, billboard=True)
        self.moon_textures = [_sprite_texture(n) for n in MOON_PHASES]
        self.moon = Entity(model='quad', texture=self.moon_textures[0], scale=55, billboard=True)
        for entity in (self.sun, self.moon):
            _behind_everything(entity, glowing=True)

        self.stars = Entity(model=self._star_mesh(500), color=color.white, double_sided=True)
        _behind_everything(self.stars)

        cloud_pixels = np.array(Image.open(SKY_DIR / 'clouds.png').convert('L'))
        rgba = np.zeros((256, 256, 4), dtype=np.uint8)
        rgba[..., :3] = 255
        rgba[..., 3] = np.where(cloud_pixels > 0, 255, 0)
        texture = Texture(Image.fromarray(rgba))
        self.clouds = Entity(model='quad', texture=texture, rotation_x=90, scale=2200, double_sided=True,
                             texture_scale=Vec2(2200 / CLOUD_REPEAT, 2200 / CLOUD_REPEAT))
        self.clouds.setBin('transparent', 5)
        self.clouds.setDepthWrite(False)
        self.cloud_drift = 0.0

        self.dimension = 'overworld'
        self.dim = 0.0                   # 0 to 1: how much bad weather darkens the sky (set by the pycraftWorld weather)
        self.flash = 0.0                 # a lightning flash, fading
        self.daylight = 1.0
        self.sky_color = DAY_COLOR / 255
        self.update(0, camera.world_position)

    @staticmethod
    def _star_mesh(count):
        """Little squares scattered over the whole sky, each facing the middle."""
        rng = np.random.default_rng(12345)
        directions = rng.normal(size=(count, 3))
        directions /= np.linalg.norm(directions, axis=1)[:, None]
        helper = np.where(np.abs(directions[:, 1:2]) > 0.9, np.array([[1, 0, 0]]), np.array([[0, 1, 0]]))
        right = np.cross(directions, helper)
        right /= np.linalg.norm(right, axis=1)[:, None]
        up = np.cross(right, directions)
        size = rng.uniform(0.9, 2.2, size=(count, 1))
        centers = directions * 300
        corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        vertices = np.stack([centers + (right * dx + up * dy) * size for dx, dy in corners], axis=1).reshape(-1, 3)
        quads = [(i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 3) for i in range(count)]
        return Mesh(vertices=[tuple(v) for v in vertices], triangles=quads)

    # ---- time --------------------------------------------------------------

    @property
    def fraction(self):
        return self.time / TICKS_PER_DAY

    @property
    def is_night(self):
        return self.daylight < 0.3

    def set_time(self, ticks):
        self.time = float(ticks) % TICKS_PER_DAY

    def phase_name(self):
        t = self.time
        if t < 1000 or t >= 23000:
            return 'Sunrise'
        if t < 11000:
            return 'Day'
        if t < 13000:
            return 'Sunset'
        return 'Night'

    # ---- every frame -------------------------------------------------------

    def set_dimension(self, name):
        """The Nether has no sun, moon, stars or clouds: just a dim red haze."""
        self.dimension = name
        shown = name == 'overworld'
        for entity in (self.sun, self.moon, self.stars, self.clouds):
            entity.enabled = shown

    def update(self, dt, eye):
        if self.dimension == 'nether':
            if not self.frozen:                               # (the overworld's clock keeps ticking)
                self.time += dt * self.speed
                if self.time >= TICKS_PER_DAY:
                    self.time -= TICKS_PER_DAY
                    self.days += 1
            self.daylight = 0.0
            self.sky_color = NETHER_COLOR / 255
            window.color = color.Color(*self.sky_color, 1)
            render = application.base.render
            render.set_shader_input('daylight', 1.0)
            render.set_shader_input('ambient', 0.34)
            render.set_shader_input('fog_color', Vec4(*self.sky_color, 1))
            return
        if not self.frozen:
            self.time += dt * self.speed
            if self.time >= TICKS_PER_DAY:
                self.time -= TICKS_PER_DAY
                self.days += 1

        angle = self.fraction * 2 * math.pi
        elevation = math.sin(angle)                       # 1 at noon, -1 at midnight
        self.daylight = smoothstep(-0.12, 0.3, elevation)

        base = NIGHT_COLOR + (DAY_COLOR - NIGHT_COLOR) * self.daylight
        glow = max(0.0, 1 - abs(elevation) / 0.28) ** 2                # sunrise and sunset glow
        base = base + (GLOW_COLOR - base) * glow * 0.85
        base = base * (1 - 0.45 * self.dim)
        if self.flash > 0:
            base = base + (255 - base) * min(1.0, self.flash)
            self.flash = max(0.0, self.flash - dt * 4)
        self.sky_color = base / 255
        window.color = color.Color(*self.sky_color, 1)

        eye = Vec3(*eye)
        sun_direction = Vec3(math.cos(angle), math.sin(angle), 0.18)
        self.sun.position = eye + sun_direction.normalized() * SUN_DISTANCE
        self.moon.position = eye - sun_direction.normalized() * SUN_DISTANCE
        self.moon.texture = self.moon_textures[self.days % 8]
        self.stars.position = eye
        self.stars.rotation_z = -math.degrees(angle)
        night = 1 - smoothstep(-0.2, 0.1, elevation)
        self.stars.color = color.Color(1, 1, 1, night * 0.9)

        self.cloud_drift += dt * 1.6
        self.clouds.position = (eye.x, CLOUD_HEIGHT, eye.z)
        self.clouds.texture_offset = Vec2((eye.x - self.cloud_drift) / CLOUD_REPEAT, -eye.z / CLOUD_REPEAT)
        cloud_light = (0.25 + 0.75 * self.daylight) * (1 - 0.4 * self.dim)
        tint = np.array([1.0, 1.0, 1.0]) * cloud_light
        tint = tint + (GLOW_COLOR / 255 - tint) * glow * 0.3
        self.clouds.color = color.Color(*tint, 0.85)

        render = application.base.render
        # moonlight keeps the nights from being pitch black
        render.set_shader_input('daylight', float((0.16 + 0.84 * self.daylight) * (1 - 0.3 * self.dim)))
        render.set_shader_input('ambient', 0.06)
        render.set_shader_input('fog_color', Vec4(*self.sky_color, 1))
