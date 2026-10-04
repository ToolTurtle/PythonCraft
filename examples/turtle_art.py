import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Drawing with the turtle: it builds a block at every step.
w = pc.plot(40, 12, 40)
w.fill(0, 0, 0, 39, 0, 39, 'grass')

t = w.turtle(5, 1, 30, facing='east', block='gold_block')
for side in range(4):                    # a square
    t.forward(8)
    t.right()

t.penup()
t.goto(20, 1, 30)
t.pendown('diamond_block')
for size in range(1, 12):                # a spiral that grows
    t.forward(size)
    t.right()

t.penup()
t.goto(4, 1, 10)
t.face('east')
t.pendown('bricks')
for step in range(8):                    # a staircase
    t.forward(2)
    t.up()
w.spawnpoint(20, 1, -6)
pc.runplot(w, pc.adventure, peaceful=True)
