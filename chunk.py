"""A chunk: a 16 x 16 column of the world, from the bottom (y = 0) up to HEIGHT."""
import numpy as np

CHUNK = 16
HEIGHT = 128


class Chunk:
    __slots__ = ('cx', 'cz', 'blocks', 'heights', 'biomes', 'skylight', 'blocklight')

    def __init__(self, cx, cz, blocks, heights, biomes):
        self.cx, self.cz = cx, cz
        self.blocks = blocks          # uint8 array [x, z, y] of block ids (0 = air)
        self.heights = heights        # int array [x, z]: height of the land surface in each column
        self.biomes = biomes          # int array [x, z]: which biome (index into terrain.BIOMES)
        self.skylight = None          # uint8 [x, z, y] 0-15, filled in when the chunk is meshed
        self.blocklight = None
