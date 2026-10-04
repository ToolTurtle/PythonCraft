# Level 1: Beginner

**You will learn:** what the three numbers (x, y, z) mean, how to place and fill blocks, how to look at your build and
save it. No coding experience needed. About 45 minutes.

## 0. A tour first (optional)

`python3 tutorialworld.py` opens a menu of tutorial worlds. Pick **0-coordinates** first: it shows what x, y and z mean with
coloured lines, number signs and a path to follow. Then **1-blocks**. Walk along the exhibits and right-click the signs:
each shows the code that built what you are looking at. ([More about tutorial worlds](README_tutorials.md).)

## 1. Run something

In a terminal, in the PythonCraft folder:

```
python3 examples/tiny.py
```

A window opens. **W A S D** walk, **Space** jumps, the **mouse** looks, **Esc** is the menu. Close the window to stop.

## 2. Your first program

Make a file called `mybuild.py` in the PythonCraft folder:

```python
import pycraft as pc

w = pc.plot(10, 10, 10)             # your building plot: 10 blocks each way. We call it w.
w.placeblock(2, 0, 2, 'stone')      # one stone block
pc.runplot(w, pc.adventure)         # open the game and walk around it
```

Run it: `python3 mybuild.py`. Closing the game window ends the program, so `pc.runplot(...)` is always the last line.

* `pc` is the library, `w` is your plot. Everything you build goes into `w`.
* `pc.adventure` means: you can walk around and use doors, but you cannot break things.

## 3. Where is (x, y, z)?

Every block has three numbers:

| number | direction |
|---|---|
| `x` | left and right |
| `y` | **up** (so `y = 0` is the ground, `y = 5` is higher) |
| `z` | forward and back |

`(0, 0, 0)` is the corner of your plot. You start standing in front of it, looking at it.

## 4. Four tools

```python
w.placeblock(3, 0, 3, 'gold_block')           # one block
w.fill(0, 0, 0, 9, 0, 9, 'grass')             # fill a whole box, corner to corner
w.line(0, 0, 0, 9, 5, 0, 'bricks')            # a line of blocks
w.hollowbox(2, 0, 2, 8, 4, 8, 'oak_planks')   # a room: walls and roof, empty inside
```

Block names are words in quotes: `'stone'`, `'dirt'`, `'glass'`, `'bricks'`, `'gold_block'`, `'oak_planks'`...
`w.blocklist()` prints all of them. If you spell one wrong, the program suggests the right one.

## 5. Try it

1. Make a grass floor, then a house on it with `hollowbox`.
2. Add a door: `w.door(5, 1, 2, 'north')`.
3. Add a torch inside: `w.torch(4, 1, 4)`.
4. Add a pig: `w.spawnmob('pig', 3, 1, 3)`.
5. Make it night: `w.settime('night')` (put it before `pc.runplot`).

## 6. When something goes wrong

The messages are written to help:

| you see | it means |
|---|---|
| `(12, 0, 3) is outside your plot...` | your plot is too small, or a number is too big. Make `pc.plot(...)` bigger. |
| `There is no block called 'stoen'. Did you mean 'stone'?` | a spelling mistake |
| `NameError: name 'w' is not defined` | you used `w.` before the line `w = pc.plot(...)` |

## 7. Keep your work

```python
w.save('myhouse')            # makes myhouse.pcplot in your folder
```

Later, to get it back: `w = pc.load('myhouse.pcplot')`.
To look at any saved file without writing code: `python3 -c "import pycraft; pycraft.view('myhouse.pcplot')"`.

## Cheat sheet

| | |
|---|---|
| `w = pc.plot(x, y, z)` | make a plot |
| `w.placeblock(x, y, z, 'stone')` | one block |
| `w.fill(x1,y1,z1, x2,y2,z2, 'grass')` | a solid box |
| `w.hollowbox(...)` | a room |
| `w.line(...)` | a line |
| `w.door(x, y, z, 'north')`, `w.torch(x, y, z)` | a door, a torch |
| `w.spawnmob('pig', x, y, z)` | a creature |
| `w.save('name')` / `pc.load('name.pcplot')` | keep it / get it back |
| `pc.runplot(w, pc.adventure)` | open the game (last line!) |

## Next

Try the first levels of **challenge mode**: `python3 challenge_mode.py` (levels 1 to 3).
Then: [Level 2: Builder](README_2_builder.md).
