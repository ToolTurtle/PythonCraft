"""Light, like Minecraft's: every cell of air has a SKY light and a BLOCK light, each 0 to 15.

Sky light: 15 wherever nothing is overhead, and it spreads sideways and downward
into caves and under roofs, losing one level for every block it travels.
Block light: torches and glowing blocks give off light that spreads up to 14 blocks.

The light is worked out chunk by chunk, whenever a chunk's mesh is made. We look at
the chunk plus the chunks around it (so light can flow across the borders), and
do the spreading on whole arrays at once (numpy)."""
import numpy as np

from blocks import EMIT_TABLE, TRANSPARENT_TABLE
from chunk import CHUNK, HEIGHT

RING = 16            # how far around the chunk we look (one whole chunk)
SKY_SPREAD = 6       # how many blocks sky light creeps into the dark
BLOCK_SPREAD = 14


def padded_blocks(world, chunk, radius=RING):
    """The chunk's blocks with `radius` extra blocks on every side, taken from the chunks around it."""
    size = CHUNK + 2 * radius
    out = np.zeros((size, size, HEIGHT), dtype=np.uint8)
    reach = (radius + CHUNK - 1) // CHUNK
    for dx in range(-reach, reach + 1):
        for dz in range(-reach, reach + 1):
            other = world.chunk_at(chunk.cx + dx, chunk.cz + dz)
            x0, z0 = dx * CHUNK + radius, dz * CHUNK + radius
            sx0, sx1 = max(0, x0), min(size, x0 + CHUNK)
            sz0, sz1 = max(0, z0), min(size, z0 + CHUNK)
            if sx0 < sx1 and sz0 < sz1:
                out[sx0:sx1, sz0:sz1] = other.blocks[sx0 - x0:sx1 - x0, sz0 - z0:sz1 - z0]
    return out


def _spread(level, blocked, iterations, sources=None):
    """Let light flow into neighboring cells (one level weaker each step) until nothing changes."""
    for _ in range(iterations):
        best = level.copy()
        for axis in (0, 1, 2):
            low = [slice(None)] * 3
            high = [slice(None)] * 3
            low[axis], high[axis] = slice(1, None), slice(None, -1)
            best[tuple(low)] = np.maximum(best[tuple(low)], level[tuple(high)] - 1)
            low[axis], high[axis] = slice(None, -1), slice(1, None)
            best[tuple(low)] = np.maximum(best[tuple(low)], level[tuple(high)] - 1)
        best = np.where(blocked, 0, best)
        if sources is not None:
            best = np.maximum(best, sources)
        if np.array_equal(best, level):
            break
        level = best
    return level


def compute(P, sky_light=True):
    """Light for the 18 x 18 block area (the chunk plus a one-block rim) inside the padded array `P`.
    Returns (sky, block): arrays of 0-15, shape (18, 18, HEIGHT).
    The air high above the ground is always full of sunlight, so we only work on the part of the world
    that has blocks in it."""
    filled = (P != 0).any(axis=(0, 1))
    top = int(np.nonzero(filled)[0].max()) + 3 if filled.any() else 1
    top = min(top, HEIGHT)
    sky_part, block_part = _compute(P[:, :, :top], sky_light)
    sky = np.full((CHUNK + 2, CHUNK + 2, HEIGHT), 15 if sky_light else 0, dtype=np.uint8)
    block = np.zeros((CHUNK + 2, CHUNK + 2, HEIGHT), dtype=np.uint8)
    sky[:, :, :top] = sky_part
    block[:, :, :top] = block_part
    return sky, block


def _compute(P, sky_light=True):
    height = P.shape[2]
    c = RING - SKY_SPREAD                                   # the sky light only needs a smaller area
    area = P[c:RING + CHUNK + SKY_SPREAD, c:RING + CHUNK + SKY_SPREAD]
    opaque = ~TRANSPARENT_TABLE[area]

    overhead = np.cumsum(opaque[:, :, ::-1], axis=2)[:, :, ::-1] - opaque     # solid blocks above each cell
    sky = np.where((overhead == 0) & ~opaque, 15, 0).astype(np.int8)
    sky = _spread(sky, opaque, SKY_SPREAD) if sky_light else np.zeros_like(sky)
    ring = SKY_SPREAD - 1
    sky18 = sky[ring:ring + CHUNK + 2, ring:ring + CHUNK + 2]

    emit = EMIT_TABLE[P]
    block18 = np.zeros_like(sky18)
    if emit.any():
        heights = np.nonzero(emit.any(axis=(0, 1)))[0]
        y0, y1 = max(0, heights.min() - BLOCK_SPREAD), min(height, heights.max() + BLOCK_SPREAD + 1)
        sources = emit[:, :, y0:y1].astype(np.int8)
        blocked = ~TRANSPARENT_TABLE[P[:, :, y0:y1]]
        level = _spread(sources, blocked, BLOCK_SPREAD, sources)
        ring = RING - 1
        block18[:, :, y0:y1] = level[ring:ring + CHUNK + 2, ring:ring + CHUNK + 2]
    return sky18.astype(np.uint8), block18.astype(np.uint8)
