# The .pcplot and .pcchallenge files

Both are plain JSON text (open them in any editor). They are data only; loading one never runs code.

## .pcplot (a saved plot)

```json
{
  "format": "pcplot", "version": 2,
  "title": "Sam's bridge",
  "size": [30, 12, 14],
  "blocks": { "grass": [0,0,0, 1,0,0, ...], "oak_planks": [10,0,7, 11,0,7, ...] },
  "facing": [[3, 1, 4, "south"]],
  "mobs": [["pig", 12, 1, 12]],
  "signs": [[3, 1, 4, ["Cross the river!", "Page two"]]],
  "npcs": [{"kind": "villager", "pos": [6, 1, 8], "name": "Ferryman", "lines": ["Hello"]}],
  "settings": {"time": "day", "cycle": false, "weather": "clear", "music": true, "start": [15, 1, -4]},
  "tutorial": {"level": 2, "summary": "...", "steps": ["..."], "try_it": ["..."], "code": "the program that builds it"},
  "meta": { ... only in a hand-in ... }
}
```

* `blocks` maps a block name to a flat list of coordinates `x, y, z, x, y, z, ...`. (`y` is up; `0,0,0` is the corner.)
* `facing` lists which way an oriented block (furnace, door, sign...) points.
* The functions a student wrote (events) are not saved.
* `tutorial` is optional: notes for `tutorialworld.py` (see [README_tutorials.md](README_tutorials.md)).

### The `meta` section of a hand-in

```json
"meta": {
  "student": "Sam", "challenge": "bridge", "attempt": 2, "submitted": "2026-10-04T10:09:39",
  "note": "My first try", "level": null, "library": "pycraft 1",
  "results": [{"label": "...", "ok": true, "detail": ""}], "score": 8, "out_of": 10,
  "code": {"file": "mybridge.py", "text": "import pycraft as pc ..."}
}
```

## .pcchallenge (a task)

```json
{
  "format": "pcchallenge", "version": 1, "id": "bridge", "title": "Cross the river", "brief": "...",
  "size": [30, 12, 14], "points": 10, "hints": ["..."], "author": "...",
  "starter": { ...a .pcplot's contents... },
  "checks": [{"type": "path", "from": [2,1,7], "to": [27,1,7], "label": null},
             {"type": "block_count", "block": ["oak_planks"], "min": 10, "max": null, "label": null}]
}
```

Check types: `block_count`, `total_blocks`, `tallest`, `kinds`, `path`, `area`, `creatures`, `builtin`.
Make them with `pc.require.*` (see [README_teachers.md](README_teachers.md)).

## The hand-in folder

```
submissions/<challenge>/<name>.pcplot          the latest hand-in
submissions/<challenge>/<name>.review.json     the review: {student, challenge, attempt, score, out_of, comment, reviewer, reviewed}
submissions/<challenge>/history/<name>.<n>.pcplot
```

## Limits

A plot is at most 256 x 100 x 256 and 2,000,000 blocks. Unknown blocks and creatures are dropped when a file is opened.
