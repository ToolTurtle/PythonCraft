# PythonCraft commands

A one-page reference. Use it to type commands yourself, or paste it to an assistant ("use these commands to build me a castle")
so it knows exactly what is allowed.

## Where you type

| Where | How |
|---|---|
| **In the game** (live coding) | start `python3 livecode.py`, press **/**, type, press **Enter**. **Esc** closes. Up/Down arrows recall lines. |
| **The terminal** | the same `pc>` prompt, in the terminal that started `livecode.py` |
| **A program** | a `.py` file that starts `import pycraft as pc`, makes a plot `w = pc.plot(x, y, z)` and ends with `pc.runplot(w, pc.adventure)` |

At the prompt, `w` is your plot, `pc` is pycraft, `math` and `random` are ready. A line starting with **:** is a prompt command
(below); anything else is Python. A line that ends with `:` (a `for`, `if`, `def`) continues on the next lines: finish it with an empty line.

## Three ways to write a command

All of these do the same thing at the prompt:

```
placeblock 0 0 0 stone            plain: the command, then its values with spaces (no brackets, no quotes)
placeblock(0, 0, 0, 'stone')      Python, without the w.
w.placeblock(0, 0, 0, 'stone')    Python, the full way (needed in programs)
```

The plain way shows the Python it turned into (`-> w.placeblock(0, 0, 0, 'stone')`), so you learn the real way as you go.
Words with spaces go in quotes: `say "hello there"`. Anything with brackets (lists, calculations) must be written as Python.
Colons are optional for prompt commands: `undo`, `tp 5 1 5`, `fly`.

Every command that puts something at a place is written the same way: **the place first, then what to put there**.

```
placeblock <x> <y> <z> [block]          placeblock 3 1 3 stone
spawnmob   <x> <y> <z> [creature]       spawnmob 5 1 5 zombie
npc        <x> <y> <z> <name> <lines>   npc 4 1 2 "Guide" "Welcome!"
tree       <x> <y> <z> [kind]           tree 8 1 8 birch
fill       <x1> <y1> <z1> <x2> <y2> <z2> <block>
```

(`[ ]` means you can leave it out: `placeblock 3 1 3` puts stone, `spawnmob 5 1 5` a pig. The older `spawnmob('zombie', 5, 1, 5)` order still works in programs.)

## Tab completion, hints and indent

- **Tab** finishes the word you are typing: commands (`pl<Tab>`), block names (`placeblock 0 0 0 oak_<Tab>`), creatures (`spawnmob 1 1 1 zom<Tab>`), `pc.` names (`pc.ob<Tab>`), `:commands`. Press Tab again to go through the choices. It also finds names that only *contain* what you typed, and fixes near-misses.
- **The hint line** (in the game, under the input) shows how the command is written (`placeblock x y z [id] [facing]`) and the names that fit.
- **Several lines**: in the game the prompt is a small editor. Enter runs what you typed, *unless* you are in the middle of a block
  (a line ending in `:`, like `for` and `if`, or brackets that are not closed yet): then Enter starts a new, indented line, and Enter on an
  empty line runs the whole block. **Shift+Enter** always starts a new line. Up/Down on the first/last line bring back earlier code.
- **Indent**: after a line ending in `:` the next line starts indented by itself; `else:`/`elif:` step back; an empty line ends the block. You can type your own spaces instead.
- Plain commands work inside blocks, with variables and sums as numbers: `placeblock i+3 1 3 stone`.

## Rules for every command

- **Coordinates** `x y z`: x goes east, **y goes up**, z goes south. `(0, 0, 0)` is the corner of the plot, on the ground. A block at y = 1 stands on the ground.
- **Boxes** `x1, y1, z1, x2, y2, z2`: two opposite corners, both included, in any order.
- **A block** is its name in quotes (`'stone'`, `'oak_planks'`, `'air'` removes), the same name without quotes as `pc.stone` / `pc.oak_planks` (also your mod's blocks, like `pc.snad`), or its number. `pc.blocklist()` prints them; `:blocks WORD` searches.
- **facing** is `'north'`, `'south'`, `'east'` or `'west'`.
- Text goes in quotes. Lists use `[...]`. Mistakes print a message that says what to fix and often suggests the right name.
- The game is always **adventure** (walk and use things) or **spectator** (fly): you can never place or break blocks by hand; you build with commands.

## Prompt commands (start with `:`)

| Command | Does |
|---|---|
| `:undo [n]` / `:redo [n]` | take back / put back the last step(s) (in game: **U** / **Y**) |
| `:delay N` | ticks between blocks (4 = fifth of a second, 20 = one second, 0 = instant) |
| `:clear` | remove everything you built (undoable) |
| `:save NAME` / `:load NAME` | keep / open a world as `NAME.pcplot` |
| `:export FILE.py` | write everything you typed as a program |
| `:run FILE.py` | run a file of code here (undoable as one step) |
| `:history` | list what you typed |
| `:tp X Y Z` | move yourself there |
| `:fly` / `:walk` | spectator flying / walking again |
| `unstuck` | move to the nearest free spot if you are inside blocks (also the **Unstuck** button in the Esc menu) |
| `:blocks WORD` | find block names containing WORD |
| `:help` / `:quit` | the list / close the game |

## Building: `w.<command>(...)`

**Blocks**
- `placeblock(x, y, z, id, facing=None)` one block
- `removeblock(x, y, z)`
- `fill(x1,y1,z1, x2,y2,z2, id)` solid box · `hollowbox(...same..., id)` walls, floor and roof only
- `line(x1,y1,z1, x2,y2,z2, id)` · `sphere(cx, cy, cz, radius, id, hollow=False)`
- `replace(old, new [, six corner numbers])` change one block kind into another
- `getblock(x, y, z)` · `count(id=None)` · `clear()`
- `terrain(height_function, top='grass', under='dirt')` hills from a function `height(x, z)`
- `text(x, y, z, 'HI', id='stone_bricks', size=1, axis='x')` block letters
- `image(x, y, z, 'picture.png', width=None, height=None, axis='x')` a picture as a wall of blocks

**Ready-made things**
- `house(x, y, z, width=7, depth=7, height=4, walls=, roof=, floor=, door='north')`
- `tree(x, y, z, kind='oak', height=None)` (`'oak' 'birch' 'spruce' 'jungle'`, or a wood you added) · `maze(x, y, z, cols=8, rows=8)` · `village(x, y, z, houses=4)`
- `door(x, y, z, facing, open=False)` · `torch(x, y, z, on='floor')` · `sign(x, y, z, text, facing='south')`
- `lever`, `button`, `lamp`, `pressureplate`, `wire(x1,y1,z1, x2,y2,z2)` redstone
- `portal(x, y, z, width=2, height=3, axis='x')` a Nether portal

**Copy and paste**
- `c = w.copy(x1,y1,z1, x2,y2,z2)` then `w.paste(c, x, y, z, rotate=0, mirror=None)` (`pc.rotate(c, 90)`, `pc.mirror(c, 'x')`) · `c.save('shape.pcschem')`

**Creatures, characters, the player**
- `spawnmob(x, y, z, 'pig')` returns a creature you can order (`.walk_to(x,y,z)`, `.follow()`, `.stay()`, `.say('hi')`, `.onclick(f)`, `.remove()`) · `removemobs()` · `pc.moblist()`
- `npc(x, y, z, name, lines)` someone who talks
- `turtle(x, y, z, facing, block)` a builder you steer: `forward(n) back(n) left(n) right(n) up(n) down(n) turn() penup() pendown()`
- `give('diamond_sword', 1)` · `teleport(x, y, z)` · `spawnpoint(x, y, z)` · `playerpos()`

**The world**
- `settime('day'|'night'|'sunrise'|'sunset'|ticks)` · `weather('clear'|'rain'|'snow'|'storm')` · `music(on)` · `say('text', seconds)` · `playsound('levelup')`
- `goal(x, y, z, 'You win!')` · `onclick(x,y,z, f)` · `onenter(x,y,z, f)` · `onkey('f', f)` · `every(seconds, f)` run your function on an event
- `delay(ticks)` · `wait(seconds)` pace a script · `undo()` / `redo()`

**Random helpers** `seed(n)`, `randint(a, b)`, `choose(...)`, `chance(p)`, `coin()`, `noise(x, z, scale)`

## Saving, sharing, school

- `w.save('name')` / `pc.load('name.pcplot')` · `w.share()` / `w.loadcode(code)` a short text to give to a classmate
- `w.challenge('house')`, `w.check()`, `w.hint()`, `w.submit()`, `w.feedback()` · `pc.challenges()` · `pc.levels()`, `w.level(n)` · `w.screenshot()`
- Programs: `pc.runplot(w, pc.adventure)` or `pc.spectator` · options `time=`, `dimension='nether'`, `peaceful=True`, `message=` · `pc.live(w, function)` runs a function while the game is open

## Mods: your own blocks, wood, items, creatures

```python
m = pc.mod('name')                                   # start a mod
m.addblock('snad', 'snad.png', like='sand')          # texture: 'a.png' | ('top.png','side.png') | {'top': ...}
m.addwood('purple', 'leaves.png', name='plum')       # plum_log, _planks, _leaves, _sapling, _slab, _stairs, _fence
m.additem('vine', 'vine.png', food=2)
m.recipe(['SS', 'SS'], {'S': 'snad'}, 'sandstone')   # shaped recipe · m.shapeless([...], result) · m.smelt(a, b)

g = pc.mob(pc.golem, 'vine_golem')                   # base it on any creature, or on one you made: pc.mob(g, 'x')
g.texture('skin.png').health(60).speed(1).attack(8).scale(1.2).hostile().title('Vine Golem')
g.drops([('vine', 1, 3)])                            # (item, least, most)
g.spawncondition(pc.block_placement('shape.pcschem'))
```

Every creature is `pc.<name>` (`pc.zombie`, `pc.golem`, `pc.vine_golem`). Helpers: `pc.export_texture('sand', 'snad.png')`, `pc.export_skin(pc.golem, 'skin.png')`.

**Spawn conditions** (add as many as you like)

| Condition | The creature appears... |
|---|---|
| `pc.block_placement('shape.pcschem', consume=True, rotate=True)` | when you build that shape (any way round); the blocks turn into it |
| `pc.near_block('vine_block', radius=6, chance=.15, limit=3)` | now and then near those blocks |
| `pc.on_block('grass')` | now and then standing on those blocks |
| `pc.at_night()` | in the dark |
| `pc.anywhere()` | now and then, anywhere |

**Pictures and files**
- `paint snad.png --like sand` (prompt) · `pc.paint('snad.png', like='sand')` · `python3 painter.py snad.png` opens the painter
- `m.save('plum.pcmod')` · `pc.loadmod('plum.pcmod')` · `m.submit('Sam')` · teachers: `python3 modtool.py info|check|install|review`

In the full game, put the mod file (`.pcmod` or `.py`) in `mods/` and it loads at start. More: [README_mods.md](README_mods.md), [README_livecode.md](README_livecode.md).

## Asking an assistant for a build

Say what, where and with what, in plot coordinates. For example:

> "In my plot (32 x 16 x 32): a 9 x 9 stone-brick tower, 12 high, at x=10, z=10, with a door facing south and torches inside, using only these commands."

The best answers are `w.<command>(...)` lines you can paste at the `/` prompt one at a time, so you can undo (`:undo`) any step you don't like.
