import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

w = pc.plot(16, 16, 16)
w.placeblock(0, 0, 0, 'stone')
pc.runplot(w, pc.adventure)
