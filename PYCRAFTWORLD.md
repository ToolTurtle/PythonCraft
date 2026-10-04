# pycraftWorld - the quick, one-plot style

`pycraftWorld` is the same library as [`pycraft`](PYCRAFT.md) with **one plot made for you**. Every method of a plot is also a
function here:

```python
import pycraftWorld as w

w.size(16, 16, 16)                  # your plot (this is the plot's resize())
w.fillblocks(0, 0, 0, 15, 0, 15, 'grass')
w.house(4, 1, 4)
w.show()                            # opens the game (this is pc.runplot with your plot); it is the last line
```

The full list of functions, with examples, is in [PYCRAFT.md](PYCRAFT.md): wherever it says `w.something(...)` you can write
`something(...)` after `import pycraftWorld as w`. Differences:

| pycraft | pycraftWorld |
|---|---|
| `w = pc.plot(16, 16, 16)` | `w.size(16, 16, 16)` |
| `pc.runplot(w, pc.adventure, ...)` | `w.show(mode='adventure', ...)` |
| `pc.live(w, build)` | `w.live(build)` |
| `w = pc.level(3)` | `w.level(3)` |
| `w = pc.challenge('bridge')` | `w.challenge('bridge')` (it attaches the challenge to your plot) |
| `pc.load('house.pcplot')` | `w.load('house.pcplot')` |

Use `pycraft` when you want more than one plot or like working with objects.
