import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# A little Nether outpost: a portal, a nether brick tower with glowstone, and some neighbours.
w = pc.plot(20, 12, 20)
w.fill(0, 0, 0, 19, 0, 19, 'netherrack')                     # y = 0 is the floor
w.fill(6, 0, 6, 9, 0, 9, 'soul_sand')
w.portal(2, 1, 4, width=2, height=3, axis='x')               # a glowing portal (just for looking)

w.hollowbox(12, 1, 8, 16, 6, 12, 'nether_bricks')            # a tower
w.placeblock(14, 1, 8, 'air')                                # a doorway
w.placeblock(14, 2, 8, 'air')
w.placeblock(14, 5, 10, 'glowstone')
w.placeblock(13, 2, 10, 'chest', facing='south')
for x in range(11, 18):                                      # a fence around it
    w.placeblock(x, 1, 6, 'nether_brick_fence')

w.fill(7, 1, 7, 8, 1, 7, 'nether_wart_3')                    # nether wart on soul sand
w.placeblock(5, 1, 14, 'lava')

w.spawnmob('zombie_pigman', 4, 1, 12)                        # creatures stand in the cell you give
w.spawnmob('magma_cube', 9, 1, 14)
w.spawnmob('ghast', 15, 8, 16)

pc.runplot(w, pc.adventure, dimension='nether', peaceful=True)                    # peaceful=True: nothing can hurt you
