"""Arrows flying through the air."""
import math

from ursina import Entity, Vec3, color, destroy, time

GRAVITY = 14
LIFETIME = 20            # seconds before an arrow lying in a wall disappears


class Arrow(Entity):
    def __init__(self, position, velocity, owner, damage):
        super().__init__(model='cube', scale=(0.06, 0.06, 0.7), color=color.rgb32(210, 200, 170), position=position)
        self.velocity = Vec3(*velocity)
        self.owner = owner               # 'player' or 'monster'
        self.damage = damage
        self.age = 0
        self.stuck = False
        self.look_at(self.position + self.velocity)


class Fireball(Entity):
    def __init__(self, position, velocity, small=False):
        super().__init__(model='cube', scale=0.3 if small else 0.8, color=color.rgb32(255, 150, 40), position=position)
        self.small = small               # a blaze's fireball: it burns and hurts but does not blow a hole
        self.velocity = Vec3(*velocity)
        self.age = 0


class Projectiles:
    def __init__(self, world, player, mobs):
        self.world, self.player, self.mobs = world, player, mobs
        self.arrows = []
        self.fireballs = []
        self.sound = None
        self.on_player_hit = None        # called with (damage, direction) when an arrow hits the player

    def shoot(self, origin, direction, speed, owner, damage, spread=0.0):
        import random
        d = Vec3(*direction).normalized() + Vec3(random.uniform(-spread, spread), random.uniform(-spread, spread),
                                                   random.uniform(-spread, spread))
        arrow = Arrow(origin, d.normalized() * speed, owner, damage)
        self.arrows.append(arrow)
        if self.sound:
            self.sound.play('random/bow', 0.6)
        return arrow

    def shoot_fireball(self, origin, direction, speed=11, small=False):
        ball = Fireball(origin, Vec3(*direction).normalized() * speed, small)
        self.fireballs.append(ball)
        if self.sound:
            self.sound.play('random/fuse', 0.6)

    def _update_fireballs(self, dt):
        import random
        p = self.player
        for ball in self.fireballs[:]:
            ball.age += dt
            ball.position += ball.velocity * dt
            ball.rotation_y += 200 * dt
            spot = (round(ball.x), round(ball.y), round(ball.z))
            hit_player = (not p.dead and p.mode == 'survival' and abs(ball.x - p.x) < 0.7 and abs(ball.z - p.z) < 0.7
                          and p.y - 0.4 < ball.y < p.y + 2.2)
            if hit_player or self.world.is_solid(spot) or ball.age > 12:
                center, velocity, expired, small = (ball.x, ball.y, ball.z), ball.velocity, ball.age > 12, ball.small
                self.fireballs.remove(ball)
                destroy(ball)
                if expired:
                    continue
                if not small:
                    self.world.explode(center, 1.6)
                if self.sound:
                    self.sound.play('random/explode' if not small else 'random/fire', 0.8)
                for _ in range(3):                                   # the blast sets things alight
                    cell = (spot[0] + random.randint(-1, 1), spot[1] + random.randint(0, 1), spot[2] + random.randint(-1, 1))
                    if self.world.get(cell) is None and self.world.is_solid((cell[0], cell[1] - 1, cell[2])):
                        self.world.set_fluid(cell, 'fire')
                        self.world.fires.add(cell)
                self.world.flush_dirty(budget=0.01)
                if hit_player:
                    self.player.damage(4 if small else 6, 'fireball')
                    away = Vec3(velocity.x, 0, velocity.z).normalized()
                    p.velocity_xz += away * 5

    def update(self, dt):
        dt = min(dt, 0.05)
        self._update_fireballs(dt)
        for arrow in self.arrows[:]:
            arrow.age += dt
            if arrow.age > LIFETIME:
                self._remove(arrow)
                continue
            if arrow.stuck:
                continue
            arrow.velocity.y -= GRAVITY * dt
            steps = max(1, int(arrow.velocity.length() * dt / 0.4))       # small steps so it can't skip through a wall
            for _ in range(steps):
                arrow.position += arrow.velocity * dt / steps
                spot = (round(arrow.x), round(arrow.y), round(arrow.z))
                if self.world.is_solid(spot):
                    arrow.stuck = True
                    if self.sound:
                        self.sound.play('random/bowhit', 0.5)
                    break
                if self._hit_creature(arrow):
                    self._remove(arrow)
                    break
            else:
                arrow.look_at(arrow.position + arrow.velocity)

    def _hit_creature(self, arrow):
        if arrow.owner == 'monster':
            p = self.player
            if (not p.dead and p.mode == 'survival' and abs(arrow.x - p.x) < 0.45 and abs(arrow.z - p.z) < 0.45
                    and p.y - 0.1 < arrow.y < p.y + 1.95):
                if self.on_player_hit:
                    self.on_player_hit(arrow.damage, arrow.velocity.normalized())
                return True
        else:
            for mob in self.mobs.mobs:
                half = mob.width / 2 + 0.1
                if abs(arrow.x - mob.x) < half and abs(arrow.z - mob.z) < half and mob.y - 0.1 < arrow.y < mob.y + mob.height + 0.1:
                    mob.hurt(self.player.position, damage=arrow.damage)
                    if self.sound:
                        self.sound.play('random/bowhit', 0.5)
                    return True
        return False

    def _remove(self, arrow):
        self.arrows.remove(arrow)
        destroy(arrow)

    def clear(self):
        for arrow in self.arrows[:]:
            self._remove(arrow)
        for ball in self.fireballs[:]:
            self.fireballs.remove(ball)
            destroy(ball)
