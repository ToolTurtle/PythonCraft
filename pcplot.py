"""pcplot - the .pcplot file, challenges, submissions and reviews.  (No game window needed.)

A .pcplot file is a saved plot: plain JSON text, so a teacher can open it in any editor. It holds blocks and creatures,
signs and what characters say, a few settings (time, weather...) and, when it was handed in, a `meta` section with the
student's name, the check results and a copy of the student's program. Loading a .pcplot never runs code: the program
inside is only ever shown as text.

A .pcchallenge file is a task from a teacher: a brief, a plot size, an optional starting build and a list of checks.

The handing-in folder looks like this (one folder per challenge, one file per student):

    submissions/
        bridge/
            Sam.pcplot            the latest hand-in
            Sam.review.json       the teacher's score and comment (after review)
            history/Sam.1.pcplot  older hand-ins
"""
import json
import os
import re
import time
from collections import deque
from pathlib import Path

FORMAT = 'pcplot'
VERSION = 2
MAX_BLOCKS = 2_000_000
MAX_SIZE = (256, 100, 256)
LIBRARY = 'pycraft 1'


class PlotFileError(ValueError):
    """A .pcplot / .pcchallenge file that cannot be used."""


# ---- the .pcplot file ----------------------------------------------------------------------------------------------

def pack_blocks(blocks):
    """{(x, y, z): name} -> {name: [x, y, z, x, y, z, ...]}: compact, and still readable."""
    packed = {}
    for (x, y, z), name in blocks.items():
        packed.setdefault(name, []).extend((x, y, z))
    return packed


def unpack_blocks(packed):
    blocks = {}
    for name, flat in packed.items():
        for i in range(0, len(flat), 3):
            blocks[(flat[i], flat[i + 1], flat[i + 2])] = name
    return blocks


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def normalize(data):
    """Bring any older plot data (saves from before .pcplot existed, share codes) up to the current layout."""
    if not isinstance(data, dict):
        raise PlotFileError('This is not a plot file.')
    out = dict(data)
    blocks = out.get('blocks', {})
    if isinstance(blocks, list):                                  # older: [[x, y, z, name], ...]
        packed = {}
        for entry in blocks:
            if not (isinstance(entry, (list, tuple)) and len(entry) == 4):
                raise PlotFileError('A block in this file is not written as [x, y, z, name].')
            packed.setdefault(entry[3], []).extend(entry[:3])
        out['blocks'] = packed
    out.setdefault('facing', [])
    out.setdefault('mobs', [])
    out.setdefault('signs', [])
    out.setdefault('npcs', [])
    out.setdefault('settings', {})
    out.setdefault('title', '')
    out.setdefault('meta', {})
    out.setdefault('tutorial', None)
    return out


def validate(data, known_blocks=None, known_mobs=None):
    """Check a plot's data is safe and sensible. Returns (clean data, [warnings]).
    Unknown block names and creatures are dropped with a warning instead of making the file unusable."""
    data = normalize(data)
    warnings = []
    size = data.get('size')
    if not (isinstance(size, (list, tuple)) and len(size) == 3 and all(_is_int(v) and v >= 1 for v in size)):
        raise PlotFileError('The plot size is missing or wrong.')
    if any(size[i] > MAX_SIZE[i] for i in range(3)):
        raise PlotFileError(f'That plot is too big (the most is {MAX_SIZE[0]} x {MAX_SIZE[1]} x {MAX_SIZE[2]}).')
    clean_blocks, total = {}, 0
    if not isinstance(data['blocks'], dict):
        raise PlotFileError('The blocks are not written the way a .pcplot file does it.')
    for name, flat in data['blocks'].items():
        if not isinstance(name, str) or not isinstance(flat, list) or len(flat) % 3 or not all(_is_int(v) for v in flat):
            raise PlotFileError(f'The block list for {name!r} is damaged.')
        if known_blocks is not None and name not in known_blocks:
            warnings.append(f'unknown block {name!r} ({len(flat) // 3} placed) was left out')
            continue
        kept = []
        for i in range(0, len(flat), 3):
            x, y, z = flat[i:i + 3]
            if 0 <= x < size[0] and 0 <= y < size[1] and 0 <= z < size[2]:
                kept.extend((x, y, z))
        total += len(kept) // 3
        if total > MAX_BLOCKS:
            raise PlotFileError('There are too many blocks in this file.')
        clean_blocks[name] = kept
    data['blocks'] = clean_blocks
    data['facing'] = [list(f) for f in data['facing']
                      if isinstance(f, (list, tuple)) and len(f) == 4 and all(_is_int(v) for v in f[:3]) and isinstance(f[3], str)]
    mobs = []
    for entry in data['mobs']:
        if isinstance(entry, (list, tuple)) and len(entry) == 4 and isinstance(entry[0], str) and all(_is_int(v) for v in entry[1:]):
            if known_mobs is not None and entry[0] not in known_mobs:
                warnings.append(f'unknown creature {entry[0]!r} was left out')
            else:
                mobs.append(list(entry))
    data['mobs'] = mobs[:2000]
    signs = []
    for entry in data['signs']:
        if isinstance(entry, (list, tuple)) and len(entry) == 4 and all(_is_int(v) for v in entry[:3]) and isinstance(entry[3], list):
            signs.append([entry[0], entry[1], entry[2], [str(p)[:600] for p in entry[3]][:20]])
    data['signs'] = signs[:500]
    npcs = []
    for entry in data['npcs']:
        if isinstance(entry, dict) and isinstance(entry.get('kind'), str) and isinstance(entry.get('pos'), list) \
                and len(entry['pos']) == 3 and all(_is_int(v) for v in entry['pos']) and isinstance(entry.get('lines'), list):
            if known_mobs is not None and entry['kind'] not in known_mobs:
                continue
            npcs.append({'kind': entry['kind'], 'pos': entry['pos'], 'name': str(entry.get('name', ''))[:60],
                         'lines': [str(t)[:600] for t in entry['lines']][:20]})
    data['npcs'] = npcs[:500]
    if not isinstance(data['settings'], dict):
        data['settings'] = {}
    data['title'] = str(data.get('title', ''))[:120]
    if not isinstance(data['meta'], dict):
        data['meta'] = {}
    data['tutorial'] = clean_tutorial(data.get('tutorial'))
    return data, warnings


def clean_tutorial(info):
    """The tutorial notes in a plot (what to do in it, things to try, the program that built it), or None."""
    if not isinstance(info, dict):
        return None
    def texts(items, limit):
        return [str(t)[:400] for t in items][:limit] if isinstance(items, list) else []
    level = info.get('level')
    return {'level': level if _is_int(level) and 1 <= level <= 9 else 1, 'summary': str(info.get('summary', ''))[:600],
            'steps': texts(info.get('steps'), 30), 'try_it': texts(info.get('try_it'), 30),
            'code': str(info.get('code', ''))[:30000]}


def write_json(path, payload):
    """Write a file in one go, so a crash never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(payload, separators=(',', ':')))
    os.replace(temporary, path)


def write_plot(path, data):
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix('.pcplot')
    payload = dict(data, format=FORMAT, version=VERSION)
    payload['blocks'] = data['blocks'] if isinstance(data['blocks'], dict) else pack_blocks(data['blocks'])
    write_json(path, payload)
    return path


def read_plot(path, known_blocks=None, known_mobs=None):
    """Read and check a .pcplot (or an older plot save). Returns (data, warnings)."""
    try:
        text = Path(path).read_text()
    except OSError as error:
        raise PlotFileError(f'Could not read {str(path)!r}: {error}') from None
    try:
        data = json.loads(text)
    except ValueError:
        raise PlotFileError(f'{str(path)!r} is not a plot file (it is not readable as JSON).') from None
    return validate(data, known_blocks, known_mobs)


def read_meta(path):
    """Only the summary of a hand-in (fast: used by the review list)."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    meta = data.get('meta') if isinstance(data.get('meta'), dict) else {}
    blocks = data.get('blocks')
    count = (sum(len(v) // 3 for v in blocks.values()) if isinstance(blocks, dict)
             else len(blocks) if isinstance(blocks, list) else 0)
    return dict(meta, blocks=count, title=data.get('title', ''), size=data.get('size'))


# ---- challenges ---------------------------------------------------------------------------------------------------

class Challenge:
    """A task for students: what to build and how it is checked.

        c = Challenge('bridge', 'Cross the river', 'Build a bridge from one side to the other.',
                      size=(24, 8, 12), starter=my_plot,
                      checks=[require.path((2, 1, 6), (21, 1, 6)), require.blocks('oak_planks', 10)])
        c.save('challenges/bridge.pcchallenge')

    `starter` is a Plot (or the plot's data) that students start with. `points` is what a perfect build is worth."""

    def __init__(self, id, title, brief, size=(16, 16, 16), starter=None, checks=(), points=10, hints=(), author=''):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', str(id)):
            raise ValueError('A challenge id uses letters, digits, - and _ only (up to 40), like "bridge" or "week3-tower".')
        self.id, self.title, self.brief = str(id), str(title), str(brief)
        self.size = tuple(size) if size else None
        self.starter = starter
        self.checks = [dict(c) for c in checks]
        self.points, self.hints, self.author = points, list(hints), author
        for check in self.checks:
            if check.get('type') not in CHECKS:
                raise ValueError(f"Unknown check type {check.get('type')!r}. Use the require helpers (require.blocks, require.path...).")

    def __repr__(self):
        return f'<Challenge {self.id!r}: {self.title} ({len(self.checks)} checks)>'

    def starter_data(self):
        """The starting build as plot data (or None)."""
        if self.starter is None:
            return None
        data = self.starter._data() if hasattr(self.starter, '_data') else self.starter
        return normalize(data)

    def to_dict(self):
        out = {'format': 'pcchallenge', 'version': 1, 'id': self.id, 'title': self.title, 'brief': self.brief,
               'size': list(self.size) if self.size else None, 'checks': self.checks, 'points': self.points,
               'hints': self.hints, 'author': self.author}
        starter = self.starter_data()
        if starter is not None:
            starter = dict(starter)
            starter['blocks'] = starter['blocks'] if isinstance(starter['blocks'], dict) else pack_blocks(starter['blocks'])
            out['starter'] = starter
        return out

    def save(self, path):
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix('.pcchallenge')
        write_json(path, self.to_dict())
        return path

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get('format') != 'pcchallenge':
            raise PlotFileError('This is not a .pcchallenge file.')
        try:
            return cls(data['id'], data['title'], data.get('brief', ''), data.get('size') or None, data.get('starter'),
                       data.get('checks', []), data.get('points', 10), data.get('hints', []), data.get('author', ''))
        except (KeyError, ValueError, TypeError) as error:
            raise PlotFileError(f'This challenge file is damaged: {error}') from None

    @classmethod
    def load(cls, path):
        try:
            return cls.from_dict(json.loads(Path(path).read_text()))
        except OSError as error:
            raise PlotFileError(f'Could not read {str(path)!r}: {error}') from None
        except ValueError as error:
            if isinstance(error, PlotFileError):
                raise
            raise PlotFileError(f'{str(path)!r} is not a challenge file.') from None


class _Require:
    """Ready-made checks to put in a challenge: require.blocks('oak_planks', 10), require.door(), ..."""

    @staticmethod
    def blocks(block, at_least=1, at_most=None, label=None):
        names = [block] if isinstance(block, str) else list(block)
        return {'type': 'block_count', 'block': names, 'min': at_least, 'max': at_most, 'label': label}

    @staticmethod
    def door(label=None):
        return {'type': 'block_count', 'block': ['oak_door_b'], 'min': 1, 'max': None, 'label': label or 'has a door'}

    @staticmethod
    def window(label=None):
        return {'type': 'block_count', 'block': ['glass', 'glass_pane'], 'min': 1, 'max': None, 'label': label or 'has a window'}

    @staticmethod
    def torches(at_least=2, label=None):
        return {'type': 'block_count', 'block': ['torch'], 'min': at_least, 'max': None,
                'label': label or f'has at least {at_least} torches'}

    @staticmethod
    def total(at_least, label=None):
        return {'type': 'total_blocks', 'min': at_least, 'label': label}

    @staticmethod
    def tall(at_least, label=None):
        return {'type': 'tallest', 'min': at_least, 'label': label}

    @staticmethod
    def kinds(at_least=3, each=20, label=None):
        return {'type': 'kinds', 'min': at_least, 'each': each, 'label': label}

    @staticmethod
    def path(start, end, label=None):
        """Someone can walk from `start` to `end` (two (x, y, z) cells): a bridge, a staircase, a corridor."""
        return {'type': 'path', 'from': list(start), 'to': list(end), 'label': label}

    @staticmethod
    def area(corner1, corner2, at_least=0.9, block=None, label=None):
        """A box of space is (mostly) filled with solid blocks (of the kinds listed, if given): a floor, a wall."""
        names = None if block is None else ([block] if isinstance(block, str) else list(block))
        return {'type': 'area', 'box': list(corner1) + list(corner2), 'min': at_least, 'block': names, 'label': label}

    @staticmethod
    def creatures(at_least=1, kind=None, label=None):
        return {'type': 'creatures', 'kind': kind, 'min': at_least, 'label': label}

    @staticmethod
    def builtin(name, label=None):
        """One of the ready-made checks: 'house', 'tower', 'bridge', 'garden', 'pyramid' or 'portal'."""
        return {'type': 'builtin', 'name': name, 'label': label}


require = _Require()


# non-solid things you walk through (for the walking check and the tallest-column check)
NON_SOLID = {'torch', 'ladder', 'redstone_wire', 'redstone_wire_on', 'lever', 'lever_on', 'stone_button', 'nether_portal',
             'sugar_cane', 'dandelion', 'poppy', 'red_mushroom', 'brown_mushroom', 'rail', 'powered_rail', 'fire', 'cobweb',
             'oak_door_b', 'oak_door_t', 'water', 'lava', 'oak_sign', 'glass_pane'}
LIQUID = {'water', 'lava'}


def _solid(blocks, pos):
    name = blocks.get(pos)
    return name is not None and name not in NON_SOLID


def _walkable(blocks, size, pos):
    """Can a player stand in this cell? (Something solid underneath, room for feet and head, not in a liquid.)
    The ground outside the plot's floor counts as solid at y = -1."""
    x, y, z = pos
    if not (0 <= x < size[0] and 0 <= y < size[1] and 0 <= z < size[2]):
        return False
    if _solid(blocks, pos) or blocks.get(pos) in LIQUID or _solid(blocks, (x, y + 1, z)):
        return False
    below = (x, y - 1, z)
    return True if y == 0 else _solid(blocks, below)


def find_path(blocks, size, start, end):
    """Is there a walkable route (steps of one block up or down are fine) from start to end? Returns the route or None."""
    start, end = tuple(start), tuple(end)
    if not _walkable(blocks, size, start) or not _walkable(blocks, size, end):
        return None
    came = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == end:
            route = []
            while cell is not None:
                route.append(cell)
                cell = came[cell]
            return route[::-1]
        x, y, z = cell
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                nxt = (x + dx, y + dy, z + dz)
                if nxt in came or not _walkable(blocks, size, nxt):
                    continue
                if dy == 1 and (_solid(blocks, (x, y + 2, z)) or _solid(blocks, (x + dx, y + 1, z + dz))):
                    continue                                       # no headroom to step up
                came[nxt] = cell
                queue.append(nxt)
    return None


def _label(check, default):
    return check.get('label') or default


def _blocks_label(names):
    return names[0] if len(names) == 1 else ' or '.join(names)


def _check_block_count(check, view):
    names = check['block'] if isinstance(check['block'], list) else [check['block']]
    found = sum(1 for n in view['blocks'].values() if n in names)
    low, high = check.get('min', 1), check.get('max')
    ok = found >= low and (high is None or found <= high)
    what = _blocks_label(names)
    label = _label(check, f'at least {low} {what}' + (f' (at most {high})' if high is not None else ''))
    detail = '' if ok else f'you have {found}' + (f', it needs {low}' if found < low else f', it needs at most {high}')
    return label, ok, detail


def _check_total(check, view):
    found = len(view['blocks'])
    ok = found >= check['min']
    return _label(check, f"at least {check['min']} blocks"), ok, '' if ok else f"you have {found}, it needs {check['min']}"


def _check_tallest(check, view):
    columns = {}
    for (x, y, z), name in view['blocks'].items():
        if name not in NON_SOLID:
            columns.setdefault((x, z), set()).add(y)
    best = 0
    for ys in columns.values():
        run = 0
        for y in range(view['size'][1]):
            run = run + 1 if y in ys else 0
            best = max(best, run)
    ok = best >= check['min']
    return _label(check, f"a tower at least {check['min']} blocks tall"), ok, '' if ok else f"your tallest is {best}, it needs {check['min']}"


def _check_kinds(check, view):
    counts = {}
    for name in view['blocks'].values():
        counts[name] = counts.get(name, 0) + 1
    good = sum(1 for c in counts.values() if c >= check.get('each', 1))
    ok = good >= check['min']
    return (_label(check, f"uses {check['min']} different blocks ({check.get('each', 1)}+ of each)"), ok,
            '' if ok else f"you used {good} kinds that much, it needs {check['min']}")


def _check_path(check, view):
    start, end = tuple(check['from']), tuple(check['to'])
    route = find_path(view['blocks'], view['size'], start, end)
    ok = route is not None
    label = _label(check, f'you can walk from {start} to {end}')
    if ok:
        return label, True, ''
    if not _walkable(view['blocks'], view['size'], start):
        return label, False, f'the start {start} is not a place you can stand'
    if not _walkable(view['blocks'], view['size'], end):
        return label, False, f'the end {end} is not a place you can stand'
    return label, False, 'there is a gap or a wall in the way'


def _check_area(check, view):
    x1, y1, z1, x2, y2, z2 = check['box']
    cells = [(x, y, z) for x in range(min(x1, x2), max(x1, x2) + 1) for y in range(min(y1, y2), max(y1, y2) + 1)
             for z in range(min(z1, z2), max(z1, z2) + 1)]
    names = check.get('block')
    good = sum(1 for c in cells if (view['blocks'].get(c) in names if names else _solid(view['blocks'], c)))
    fraction = good / max(1, len(cells))
    ok = fraction >= check.get('min', 0.9)
    what = _blocks_label(names) if names else 'blocks'
    return (_label(check, f"the area {tuple(check['box'][:3])} to {tuple(check['box'][3:])} is filled with {what}"), ok,
            '' if ok else f'{round(fraction * 100)}% filled, it needs {round(check.get("min", 0.9) * 100)}%')


def _check_creatures(check, view):
    kind = check.get('kind')
    found = sum(1 for m in view['mobs'] if kind is None or m[0] == kind)
    ok = found >= check.get('min', 1)
    return (_label(check, f"has {check.get('min', 1)} {kind or 'creature'}(s)"), ok,
            '' if ok else f"you have {found}, it needs {check.get('min', 1)}")


def _check_builtin(check, view):
    import pycraft_extras as x
    name = check['name']
    if name not in x.CHALLENGES:
        return _label(check, name), False, f'there is no ready-made check called {name!r}'
    problems = x.CHALLENGES[name][1](view['blocks'], tuple(view['size']))
    return _label(check, x.CHALLENGES[name][0]), not problems, problems[0] if problems else ''


CHECKS = {'block_count': _check_block_count, 'total_blocks': _check_total, 'tallest': _check_tallest, 'kinds': _check_kinds,
          'path': _check_path, 'area': _check_area, 'creatures': _check_creatures, 'builtin': _check_builtin}


def run_checks(checks, blocks, size, mobs=()):
    """Run a challenge's checks on a build. Returns [{'label', 'ok', 'detail'}]. (Never runs anyone's code.)"""
    view = {'blocks': blocks, 'size': tuple(size), 'mobs': list(mobs)}
    results = []
    for check in checks:
        try:
            label, ok, detail = CHECKS[check['type']](check, view)
        except Exception as error:                                    # a badly written check must not stop the lesson
            label, ok, detail = check.get('label') or check.get('type', '?'), False, f'this check could not run ({error})'
        results.append({'label': label, 'ok': bool(ok), 'detail': detail})
    return results


def score_of(results, points):
    """(score, out_of): the points a build earns for the share of checks passed."""
    if not results:
        return points, points
    return round(points * sum(1 for r in results if r['ok']) / len(results)), points


# ---- handing in --------------------------------------------------------------------------------------------------

def slug(text, fallback='student'):
    """Safe for a file name: letters, digits, - and _ (so a name can never point outside the folder)."""
    text = re.sub(r'[^A-Za-z0-9_-]+', '_', str(text or '')).strip('_')[:40]
    return text or fallback


def submissions_folder(to=None, start_dir='.'):
    chosen = to or os.environ.get('PYCRAFT_SUBMISSIONS') or 'submissions'
    path = Path(chosen)
    return path if path.is_absolute() else Path(start_dir) / path


def hand_in(data, student, challenge_id, folder, note='', results=None, score=None, out_of=None, level=None, code=None):
    """Write a student's build to the hand-in folder as <folder>/<challenge>/<name>.pcplot. A hand-in that was
    already there moves to history/. Returns (path, attempt)."""
    directory = Path(folder) / slug(challenge_id or 'free', 'free')
    name = slug(student)
    latest = directory / f'{name}.pcplot'
    attempt = 1
    if latest.exists():
        old = read_meta(latest) or {}
        attempt = int(old.get('attempt', 1)) + 1
        history = directory / 'history'
        history.mkdir(parents=True, exist_ok=True)
        os.replace(latest, history / f"{name}.{old.get('attempt', attempt - 1)}.pcplot")
    meta = {'student': str(student)[:60], 'challenge': challenge_id or 'free', 'attempt': attempt,
            'submitted': time.strftime('%Y-%m-%dT%H:%M:%S'), 'note': str(note or '')[:1000], 'results': results or [],
            'score': score, 'out_of': out_of, 'level': level, 'library': LIBRARY, 'code': code}
    payload = dict(data, meta=meta)
    write_plot(latest, payload)
    return latest, attempt


def list_submissions(folder, challenge=None):
    """Every hand-in in a folder, newest first: a list of dicts with the summary and the review (if any)."""
    folder = Path(folder)
    found = []
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob('*/*.pcplot')):
        if challenge and path.parent.name != challenge:
            continue
        meta = read_meta(path)
        if meta is None:
            continue
        review = read_review(path)
        found.append({'path': path, 'student': meta.get('student', path.stem), 'challenge': path.parent.name,
                      'attempt': meta.get('attempt', 1), 'submitted': meta.get('submitted', ''), 'score': meta.get('score'),
                      'out_of': meta.get('out_of'), 'blocks': meta.get('blocks', 0), 'note': meta.get('note', ''),
                      'results': meta.get('results', []), 'code': meta.get('code'), 'review': review,
                      'level': meta.get('level'), 'title': meta.get('title', '')})
    found.sort(key=lambda s: s['submitted'], reverse=True)
    return found


def review_path(plot_path):
    plot_path = Path(plot_path)
    return plot_path.with_name(plot_path.stem + '.review.json')


def read_review(plot_path):
    try:
        data = json.loads(review_path(plot_path).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_review(plot_path, score, out_of, comment, reviewer='', attempt=None):
    meta = read_meta(plot_path) or {}
    payload = {'student': meta.get('student', Path(plot_path).stem), 'challenge': Path(plot_path).parent.name,
               'attempt': attempt if attempt is not None else meta.get('attempt', 1), 'score': score, 'out_of': out_of,
               'comment': str(comment or '')[:2000], 'reviewer': str(reviewer or '')[:60],
               'reviewed': time.strftime('%Y-%m-%dT%H:%M:%S')}
    write_json(review_path(plot_path), payload)
    return payload


def find_hand_in(folder, student, challenge_id=None):
    """The path of a student's latest hand-in (in one challenge's folder, or the newest of any)."""
    folder, name = Path(folder), slug(student)
    if challenge_id:
        path = folder / slug(challenge_id, 'free') / f'{name}.pcplot'
        return path if path.exists() else None
    matches = [p for p in folder.glob(f'*/{name}.pcplot')]
    return max(matches, key=lambda p: p.stat().st_mtime) if matches else None


# ---- finding challenges ---------------------------------------------------------------------------------------------

def builtin_challenges():
    """The ready-made challenges (from pycraft_extras): {id: Challenge}."""
    import pycraft_extras as x
    return {name: Challenge(name, name.title(), what, size=None, checks=[{'type': 'builtin', 'name': name, 'label': what}])
            for name, (what, _fn) in x.CHALLENGES.items()}


def challenge_folders(start_dir='.'):
    folders = []
    if os.environ.get('PYCRAFT_CHALLENGES'):
        folders.append(Path(os.environ['PYCRAFT_CHALLENGES']))
    folders.append(Path(start_dir) / 'challenges')
    return folders


def find_challenges(start_dir='.'):
    """Every challenge file in the challenges folder(s): {id: path}."""
    found = {}
    for folder in challenge_folders(start_dir):
        if folder.is_dir():
            for path in sorted(folder.glob('*.pcchallenge')):
                found.setdefault(path.stem, path)
    return found
