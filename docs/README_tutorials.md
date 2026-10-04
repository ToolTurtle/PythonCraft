# Tutorial worlds

A tutorial world is a Minecraft-style world you **walk around** to learn pycraft. It is a row of **exhibits**. In front of
each exhibit is a **sign**: right-click it and it shows the code that built the exhibit. A **Guide** character at the start
tells you what to do.

```
python3 tutorialworld.py
```

A menu lists the worlds (they are `.pcplot` files in the `tutorials/` folder). Type a number to walk around one.

| World | Level | What it shows |
|---|---|---|
| `0-coordinates` | 1 | **start here**: x, y and z. Coloured lines for each direction, number signs, a path to follow, a treasure to find |
| `1-blocks` | 1 | `placeblock`, `fill`, `line`, `hollowbox`, doors, creatures |
| `2-loops` | 2 | loops and `if`: a staircase, a checkerboard, a pyramid, a ring |
| `3-built-for-you` | 2 | trees, a house, a maze, block letters |
| `4-people-and-signs` | 3 | signs, a talking character, creature orders, the turtle |
| `5-sky` | 2 | time of day, weather, lamp posts (the world itself is a rainy afternoon) |

## Commands

```
python3 tutorialworld.py list            the worlds
python3 tutorialworld.py play 0-coordinates   walk around one (a name, or its number in the list)
python3 tutorialworld.py info 2-loops         what it teaches and what to try
python3 tutorialworld.py code 2-loops         the program that builds it
python3 tutorialworld.py export 2-loops       write that program to 2-loops.py: run it, change it!
```

## How to use a tutorial world

1. `play` it and walk along the exhibits. **W A S D** walk, the mouse looks, **Space** jumps.
2. Right-click each sign (the page changes each time you click: first the idea, then the code).
3. `export` the world's program (for example `python3 tutorialworld.py export 2-loops`), run it (`python3 2-loops.py`) and change numbers or block names. What changes?
4. Do the "Try it" list from `info`.

The code on a sign is *exactly* the code that built the exhibit above it, so you can copy it into your own program.

## Make your own tutorial world: `maketutorial.py`

The easy way is to make it live. `maketutorial.py` opens the game in **creative mode**, so you can build by hand *and* type
code (like [livecode](README_livecode.md)). `:sign` puts up a sign showing the code that built the exhibit.

**By hand:** double-tap **Space** to fly, press **E** for every block, **left-click** breaks, **right-click** places.
Whatever you build or break is noticed and kept as a step you can `:undo`, and it is written as code (`fill` and
`placeblock` lines) so the sign can show it and the program stored in the world rebuilds it. (Flowing water and lava are
not kept.) **By code:** type Python at the `tutorial>` prompt: blocks appear one at a time.

```
python3 maketutorial.py my-lesson
```

```text
tutorial> w.fill(X, 1, 9, X + 4, 3, 9, 'bricks')           # build something (X = where the next exhibit starts)
tutorial> :sign A wall | fill() fills a whole box.          # a sign in front, showing that code
tutorial> for i in range(5): w.placeblock(X + i, 1 + i, 9, 'stone')
...
tutorial> :sign Stairs | A loop repeats a line.
tutorial> :title Tutorial 6: Walls
tutorial> :level 1
tutorial> :summary Build walls and stairs.
tutorial> :step Walk along the exhibits.
tutorial> :try Make the wall taller.
tutorial> :guide Welcome to walls! | Right-click the signs.
tutorial> :save
```

* **`:sign TITLE | WHY`** puts a sign in front of everything you built since the last sign. Page 1 is the title and the why,
  page 2 is the code you typed (with `X` filled in, so it runs on its own). Then `X` moves on to the next exhibit spot.
* **`:undo` / `:redo`** work on signs and on things you built by hand. **`:status`** shows what is set so far.
* **`:save`** puts `tutorials/my-lesson.pcplot` in the tutorials folder. Walk around it with
  `python3 tutorialworld.py play my-lesson`. (If the window is closed first, a draft is kept in `drafts/maketutorial/`.)
* The program that builds the world is stored in it, so `python3 tutorialworld.py export my-lesson` works.

`:help` lists every command (`:title :level :summary :step :try :guide :sign :status :save`, plus the livecode ones).

Creative mode is only for the tutorial maker: in your own programs the game is always adventure or spectator.

## Make your own by writing a program

You can also write the world as a normal pycraft program. A tutorial world is just a world with signs.

```
python3 tutorialworld.py new my-lesson     # a starter program: my-lesson.py
python3 my-lesson.py                       # look at it
python3 tutorialworld.py save my-lesson.py # keep it in the tutorials folder
python3 tutorialworld.py play my-lesson
```

`save` runs your program without opening the game, takes the plot it was going to show, and saves it as
`tutorials/my-lesson.pcplot`. Add notes to your plot so the menu can show them:

```python
import pycraft as pc

w = pc.plot(40, 14, 20)
w.title = 'My lesson'
w.fill(0, 0, 0, 39, 0, 19, 'grass')
w.npc('Guide', 4, 1, 2, ['Welcome!', 'Right-click the signs.'])      # a guide at the start
w.spawnpoint(5, 1, -3)

w.fill(10, 1, 9, 14, 3, 9, 'bricks')                                  # an exhibit...
w.sign(12, 1, 5, ['A wall', "w.fill(10, 1, 9, 14, 3, 9, 'bricks')"])  # ...and its sign: page 1 idea, page 2 code

w.tutorial = {
    'level': 1,
    'summary': 'One line about what it teaches.',
    'steps': ['Walk to the first exhibit.', 'Right-click its sign.'],
    'try_it': ['Change the wall to a different block.'],
}
pc.runplot(w, pc.adventure)
```

Tip: to make sure the code on the sign is the code that built the exhibit, build the exhibit by running the string:

```python
code = "w.fill(10, 1, 9, 14, 3, 9, 'bricks')"
exec(code, {'w': w})
w.sign(12, 1, 5, ['A wall', code])
```

`examples/make_tutorials.py` makes the five worlds that come with PythonCraft this way, and also stores the whole program in
each world (`w.tutorial['code']`) so `code` and `export` work. Copy it as a starting point.

## Where the files are

Tutorial worlds live in `tutorials/` (set the setting `PYCRAFT_TUTORIALS` to use another folder, or add `--folder some/folder`).
They are ordinary `.pcplot` files (see [PCPLOT_FORMAT.md](PCPLOT_FORMAT.md)), so `pc.load('tutorials/2-loops.pcplot')`
works too. What happens when you click a sign or the Guide is saved in the world; events you wrote with `onenter` and
friends are not.

[Back to the start](../README.md)
