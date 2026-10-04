"""Weather for a world: rain, snow and storms. Rain falls around the player (but not under a roof),
the sky gets darker, and a storm adds lightning."""
import math
import random

from ursina import Entity, Vec3, color, destroy

RADIUS = 13
INTENSITY = {'clear': 0.0, 'rain': 0.6, 'snow': 0.55, 'storm': 1.0}
DARKNESS = {'clear': 0.0, 'rain': 0.4, 'snow': 0.25, 'storm': 0.75}
MAX_DROPS = 260


class Weather:
    def __init__(self, sky, player, world, sound=None):
        self.sky, self.player, self.world, self.sound = sky, player, world, sound
        self.kind = 'clear'
        self.level = 0.0                     # fades in and out
        self.drops = []
        self.lightning_timer = random.uniform(6, 14)
        self.thunder_in = None

    def set(self, kind):
        if kind not in INTENSITY:
            raise ValueError(f"weather must be one of {', '.join(repr(k) for k in INTENSITY)}.")
        self.kind = kind

    def _make_drop(self):
        snow = self.kind == 'snow'
        drop = Entity(model='quad', double_sided=True, billboard=True, enabled=False,
                      scale=(0.09, 0.09) if snow else (0.025, 0.55),
                      color=color.rgba32(245, 245, 255, 230) if snow else color.rgba32(160, 185, 255, 150))
        drop.snow = snow
        drop.sway = random.uniform(0, 6)
        return drop

    def _sheltered(self, x, y, z):
        """Is there a roof over this spot? (The sky light under a roof is less than full.)"""
        sky, _block = self.world.light_at((round(x), math.floor(y), round(z)))
        return sky < 0.99

    def _respawn(self, drop):
        p = self.player
        angle, distance = random.uniform(0, 6.2832), RADIUS * math.sqrt(random.random())
        x, z = p.x + math.cos(angle) * distance, p.z + math.sin(angle) * distance
        y = p.y + random.uniform(4, 11)
        drop.position = Vec3(x, y, z)
        drop.enabled = not self._sheltered(x, p.y + 1, z)
        drop.floor = p.y - 3

    def update(self, dt):
        dt = min(dt, 0.05)
        kind = self.kind if not self.world.nether else 'clear'
        self.level += (INTENSITY[kind] - self.level) * min(1.0, dt * 0.7)
        self.sky.dim += (DARKNESS[kind] - self.sky.dim) * min(1.0, dt * 0.7)

        wanted = int(MAX_DROPS * self.level) if kind != 'clear' or self.level > 0.02 else 0
        snow = kind == 'snow'
        while len(self.drops) < wanted:
            drop = self._make_drop()
            self._respawn(drop)
            self.drops.append(drop)
        while len(self.drops) > wanted:
            destroy(self.drops.pop())
        for drop in self.drops:
            if drop.snow != snow and kind != 'clear':          # the weather changed kind: remake the pieces
                drop.snow = snow
                drop.scale = (0.09, 0.09) if snow else (0.025, 0.55)
                drop.color = color.rgba32(245, 245, 255, 230) if snow else color.rgba32(160, 185, 255, 150)
            speed = 3.0 if drop.snow else 22.0
            drop.y -= speed * dt
            if drop.snow:
                drop.sway += dt
                drop.x += math.sin(drop.sway * 1.7) * dt * 0.8
            if drop.y < drop.floor or math.hypot(drop.x - self.player.x, drop.z - self.player.z) > RADIUS + 3:
                self._respawn(drop)

        if kind == 'storm':
            self.lightning_timer -= dt
            if self.lightning_timer <= 0:
                self.lightning_timer = random.uniform(5, 14)
                self.sky.flash = 0.9
                self.thunder_in = random.uniform(0.3, 1.6)
            if self.thunder_in is not None:
                self.thunder_in -= dt
                if self.thunder_in <= 0:
                    self.thunder_in = None
                    if self.sound is not None:
                        self.sound.play('random/explode', 0.35, pitch_variation=0.3)

    def clear(self):
        for drop in self.drops:
            destroy(drop)
        self.drops.clear()
