import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# FOR TEACHERS: make challenge files. Each challenge is a .pcchallenge file: a brief, a plot size, an optional starting
# build and some checks. Put them in the challenges/ folder (or any folder; give students the path).
# Run this file to (re)make the four challenges that come with PythonCraft.
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'challenges')
os.makedirs(OUT, exist_ok=True)

# 1. The bridge: the starting build is a river with a sign and a ferryman on the west bank.
river = pc.plot(30, 12, 14)
river.fill(0, 0, 0, 29, 0, 13, 'grass')
river.fill(10, 0, 0, 14, 0, 13, 'water')                 # the river runs north-south
river.sign(3, 1, 4, ['Cross the river!', 'Build a bridge strong enough to walk on.'], 'south')
river.npc('Ferryman', 6, 1, 8, ['The ferry is broken.', 'Could you build a bridge?'])

bridge = pc.Challenge(
    'bridge', 'Cross the river',
    'Build a bridge so a person can walk from the west bank to the east bank: from (2, 1, 7) to (27, 1, 7). '
    'Give it fences on the sides and two torches, and make it out of planks or stone.',
    size=(30, 12, 14), starter=river, points=10,
    checks=[pc.require.path((2, 1, 7), (27, 1, 7)),
            pc.require.blocks(['oak_planks', 'spruce_planks', 'birch_planks', 'cobblestone', 'stone_bricks', 'bricks'], 10,
                              label='built from at least 10 plank or stone blocks'),
            pc.require.blocks('oak_fence', 4, label='has at least 4 fence blocks as railings'),
            pc.require.torches(2)],
    hints=['The river is 5 blocks wide at y = 0. A deck at y = 0 over the water is a bridge.',
           'w.fill(10, 0, 7, 14, 0, 7, "oak_planks") fills the river with planks in one go.'],
    author='PythonCraft')
print(bridge.save(os.path.join(OUT, 'bridge.pcchallenge')))

# 2. The skyline: one tall tower with lights.
skyline = pc.Challenge(
    'skyline', 'Touch the clouds',
    'Build a tower at least 15 blocks tall, with a window, at least two torches and at least two different kinds of block.',
    size=(24, 24, 24), points=10,
    checks=[pc.require.tall(15), pc.require.window(), pc.require.torches(2), pc.require.kinds(2, each=10)],
    hints=['A loop makes tall towers easy: for y in range(15): ...'])
print(skyline.save(os.path.join(OUT, 'skyline.pcchallenge')))

# 3. The garden: uses the ready-made garden check, plus a sign.
garden = pc.Challenge(
    'garden', 'A fenced garden',
    'Make a garden with at least 8 flowers or plants, a fence around it and a sign that says what it is.',
    size=(24, 8, 24), starter=None, points=10,
    checks=[pc.require.builtin('garden'), pc.require.blocks('oak_sign', 1, label='has a sign')],
    hints=['w.sign(x, y, z, "My garden") puts up a sign.'])
print(garden.save(os.path.join(OUT, 'garden.pcchallenge')))

# 4. The village: several houses, trees, a villager and a sign.
meadow = pc.plot(50, 16, 40)
meadow.fill(0, 0, 0, 49, 0, 39, 'grass')
village = pc.Challenge(
    'village', 'Build a village',
    'Build a village: at least 3 houses (each with a door), at least 6 logs of trees, a villager and a sign.',
    size=(50, 16, 40), starter=meadow, points=12,
    checks=[pc.require.blocks('oak_door_b', 3, label='at least 3 houses (3 doors)'),
            pc.require.blocks(['oak_log', 'birch_log', 'spruce_log'], 6, label='at least 6 tree logs'),
            pc.require.creatures(1, 'villager', label='has a villager'),
            pc.require.blocks('oak_sign', 1, label='has a sign'),
            pc.require.total(500, label='has at least 500 blocks (a village is big)')],
    hints=['w.house(x, 1, z) builds a house, and w.tree(x, 1, z) a tree.'])
print(village.save(os.path.join(OUT, 'village.pcchallenge')))
