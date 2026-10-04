"""Biomes: what the surface is made of and what grows on it. Add a new biome here."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Biome:
    name: str
    grass_color: tuple = (145, 189, 89)     # tints grass tops and the grass side fringe (R, G, B)
    foliage_color: tuple = (119, 171, 47)   # tints leaves
    water_color: tuple = (63, 118, 228)     # tints water
    surface: str = 'grass'                  # the top block
    filler: str = 'dirt'                    # the few blocks under it
    trees: tuple = ('oak',)                 # what can grow: 'oak', 'birch', 'spruce', 'cactus'
    frozen_water: bool = False              # the top layer of water is ice
    tree_chance: float = 0.002              # chance for each column to grow one

    @property
    def tints(self):
        return {'grass': self.grass_color, 'foliage': self.foliage_color, 'water': self.water_color}


PLAINS = Biome('Plains', tree_chance=0.002)
FOREST = Biome('Forest', trees=('oak', 'oak', 'birch'), tree_chance=0.03)
DESERT = Biome('Desert', surface='sand', filler='sand', trees=('cactus',), tree_chance=0.004)
SNOWY = Biome('Snowy Plains', surface='grass_snow', trees=('spruce',), frozen_water=True, tree_chance=0.006)
JUNGLE = Biome('Jungle', trees=('jungle', 'jungle', 'oak'), tree_chance=0.05)
SWAMP = Biome('Swamp', trees=('oak',), tree_chance=0.012)
TAIGA = Biome('Taiga', trees=('spruce',), tree_chance=0.04)
