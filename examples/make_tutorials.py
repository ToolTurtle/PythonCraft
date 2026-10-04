import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Makes the tutorial worlds in the tutorials/ folder (run:  python3 tutorialworld.py  to walk around them).
#
# A tutorial world is a row of exhibits. Each exhibit has a SIGN in front of it, and the sign shows the code that built
# the exhibit. The code on the sign is the very code that is run here to build it, so it always works.
# To make your own: copy this file, change the exhibits, and run it (or see docs/README_tutorials.md).
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'tutorials')
os.makedirs(OUT, exist_ok=True)
SIZE = (52, 14, 24)


def new_world(title, summary, level, steps, try_it, guide_lines):
    w = pc.plot(*SIZE)
    w.title = title
    w.fill(0, 0, 0, SIZE[0] - 1, 0, SIZE[2] - 1, 'grass')
    w.npc('Guide', 4, 1, 2, guide_lines)
    w.spawnpoint(5, 1, -3)
    w._program = ['import pycraft as pc', '', f'w = pc.plot({SIZE[0]}, {SIZE[1]}, {SIZE[2]})',
                  f'w.fill(0, 0, 0, {SIZE[0] - 1}, 0, {SIZE[2] - 1}, "grass")']
    w._info = {'level': level, 'summary': summary, 'steps': steps, 'try_it': try_it}
    return w


def exhibit(w, x, title, why, code):
    """Build an exhibit by running `code`, and put a sign in front of it showing that code."""
    exec(code, {'w': w, 'pc': pc})
    w.placeblock(x, 0, 5, 'stone_bricks')
    w.sign(x, 1, 5, [f'{title}\n{why}', code], 'south')
    w._program.append(f'# {title}: {why}\n{code}')


def finish(w, name):
    w._program += ['', 'pc.runplot(w, pc.adventure)']
    w.tutorial = dict(w._info, code='\n'.join(w._program) + '\n')
    path = w.save(os.path.join(OUT, name))
    print(path)


# ---- 0. Coordinates ----------------------------------------------------------------------------------------------------
w = new_world('Tutorial 0: Where is everything?', 'x, y and z: the three numbers that say where every block goes.', 1,
              ['Stand at the start and look at the coloured lines: red is x, green is y, blue is z.',
               'Walk along each line and read the number signs.',
               'Walk 20 along the red line and 12 along the stone path to the diamond tower, counting your steps.'],
              ['Find the treasure chest at x = 35, y = 1, z = 16 by counting from the corner.',
               'Place a block at (10, 5, 10) and walk to it.', 'Build a column at x = 2, z = 18 that is 4 blocks tall.'],
              ['Welcome to Tutorial 0: Where is everything?', 'Every block has three numbers: x, y and z.',
               'Red line = x (right), green = y (up), blue = z (away from you). Right-click the signs!'])
w.spawnpoint(8, 1, 3)
exhibit(w, 3, 'The three directions',
        'Every place is (x, y, z). x goes RIGHT (red), y goes UP (green), z goes AWAY from you (blue). The corner is (0, 0, 0). '
        'The lawn is y = 0, so blocks standing on it start at y = 1.',
        "w.fill(0, 0, 0, 30, 0, 0, 'redstone_block')    # x: a red line along the front, to the right\n"
        "w.fill(0, 0, 0, 0, 0, 20, 'lapis_block')       # z: a blue line going away from you\n"
        "w.fill(0, 1, 0, 0, 10, 0, 'emerald_block')     # y: a green tower, UP\n"
        "w.placeblock(0, 1, 0, 'gold_block')            # the corner, (0, 1, 0)")
exhibit(w, 6, 'y: up', 'Go up and y gets bigger. The gold blocks are at y = 5 and y = 10.',
        "w.placeblock(1, 5, 0, 'gold_block')\nw.placeblock(1, 10, 0, 'gold_block')")
exhibit(w, 9, 'z: away from you', 'Go away from the start and z gets bigger. Read the signs along the blue line.',
        "for z in range(5, 21, 5):\n    w.placeblock(1, 1, z, 'gold_block')\n    w.sign(2, 1, z, f'z = {z}')")
exhibit(w, 15, 'x: right', 'Go right and x gets bigger. A gold block and a sign every 5 steps along the red line.',
        "for x in range(5, 31, 5):\n    w.placeblock(x, 2, 0, 'gold_block')\n    w.sign(x, 1, 2, f'x = {x}')")
exhibit(w, 24, 'Walk to a place', 'The diamond tower top is at (20, 3, 12): 20 right, 12 away, 3 up. Walk 20 along the red line, then follow the stone path 12, and count.',
        "# walk 20 steps along the red line (x)...\n"
        "w.fill(20, 0, 0, 20, 0, 12, 'stone_bricks')    # ...then 12 steps along z...\n"
        "w.fill(20, 1, 12, 20, 3, 12, 'diamond_block')  # ...then 3 up")
exhibit(w, 34, 'Treasure!', 'The chest is at x = 35, y = 1, z = 16. Count the steps from the corner (0, 0, 0).',
        "w.placeblock(35, 1, 16, 'chest', 'north')")
exhibit(w, 43, 'Two corners', 'fill() takes two corners: (x1, y1, z1) and (x2, y2, z2). The gold blocks mark the wall\'s two top corners.',
        "w.fill(40, 1, 12, 46, 4, 12, 'bricks')         # from (40, 1, 12) to (46, 4, 12)\n"
        "w.placeblock(40, 5, 12, 'gold_block')          # above corner 1\n"
        "w.placeblock(46, 5, 12, 'gold_block')          # above corner 2")
finish(w, '0-coordinates')

# ---- 1. Blocks ----------------------------------------------------------------------------------------------------------
w = new_world('Tutorial 1: Blocks', 'Place single blocks, fill boxes, draw lines and build a room.', 1,
              ['Walk east along the row of exhibits.',
               'Right-click the sign in front of each one: it shows the code that built it.',
               'Press Esc for the menu.'],
              ['Open the program with: python3 tutorialworld.py code 1-blocks, and change a block name.',
               'Make the wall twice as tall.', 'Add a second door to the room.'],
              ['Welcome to Tutorial 1: Blocks!', 'Walk east along the row of exhibits.',
               'Right-click a sign to see the code that built the exhibit.'])
exhibit(w, 6, 'One block', 'placeblock(x, y, z, name) puts down one block. y is UP.', "w.placeblock(6, 1, 9, 'gold_block')")
exhibit(w, 14, 'A wall', 'fill(x1, y1, z1, x2, y2, z2, name) fills a whole box, corner to corner.',
        "w.fill(12, 1, 9, 16, 3, 9, 'bricks')")
exhibit(w, 24, 'A line', 'line(...) draws a straight line between two points.', "w.line(21, 1, 9, 27, 6, 9, 'diamond_block')")
exhibit(w, 34, 'A room', 'hollowbox(...) makes a room: walls and a roof, empty inside. door() adds a door.',
        "w.hollowbox(31, 1, 9, 37, 4, 15, 'oak_planks')\nw.door(34, 1, 9, 'north')\nw.torch(34, 1, 12)")
exhibit(w, 45, 'Creatures', "spawnmob(name, x, y, z) puts a creature in your build.",
        "w.spawnmob('pig', 44, 1, 10)\nw.spawnmob('cow', 46, 1, 12)")
finish(w, '1-blocks')

# ---- 2. Loops -----------------------------------------------------------------------------------------------------------
w = new_world('Tutorial 2: Loops', 'Let the computer repeat things: stairs, a checkerboard, a pyramid and a ring.', 2,
              ['Walk east along the exhibits and read each sign.',
               'Look at how few lines of code build something big.'],
              ['Change range(8) to range(12) in the staircase.', 'Use three different blocks in the checkerboard.',
               'Make the pyramid one layer taller.'],
              ['Welcome to Tutorial 2: Loops!', 'A loop repeats lines of code.',
               'Each exhibit here was built with a loop. Read the signs.'])
exhibit(w, 6, 'A staircase', 'for i in range(8) repeats the indented line 8 times, with i = 0, 1, 2, ...',
        "for i in range(8):\n    w.placeblock(2 + i, 1 + i, 9, 'cobblestone')")
exhibit(w, 17, 'A checkerboard', 'Two loops: one for x and one for z. if/else picks the block.',
        "for x in range(8):\n    for z in range(8):\n        if (x + z) % 2 == 0:\n            w.placeblock(13 + x, 1, 9 + z, 'stone')\n"
        "        else:\n            w.placeblock(13 + x, 1, 9 + z, 'white_wool')")
exhibit(w, 29, 'A pyramid', 'One fill() for each layer. Each layer is 2 smaller than the one below.',
        "for i in range(4):\n    size = 7 - 2 * i\n    w.fill(26 + i, 1 + i, 9 + i, 26 + i + size - 1, 1 + i, 9 + i + size - 1, 'sandstone')")
exhibit(w, 44, 'A ring', 'Maths in a loop: sin and cos place things round a circle.',
        "import math\nfor k in range(12):\n    x = round(44 + 5 * math.cos(k * math.pi / 6))\n"
        "    z = round(13 + 5 * math.sin(k * math.pi / 6))\n    w.fill(x, 1, z, x, 4, z, 'stone_bricks')")
finish(w, '2-loops')

# ---- 3. Built for you ---------------------------------------------------------------------------------------------------
w = new_world('Tutorial 3: Built for you', 'Trees, houses, mazes and words: things the library builds in one line.', 2,
              ['Walk east along the exhibits and read each sign.', 'Each one is a single line (or two) of code.'],
              ['Make the house bigger: house(24, 1, 9, 11, 9, 6).', 'Build a maze with cols=8, rows=3.',
               'Write your own name with text().'],
              ['Welcome to Tutorial 3: Built for you!', 'Some things take lots of blocks, so the library builds them for you.'])
exhibit(w, 8, 'Trees', "tree(x, y, z, kind): 'oak', 'birch', 'spruce' or 'jungle'.",
        "w.seed(1)      # the same seed gives the same trees every time\nw.tree(5, 1, 10, 'oak')\nw.tree(9, 1, 10, 'birch')\nw.tree(13, 1, 10, 'spruce')")
exhibit(w, 21, 'A house', 'house(x, y, z, width, depth, height) builds a house with a door, windows and a roof.',
        "w.house(17, 1, 9, 9, 7, 5)")
exhibit(w, 33, 'A maze', 'maze(...) makes a random maze. seed() makes the same one every time.',
        "w.seed(5)\nw.maze(29, 1, 8, cols=5, rows=5, wall='stone_bricks', height=2)")
exhibit(w, 45, 'Words', 'text(x, y, z, "HI", block) writes block letters, 7 tall.', "w.text(42, 1, 10, 'HI', 'gold_block')")
finish(w, '3-built-for-you')

# ---- 4. People and signs ------------------------------------------------------------------------------------------------
w = new_world('Tutorial 4: People and signs', 'Signs, characters, creatures with orders, the turtle, and events.', 3,
              ['Right-click the Baker and the sign in this world.', 'Read how each was made.'],
              ['Give the Baker three lines to say.', 'Make the turtle draw a bigger square.',
               'Put a sign next to your own build.'],
              ['Welcome to Tutorial 4: People and signs!', 'Right-click me, the Baker, and the signs.'])
exhibit(w, 8, 'A sign', 'sign(x, y, z, pages) makes a sign. Give a list for several pages.',
        "w.sign(8, 1, 9, ['Welcome to my village!', 'This is page two.'])")
exhibit(w, 19, 'A character', 'npc(name, x, y, z, lines) makes someone who talks when you right-click.',
        "w.npc('Baker', 19, 1, 10, ['Fresh bread!', 'Come back tomorrow.'])")
exhibit(w, 31, 'Orders', 'A creature can be told what to do. (Orders work while the game runs; they are not saved in the world.)',
        "wolf = w.spawnmob('wolf', 31, 1, 10)\nwolf.follow()      # or wolf.walk_to(x, z), wolf.stay()")
exhibit(w, 42, 'The turtle', 'turtle(...) is a builder you steer. With the pen down it builds at every step.',
        "t = w.turtle(40, 1, 9, 'east', 'bricks')\nfor side in range(4):\n    t.forward(5)\n    t.right()")
finish(w, '4-people-and-signs')

# ---- 5. The sky ---------------------------------------------------------------------------------------------------------
w = new_world('Tutorial 5: The sky', 'Change the time and weather, and light up the night.', 2,
              ['The time and weather you see were set in code: read the first two signs.',
               'Walk along the lamp posts.'],
              ['Change settime to "night" and watch the lamps glow.', 'Try weather("snow") and weather("storm").',
               'Make a street of lamp posts with a loop.'],
              ['Welcome to Tutorial 5: The sky!', 'It is a rainy afternoon here. Read the first two signs to see why.'])
exhibit(w, 6, 'The time', "settime('sunrise' | 'day' | 'afternoon' | 'sunset' | 'night') sets the time of day.", "w.settime('afternoon')")
exhibit(w, 14, 'The weather', "weather('clear' | 'rain' | 'snow' | 'storm'). Rain does not fall under a roof.", "w.weather('rain')")
exhibit(w, 33, 'Lamp posts', 'A fence post with a torch on top. A loop makes a whole street.',
        "for i in range(6):\n    x = 24 + i * 5\n    w.fill(x, 1, 9, x, 3, 9, 'oak_fence')\n    w.torch(x, 4, 9)")
exhibit(w, 46, 'Lanterns', 'glowstone gives light too: it works in the Nether, where there is no sun.',
        "w.fill(45, 3, 12, 47, 3, 12, 'glowstone')\nw.house(44, 1, 14, 7, 6, 4)")
finish(w, '5-sky')
