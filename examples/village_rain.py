import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Make a whole village with one line, then change the weather and the time.
w = pc.plot(60, 24, 44)
w.seed(11)
w.terrain(lambda x, z: 1 + 2 * w.noise(x, z, 12))        # gentle hills
w.fill(0, 0, 0, 0, 0, 0, 'grass')
w.village(2, 3, 12, houses=6, spacing=14)
for x, z in ((6, 2), (30, 4), (50, 6), (54, 30)):
    ground = max(y for y in range(24) if w.getblock(x, y, z) != 'air')
    w.tree(x, ground + 1, z, 'spruce')
w.spawnmob('villager', 10, 5, 22)
w.spawnmob('iron_golem', 20, 5, 22)
w.settime('afternoon')
w.weather('storm')                                        # rain, thunder and lightning
w.spawnpoint(2, 5, 3)
pc.runplot(w, pc.adventure, peaceful=True)
