"""A small house, built with pycraftWorld.   Run it with:  python3 examples/house.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

w = pc.plot(16, 16, 16)

# A stone floor, then a hollow room of planks on top of it
w.fillblocks(2, 0, 2, 12, 0, 12, 'cobblestone')
w.hollowbox(2, 1, 2, 12, 5, 12, 'oak_planks')

# A door, windows and a torch inside
w.placeblock(7, 1, 2, 'oak_door_b', facing='south')
w.placeblock(7, 2, 2, 'oak_door_t', facing='south')
for x in (4, 5, 9, 10):
    w.placeblock(x, 3, 2, 'glass')
w.placeblock(3, 2, 3, 'torch', facing='down')

# A roof made of stairs, a chimney and some trees
w.fillblocks(2, 6, 2, 12, 6, 12, 'oak_slab')
w.fillblocks(10, 6, 10, 10, 9, 10, 'bricks')
for tx, tz in ((0, 0), (14, 1), (1, 14)):
    w.fillblocks(tx, 1, tz, tx, 4, tz, 'oak_log')
    w.sphere(tx, 5, tz, 2, 'oak_leaves')

# A round tower
w.sphere(13, 3, 13, 3, 'stone_bricks', hollow=True)

print(f'Built {w.count()} blocks. Opening the game...')
pc.runplot(w, pc.adventure)
