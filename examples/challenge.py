import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Challenges: pick one, build it, then ask check() what is still missing.
w = pc.plot(24, 20, 24)
w.fill(0, 0, 0, 23, 0, 23, 'grass')
w.challenges()                  # prints the list
w.challenge('house')

# Build your house here! (This one is quick: house() does the work.)
w.house(6, 1, 6, 9, 7, 5)

if w.check():                   # prints what is missing, or "Challenge complete!"
    w.share('my_house.pycraft')     # a share code: send the file (or the text) to a friend, who uses w.load('my_house.pycraft')
    pc.runplot(w, pc.adventure)
