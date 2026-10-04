import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Signs, a character who talks, and creatures that obey orders. Click the sign and the farmer!
w = pc.plot(24, 12, 24)
w.fill(0, 0, 0, 23, 0, 23, 'grass')
w.house(14, 1, 12, 7, 6, 4)
w.sign(8, 1, 6, ['Welcome to Pigtown!', 'The farmer lives in the house.', 'Please feed the pig.'])
w.npc('Farmer', 12, 1, 8, ['Hello, traveller!', 'My pig keeps running away.', 'Can you follow it?'])

pig = w.spawnmob('pig', 4, 1, 4)
pig.walk_to(18, 20)                      # give it somewhere to walk
dog = w.spawnmob('wolf', 6, 1, 4)
dog.follow()                             # a wolf that follows you


def pig_says():
    pig.say('Oink! Catch me if you can!')


pig.onclick(pig_says)
w.spawnpoint(12, 1, -4)
pc.runplot(w, pc.adventure, peaceful=True)
