import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Words and pictures made of blocks. Any small picture works: try your own .png file!
w = pc.plot(48, 24, 20)
w.fill(0, 0, 0, 47, 0, 19, 'grass')
w.text(2, 1, 4, 'HELLO', 'gold_block')                     # block letters (A-Z, 0-9 and some symbols)
w.text(2, 10, 4, 'WORLD', 'diamond_block', size=1)
picture = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'textures', 'item', 'diamond_sword.png')
w.image(32, 1, 4, picture, width=14)                      # a picture turned into blocks
w.spawnpoint(24, 1, -10)
w.settime('day')
pc.runplot(w, pc.adventure)
