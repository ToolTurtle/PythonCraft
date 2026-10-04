"""Experience: glowing orbs that fly to you, and the level they add up to."""
import math
import random

from ursina import Entity, Vec3, color, destroy, time

PICKUP_RANGE = 6.5
GRAB_RANGE = 0.9


def level_for(points):
    """(level, progress 0-1 toward the next level) for a total number of experience points. (Minecraft's formula.)"""
    level = 0
    needed = lambda lv: 2 * lv + 7 if lv < 15 else 5 * lv - 38 if lv < 30 else 9 * lv - 158
    remaining = points
    while remaining >= needed(level):
        remaining -= needed(level)
        level += 1
    return level, remaining / needed(level)


def points_for_level(level):
    return level * level + 6 * level if level <= 16 else (2.5 * level * level - 40.5 * level + 360 if level <= 31 else 4.5 * level * level - 162.5 * level + 2220)


class Orb(Entity):
    def __init__(self, position, value):
        super().__init__(model='sphere', scale=0.18 + 0.03 * min(value, 6), color=color.rgb32(120, 255, 40), position=position)
        self.value = value
        self.velocity = Vec3(random.uniform(-1.5, 1.5), random.uniform(2, 4), random.uniform(-1.5, 1.5))
        self.age = 0


class ExperienceOrbs:
    def __init__(self, world, player, sound):
        self.world, self.player, self.sound = world, player, sound
        self.orbs = []

    def spawn(self, position, amount):
        """Drop `amount` experience as a few orbs."""
        amount = int(round(amount))
        while amount > 0:
            value = min(amount, random.choice((1, 1, 2, 3, 5)))
            self.orbs.append(Orb(position, value))
            amount -= value

    def update(self, dt):
        dt = min(dt, 0.05)
        p = self.player
        for orb in self.orbs[:]:
            orb.age += dt
            target = Vec3(p.x, p.y + 0.8, p.z)
            offset = target - orb.position
            distance = offset.length()
            if orb.age > 0.5 and distance < GRAB_RANGE and not p.dead:
                p.add_xp(orb.value)
                self.sound.play('random/orb', 0.4)
                self.orbs.remove(orb)
                destroy(orb)
                continue
            if distance < PICKUP_RANGE and orb.age > 0.5 and not p.dead:
                orb.velocity += offset.normalized() * 30 * dt                   # drawn toward the player
                orb.velocity *= 0.92
            else:
                orb.velocity.y -= 18 * dt
                if self.world.is_solid((round(orb.x), round(orb.y - 0.2), round(orb.z))) and orb.velocity.y < 0:
                    orb.velocity = Vec3(orb.velocity.x * 0.5, 0, orb.velocity.z * 0.5)
            orb.position += orb.velocity * dt
            if orb.age > 300:
                self.orbs.remove(orb)
                destroy(orb)
