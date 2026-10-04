"""Perlin noise: smooth random hills, and 'layers' of it (fractal noise).

Plain Perlin noise is one smooth wobble. Real-looking terrain comes from
adding several layers (octaves): each layer has twice the detail but half the
strength of the one before, so you get big shapes plus smaller and smaller bumps."""
import math
import random

_GRADIENTS = ((1, 1), (-1, 1), (1, -1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1))


def _fade(t):
    """Ease curve so the noise has no sharp creases between grid squares."""
    return t * t * t * (t * (t * 6 - 15) + 10)


class Perlin:
    def __init__(self, seed):
        order = list(range(256))
        random.Random(seed).shuffle(order)
        self.perm = order * 2     # a shuffled list of 0..255, used to pick a direction per grid corner

    def noise(self, x, y):
        """Smooth noise between about -1 and 1."""
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        xi, yi = xi & 255, yi & 255
        p = self.perm

        def corner(hash_value, dx, dy):
            gx, gy = _GRADIENTS[hash_value & 7]
            return gx * dx + gy * dy

        u, v = _fade(xf), _fade(yf)
        a, b = p[xi] + yi, p[xi + 1] + yi
        top = corner(p[a], xf, yf) * (1 - u) + corner(p[b], xf - 1, yf) * u
        bottom = corner(p[a + 1], xf, yf - 1) * (1 - u) + corner(p[b + 1], xf - 1, yf - 1) * u
        return top * (1 - v) + bottom * v

    def layers(self, x, y, count=4, persistence=0.5, lacunarity=2.0):
        """Add `count` layers of noise. Each layer has `lacunarity` times more
        detail and `persistence` times the strength of the previous one."""
        total = strength_sum = 0
        strength = frequency = 1
        for layer in range(count):
            total += strength * self.noise(x * frequency + layer * 31.7, y * frequency + layer * 17.3)
            strength_sum += strength
            strength *= persistence
            frequency *= lacunarity
        return total / strength_sum
