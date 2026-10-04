# Mods: your own blocks, wood and creatures

```python
import pycraft as pc

m = pc.mod('my-mod')
m.addblock('snad', 'snad.png', like='sand')            # a block that falls like sand
m.addwood('purple', 'plum_leaves.png', name='plum')    # plum_log, _planks, _leaves, _sapling, _slab, _stairs, _fence

golem = pc.mob(pc.golem, 'vine_golem')                 # a new creature made from the iron golem
golem.texture('vine_golem.png').health(60)
golem.spawncondition(pc.block_placement('vinegolem_spawn.pcschem'))

w = pc.plot(20, 14, 20)
w.tree(4, 1, 4, 'plum')
pc.runplot(w, pc.adventure)
```

Pictures are `.png` files next to your program. Everything is added the moment you call it, so the new names work in
`placeblock`, `fill`, `tree`, `spawnmob` and so on. Mistakes give a message that says what to fix.

## Blocks
`m.addblock(name, texture, like=None, **options)`
- `texture`: one picture for every side, `(top, side)`, `(top, side, bottom)`, or `{'top': ..., 'side': ...}`.
- `like='sand'` copies how another block behaves. Options: `hardness`, `tool`, `light` (0-15), `transparent`, `gravity`, `drops`, `sound`.
- `pc.export_texture('sand', 'snad.png')` gives you a 16x16 picture to paint on.

## Wood
`m.addwood(colour, leaves_picture, name='plum')` — colour is a name (`'purple'`), `'#aa3355'` or `(r, g, b)`.
Makes the whole family with crafting recipes; saplings grow into trees; `w.tree(x, y, z, 'plum')` works.

## Items and recipes
`m.additem('vine', 'vine.png', food=2)`, `m.recipe(['SS', 'SS'], {'S': 'snad'}, 'sandstone')`, `m.shapeless([...], result)`, `m.smelt('snad', 'glass')`.

## Creatures
`pc.mob(pc.golem, 'vine_golem')` then (each returns the creature, so they chain):
`.texture('skin.png')` (`pc.export_skin(pc.golem, 'skin.png')` gives a skin to paint), `.health(n)`, `.speed(n)`, `.attack(n)`, `.scale(2)`,
`.drops([('vine', 1, 3)])`, `.hostile()`, `.title('Vine Golem')`, `.spawncondition(...)`.
It behaves like the creature it is made from. `pc.moblist()` lists them; `w.spawnmob('vine_golem', x, y, z)` places one.

## When creatures appear (`spawncondition`)
- `pc.block_placement('shape.pcschem')` — build the shape (any way round) and the blocks turn into the creature. Make the shape file with `w.copy(x1, y1, z1, x2, y2, z2).save('shape.pcschem')`.
  `consume=False` keeps the blocks.
- `pc.near_block('vine_block')`, `pc.on_block('grass')`, `pc.at_night()`, `pc.anywhere()` — now and then, near you.

## The full game
Put your mod file in the `mods/` folder (a mod is a program without the `runplot` line). PythonCraft loads it at start.
Saves remember modded blocks by name: if the mod is missing later, those blocks are skipped with a note.
See `examples/mod_example/mod_demo.py`.
