# pycraft - build with code

```python
import pycraft as pc

w = pc.plot(16, 16, 16)                       # a plot: x, y, z
w.placeblock(0, 0, 0, 'stone')                # one block
w.fillblocks(0, 0, 0, 15, 0, 15, 'grass')
pc.runplot(w, pc.adventure)                   # walk around your creation
```

`pc.plot(x, y, z)` makes a **plot** (an object). Everything below is a method of a plot (`w.placeblock(...)`), except the
functions that start with `pc.`. Make several plots if you like (`a = pc.plot(...)`, `b = pc.plot(...)`), then run the one you
want. `pc.runplot(w, mode)` opens the game: **closing the window ends your program, so it is the last line**, and the game
can only be opened once each time your program runs.

(`import pycraftWorld as w` is the quick one-plot style: the same functions, with a plot made for you, and `size()` and `show()`.)

Run your script from this folder, e.g. `python3 examples/house.py`.

**Coordinates:** x = east, y = **up**, z = south. `(0, 0, 0)` is the corner of the plot, on the ground.
The game starts you at the north side (low z), looking south (+z), so text and pictures that run along +x read left to right.
**Block ids:** a name (`'stone'`, `'oak_planks'`) or a number. `w.blocklist()` prints them all. Names are best:
numbers can change when new blocks are added. `'air'` (or `0`) removes a block.

Blocks outside the plot give a friendly error, and a misspelt block name suggests the right one.
`runplot()` never touches your saved games: it uses a throwaway world.

## Blocks

| Function | What it does |
|---|---|
| `pc.plot(x, y, z)` / `w.resize(x, y, z)` | make a plot / change its size |
| `placeblock(x, y, z, id, facing=None)` | one block; facing is `'north'/'south'/'east'/'west'` for furnaces, stairs, doors, chests |
| `fill(x1,y1,z1, x2,y2,z2, id)` (or `fillblocks`) | a solid box |
| `hollowbox(x1,y1,z1, x2,y2,z2, id)` | a room: walls, floor and roof only |
| `line(x1,y1,z1, x2,y2,z2, id)` | a straight line |
| `sphere(cx, cy, cz, radius, id, hollow=False)` | a ball |
| `replace(old, new)` | change every `old` block into `new` (add a box's six corners to limit it). Returns how many |
| `removeblock(x, y, z)` / `getblock(x, y, z)` | take a block away / what is here? (`'air'` if empty) |
| `count(id=None)` / `clear()` | how many blocks you placed / remove everything |

## Copy, paste, turn and flip

```python
roof = w.copy(0, 0, 0, 4, 3, 4)              # copy a box of blocks (returns a Clip)
w.paste(roof, 10, 0, 0)                      # paste it with its lowest corner here
w.paste(roof, 20, 0, 0, rotate=90)           # turned a quarter (90, 180 or 270)
w.paste(w.mirror(roof, 'x'), 30, 0, 0)       # flipped left-right ('z' flips front-back)
```
`rotate(clip, 90)` and `mirror(clip, 'x')` give you a new Clip. Furnaces, doors and stairs turn with it.
`paste(..., air=True)` also clears blocks where the clip is empty.

## Words and pictures

| Function | What it does |
|---|---|
| `text(x, y, z, 'HELLO', 'gold_block', size=1, axis='x')` | block letters 7 tall (A-Z, 0-9, `! ? . , : - + = ( ) / * ' < > #`). Returns how wide it is |
| `image(x, y, z, 'dog.png', width=16, axis='x')` | turn a picture into a wall of blocks using the closest colours. `palette=['stone','snow']` limits the blocks it may use |

## Make things for me

| Function | What it does |
|---|---|
| `tree(x, y, z, kind='oak')` | `'oak'`, `'birch'`, `'spruce'`, `'jungle'` (the trunk starts at y) |
| `house(x, y, z, width=7, depth=7, height=4, walls=..., roof=..., door='north')` | a little house with door, windows, roof, torch |
| `maze(x, y, z, cols=8, rows=8, wall='stone_bricks', height=3)` | a random maze with an entrance and an exit |
| `village(x, y, z, houses=4, spacing=10)` | houses along a gravel street |
| `terrain(lambda x, z: 2 + 6 * w.noise(x, z, 8))` | hills: your function says how tall the ground is at each (x, z) |
| `noise(x, z, scale=10)` | smooth random numbers from 0 to 1 (for hills) |
| `seed(42)` | the same seed gives the same trees, mazes and villages |
| `portal(x, y, z, width=2, height=3, axis='x')` | a Nether portal in an obsidian frame (for looking at) |
| `spawnmob('pig', x, y, z)` / `moblist()` / `removemobs()` | creatures that stand in your build |

## Characters, signs, the turtle and chance

| Function | What it does |
|---|---|
| `sign(x, y, z, 'Welcome!')` | a sign: right-click it to read (give a list for several pages) |
| `npc('Farmer', x, y, z, ['Hello', 'Nice day'])` | a character who talks when clicked (each click says the next line) |
| `spawnmob(...)` returns a **Creature** | `.walk_to(x, z)`, `.follow()`, `.stay()`, `.free()`, `.say(text)`, `.onclick(fn)`, `.arrived`, `.position`, `.remove()` |
| `turtle(x, y, z, 'east', 'bricks')` | a builder you steer: `.forward(n)`, `.back(n)`, `.up(n)`, `.down(n)`, `.right()`, `.left()`, `.face('east')`, `.penup()`, `.pendown()`, `.place()`, `.goto(x, y, z)` |
| `chance(0.3)`, `coin()`, `choose('a', 'b')`, `randint(1, 6)` | random numbers (`seed(n)` makes them repeatable) |

## Redstone and doors

`lever(x, y, z, on='floor')`, `button(...)`, `torch(...)` (`on` is `'floor'` or the side the wall is on),
`lamp(x, y, z)`, `pressureplate(x, y, z)`, `wire(x1,y1,z1, x2,y2,z2)` (dust along the ground), `door(x, y, z, 'north', open=False)`.
Lever -> wire -> lamp works in the game just like the real thing.

## The sky and the sound

`settime('sunset')` (`'sunrise'`, `'morning'`, `'day'`, `'sunset'`, `'night'`, or a number: 0 sunrise, 6000 noon, 18000 midnight;
`cycle=True` lets the day pass), `weather('rain')` (`'clear'`, `'rain'`, `'snow'`, `'storm'`; rain does not fall under a roof),
`music(False)`.

## Make it react: events

```python
def hello():
    w.say('Welcome!')

w.onenter(5, 1, 5, hello)             # when the player walks into this spot
w.onclick(3, 1, 3, grow_tower)        # when the player right-clicks the block here
w.onkey('f', lightning)               # when F is pressed
w.every(10, new_day_message)          # every 10 seconds
w.goal(26, 1, 26, 'You win!')         # a finish line
```
Your function can take no arguments, or `(x, y, z)`. Inside it you can use everything in the library, and the game
changes right away: `placeblock`, `spawnmob`, `settime`, `weather`, `say('text')`, `give('bread', 3)`, `teleport(x, y, z)`,
`playsound('levelup')`. (`onclick` needs adventure mode; a spectator cannot click.) `playerpos()` says where the player is. `spawnpoint(x, y, z)` is where they start and respawn
(it can be outside the plot, like z = -5).

## Watch it happen: live()

```python
def build():
    for y in range(10):
        w.placeblock(5, y, 5, 'gold_block')
        pc.wait(0.3)               # pause your function, not the game

pc.live(w, build)                 # opens the game AND runs build() at the same time
```
Use `while pc.running():` for a loop that ends when the window closes. A mistake in your function is shown in the
terminal and on screen, and the game keeps running.

## Saving and sharing: .pcplot files

```python
path = w.save('house')            # writes house.pcplot (plain text; blocks, creatures, signs, sky settings)
w = pc.load('house.pcplot')       # a new plot from a file    (or w.load('house.pcplot') to replace what you have)
code = w.share()                  # the same thing as a block of text a friend can paste into w.loadcode(code)
pc.view('house.pcplot')           # open a file in the game to look around it (a spectator)
w.title = 'My house'              # a name that is saved in the file
```
Loading a file never runs anything: it is only data, and a damaged or odd file gives a clear message
(blocks the game does not know are left out with a note). The functions you wrote (events) are not saved.
The file format is described in [docs/PCPLOT_FORMAT.md](docs/PCPLOT_FORMAT.md).

## Watching your code build, and undo

```python
w.delay(4)        # blocks placed from your own thread (pc.live, livecode.py) appear 4 ticks (0.2 s) apart
w.undo(); w.redo()  # take back / put back the last recorded step (livecode.py records each line as a step)
```
`python3 livecode.py` is an interactive prompt built on this: see [docs/README_livecode.md](docs/README_livecode.md).

## Tutorial worlds

`python3 tutorialworld.py` walks you around the worlds in `tutorials/` (signs show the code). Make your own with
`w.tutorial = {...}`, signs and `python3 tutorialworld.py save myprogram.py`: see [docs/README_tutorials.md](docs/README_tutorials.md).

## Challenges, handing in, feedback

```python
pc.challenges()                   # the challenges you can take
w = pc.challenge('bridge')        # a plot ready for it (right size, starting build) and the brief
w.check()                         # [x] / [ ] for every check, with what is wrong, and your score
w.submit('Sam', note='done!')     # hand it in: submissions/bridge/Sam.pcplot  (the newest one is reviewed)
w.feedback()                      # what your teacher said (or pc.feedback('Sam', 'bridge'))
```
`submit` saves your build, your check results, your note and a copy of your program (`code=False` leaves the program out)
as a .pcplot file in the `submissions` folder, or in `to='some/shared/folder'` (or the PYCRAFT_SUBMISSIONS setting).
Nothing is sent over the network. See [docs/README_challenges.md](docs/README_challenges.md).

Making challenges (teachers):

```python
c = pc.Challenge('bridge', 'Cross the river', 'Build a bridge from bank to bank.', size=(30, 12, 14), starter=river_plot,
                 checks=[pc.require.path((2, 1, 7), (27, 1, 7)), pc.require.blocks('oak_planks', 10)], points=10)
c.save('challenges/bridge.pcchallenge')
```

| Check | What it asks for |
|---|---|
| `pc.require.blocks('oak_planks', 10)` | at least 10 of a block (a list of names means "any of these"; `at_most=` too) |
| `pc.require.door()`, `.window()`, `.torches(2)` | a door, a window, torches |
| `pc.require.total(500)` | at least 500 blocks |
| `pc.require.tall(15)` | a column at least 15 blocks tall |
| `pc.require.kinds(3, each=20)` | at least 3 different blocks, 20 or more of each |
| `pc.require.path((x, y, z), (x, y, z))` | someone can walk from one cell to the other (bridges, stairs, corridors) |
| `pc.require.area(corner1, corner2, 0.9)` | a box of space is 90% filled (a floor, a wall) |
| `pc.require.creatures(1, 'villager')` | a creature of a kind |
| `pc.require.builtin('house')` | a ready-made check: `house`, `tower`, `bridge`, `garden`, `pyramid`, `portal` |

Review what students handed in with `python3 review.py` (see [docs/README_teachers.md](docs/README_teachers.md)).
Checks never run a student's code; they only look at the build.

Teacher-written checks in Python also work: `w.assignment('A house', [('has a door', w.has('oak_door_b')),
('big', lambda: w.count() > 100)])`; they are included in `check()` and `submit()`.

## Challenge mode (12 levels)

```python
w = pc.level(5)  # a new plot for level 5 of 12: it has the right size and tells you the goal
w.hint()         # a clue
w.check()        # what is missing? (or: Level complete! and your stars)
```
`pc.levels()` lists the levels with your stars. In the game, press **C** to see the goal and **K** to check.
`python3 challenge_mode.py` makes a starter file for each level. Stars: 3 for finishing with 2 or fewer "not yet"s,
2 for up to 6, then 1. A level can be handed in too (`w.submit('Sam')`, filed under `level-5`).

## Teachers: homework and showing off

```python
pc.makegallery('pictures')       # a web page of every picture in the gallery folder
```

## runplot()

`pc.runplot(w, mode=pc.adventure, time=None, border=True, dimension='overworld', peaceful=False, gallery=None, name=None)`

| Option | What it does |
|---|---|
| `mode` | `pc.adventure` (default): walk and use doors, chests, furnaces, crafting tables, beds, levers, buttons; you cannot place or break blocks. `pc.spectator`: fly through everything to look around (nothing can be clicked). The game is always one of these two, and the pause menu cannot change it |
| `time` | `'day'`, `'night'`, ... as in `settime` |
| `dimension` | `'nether'`: netherrack floor, red haze, no sunlight (light it with glowstone or lava) |
| `peaceful` | nothing can hurt you, even the creatures you placed |
| `gallery`, `name` | a folder and a name: press **F2** (or leave through the menu) to save a picture of your build, e.g. `pc.runplot(w, pc.adventure, gallery='class_pictures', name='Sam')` |

In the game: WASD to walk, Space to jump, right-click doors, chests, furnaces, crafting tables and beds.

## Examples (in `examples/`)

`house.py`, `tiny.py`, `nether.py`, `live_build.py` (a tower that builds itself), `events.py` (click, walk, key, timer),
`maze_game.py` (find your way to the finish line), `village_rain.py` (a village in a storm), `pixel_art.py` (words and
pictures), `challenge.py` (check your house, then share it), `bridge_challenge.py` (a student doing a challenge and handing in), `make_challenges.py` (a teacher making challenges), `village_story.py` (signs, a talking farmer, creatures with orders), `turtle_art.py` (drawing with the turtle).
