"""Block types. To add a new block, add an entry to BLOCKS.

Each face is a list of texture names (files in assets/textures, without .png).
When a face has several names they are layered on top of each other, so the
grass side is the dirt side with the grass overlay drawn over it.
A layer can be ('name', 'grass' / 'foliage' / 'water' / 'birch' / 'spruce') to be
colored (these textures are gray in the files).

Use 'all' when every face looks the same, or give 'top', 'bottom' and 'side'.
'fallback' is the color shown for any texture file that is missing.

Mining (like Minecraft):
  hardness      how tough it is. Time to mine = hardness x a factor, divided by the tool speed.
  tool          the best tool for it: 'pickaxe', 'axe' or 'shovel'
  tier          the weakest tool that makes it DROP something: 1 wood, 2 stone, 3 iron, 4 diamond
  hardness=None cannot be broken (bedrock)

Other optional settings:
  transparent=True   you can see through it, so the faces of its neighbors stay visible
  solid=False        you walk through it (water)
  translucent=True   drawn semi-see-through, in its own mesh (water)
  light=15           it glows: how far its light reaches (0-15)
  shape='torch'      not a full cube: 'torch' (thin stick) or 'cross' (plants)
  orient='attach'    a torch: remembers which block it hangs on (floor or wall)
  placeable=False    cannot be held and placed (water, bedrock, snowy grass)
  gravity=True       falls when nothing is under it (sand, gravel)
  orient='facing6'     six directions (pistons): which way the front points, including up and down
  orient='horizontal'  the front turns toward you when placed (furnace, pumpkin)
  orient='axis'        lies along the face you click (logs)
  front/back/left/right/north/south/east/west   textures for single sides (see facing.py)
  drops='name'       what it drops when broken (default: itself); drops=None drops nothing
"""
from ursina import color

BLOCKS = {
    'grass': dict(
        hardness=0.6, tool='shovel', drops='dirt',
        top=[('grass_block_top', 'grass')],
        bottom=['dirt'],
        side=['grass_block_side', ('grass_block_side_overlay', 'grass')],
        fallback=color.green,
    ),
    'grass_snow': dict(hardness=0.6, tool='shovel', drops='dirt', top=['snow'], bottom=['dirt'],
                       side=['grass_block_snow'], fallback=color.white, placeable=False),
    'dirt': dict(hardness=0.5, tool='shovel', all=['dirt'], fallback=color.brown),
    'stone': dict(hardness=1.5, tool='pickaxe', tier=1, drops='cobblestone', all=['stone'], fallback=color.gray),
    'cobblestone': dict(hardness=2.0, tool='pickaxe', tier=1, all=['cobblestone'], fallback=color.gray),
    'mossy_cobblestone': dict(hardness=2.0, tool='pickaxe', tier=1, all=['mossy_cobblestone'], fallback=color.gray),
    'stone_bricks': dict(hardness=1.5, tool='pickaxe', tier=1, all=['stone_bricks'], fallback=color.gray),
    'bricks': dict(hardness=2.0, tool='pickaxe', tier=1, all=['bricks'], fallback=color.red),
    'sand': dict(hardness=0.5, tool='shovel', gravity=True, all=['sand'], fallback=color.yellow),
    'sandstone': dict(hardness=0.8, tool='pickaxe', tier=1, top=['sandstone_top'], bottom=['sandstone_bottom'],
                      side=['sandstone'], fallback=color.yellow),
    'gravel': dict(hardness=0.6, tool='shovel', gravity=True, all=['gravel'], fallback=color.gray),
    'clay': dict(hardness=0.6, tool='shovel', all=['clay'], fallback=color.light_gray),
    'snow': dict(hardness=0.2, tool='shovel', all=['snow'], fallback=color.white),
    'ice': dict(hardness=0.5, tool='pickaxe', drops=None, all=['ice'], fallback=color.cyan, transparent=True),
    'coal_ore': dict(hardness=3.0, tool='pickaxe', tier=1, drops='coal', all=['coal_ore'], fallback=color.dark_gray),
    'iron_ore': dict(hardness=3.0, tool='pickaxe', tier=2, all=['iron_ore'], fallback=color.orange),
    'gold_ore': dict(hardness=3.0, tool='pickaxe', tier=3, all=['gold_ore'], fallback=color.gold),
    'diamond_ore': dict(hardness=3.0, tool='pickaxe', tier=3, drops='diamond', all=['diamond_ore'], fallback=color.cyan),
    'emerald_ore': dict(hardness=3.0, tool='pickaxe', tier=3, drops='emerald', all=['emerald_ore'], fallback=color.green),
    'emerald_block': dict(hardness=5.0, tool='pickaxe', tier=3, all=['emerald_block'], fallback=color.green),
    'lapis_ore': dict(hardness=3.0, tool='pickaxe', tier=2, drops='lapis_lazuli', all=['lapis_ore'], fallback=color.blue),
    'lapis_block': dict(hardness=3.0, tool='pickaxe', tier=2, all=['lapis_block'], fallback=color.blue),
    'enchanting_table': dict(hardness=5.0, tool='pickaxe', tier=1, shape='enchtable', transparent=True,
                             top=['enchanting_table_top'], bottom=['enchanting_table_bottom'],
                             side=['enchanting_table_side'], fallback=color.red),
    'coal_block': dict(hardness=5.0, tool='pickaxe', tier=1, all=['coal_block'], fallback=color.black),
    'iron_block': dict(hardness=5.0, tool='pickaxe', tier=2, all=['iron_block'], fallback=color.light_gray),
    'gold_block': dict(hardness=3.0, tool='pickaxe', tier=3, all=['gold_block'], fallback=color.gold),
    'diamond_block': dict(hardness=5.0, tool='pickaxe', tier=3, all=['diamond_block'], fallback=color.cyan),
    'bedrock': dict(hardness=None, all=['bedrock'], fallback=color.black, placeable=False),
    'oak_log': dict(hardness=2.0, tool='axe', orient='axis', top=['oak_log_top'], bottom=['oak_log_top'], side=['oak_log'],
                    fallback=color.dark_gray),
    'birch_log': dict(hardness=2.0, tool='axe', orient='axis', top=['birch_log_top'], bottom=['birch_log_top'], side=['birch_log'],
                      fallback=color.white),
    'spruce_log': dict(hardness=2.0, tool='axe', orient='axis', top=['spruce_log_top'], bottom=['spruce_log_top'],
                       side=['spruce_log'], fallback=color.dark_gray),
    'jungle_log': dict(hardness=2.0, tool='axe', orient='axis', top=['jungle_log_top'], bottom=['jungle_log_top'],
                       side=['jungle_log'], fallback=color.brown),
    'jungle_planks': dict(hardness=2.0, tool='axe', all=['jungle_planks'], fallback=color.orange),
    'jungle_leaves': dict(hardness=0.2, drops=None, all=[('jungle_leaves', 'foliage')], fallback=color.lime, transparent=True),
    'jungle_sapling': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['jungle_sapling'],
                           plant_on=('grass', 'dirt', 'farmland', 'podzol'), sapling='jungle', fallback=color.lime),
    'podzol': dict(hardness=0.5, tool='shovel', drops='dirt', top=['podzol_top'], bottom=['dirt'], side=['podzol_side'],
                   fallback=color.brown),
    'oak_planks': dict(hardness=2.0, tool='axe', all=['oak_planks'], fallback=color.orange),
    'birch_planks': dict(hardness=2.0, tool='axe', all=['birch_planks'], fallback=color.yellow),
    'spruce_planks': dict(hardness=2.0, tool='axe', all=['spruce_planks'], fallback=color.brown),
    'oak_leaves': dict(hardness=0.2, drops=None, all=[('oak_leaves', 'foliage')], fallback=color.lime,
                       transparent=True),
    'birch_leaves': dict(hardness=0.2, drops=None, all=[('birch_leaves', 'birch')], fallback=color.lime,
                         transparent=True),
    'spruce_leaves': dict(hardness=0.2, drops=None, all=[('spruce_leaves', 'spruce')], fallback=color.green,
                          transparent=True),
    'glass': dict(hardness=0.3, drops=None, all=['glass'], fallback=color.white, transparent=True),
    'cactus': dict(hardness=0.4, all=['cactus_side'], top=['cactus_top'], bottom=['cactus_bottom'],
                   side=['cactus_side'], fallback=color.green),
    'bookshelf': dict(hardness=1.5, tool='axe', top=['oak_planks'], bottom=['oak_planks'], side=['bookshelf'],
                      fallback=color.brown),
    'crafting_table': dict(hardness=2.5, tool='axe', top=['crafting_table_top'], bottom=['oak_planks'],
                           side=['crafting_table_side'], south=['crafting_table_front'],
                           west=['crafting_table_front'], fallback=color.brown),
    'furnace': dict(hardness=3.5, tool='pickaxe', tier=1, orient='horizontal', top=['furnace_top'],
                    bottom=['furnace_top'], side=['furnace_side'], front=['furnace_front'], fallback=color.gray),
    'pumpkin': dict(hardness=1.0, tool='axe', orient='horizontal', top=['pumpkin_top'], bottom=['pumpkin_top'],
                    side=['pumpkin_side'], front=['carved_pumpkin'], fallback=color.orange),
    'jack_o_lantern': dict(hardness=1.0, tool='axe', orient='horizontal', light=15, top=['pumpkin_top'],
                           bottom=['pumpkin_top'], side=['pumpkin_side'], front=['jack_o_lantern'],
                           fallback=color.orange),
    'glowstone': dict(hardness=0.3, drops='glowstone', light=15, all=['glowstone'], fallback=color.yellow),
    'torch': dict(hardness=0.0, light=14, shape='torch', orient='attach', transparent=True, solid=False,
                  all=['torch'], fallback=color.yellow),
    'white_wool': dict(hardness=0.8, all=['white_wool'], fallback=color.white),
    'tnt': dict(hardness=0.0, redstone='tnt', top=['tnt_top'], bottom=['tnt_bottom'], side=['tnt_side'], fallback=color.red),
    'chest': dict(hardness=2.5, tool='axe', orient='horizontal', top=['chest_top'], bottom=['chest_top'],
                  side=['chest_side'], front=['chest_front'], fallback=color.brown),
    'oak_slab': dict(hardness=1.5, tool='axe', shape='slab', transparent=True, all=['oak_planks'], fallback=color.gray),
    'cobblestone_slab': dict(hardness=1.5, tool='pickaxe', tier=1, shape='slab', transparent=True, all=['cobblestone'], fallback=color.gray),
    'stone_slab': dict(hardness=1.5, tool='pickaxe', tier=1, shape='slab', transparent=True, all=['stone'], fallback=color.gray),
    'sandstone_slab': dict(hardness=1.5, tool='pickaxe', tier=1, shape='slab', transparent=True, all=['sandstone'], fallback=color.gray),
    'brick_slab': dict(hardness=1.5, tool='pickaxe', tier=1, shape='slab', transparent=True, all=['bricks'], fallback=color.gray),
    'stone_brick_slab': dict(hardness=1.5, tool='pickaxe', tier=1, shape='slab', transparent=True, all=['stone_bricks'], fallback=color.gray),
    'oak_stairs': dict(hardness=1.5, tool='axe', shape='stairs', orient='horizontal', transparent=True, all=['oak_planks'], fallback=color.gray),
    'cobblestone_stairs': dict(hardness=1.5, tool='pickaxe', tier=1, shape='stairs', orient='horizontal', transparent=True, all=['cobblestone'], fallback=color.gray),
    'brick_stairs': dict(hardness=1.5, tool='pickaxe', tier=1, shape='stairs', orient='horizontal', transparent=True, all=['bricks'], fallback=color.gray),
    'stone_brick_stairs': dict(hardness=1.5, tool='pickaxe', tier=1, shape='stairs', orient='horizontal', transparent=True, all=['stone_bricks'], fallback=color.gray),
    'sandstone_stairs': dict(hardness=1.5, tool='pickaxe', tier=1, shape='stairs', orient='horizontal', transparent=True, all=['sandstone'], fallback=color.gray),
    'oak_fence': dict(hardness=2.0, tool='axe', shape='fence', transparent=True, all=['oak_planks'], fallback=color.orange),
    'glass_pane': dict(hardness=0.3, drops=None, shape='pane', transparent=True, all=['glass'], fallback=color.white),
    'ladder': dict(hardness=0.4, tool='axe', shape='ladder', orient='attach', transparent=True, solid=False,
                   all=['ladder'], fallback=color.brown),
    'oak_door_b': dict(hardness=3.0, tool='axe', drops='oak_door', redstone='door', shape='door', orient='horizontal', transparent=True,
                       all=['oak_door_bottom'], fallback=color.brown, placeable=False),
    'oak_door_t': dict(hardness=3.0, tool='axe', drops='oak_door', shape='door', orient='horizontal', transparent=True,
                       all=['oak_door_top'], fallback=color.brown, placeable=False),
    'farmland': dict(hardness=0.6, tool='shovel', drops='dirt', shape='farmland', transparent=True, top=['farmland'],
                     bottom=['dirt'], side=['dirt'], fallback=color.brown, placeable=False),
    'sugar_cane': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['sugar_cane'],
                       plant_on=('sand', 'dirt', 'grass', 'sugar_cane'), fallback=color.lime),
    'bed': dict(hardness=0.4, top=['red_wool'], bottom=['oak_planks'], side=['oak_planks'], fallback=color.red),
    'wheat_0': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage0'], fallback=color.lime, placeable=False, crop=0),
    'wheat_1': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage1'], fallback=color.lime, placeable=False, crop=1),
    'wheat_2': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage2'], fallback=color.lime, placeable=False, crop=2),
    'wheat_3': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage3'], fallback=color.lime, placeable=False, crop=3),
    'wheat_4': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage4'], fallback=color.lime, placeable=False, crop=4),
    'wheat_5': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage5'], fallback=color.lime, placeable=False, crop=5),
    'wheat_6': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage6'], fallback=color.lime, placeable=False, crop=6),
    'wheat_7': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('farmland',), all=['wheat_stage7'], fallback=color.lime, placeable=False, crop=7),
    'oak_sapling': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['oak_sapling'],
                        plant_on=('grass', 'dirt', 'farmland'), sapling='oak', fallback=color.lime),
    'birch_sapling': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['birch_sapling'],
                          plant_on=('grass', 'dirt', 'farmland'), sapling='birch', fallback=color.lime),
    'spruce_sapling': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['spruce_sapling'],
                           plant_on=('grass', 'dirt', 'farmland'), sapling='spruce', fallback=color.green),
    'dandelion': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['dandelion'],
                      plant_on=('grass', 'dirt', 'farmland'), fallback=color.yellow),
    'poppy': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['poppy'],
                  plant_on=('grass', 'dirt', 'farmland'), fallback=color.red),
    'brown_mushroom': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['brown_mushroom'],
                           light=1, fallback=color.brown),
    'red_mushroom': dict(hardness=0.0, shape='cross', transparent=True, solid=False, all=['red_mushroom'],
                         fallback=color.red),
    'spawner': dict(hardness=5.0, tool='pickaxe', tier=1, drops=None, transparent=True, all=['spawner'], fallback=color.dark_gray, placeable=False),
    'redstone_ore': dict(hardness=3.0, tool='pickaxe', tier=3, drops='redstone', all=['redstone_ore'], fallback=color.red),
    'redstone_block': dict(hardness=5.0, tool='pickaxe', tier=1, redstone='block', all=['redstone_block'], fallback=color.red),
    'redstone_wire': dict(hardness=0.0, plant_on='solid', shape='wire', transparent=True, solid=False, drops='redstone', redstone='wire',
                          all=[('redstone_dust_dot', 'rs_off')], fallback=color.dark_gray, placeable=False),
    'redstone_wire_on': dict(hardness=0.0, plant_on='solid', shape='wire', transparent=True, solid=False, drops='redstone', redstone='wire',
                             all=[('redstone_dust_dot', 'rs_on')], fallback=color.red, placeable=False, light=3),
    'redstone_torch': dict(hardness=0.0, shape='torch', orient='attach', transparent=True, solid=False, redstone='torch',
                           light=7, all=['redstone_torch'], fallback=color.red),
    'redstone_torch_off': dict(hardness=0.0, shape='torch', orient='attach', transparent=True, solid=False,
                               redstone='torch_off', drops='redstone_torch', all=['redstone_torch_off'],
                               fallback=color.dark_gray, placeable=False),
    'lever': dict(hardness=0.5, shape='lever', orient='attach', transparent=True, solid=False, redstone='lever',
                  all=['lever'], fallback=color.gray),
    'lever_on': dict(hardness=0.5, shape='lever', orient='attach', transparent=True, solid=False, redstone='lever_on',
                     drops='lever', all=['lever'], fallback=color.gray, placeable=False),
    'stone_button': dict(hardness=0.5, shape='button', orient='attach', transparent=True, solid=False, redstone='button',
                         all=['stone'], fallback=color.gray),
    'stone_button_on': dict(hardness=0.5, shape='button', orient='attach', transparent=True, solid=False,
                            redstone='button_on', drops='stone_button', all=['stone'], fallback=color.gray, placeable=False),
    'stone_pressure_plate': dict(hardness=0.5, tool='pickaxe', tier=1, shape='plate', transparent=True, solid=False,
                                 redstone='plate', all=['stone'], fallback=color.gray),
    'stone_pressure_plate_on': dict(hardness=0.5, tool='pickaxe', tier=1, shape='plate', transparent=True, solid=False,
                                    redstone='plate_on', drops='stone_pressure_plate', all=['stone'], fallback=color.gray,
                                    placeable=False),
    'oak_pressure_plate': dict(hardness=0.5, tool='axe', shape='plate', transparent=True, solid=False, redstone='plate',
                               all=['oak_planks'], fallback=color.orange),
    'oak_pressure_plate_on': dict(hardness=0.5, tool='axe', shape='plate', transparent=True, solid=False,
                                  redstone='plate_on', drops='oak_pressure_plate', all=['oak_planks'],
                                  fallback=color.orange, placeable=False),
    'redstone_lamp': dict(hardness=0.3, redstone='lamp', all=['redstone_lamp'], fallback=color.orange),
    'redstone_lamp_on': dict(hardness=0.3, redstone='lamp_on', light=15, drops='redstone_lamp', all=['redstone_lamp_on'],
                             fallback=color.yellow, placeable=False),
    'piston': dict(hardness=0.5, orient='facing6', redstone='piston', front=['piston_top'], back=['piston_bottom'],
                   side=['piston_side'], fallback=color.gray),
    'sticky_piston': dict(hardness=0.5, orient='facing6', redstone='piston', front=['piston_top_sticky'],
                          back=['piston_bottom'], side=['piston_side'], fallback=color.gray),
    'piston_extended': dict(hardness=0.5, orient='facing6', redstone='piston_out', drops='piston', front=['piston_inner'],
                            back=['piston_bottom'], side=['piston_side'], fallback=color.gray, placeable=False),
    'sticky_piston_extended': dict(hardness=0.5, orient='facing6', redstone='piston_out', drops='sticky_piston',
                                   front=['piston_inner'], back=['piston_bottom'], side=['piston_side'],
                                   fallback=color.gray, placeable=False),
    'piston_head': dict(hardness=0.5, orient='facing6', drops=None, top=['piston_top'], bottom=['piston_top'],
                        side=['piston_top'], front=['piston_top'], back=['piston_side'], fallback=color.gray,
                        placeable=False),
    'sponge': dict(hardness=0.6, all=['sponge'], fallback=color.yellow),
    'cobweb': dict(hardness=4.0, tool='sword', shape='cross', transparent=True, solid=False, all=['cobweb'],
                   fallback=color.white, drops='string'),
    'note_block': dict(hardness=0.8, tool='axe', redstone='note', all=['note_block'], fallback=color.brown),
    'fire': dict(hardness=0.0, shape='cross', transparent=True, solid=False, drops=None, light=15, fire=True,
                 all=['fire_0'], fallback=color.orange, placeable=False),
    'rail': dict(hardness=0.7, tool='pickaxe', shape='rail', transparent=True, solid=False, plant_on='solid',
                 top=['rail'], corner=['rail_corner'], side=['rail'], bottom=['rail'], fallback=color.gray, rail=True),
    'powered_rail': dict(hardness=0.7, tool='pickaxe', shape='rail', transparent=True, solid=False, plant_on='solid',
                         redstone='prail', top=['powered_rail'], corner=['powered_rail'], side=['powered_rail'],
                         bottom=['powered_rail'], fallback=color.yellow, rail=True),
    'powered_rail_on': dict(hardness=0.7, tool='pickaxe', shape='rail', transparent=True, solid=False, plant_on='solid',
                            redstone='prail_on', drops='powered_rail', top=['powered_rail_on'], corner=['powered_rail_on'],
                            side=['powered_rail_on'], bottom=['powered_rail_on'], fallback=color.yellow, rail=True,
                            placeable=False, light=3),
    'melon': dict(hardness=1.0, tool='axe', top=['melon_top'], bottom=['melon_top'], side=['melon_side'],
                  fallback=color.lime),
    'lava': dict(hardness=None, light=15, all=['lava_still'], fallback=color.orange, solid=False, placeable=False, fluid='lava'),
    'obsidian': dict(hardness=50.0, tool='pickaxe', tier=4, all=['obsidian'], fallback=color.black),
    'netherrack': dict(hardness=0.4, tool='pickaxe', tier=1, all=['netherrack'], fallback=color.red),
    'soul_sand': dict(hardness=0.5, tool='shovel', all=['soul_sand'], fallback=color.brown),
    'nether_quartz_ore': dict(hardness=3.0, tool='pickaxe', tier=1, drops='nether_quartz', all=['nether_quartz_ore'], fallback=color.white),
    'nether_bricks': dict(hardness=2.0, tool='pickaxe', tier=1, all=['nether_bricks'], fallback=color.dark_gray),
    'nether_brick_slab': dict(hardness=2.0, tool='pickaxe', tier=1, shape='slab', transparent=True, all=['nether_bricks'], fallback=color.dark_gray),
    'nether_brick_stairs': dict(hardness=2.0, tool='pickaxe', tier=1, shape='stairs', orient='horizontal', transparent=True, all=['nether_bricks'], fallback=color.dark_gray),
    'nether_brick_fence': dict(hardness=2.0, tool='pickaxe', tier=1, shape='fence', transparent=True, all=['nether_bricks'], fallback=color.dark_gray),
    'quartz_block': dict(hardness=0.8, tool='pickaxe', tier=1, top=['quartz_block_top'], bottom=['quartz_block_bottom'], side=['quartz_block_side'], fallback=color.white),
    'quartz_pillar': dict(hardness=0.8, tool='pickaxe', tier=1, orient='axis', top=['quartz_pillar_top'], bottom=['quartz_pillar_top'], side=['quartz_pillar_side'], fallback=color.white),
    'chiseled_quartz': dict(hardness=0.8, tool='pickaxe', tier=1, top=['quartz_pillar_top'], bottom=['quartz_pillar_top'], side=['chiseled_quartz_block'], fallback=color.white),
    'magma_block': dict(hardness=0.5, tool='pickaxe', tier=1, light=3, all=['magma'], fallback=color.orange),
    'oak_sign': dict(hardness=1.0, tool='axe', shape='sign', orient='horizontal', transparent=True, solid=False,
                     all=['oak_planks'], fallback=color.orange),
    'nether_portal': dict(hardness=None, light=11, all=['nether_portal'], fallback=color.magenta, solid=False,
                          transparent=True, translucent=True, placeable=False),
    'nether_wart_0': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('soul_sand',), all=['nether_wart_stage0'], fallback=color.red, placeable=False, drops='nether_wart', nether_crop=0),
    'nether_wart_1': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('soul_sand',), all=['nether_wart_stage1'], fallback=color.red, placeable=False, drops='nether_wart', nether_crop=1),
    'nether_wart_2': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('soul_sand',), all=['nether_wart_stage1'], fallback=color.red, placeable=False, drops='nether_wart', nether_crop=2),
    'nether_wart_3': dict(hardness=0.0, shape='cross', transparent=True, solid=False, plant_on=('soul_sand',), all=['nether_wart_stage2'], fallback=color.red, placeable=False, drops='nether_wart', nether_crop=3),
    'water': dict(fluid='water', hardness=None, all=[('water_still', 'water')], fallback=color.azure,
                  transparent=True, translucent=True, solid=False, placeable=False),
}

# Blocks you can hold and place (the creative inventory lists these)
PLACEABLE = [name for name, spec in BLOCKS.items() if spec.get('placeable', True)]
SOLID = {name for name, spec in BLOCKS.items() if spec.get('solid', True)}


# ---- numbers instead of names (the world stores one small number per block) ----
import numpy as np

TABLE_SIZE = 256                                  # a block's number fits in one byte; the tables have room for mods to add blocks
NAMES = ['air'] + list(BLOCKS)                    # NAMES[id] -> name  (id 0 is empty air)
ID = {name: i for i, name in enumerate(NAMES)}    # ID[name] -> id


def _table(key, default, air=False, dtype=bool):
    out = np.full(TABLE_SIZE, default, dtype=dtype)
    out[0] = air
    for i, spec in enumerate(BLOCKS.values(), start=1):
        out[i] = spec.get(key, default)
    return out


SOLID_TABLE = _table('solid', True)               # SOLID_TABLE[id] -> can you stand on / bump into it?
TRANSPARENT_TABLE = _table('transparent', False, air=True)
TRANSLUCENT_TABLE = _table('translucent', False)
EMIT_TABLE = _table('light', 0, dtype=np.uint8)   # how much light each block gives off
EMIT_TABLE[0] = 0


SHAPE_OF = {ID[name]: spec['shape'] for name, spec in BLOCKS.items() if spec.get('shape')}    # id -> 'torch' / 'cross'
SHAPED_TABLE = np.zeros(TABLE_SIZE, dtype=bool)   # SHAPED_TABLE[id] -> is it drawn from small boxes instead of a cube?
for _id in SHAPE_OF:
    SHAPED_TABLE[_id] = True
# What you can point at and mine: solid blocks and shaped ones like torches (but not water)
TARGET_TABLE = SOLID_TABLE.copy()
for _id in SHAPE_OF:
    TARGET_TABLE[_id] = True

GRAVITY_TABLE = _table('gravity', False)


# How tall the solid part of each block is, as a fraction of a full block (slabs and stairs: half; farmland: a bit less)
TOP_TABLE = np.ones(TABLE_SIZE, dtype=np.float32)
for _name, _spec in BLOCKS.items():
    if _spec.get('shape') in ('slab', 'stairs'):
        TOP_TABLE[ID[_name]] = 0.5
    elif _spec.get('shape') == 'farmland':
        TOP_TABLE[ID[_name]] = 0.9375
    elif _spec.get('shape') == 'enchtable':
        TOP_TABLE[ID[_name]] = 0.75
DOOR_IDS = np.array([ID['oak_door_b'], ID['oak_door_t']])

import shapes as _shapes
_shapes.SOLID_FULL.update(n for n, s in BLOCKS.items() if not s.get('shape') and s.get('solid', True)
                          and not s.get('transparent'))

FLUID_TABLE = _table('fluid', False)


REDSTONE_ROLE = {ID[name]: spec['redstone'] for name, spec in BLOCKS.items() if spec.get('redstone')}   # id -> role


# What burns: block name (or name ending) -> how likely fire next to it is to spread onto it (0-1)
FLAMMABLE = {'planks': 0.6, 'log': 0.25, 'leaves': 0.7, 'wool': 0.8, 'bookshelf': 0.6, 'fence': 0.6, 'door': 0.4,
             'slab': 0.5, 'stairs': 0.5, 'crafting_table': 0.5, 'chest': 0.4, 'tnt': 1.0, 'coal_block': 0.1,
             'sapling': 0.9, 'wheat': 0.9, 'sugar_cane': 0.5, 'note_block': 0.4, 'cobweb': 0.9}


def flammability(name):
    for key, chance in FLAMMABLE.items():
        if name and (name.endswith(key) or key in name and key in ('crafting_table', 'bookshelf', 'tnt', 'chest')):
            if name.startswith(('stone', 'cobblestone', 'brick', 'sandstone')) and key in ('slab', 'stairs'):
                continue
            return chance
    return 0.0


# ---- adding a block while the program runs (mods.py does this) ----------------------------------------------------------------

ON_REGISTER = []          # functions called with the new block's name, so modules that keep their own copies can update


def register_block(name, spec):
    """Add a block type. Everything that is looked up by block number is updated in place."""
    if name in BLOCKS:
        raise ValueError(f'There is already a block called {name!r}.')
    if len(NAMES) >= TABLE_SIZE:
        raise ValueError(f'There is no room for more blocks (the most is {TABLE_SIZE - 1}).')
    BLOCKS[name] = spec
    NAMES.append(name)
    number = ID[name] = len(NAMES) - 1
    SOLID_TABLE[number] = bool(spec.get('solid', True))
    TRANSPARENT_TABLE[number] = bool(spec.get('transparent', False))
    TRANSLUCENT_TABLE[number] = bool(spec.get('translucent', False))
    EMIT_TABLE[number] = int(spec.get('light', 0))
    GRAVITY_TABLE[number] = bool(spec.get('gravity', False))
    FLUID_TABLE[number] = bool(spec.get('fluid'))
    TARGET_TABLE[number] = SOLID_TABLE[number]
    TOP_TABLE[number] = {'slab': 0.5, 'stairs': 0.5, 'farmland': 0.9375, 'enchtable': 0.75}.get(spec.get('shape'), 1.0)
    if spec.get('shape'):
        SHAPE_OF[number] = spec['shape']
        SHAPED_TABLE[number] = True
        TARGET_TABLE[number] = True
    if spec.get('placeable', True):
        PLACEABLE.append(name)
    if spec.get('solid', True):
        SOLID.add(name)
    if not spec.get('shape') and spec.get('solid', True) and not spec.get('transparent'):
        _shapes.SOLID_FULL.add(name)
    if spec.get('redstone'):
        REDSTONE_ROLE[number] = spec['redstone']
    for callback in ON_REGISTER:
        callback(name)
    return number
