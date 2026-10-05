# PythonCraft

A Minecraft-style game written in Python, made for learning. You can **play** it (endless world, caves, villages, mobs,
redstone, enchanting, the Nether), and you can **build in it with code** using a small library called `pycraft`.
Students write Python, press run, and walk around what they built. Teachers can set **challenges**, collect the
finished builds, and review them.

## Start in two minutes

```
pip install ursina numpy pillow
python3 examples/tiny.py            # a small build to walk around
python3 tutorialworld.py            # tutorial worlds: walk around and read the code on the signs (start with 0-coordinates)
```

A window opens with a small build. **W A S D** walk, **Space** jumps, the mouse looks, **Esc** is the menu.
To play the full game instead: `python3 main.py`.

## What do you want to do?

| I want to... | Go to |
|---|---|
| type code and watch it build, with undo | `python3 livecode.py` ([Live coding](docs/README_livecode.md)) |
| walk around a world that teaches me | `python3 tutorialworld.py` ([Tutorial worlds](docs/README_tutorials.md)) |
| write my first program | [Level 1: Beginner](docs/README_1_beginner.md) |
| build bigger things with loops | [Level 2: Builder](docs/README_2_builder.md) |
| make builds that react and talk | [Level 3: Coder](docs/README_3_coder.md) |
| do the challenges and hand in my work | [Challenges](docs/README_challenges.md) |
| set challenges, collect and review work | [Teachers](docs/README_teachers.md) |
| look up every function | [PYCRAFT.md](PYCRAFT.md) |
| know what is inside a .pcplot file | [docs/PCPLOT_FORMAT.md](docs/PCPLOT_FORMAT.md) |

## A taste

```python
import pycraft as pc

w = pc.plot(16, 16, 16)                 # a building plot
w.fill(0, 0, 0, 15, 0, 15, 'grass')     # a lawn
w.house(4, 1, 4)                        # a house
pc.runplot(w, pc.adventure)             # open the game and walk around it
```

## Challenges in one picture

```
teacher                                       student
-------                                       -------
makes bridge.pcchallenge  --------------->    w = pc.challenge('bridge')
                                              ... builds ...
                                              w.check()          (what is missing?)
                                              w.submit('Sam')    --> submissions/bridge/Sam.pcplot
python3 review.py  <-------------------------
  open it in the game, read the code,
  give a score and a comment  ------------>   w.feedback()
```

Nothing goes over the internet: a hand-in is a file in a folder. Point that folder at a shared drive (or collect the files
by hand) and the teacher sees everything.

## The folders

| | |
|---|---|
| `pycraft.py` | the building library (`import pycraft as pc`) |
| `pycraftWorld.py` | the same library with one plot made for you (the quick style) |
| `pcplot.py` | .pcplot files, challenges, hand-ins and reviews |
| `challenge_mode.py` | 12 levels, from one block to a castle |
| `livecode.py` | an interactive interpreter: type code, watch it build, undo and redo |
| `tutorialworld.py` | walk around tutorial worlds (`.pcplot` files in `tutorials/`) |
| `maketutorial.py` | make a tutorial world in creative mode: build by hand or type code, then `:sign` it |
| `tutorials/` | the tutorial worlds: blocks, loops, built-for-you, people, sky |
| `review.py` | the teacher's tool |
| `challenges/` | challenges that come with it: `bridge`, `skyline`, `garden`, `village` |
| `examples/` | small programs to run and change |
| `docs/` | the guides |
| `saves/` | saved worlds of the game |
| `assets/` | the game's pictures and sounds |

The game itself is split into small files by topic (`world.py`, `terrain.py`, `nether.py`, `mobs.py`, `redstone.py`,
`interaction.py`...). Adding a block is one line in `blocks.py`.

## If something goes wrong

* **"No module named ursina"**: run `pip install ursina numpy pillow`.
* **The window does not open on a Mac**: the first run builds some shader files; run it again.
* **A message that says what is wrong in your code**: read it, the library tries to say how to fix it
  (a misspelt block name suggests the right one; a block outside the plot says how big the plot is).
* **The program stops when I close the game window**: that is normal. `pc.runplot(...)` is always the last line.


## Mods
Add your own blocks, wood and creatures with `pc.mod()` and `pc.mob()`: see docs/README_mods.md (example: examples/mod_example/).

## Command list
Every command on one page: docs/COMMANDS.md (press / in a live-coding game to type them).

## Playing together
`python3 launcher.py` opens one window for everything. Classroom worlds on the local network: teachers use the class tool (`python3 classtool.py`) or `python3 lan.py host`, students use `python3 lan.py join`; anyone can be the teacher with `/teacher PIN`. `lan.py host --plot-mode` gives everyone who joins a plot in a flat world (the teacher can change the sizes). Plots, building with code, a teacher panel, rolling back changes, shared animals and more: see docs/README_lan.md. If something will not connect: `python3 doctor.py`.

## Tests
`python3 run_tests.py` runs the checks (add `-v` to see each one; `PYCRAFT_NO_WINDOW=1` skips the ones that open the game).
They use a throwaway folder: your saves are never touched.

## License
The code is MIT licensed (see LICENSE). Minecraft's own pictures and sounds in `assets/` are not part of that: see NOTICE.
