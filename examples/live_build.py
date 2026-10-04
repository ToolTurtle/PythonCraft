import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Watch your build grow while the game is open: pc.live(w, build) runs your function and the game at the same time.
w = pc.plot(30, 20, 30)
w.fill(0, 0, 0, 29, 0, 29, 'grass')
w.spawnpoint(15, 1, -6)


def build():
    w.say('Watch a tower appear!')
    for y in range(1, 15):
        w.hollowbox(12, y, 12, 17, y, 17, 'stone_bricks' if y % 2 else 'bricks')
        pc.wait(0.25)                       # wait() pauses your function, not the game
    w.fill(11, 15, 11, 18, 15, 18, 'oak_planks')
    w.say('Done! Walk around it.', 5)


pc.live(w, build, peaceful=True)
