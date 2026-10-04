import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# A student doing the "bridge" challenge: get the plot, build, check, hand in.
NAME = 'Sam'                                       # <- write your own name here

w = pc.challenge('bridge')                         # a plot with the river already in it (it prints the brief)

# ---- build your bridge here --------------------------------------------------------------------------
w.fill(10, 0, 6, 14, 0, 8, 'oak_planks')           # the deck, over the water
w.fill(10, 1, 6, 14, 1, 6, 'oak_fence')            # railings on both sides
w.fill(10, 1, 8, 14, 1, 8, 'oak_fence')
w.torch(10, 2, 6)
w.torch(14, 2, 8)
# -----------------------------------------------------------------------------------------------------

w.check()                                          # what is still missing?
w.submit(NAME, note='My first bridge!')            # hand it in for review (saved in submissions/bridge/)
pc.runplot(w, pc.adventure)                        # walk across it
