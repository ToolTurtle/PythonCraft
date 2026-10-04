import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# A tiny game: find your way through the maze to the glowing finish.
# Same seed = same maze. (Try pc.runplot(w, pc.spectator) to fly over it and see the way.)
w = pc.plot(30, 10, 30)
w.fill(0, 0, 0, 29, 0, 29, 'grass')
w.seed(2024)
w.maze(2, 1, 2, cols=12, rows=12, wall='stone_bricks', height=3)
w.placeblock(26, 0, 26, 'glowstone')
w.goal(26, 1, 26, 'You escaped the maze!')
w.torch(1, 1, 1)
w.spawnpoint(3, 1, 0)
w.spawnmob('zombie', 14, 1, 14)
w.settime('sunset')
pc.runplot(w, pc.adventure)
