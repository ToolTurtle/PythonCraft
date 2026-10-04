# Live coding

`livecode.py` is an interactive interpreter for building worlds. The game window opens, your terminal becomes a Python
prompt, and **whatever you type appears in the world**, a block at a time so you can watch it. Made a mistake? **Undo it.**

```
python3 livecode.py
```

```text
pc> w.fill(5, 1, 5, 9, 3, 9, 'bricks')
pc> for i in range(8):
...     w.placeblock(i, 1 + i, 3, 'cobblestone')
...
pc> :undo
Undone 1 step(s).
```

(The `...` prompt means "more lines of this block"; press Enter on an empty line to finish it.)

`w` is your plot, `pc` is pycraft (so `w.house(...)`, `w.tree(...)`, `w.text(...)` and everything from the other guides work),
and `math` and `random` are ready to use. The plot starts as a grass lawn, 32 x 16 x 32.

## How fast do blocks appear?

Blocks you build from the prompt are placed **4 ticks** apart (a tick is 1/20 of a second, so 0.2 seconds), so a long wall
grows in front of you. Change it any time:

```text
pc> :delay 10        # slower: half a second per block
pc> :delay 0         # instantly
```

(Start with `python3 livecode.py --delay 10`.) The same works in your own programs: `w.delay(4)` before `pc.live(...)`.

## Undo and redo

Each thing you type is one **step**: a single block, a whole loop, a house. Undo takes back the last step (blocks,
creatures and signs).

| | |
|---|---|
| `:undo` or `:undo 3` | take back the last step / the last 3 |
| `:redo` or `:redo 3` | put them back |
| **U** and **Y** in the game window | undo and redo |
| **Esc** menu in the game: **Undo** and **Redo** buttons | the same, with the mouse |

Typing something new that builds replaces what you could redo. Lines that build nothing (like `x = 5`) are kept, and
undo moves past them.

## All the commands

```text
:undo [n]  :redo [n]    take back / put back steps
:delay N                ticks between blocks (4 = fifth of a second, 20 = a second, 0 = instant)
:clear                  remove everything you built (you can undo it)
:save NAME  :load NAME  keep the world as NAME.pcplot / open one (the load can be undone)
:export FILE.py         write everything you typed as a program you can run
:run FILE.py            run a file of code here (undoable as one step)
:history                what you have typed so far
:tp X Y Z               move yourself to a place in the plot
:fly  :walk             fly around (spectator) / walk again
:blocks WORD            find block names containing WORD (try :blocks stone)
:help  :quit            the list / close the game
```

## From a session to a program

Everything that worked and was not undone is a program. `:export my-build.py` writes it, and you can run it with
`python3 my-build.py`, change it, or hand it in. (A mistake like a misspelt block name does not end up in the program.)
If you close the window without saving, your work is kept in `drafts/livecode/last.pcplot` and `last.py`.

## Options

```
python3 livecode.py --size 48 20 48      a bigger plot
python3 livecode.py --load my.pcplot     start from a saved world
python3 livecode.py --no-floor           an empty plot
python3 livecode.py --nether             build in the Nether
python3 livecode.py --delay 10           slower building
```

## Tips

* A message like `ValueError: (99, 1, 1) is outside your plot...` just means that line did not happen. Type it again.
* Walk around to look: **W A S D**. `:fly` lets you go through anything and high up.
* Blocks stand on the lawn at `y = 1` (the lawn is `y = 0`).

[Back to the start](../README.md)


## Typing in the game
Press **/** in the game to open the code prompt on screen (Enter runs a line, Esc closes it, Up/Down recall lines). It is the same prompt as the terminal one. All commands: [COMMANDS.md](COMMANDS.md).

You can also type commands plainly, like `fill 0 0 0 5 0 5 stone` or `placeblock 3 1 3 bricks`: it shows the Python it turned into. See [COMMANDS.md](COMMANDS.md).
