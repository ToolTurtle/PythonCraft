"""Perlin noise: smooth random hills, and 'layers' of it (fractal noise).

Plain Perlin noise is one smooth wobble. Real-looking terrain comes from
adding several layers (octaves): each layer has twice the detail but half the
strength of the one before, so you get big shapes plus smaller and smaller bumps.

Everything works on whole grids of points at once (numpy), which makes it fast
enough to invent a whole chunk of land in a few milliseconds."""
import numpy as np

_GRADIENTS_2D = np.array([(1, 1), (-1, 1), (1, -1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)], dtype=np.float64)
_GRADIENTS_3D = np.array([(1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0), (1, 0, 1), (-1, 0, 1), (1, 0, -1),
                          (-1, 0, -1), (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1)], dtype=np.float64)


def _fade(t):
    """Ease curve so the noise has no sharp creases between grid squares."""
    return t * t * t * (t * (t * 6 - 15) + 10)


class Perlin:
    def __init__(self, seed):
        order = np.arange(256)
        np.random.default_rng(seed).shuffle(order)
        self.perm = np.concatenate([order, order])     # a shuffled list of 0..255 that picks a direction per grid corner

    def noise(self, x, y):
        """Smooth noise between about -1 and 1. `x` and `y` can be single numbers or whole arrays."""
        x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
        xf, yf = np.floor(x), np.floor(y)
        dx, dy = x - xf, y - yf
        xi, yi = xf.astype(np.int64) & 255, yf.astype(np.int64) & 255
        p = self.perm

        def corner(hash_values, ox, oy):
            gradient = _GRADIENTS_2D[hash_values & 7]
            return gradient[..., 0] * ox + gradient[..., 1] * oy

        u, v = _fade(dx), _fade(dy)
        a, b = p[xi] + yi, p[xi + 1] + yi
        top = corner(p[a], dx, dy) * (1 - u) + corner(p[b], dx - 1, dy) * u
        bottom = corner(p[a + 1], dx, dy - 1) * (1 - u) + corner(p[b + 1], dx - 1, dy - 1) * u
        return top * (1 - v) + bottom * v

    def layers(self, x, y, count=4, persistence=0.5, lacunarity=2.0):
        """Add `count` layers of noise. Each layer has `lacunarity` times more
        detail and `persistence` times the strength of the previous one."""
        x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
        total = 0.0
        strength_sum = 0.0
        strength = frequency = 1.0
        for layer in range(count):
            total = total + strength * self.noise(x * frequency + layer * 31.7, y * frequency + layer * 17.3)
            strength_sum += strength
            strength *= persistence
            frequency *= lacunarity
        return total / strength_sum

    def noise3(self, x, y, z):
        """3D Perlin noise (used for caves)."""
        x, y, z = (np.asarray(a, dtype=np.float64) for a in (x, y, z))
        xf, yf, zf = np.floor(x), np.floor(y), np.floor(z)
        dx, dy, dz = x - xf, y - yf, z - zf
        xi, yi, zi = xf.astype(np.int64) & 255, yf.astype(np.int64) & 255, zf.astype(np.int64) & 255
        p = self.perm
        u, v, w = _fade(dx), _fade(dy), _fade(dz)

        def corner(ix, iy, iz, ox, oy, oz):
            h = p[p[p[xi + ix] + yi + iy] + zi + iz] % 12
            g = _GRADIENTS_3D[h]
            return g[..., 0] * ox + g[..., 1] * oy + g[..., 2] * oz

        def lerp(a, b, t):
            return a + (b - a) * t

        x00 = lerp(corner(0, 0, 0, dx, dy, dz), corner(1, 0, 0, dx - 1, dy, dz), u)
        x10 = lerp(corner(0, 1, 0, dx, dy - 1, dz), corner(1, 1, 0, dx - 1, dy - 1, dz), u)
        x01 = lerp(corner(0, 0, 1, dx, dy, dz - 1), corner(1, 0, 1, dx - 1, dy, dz - 1), u)
        x11 = lerp(corner(0, 1, 1, dx, dy - 1, dz - 1), corner(1, 1, 1, dx - 1, dy - 1, dz - 1), u)
        return lerp(lerp(x00, x10, v), lerp(x01, x11, v), w)


def smoothstep(low, high, x):
    t = np.clip((x - low) / (high - low), 0.0, 1.0)
    return t * t * (3 - 2 * t)
