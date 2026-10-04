# Challenges

There are three kinds. All of them let you check your own work; the second kind lets you **hand it in for review**.

| | What it is | Start with |
|---|---|---|
| **Challenge mode** | 12 levels, one block to a castle, with stars | `python3 challenge_mode.py` |
| **Teacher challenges** | a task from your teacher: a brief, maybe a starting build, checks. You hand in your work | `w = pc.challenge('bridge')` |
| **Quick checks** | "is this a house?" for any build | `w.challenge('house')` then `w.check()` |

## Challenge mode (12 levels)

```
python3 challenge_mode.py
```

Pick a level. It makes a file in `my_levels/` with the goal at the top. Write your code in the marked space, run the file,
and the game opens. It tells you what is missing or gives you stars (3 stars for finishing with 2 or fewer "not yet"s).
In the game: **C** shows the goal again and **K** checks your build. `w.hint()` gives a clue.

## Teacher challenges

```python
import pycraft as pc

w = pc.challenge('bridge')          # a plot with the river already in it, and the brief printed

# ---- build here ------------------------------------------------------------------
w.fill(10, 0, 6, 14, 0, 8, 'oak_planks')

w.check()                           # what is still missing?
w.submit('Sam', note='My first try')    # hand it in
pc.runplot(w, pc.adventure)         # walk around it
```

`pc.challenges()` lists the challenges you can take. Your teacher may give you a file: `pc.challenge('path/to/task.pcchallenge')`.

### check()

```
Cross the river:
  [x] you can walk from (2, 1, 7) to (27, 1, 7)
  [ ] built from at least 10 plank or stone blocks  (you have 4, it needs 10)
  [x] has at least 4 fence blocks as railings
Score: 8 / 10  (2 of 3 checks)
Not yet: fix the ones with [ ] and check() again.
```

Checking only looks at your build. It never changes anything, so check as often as you like.

### submit(): handing in

`w.submit('Sam')` saves a file called `submissions/bridge/Sam.pcplot`. It contains:

* your build (blocks, creatures, signs),
* the results of the checks and your score,
* your name and your note,
* **a copy of your program**, so your teacher can read how you did it (`w.submit('Sam', code=False)` leaves it out).

Nothing is sent over the internet. The file goes in a folder: your teacher will tell you where. If you were given a shared
folder, write `w.submit('Sam', to='/path/to/shared')`, or set it once with the setting `PYCRAFT_SUBMISSIONS`.
You can hand in again as often as you like. The newest one is reviewed; the old ones are kept in a `history` folder.

### feedback()

```python
w.feedback()                        # or: pc.feedback('Sam', 'bridge')
```

```
Review of bridge (attempt 2), by Ms Ng:
  Score: 9 / 10
  Great bridge! Next time add a torch on the far side.
```

If there is nothing yet it says it has not been reviewed.

## Quick checks

```python
w = pc.plot(20, 20, 20)
w.challenge('house')                # 'house', 'tower', 'pyramid', 'portal'...
w.house(4, 1, 4)
w.check()
```

## Questions

* **Can my teacher run my code?** No. The review tool shows your program as text and only opens your build.
* **Can I change a hand-in?** Hand in again; the newest replaces the older one.
* **What if I get a message about a missing name?** `w.submit('Sam')` needs your name. Set `PYCRAFT_NAME` to skip typing it.

[Back to the start](../README.md)
