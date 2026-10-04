import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import pycraft as pc

# 1. Blocks and wood
m = pc.mod('demo')
m.addblock('snad', 'snad.png', like='sand')                  # falls like sand
m.addwood('purple', 'plum_leaves.png', name='plum')          # plum_log, plum_planks, plum_leaves, plum_sapling...

# 2. A creature, made from the iron golem, that appears when you build its shape (a T of iron blocks)
golem = pc.mob(pc.golem, 'vine_golem').health(60).title('Vine Golem')
golem.spawncondition(pc.block_placement('vinegolem_spawn.pcschem'))

w = pc.plot(20, 14, 20)
w.fill(0, 0, 0, 19, 0, 19, 'grass')
w.tree(4, 1, 4, 'plum')
w.fill(8, 1, 3, 11, 1, 3, 'snad')

if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vinegolem_spawn.pcschem')):
    # build the pattern once and save it (a real mod would draw it in a creative world and copy it)
    shape = pc.plot(5, 5, 5)
    shape.fill(1, 0, 0, 1, 1, 0, 'iron_block')
    shape.fill(0, 1, 0, 2, 1, 0, 'iron_block')
    shape.copy(0, 0, 0, 2, 1, 0).save('vinegolem_spawn.pcschem')

for pos in [(14, 1, 12), (14, 2, 12), (13, 2, 12), (15, 2, 12)]:     # build the shape: a golem appears!
    w.placeblock(*pos, 'iron_block')
w.spawnpoint(10, 1, -3)
pc.runplot(w, pc.adventure)
