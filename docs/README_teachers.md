# For teachers

How to set up, plan lessons, set challenges, collect the work and review it.

## 1. Set up

```
pip install ursina numpy pillow
python3 examples/tiny.py
```

If a window with a small build opens, you are ready. Everything runs on each student's own computer. Their saved games are
never touched: the building library opens a throwaway world. The game window is always **adventure** (walk around and use
things, but not place or break blocks) or **spectator** (fly and look), and students cannot change that from the menu.

## 2. A lesson plan

| When | Guide | Students learn |
|---|---|---|
| Lesson 1 (45 min) | [Level 1: Beginner](README_1_beginner.md) | coordinates, `placeblock`, `fill`, `hollowbox`, saving |
| Lessons 2-3 | [Level 2: Builder](README_2_builder.md) | loops, `if`, built-in generators, text, copy and paste |
| Lessons 4-6 | [Level 3: Coder](README_3_coder.md) | functions, events, characters, the turtle, chance |
| Any time | [Challenges](README_challenges.md) | practice, with checking |

`python3 challenge_mode.py` has 12 self-checking levels (stars), good for homework or fast finishers.
`python3 challenge_mode.py solution 5` prints one way to solve a level.

## 3. Tutorial worlds

`python3 tutorialworld.py` lets students walk around worlds that teach (signs show the code that built each exhibit). Five come
with it, in `tutorials/`. You can make your own live with `python3 maketutorial.py my-lesson` (type code, `:sign` it, `:save`), or by writing a pycraft program with signs and `python3 tutorialworld.py save myprogram.py`.
`python3 livecode.py` is a live prompt (blocks appear one at a time, with undo) that is great for projecting while you teach.
See [README_tutorials.md](README_tutorials.md). They make a good warm-up before each lesson.

## 4. Challenges

A **challenge** is a `.pcchallenge` file: a title, a brief, a plot size, an optional starting build and a list of checks.
Four come with the project in `challenges/`: `bridge`, `skyline`, `garden`, `village`. Students take them with
`w = pc.challenge('bridge')`.

### Make your own

`examples/make_challenges.py` makes the four above, and is the best thing to copy. In short:

```python
import pycraft as pc

river = pc.plot(30, 12, 14)                          # the starting build
river.fill(0, 0, 0, 29, 0, 13, 'grass')
river.fill(10, 0, 0, 14, 0, 13, 'water')
river.npc('Ferryman', 6, 1, 8, ['Could you build a bridge?'])

task = pc.Challenge(
    'bridge', 'Cross the river',
    'Build a bridge from the west bank to the east bank, from (2, 1, 7) to (27, 1, 7).',
    size=(30, 12, 14), starter=river, points=10,
    checks=[pc.require.path((2, 1, 7), (27, 1, 7)),
            pc.require.blocks('oak_planks', 10),
            pc.require.torches(2)],
    hints=['A deck of planks at y = 0 over the water is a bridge.'])
task.save('challenges/bridge.pcchallenge')
```

The checks (all look at the build; none runs student code):

| Check | Asks for |
|---|---|
| `pc.require.blocks('oak_planks', 10)` | at least 10 of a block (a list of names = "any of these"; `at_most=` too) |
| `pc.require.door()`, `.window()`, `.torches(2)` | a door, a window, torches |
| `pc.require.total(500)` | at least 500 blocks |
| `pc.require.tall(15)` | a column 15 blocks tall |
| `pc.require.kinds(3, each=20)` | 3 different blocks, 20+ of each |
| `pc.require.path(start, end)` | someone can walk from one cell to the other |
| `pc.require.area(corner1, corner2, 0.9)` | a floor or wall that is 90% filled |
| `pc.require.creatures(1, 'villager')` | a creature of a kind |
| `pc.require.builtin('house')` | a ready-made check (`house`, `tower`, `bridge`, `garden`, `pyramid`, `portal`) |

Each check passed is worth an equal share of `points`. Put the file in `challenges/`, or give students its path.
A file in `challenges/` has priority over a ready-made quick check of the same name.

## 5. Collecting the work

When a student calls `w.submit('Sam')`, a file appears:

```
submissions/bridge/Sam.pcplot            the latest hand-in
submissions/bridge/Sam.review.json       your score and comment (after review)
submissions/bridge/history/Sam.1.pcplot  older hand-ins
```

Every student has their own file, so a whole class can hand in at the same moment, even into the same folder. Ways to
collect:

* **A shared network or cloud folder** (a school drive, a synced folder): set the setting `PYCRAFT_SUBMISSIONS` to its path on
  every computer, or students write `w.submit('Sam', to='/path/to/folder')`.
* **By hand**: students send you their `.pcplot` file (email, USB). Put them in `submissions/<challenge>/`, or open one directly:
  `python3 review.py view Sam.pcplot`.

Nothing is sent over the internet by the library: handing in is writing a file.

## 6. Reviewing

```
python3 review.py                          a menu: pick, open, read the code, score
python3 review.py list                     a table of every hand-in
python3 review.py show Sam                 checks, note and the student's program (as text)
python3 review.py open Sam                 open Sam's build in the game: you fly around it
python3 review.py grade Sam 8 "Nice bridge!"    score and comment
python3 review.py export                   grades.csv, for a spreadsheet
python3 review.py view some.pcplot         open any .pcplot file
```

Add `--challenge bridge` to look at one challenge, `--folder path` for another folder, and `--reviewer "Ms Ng"` (or the
setting `PYCRAFT_REVIEWER`) so students see who wrote the comment. The status column says `new`, `reviewed`, or
`resubmitted` (a student handed in again after your review).

Students read your comment with `w.feedback()` (or `pc.feedback('Sam', 'bridge')`).

## 7. Safety and privacy

* A `.pcplot` is plain JSON data. **Opening one never runs code.** The student's program inside is shown as text only.
* A hand-in is checked when opened: unknown blocks or creatures are dropped with a note, plots that are too big or damaged
  are refused with a message.
* Names are cleaned to letters, digits, `-` and `_` before they become file names, so a name cannot point outside the folder.
* The library does not use the network. What a hand-in contains: the build, check results, name, note, and (unless the
  student turned it off) a copy of the program.

## 8. Other things you can do

* **Gallery:** `pc.runplot(w, pc.adventure, gallery='pictures', name='Sam')` and F2 save a picture; `pc.makegallery('pictures')`
  makes a web page of them for the projector.
* **Python checks:** `w.assignment('A house', [('has a door', w.has('oak_door_b')), ('big', lambda: w.count() > 100)])` adds
  your own checks to `check()` and `submit()`.
* **Peaceful mode:** `pc.runplot(w, pc.adventure, peaceful=True)` stops anything from hurting the player.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| "Say who you are: submit('Sam')" | give the name, or set `PYCRAFT_NAME` |
| Nothing in `review.py list` | check the folder: `--folder`, or the setting `PYCRAFT_SUBMISSIONS` |
| A student's file says "not a plot file" | it was damaged or edited; ask them to hand in again |
| The game window opens only once per run | normal; close it and run the program again |
| A check says "not a place you can stand" | the start or end cell of a `path` check is inside a block or in water |

[Back to the start](../README.md)
