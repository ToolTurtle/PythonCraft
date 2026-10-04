# Level 2: Builder

**You will learn:** loops and `if`, so the computer does the repeating; things the library builds for you; words and
pictures made of blocks; copy and paste; the sky. About two lessons. (You should have done Level 1.)

All the code on this page goes after these two lines, and `pc.runplot(...)` is the last line of your program:

```python
import pycraft as pc
w = pc.plot(40, 20, 40)
```

## 1. Loops: do something again and again

```python
for i in range(8):                          # i is 0, 1, 2, ... 7
    w.placeblock(i, i, 0, 'cobblestone')    # a staircase
```

A loop inside a loop covers a floor:

```python
for x in range(8):
    for z in range(8):
        w.placeblock(x, 0, z, 'stone')
```

## 2. `if`: choose

This makes a checkerboard (`%` gives the remainder of a division, so `% 2 == 0` means "even"):

```python
for x in range(8):
    for z in range(8):
        if (x + z) % 2 == 0:
            w.placeblock(x, 0, z, 'stone')
        else:
            w.placeblock(x, 0, z, 'white_wool')
```

## 3. Things the library builds for you

```python
w.house(2, 0, 2)                                   # a house (door, windows, roof)
w.tree(20, 0, 5, 'oak')                            # 'oak', 'birch', 'spruce' or 'jungle'
w.maze(2, 0, 20, cols=6, rows=6)                   # a random maze
w.village(2, 0, 2, houses=4)                       # houses along a street
w.terrain(lambda x, z: 2 + 5 * w.noise(x, z, 8))   # hills: you say how tall the ground is at each (x, z)
w.seed(7)                                          # the same number gives the same trees and mazes again
```

## 4. Words and pictures

```python
w.text(2, 1, 4, 'HELLO', 'gold_block')                    # block letters
w.image(0, 0, 0, 'my_picture.png', width=20)              # a picture turned into blocks (use your own file)
```

## 5. Copy, paste, turn

```python
tower = w.copy(0, 0, 0, 3, 9, 3)        # copy a box of blocks
w.paste(tower, 10, 0, 0)                # paste it somewhere else
w.paste(tower, 20, 0, 0, rotate=90)     # turned a quarter
w.paste(w.mirror(tower), 30, 0, 0)      # flipped
```

`w.replace('stone', 'bricks')` swaps one kind of block for another everywhere.

## 6. The sky and the world

```python
w.settime('sunset')         # 'sunrise', 'day', 'sunset', 'night'
w.weather('rain')           # 'clear', 'rain', 'snow', 'storm'
```

And in the last line, `pc.runplot(w, pc.adventure, dimension='nether')` builds in the Nether (red haze, no sunlight:
light it with `'glowstone'`).

## 7. Try it

* A village with a street, trees and a sign: `w.sign(x, y, z, 'Welcome!')`.
* A pyramid: one `fill` per layer, in a loop, each layer smaller.
* Your name in giant letters.
* A maze with a chest in the middle.

## Cheat sheet

| | |
|---|---|
| `for i in range(n):` | repeat n times (indent what repeats) |
| `if a == b:` / `else:` | choose |
| `w.house`, `w.tree`, `w.maze`, `w.village`, `w.terrain` | built for you |
| `w.text(x, y, z, 'HI', 'stone')` / `w.image(...)` | words / a picture |
| `w.copy(...)`, `w.paste(clip, x, y, z)`, `w.mirror(clip)` | copy and paste |
| `w.settime(...)`, `w.weather(...)` | the sky |

## Challenges for this level

* Challenge mode **levels 4 to 8**: a room with a door, stairs, a checkerboard, a pyramid, three towers.
* Teacher challenges: `skyline` (a tall tower) and `bridge`. See [Challenges](README_challenges.md).

**Next:** [Level 3: Coder](README_3_coder.md).
