"""pycraft - build a Minecraft-style world by writing Python.

    import pycraft as pc

    w = pc.plot(16, 16, 16)                    # a building plot: x, y, z
    w.fill(0, 0, 0, 15, 0, 15, 'grass')
    w.house(4, 1, 4)
    pc.runplot(w, pc.adventure)                # open the game and walk around it

A plot is an object: make as many as you like (`a = pc.plot(...)`, `b = pc.plot(...)`), build in each with its
methods, and run the one you want with pc.runplot(plot, mode). The mode is pc.adventure (walk around and use
things) or pc.spectator (fly around and look): the game never lets you place or break blocks.

Coordinates: x goes east, y goes UP, z goes south. (0, 0, 0) is the corner of your plot, on the ground.
A block's id is its name ('stone', 'oak_planks', ...) or its number: pc.blocklist() lists them all.

Nothing here opens the game window until you call runplot(), so your program can build as much as it likes
first. The library never touches your saved games.

(The older one-plot style, `import pycraftWorld as w`, still works: it is a plot made for you.)
"""
import difflib
import inspect
import json
import os
import random
import sys
import tempfile
import threading
import time as _time
import traceback

import pcplot as _pcplot
import pycraft_extras as _x

adventure = 'adventure'        # pc.runplot(plot, pc.adventure)
spectator = 'spectator'
Challenge = _pcplot.Challenge  # a task for students (see pcplot.py)
require = _pcplot.require      # ready-made checks: pc.require.blocks('oak_planks', 10)

_FLOOR = 3


_START_DIR = os.getcwd()


_PROGRESS_FILE = os.path.abspath(os.environ.get('PYCRAFTWORLD_PROGRESS') or 'pycraft_progress.json')


def _mob_names():
    from mobtypes import TYPES
    return set(TYPES)


def _userpath(path):
    """A file or folder the way you meant it: relative to where your script was started."""
    path = os.fspath(path)
    return path if os.path.isabs(path) else os.path.join(_START_DIR, path)


def _names():
    """All the block names. (Loaded the first time it is needed.)"""
    import blocks
    return list(blocks.BLOCKS)


class _Blocks:
    """BLOCKS['stone'] -> number, BLOCKS[number] -> 'stone'. (Looked up from the game's block list.)"""

    def __getitem__(self, key):
        names = _names()
        if isinstance(key, str):
            return names.index(key) + 1
        return names[key - 1]

    def __iter__(self):
        return iter(_names())

    def __len__(self):
        return len(_names())

    def __contains__(self, key):
        return key in _names() or (isinstance(key, int) and 1 <= key <= len(_names()))

    def __repr__(self):
        return f'<{len(self)} blocks: call blocklist() to see them>'


BLOCKS = _Blocks()


def _name_of(block):
    """Turn a block id (a name or a number) into a block name, with a friendly error if it is wrong."""
    names = _names()
    if isinstance(block, str):
        name = block.strip().lower().replace(' ', '_')
        if name in ('air', 'none', ''):
            return None
        if name in names:
            return name
        close = difflib.get_close_matches(name, names, n=3)
        hint = f' Did you mean {", ".join(repr(c) for c in close)}?' if close else ' Call blocklist() to see all the blocks.'
        raise ValueError(f'There is no block called {block!r}.{hint}')
    if isinstance(block, int) and not isinstance(block, bool):
        if block == 0:
            return None
        if 1 <= block <= len(names):
            return names[block - 1]
        raise ValueError(f'Block number {block} does not exist (use 1 to {len(names)}, or 0 for air).')
    raise TypeError(f'A block id must be a name like "stone" or a number, not {block!r}.')


def blockid(name):
    """The number of a block name."""
    return BLOCKS[_name_of(name)] if _name_of(name) else 0


def blocklist():
    """Print every block you can use."""
    for number, name in enumerate(_names(), start=1):
        print(f'{number:3}  {name}')


def _on_main_thread():
    return threading.current_thread() is threading.main_thread()


def _to_game(x, y, z):
    return (x, y + _FLOOR + 1, z)


def _from_game(x, y, z):
    return (x, y - _FLOOR - 1, z)


_FACINGS = ('north', 'south', 'east', 'west', 'up', 'down', 'x', 'y', 'z')


class Clip:
    """A piece of build you copied. Paste it with paste(clip, x, y, z); turn it with rotate() and mirror()."""

    def __init__(self, blocks, size):
        self.blocks = blocks            # (dx, dy, dz) -> (block name, facing)
        self.size = size                # (width, height, depth)

    def __repr__(self):
        return f'<Clip of {len(self.blocks)} blocks, {self.size[0]} x {self.size[1]} x {self.size[2]}>'

    def save(self, filename):
        """Keep the shape in a .pcschem file: pc.block_placement('shape.pcschem') makes a creature appear when it is built."""
        import mods
        return mods.save_pattern(self, _userpath(str(filename)))

    def rotated(self, degrees):
        turns = _turns(degrees)
        blocks, (w, h, d) = dict(self.blocks), self.size
        for _ in range(turns):
            blocks = {(d - 1 - dz, dy, dx): (name, _x.turn_facing(f, 1)) for (dx, dy, dz), (name, f) in blocks.items()}
            w, d = d, w
        return Clip(blocks, (w, h, d))

    def mirrored(self, axis='x'):
        if axis not in ('x', 'z'):
            raise ValueError("mirror axis must be 'x' (left-right) or 'z' (front-back).")
        w, h, d = self.size
        if axis == 'x':
            blocks = {(w - 1 - dx, dy, dz): (name, _x.mirror_facing(f, 'x')) for (dx, dy, dz), (name, f) in self.blocks.items()}
        else:
            blocks = {(dx, dy, d - 1 - dz): (name, _x.mirror_facing(f, 'z')) for (dx, dy, dz), (name, f) in self.blocks.items()}
        return Clip(blocks, self.size)


def _turns(degrees):
    if not isinstance(degrees, int) or degrees % 90 != 0:
        raise ValueError('rotate by 90, 180 or 270 degrees.')
    return (degrees // 90) % 4


def rotate(clip, degrees=90):
    """A copy of a Clip turned clockwise (seen from above) by 90, 180 or 270 degrees."""
    return clip.rotated(degrees)


def mirror(clip, axis='x'):
    """A copy of a Clip flipped left-right (axis 'x') or front-back (axis 'z')."""
    return clip.mirrored(axis)


def _along(axis):
    if axis not in ('x', 'z'):
        raise ValueError("axis must be 'x' (the writing runs east) or 'z' (the writing runs south).")
    return (1, 0) if axis == 'x' else (0, 1)


def _attach(on):
    """'floor' or the side of the wall a lever or torch hangs on ('north', 'south', 'east', 'west')."""
    if on in ('floor', 'down', None):
        return 'down'
    if on not in ('north', 'south', 'east', 'west'):
        raise ValueError("on must be 'floor', or the side the wall is on: 'north', 'south', 'east' or 'west'.")
    return on


class Creature:
    """A creature you placed (spawnmob() gives you one). Give it orders:

        pig = w.spawnmob('pig', 5, 1, 5)
        pig.walk_to(10, 10)      # walk to x = 10, z = 10
        pig.follow()             # follow the player
        pig.stay()               # stand still
        pig.say('Oink!')         # a message from it
        pig.onclick(function)    # run a function when it is right-clicked
    """

    def __init__(self, plot, kind, x, y, z, label=None):
        self._plot = plot
        self.kind = kind
        self.start = (x, y, z)
        self.label = label or kind.replace('_', ' ').title()
        self._order = None
        self._click = None
        self._mob = None

    def __repr__(self):
        return f'<Creature {self.kind} at {self.start}>'

    def _attach(self, game):
        mob = game.mobs.add(self.kind, (self.start[0], self.start[1] + _FLOOR + 0.55, self.start[2]), self._plot._rng.uniform(0, 360))
        self._mob = mob
        mob.order = self._order
        if self._click is not None:
            mob.script_click = lambda: self._plot._call(self._click, self)

    def _give_order(self, order):
        self._order = order
        if self._mob is not None:
            def apply():
                self._mob.order = order
                self._mob.arrived = False
            self._plot._later(apply)

    def walk_to(self, x, z):
        """Walk to the spot (x, z). `arrived` becomes True when it gets there."""
        self._give_order(('goto', float(x), float(z)))

    def follow(self):
        """Follow the player around."""
        self._give_order(('follow',))

    def stay(self):
        """Stand still."""
        self._give_order(('stay',))

    def free(self):
        """Go back to behaving like a normal creature of its kind."""
        self._give_order(None)

    @property
    def arrived(self):
        return bool(self._mob is not None and self._mob.arrived)

    @property
    def position(self):
        """Where it is now, in plot coordinates (or where it starts, if the game is not open)."""
        if self._mob is not None and self._plot._game is not None and self._mob in self._plot._game.mobs.mobs:
            m = self._mob
            return (round(m.x, 1), round(m.y - _FLOOR - 0.5, 1), round(m.z, 1))
        return self.start

    def say(self, text, seconds=4.0):
        """Show something this creature says."""
        self._plot.say(f'{self.label}: {text}', seconds)

    def onclick(self, function):
        """Run function(creature) (or function()) when the player right-clicks this creature."""
        _need_function(function)
        self._click = function
        if self._mob is not None:
            self._plot._later(lambda: setattr(self._mob, 'script_click', lambda: self._plot._call(function, self)))

    def remove(self):
        """Take this creature away."""
        if self in self._plot._mobs:
            self._plot._mobs.remove(self)
            if self._plot._journal is not None:
                self._plot._journal.append(('mob-', self))
        self._plot._npcs[:] = [n for n in self._plot._npcs if n['creature'] is not self]
        mob, self._mob = self._mob, None
        if mob is not None and self._plot._game is not None:
            self._plot._later(lambda: self._plot._game.mobs.remove(mob))


def moblist():
    """Print every creature you can place with spawnmob()."""
    from mobtypes import TYPES
    for name, kind in TYPES.items():
        print(f'{name:14} {kind.title}')


def noise(x, z, scale=10.0, seed=0):
    """Smooth random numbers from 0 to 1: close-by points give close-by numbers. Use it for hills:
    height = 2 + 8 * w.noise(x, z, scale=6)"""
    return _x.noise(x, z, scale, seed)


def _find_challenge(which):
    """A Challenge from a ready-made name ('house'), a challenge id from the challenges folder, a file name, or a Challenge."""
    if isinstance(which, _pcplot.Challenge):
        return which
    builtin = _pcplot.builtin_challenges()
    available = _pcplot.find_challenges(_START_DIR)
    path = _userpath(which)
    for candidate in (path, path + '.pcchallenge'):                 # a file you name
        if os.path.isfile(candidate):
            return _pcplot.Challenge.load(candidate)
    if which in available:                                           # a challenge in the challenges folder wins over a ready-made one
        return _pcplot.Challenge.load(available[which])
    if which in builtin:
        return builtin[which]
    close = difflib.get_close_matches(str(which), list(builtin) + list(available), n=3)
    raise ValueError(f'There is no challenge called {which!r}.' + (f' Did you mean {", ".join(close)}?' if close else
                                                                  ' pc.challenges() lists the ones you can try.'))


def challenges():
    """Print the challenges you can try: the ready-made ones and any .pcchallenge files in your challenges folder."""
    files = _pcplot.find_challenges(_START_DIR)
    if files:
        print('Challenges (from your challenges folder):')
        for name, path in files.items():
            try:
                c = _pcplot.Challenge.load(path)
                print(f'  {name:10} {c.title}: {c.brief[:70]}')
            except _pcplot.PlotFileError as error:
                print(f'  {name:10} (damaged: {error})')
    print('Quick ready-made checks (no brief, any plot):')
    for name, c in _pcplot.builtin_challenges().items():
        if name not in files:
            print(f'  {name:10} {c.brief}')


def feedback(name=None, challenge=None, to=None):
    """Read what your teacher said about your latest hand-in: pc.feedback('Sam', 'bridge'). Returns the review (or None)."""
    name = name or os.environ.get('PYCRAFT_NAME')
    if not name:
        raise ValueError("Say whose feedback to read: pc.feedback('Sam')")
    folder = _pcplot.submissions_folder(to, _START_DIR)
    cid = challenge.id if isinstance(challenge, _pcplot.Challenge) else challenge
    path = _pcplot.find_hand_in(folder, name, cid)
    if path is None:
        print(f'No hand-in from {name!r} found in {folder}.')
        return None
    meta = _pcplot.read_meta(path) or {}
    review = _pcplot.read_review(path)
    if review is None:
        print(f"Your attempt {meta.get('attempt', 1)} for {path.parent.name} is handed in. It has not been reviewed yet.")
        return None
    print(f"Review of {path.parent.name} (attempt {review.get('attempt', '?')}), by {review.get('reviewer') or 'your teacher'}:")
    if review.get('score') is not None:
        print(f"  Score: {review['score']} / {review.get('out_of', '?')}")
    if review.get('comment'):
        print(f"  {review['comment']}")
    if int(meta.get('attempt', 1)) > int(review.get('attempt', 1)):
        print(f"  (You have handed in attempt {meta['attempt']} since this review.)")
    return review


_COMPASS = ['north', 'east', 'south', 'west']


_STEP = {'north': (0, -1), 'east': (1, 0), 'south': (0, 1), 'west': (-1, 0)}


class Turtle:
    """A builder you steer. It remembers where it is and which way it faces; with the pen down it leaves a block
    behind at every step.

        t = w.turtle(2, 0, 2, block='stone')
        for side in range(4):
            t.forward(5)
            t.right()            # turn 90 degrees clockwise (seen from above)
    """

    def __init__(self, plot, x=0, y=0, z=0, facing='north', block='stone', pen=True):
        self._plot = plot
        if facing not in _COMPASS:
            raise ValueError("facing must be 'north', 'east', 'south' or 'west'.")
        self.x, self.y, self.z = x, y, z
        self.heading = _COMPASS.index(facing)
        self.block = block
        _name_of(block)
        self.pen = pen
        if pen:
            self.place()

    def __repr__(self):
        return f'<Turtle at {self.position} facing {self.facing}>'

    @property
    def position(self):
        return (self.x, self.y, self.z)

    @property
    def facing(self):
        return _COMPASS[self.heading]

    def place(self, id=None):
        """Put a block where the turtle is (with the pen's block, or the one you name)."""
        self._plot.placeblock(self.x, self.y, self.z, id if id is not None else self.block)

    def _move(self, dx, dy, dz, steps):
        for _ in range(steps):
            self.x, self.y, self.z = self.x + dx, self.y + dy, self.z + dz
            if self.pen:
                self.place()

    def forward(self, steps=1):
        """Walk forward, building if the pen is down."""
        dx, dz = _STEP[self.facing]
        self._move(dx, 0, dz, steps)

    def back(self, steps=1):
        dx, dz = _STEP[self.facing]
        self._move(-dx, 0, -dz, steps)

    def up(self, steps=1):
        self._move(0, 1, 0, steps)

    def down(self, steps=1):
        self._move(0, -1, 0, steps)

    def right(self, degrees=90):
        """Turn clockwise (90, 180 or 270)."""
        if not isinstance(degrees, int) or degrees % 90:
            raise ValueError('The turtle turns in steps of 90 degrees.')
        self.heading = (self.heading + degrees // 90) % 4

    def left(self, degrees=90):
        self.right(-degrees)

    turn = right

    def face(self, direction):
        """Turn to face 'north', 'east', 'south' or 'west'."""
        if direction not in _COMPASS:
            raise ValueError("direction must be 'north', 'east', 'south' or 'west'.")
        self.heading = _COMPASS.index(direction)

    def penup(self):
        """Walk without building."""
        self.pen = False

    def pendown(self, id=None):
        """Build as you walk (optionally with a different block)."""
        if id is not None:
            _name_of(id)
            self.block = id
        self.pen = True
        self.place()

    def goto(self, x, y, z):
        """Jump to a spot (nothing is built on the way)."""
        self.x, self.y, self.z = x, y, z
        if self.pen:
            self.place()


def makegallery(folder='pictures', title='Our builds'):
    """Make a web page (index.html) showing every picture saved in a folder (from runplot(gallery=...) and F2).
    Open it in a browser to show off the class's work. Returns the page's file name."""
    import html
    directory = _userpath(folder)
    if not os.path.isdir(directory):
        raise ValueError(f'There is no folder called {folder!r} yet. Save pictures into it with pc.runplot(w, pc.adventure, gallery={folder!r}).')
    pictures = sorted(f for f in os.listdir(directory) if f.lower().endswith('.png'))
    cards = ''.join(f'<figure><img src="{html.escape(f)}" alt=""><figcaption>{html.escape(os.path.splitext(f)[0])}</figcaption></figure>'
                    for f in pictures)
    page = (f'<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title>'
            '<style>body{font-family:sans-serif;margin:2rem;background:#222;color:#eee}'
            'h1{margin-top:0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}'
            'figure{margin:0;background:#333;padding:.5rem;border-radius:6px}img{width:100%;border-radius:4px}'
            'figcaption{text-align:center;padding-top:.4rem;font-weight:bold}</style>'
            f'<h1>{html.escape(title)}</h1><div class="grid">{cards}</div>')
    path = os.path.join(directory, 'index.html')
    with open(path, 'w') as handle:
        handle.write(page)
    print(f'{len(pictures)} pictures: open {path} in a browser.')
    return path


def _load_progress():
    try:
        with open(_PROGRESS_FILE) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _save_progress(data):
    try:
        with open(_PROGRESS_FILE, 'w') as handle:
            json.dump(data, handle)
    except OSError:
        pass


def _stars(n):
    return '*' * n + '-' * (3 - n)


def levels():
    """Print the challenge levels and the stars you earned."""
    saved = _load_progress()
    for number, (title, _plot_size, goal, _hint, _check_fn, _solution) in enumerate(_x.LEVELS, start=1):
        print(f'  Level {number:2}  [{_stars(saved.get(str(number), 0))}]  {title}')


def progress():
    """Print your stars for every level."""
    levels()


def reset_progress():
    """Forget all stars."""
    _save_progress({})
    print('Progress cleared.')


_TIMES = {'sunrise': 0, 'morning': 1000, 'day': 6000, 'noon': 6000, 'afternoon': 9000, 'sunset': 12000, 'evening': 12500,
          'night': 18000, 'midnight': 18000}


def _ticks(when):
    if isinstance(when, str):
        if when not in _TIMES:
            raise ValueError(f"time must be a number from 0 to 24000 or one of: {', '.join(_TIMES)}.")
        return _TIMES[when]
    if isinstance(when, bool) or not isinstance(when, (int, float)):
        raise TypeError('time must be a name like "night" or a number of ticks (0 = sunrise, 6000 = noon, 18000 = midnight).')
    return when % 24000


def _numbers(x, y, z):
    for value in (x, y, z):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f'Coordinates must be numbers, not {value!r}.')
    return x, y, z


def _player_feet(x, y, z):
    return (x, y + _FLOOR + 0.52, z)


_SOUNDS = {'levelup': 'random/levelup', 'pop': 'random/pop', 'click': 'random/click', 'explode': 'random/explode',
           'door': 'random/door_open', 'orb': 'random/orb', 'fire': 'random/fire', 'lever': 'random/lever',
           'bow': 'random/bow', 'break': 'random/break', 'enchant': 'random/enchant', 'fuse': 'random/fuse'}


def _need_function(function):
    if not callable(function):
        raise TypeError('Give a function (without brackets): w.onenter(3, 0, 3, my_function)')


def _take_screenshot(path):
    """Save the picture without the on-screen controls in it."""
    from ursina import application, camera
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    camera.ui.enabled = False
    try:
        application.base.graphicsEngine.renderFrame()
        application.base.screenshot(path, defaultFilename=False)
    finally:
        camera.ui.enabled = True
    return path


class Plot:
    """A building plot. Make one with pc.plot(x, y, z). Everything you build goes into it; pc.runplot(plot) shows it."""

    def __init__(self, x=16, y=16, z=16):
        self._plot = [16, 16, 16]         # the size: x, y, z
        self._blocks = {}                 # (x, y, z) -> block name
        self._facing = {}                 # (x, y, z) -> which way the block faces
        self._mobs = []                   # the Creatures that stand in your build
        self._rng = random.Random()
        # what the running game should do (set before runplot(), or changed while it runs)
        self._hooks = {'enter': {}, 'click': {}, 'every': [], 'keys': {}}
        self._gives = []                  # (item name, count) to put in the inventory
        self._start = [None]              # where the player starts, in plot coordinates
        self._time_setting = ['day', False]            # (time, let the clock run)
        self._weather_setting = ['clear']
        self._music_on = [True]
        self._challenge = [None]
        self._level = [None]              # the challenge-mode level you are working on
        self._failures = [0]              # how many times check() said 'not yet' on this level
        self._assignment = [None]         # (title, [(what, function)]) set by assignment()
        self.title = ''                   # a name for the build (saved in the .pcplot file)
        self.tutorial = None              # tutorial notes for tutorialworld.py: {'level', 'summary', 'steps', 'try_it', 'code'}
        self._signs = {}                  # (x, y, z) -> pages of text on that sign
        self._origin = None               # where plot (0, 0, 0) is in the game world (x, y, z); None: the usual plot place
        self._wrap_call = None            # a function that runs each piece of work for the game (class worlds use it to share blocks)
        self._networked = False           # True in a class (LAN) world: creatures, weather and such are not shared there
        self._npcs = []                   # [{'creature', 'name', 'lines'}] for npc() characters
        self._student = None              # who you said you are in submit()
        self._journal = None              # while a step is being recorded: what changed (for undo)
        self._undo = []                   # recorded steps, newest last
        self._redo = []
        self._build_delay = 0.0           # seconds between block placements made from your own thread (see delay())
        self._menu_buttons = []           # [(label, function)] extra buttons in the game's Esc menu
        self._authoring = False           # True while the game is open in the tutorial maker's creative mode
        self._manual_steps = []           # changes made by hand in the game, waiting to be picked up (take_manual)
        # the running game (only while runplot() has the window open)
        self._game = None
        self._runtime = {'weather': None, 'queue': [], 'closed': False, 'gallery': None, 'name': None, 'enter_state': {},
                         'timers': {}}
        self._lock = threading.Lock()
        self.resize(x, y, z)

    def __repr__(self):
        return f'<Plot {self._plot[0]} x {self._plot[1]} x {self._plot[2]}: {len(self._blocks)} blocks>'

    @property
    def dimensions(self):
        """The size of the plot: (x, y, z)."""
        return tuple(self._plot)

    def turtle(self, x=0, y=0, z=0, facing='north', block='stone', pen=True):
        """A builder you steer with forward(), right(), up()... (see Turtle). It builds in this plot."""
        return Turtle(self, x, y, z, facing, block, pen)

    def _gpos(self, pos):
        """Where a plot position is in the game's world."""
        ox, oy, oz = self._origin if self._origin else (0, _FLOOR + 1, 0)
        return (pos[0] + ox, pos[1] + oy, pos[2] + oz)

    def _run(self, function):
        (self._wrap_call or (lambda f: f()))(function)

    def _run_queue(self, dt):
        """Do the work your own thread queued for the game (a few things each frame; block placements wait their turn: delay())."""
        deadline = _time.perf_counter() + 0.008
        delay = self._build_delay
        credit = self._runtime.get('credit', 0.0) + dt
        while self._runtime['queue'] and _time.perf_counter() < deadline:
            if delay > 0 and self._runtime['queue'][0][1]:
                if credit < delay:
                    break                                  # wait for the next block's turn
                credit -= delay
            with self._lock:
                function, _is_block = self._runtime['queue'].pop(0)
            self._run(function)
        self._runtime['credit'] = min(credit, delay) if delay > 0 else 0.0

    def _later(self, function, block=False):
        """Do something to the running game. (From your own thread it waits for the next frame; nothing happens
        if the game is not open.) block=True marks a block placement, which delay() slows down so you can watch."""
        if self._game is None:
            return
        if _on_main_thread():
            self._run(function)
        else:
            with self._lock:
                self._runtime['queue'].append((function, block))

    def _sync_block(self, pos):
        """Make the running game show what the plot says is at `pos`."""
        if self._game is None:
            return
        name, orient = self._blocks.get(pos), self._facing.get(pos)

        def apply():
            world = self._game.world
            game_pos = self._gpos(pos)
            if name is None and world.get(game_pos) is None:
                return
            world.set_fluid(game_pos, name)
            if orient:
                world.facing[game_pos] = orient
            else:
                world.facing.pop(game_pos, None)
            for listener in world.listeners:
                listener(game_pos)
        self._later(apply, block=True)

    def _call(self, function, *args):
        """Run one of your functions for the game. A mistake in it is reported without stopping the game."""
        try:
            wanted = len(inspect.signature(function).parameters)
        except (TypeError, ValueError):
            wanted = len(args)
        try:
            return function(*args[:wanted])
        except SystemExit:
            raise
        except Exception as error:
            name = getattr(function, '__name__', 'your function')
            print(f'\nProblem in {name}():')
            traceback.print_exc()
            self.say(f'{name}() had a problem: {error}', 6)

    def resize(self, x, y, z):
        """Set the size of your plot. Call this first. Blocks outside the plot are not allowed,
        which catches mistakes like a house that sticks out by accident."""
        for value in (x, y, z):
            if not isinstance(value, int) or value < 1:
                raise ValueError('size(x, y, z) needs whole numbers that are at least 1.')
        if x > 256 or z > 256 or y > 100:
            raise ValueError('That plot is too big. The most is 256 x 100 x 256.')
        self._plot[:] = [x, y, z]
        for pos in [p for p in self._blocks if not self._inside(*p)]:           # shrinking the plot throws away blocks outside it
            del self._blocks[pos]
            self._facing.pop(pos, None)

    def _inside(self, x, y, z):
        return 0 <= x < self._plot[0] and 0 <= y < self._plot[1] and 0 <= z < self._plot[2]

    def _check(self, x, y, z):
        for value in (x, y, z):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                raise TypeError(f'Coordinates must be whole numbers, not {value!r}.')
        x, y, z = int(x), int(y), int(z)
        if not self._inside(x, y, z):
            raise ValueError(f'({x}, {y}, {z}) is outside your plot, which goes from (0, 0, 0) to '
                             f'({self._plot[0] - 1}, {self._plot[1] - 1}, {self._plot[2] - 1}). Use size() to make it bigger.')
        return x, y, z

    def placeblock(self, x, y, z, id='stone', facing=None):
        """Put one block at (x, y, z). `id` is a block name or number. Optional facing: 'north', 'south',
        'east' or 'west' for blocks like furnaces and stairs. Placing 'air' (or 0) removes a block."""
        x, y, z = self._check(x, y, z)
        name = _name_of(id)
        before = (self._blocks.get((x, y, z)), self._facing.get((x, y, z)))
        if name is None:
            self._blocks.pop((x, y, z), None)
            self._facing.pop((x, y, z), None)
        else:
            if facing is not None and facing not in _FACINGS and not (isinstance(facing, str) and facing.rstrip('+') in _FACINGS):
                raise ValueError("facing must be 'north', 'south', 'east' or 'west'.")
            self._blocks[(x, y, z)] = name
            if facing is not None:
                self._facing[(x, y, z)] = facing
            else:
                self._facing.pop((x, y, z), None)
        after = (self._blocks.get((x, y, z)), self._facing.get((x, y, z)))
        if self._journal is not None and before != after:
            self._journal.append(((x, y, z), before[0], before[1], after[0], after[1]))
        self._sync_block((x, y, z))

    def delay(self, ticks=4):
        """Slow down building you do from your own thread (live scripts, livecode.py) so you can watch it happen:
        each block is placed `ticks` ticks after the last one (20 ticks = 1 second; 0 = as fast as possible)."""
        if not isinstance(ticks, (int, float)) or ticks < 0:
            raise ValueError('delay() takes a number of ticks from 0 up (20 ticks is one second).')
        self._build_delay = ticks / 20.0

    def add_menu_button(self, label, function):
        """Add a button to the game's Esc menu that runs `function` (it shows when the game starts)."""
        _need_function(function)
        self._menu_buttons.append((str(label), function))

    def _pull_from_game(self):
        """(Main thread.) Notice blocks the player placed or broke by hand in the game, and bring the plot up to date.
        The change becomes one undoable step. Returns the changes: [(pos, old, old_facing, new, new_facing)]."""
        if self._game is None or self._runtime['queue'] or self._journal is not None:
            return []                                       # (blocks still on their way, or a step in progress)
        world = self._game.world
        liquids = ('water', 'lava')
        seen = {}
        for game_pos, kind in dict(world.modified).items():
            x, y, z = game_pos[0], game_pos[1] - _FLOOR - 1, game_pos[2]
            if self._inside(x, y, z):
                seen[(x, y, z)] = (kind, world.facing.get(game_pos))
        step = []
        for pos in set(seen) | set(self._blocks):
            kind, facing = seen.get(pos, (None, None))
            old, old_facing = self._blocks.get(pos), self._facing.get(pos)
            if kind in liquids or old in liquids:
                continue                                    # flowing water and lava are not kept
            if kind != old or (kind is not None and (facing or None) != (old_facing or None)):
                step.append((pos, old, old_facing, kind, facing if kind else None))
        if not step:
            return []
        step.sort(key=lambda e: e[0])
        for pos, _old, _old_facing, kind, facing in step:
            if kind is None:
                self._blocks.pop(pos, None)
                self._facing.pop(pos, None)
                self._drop_sign(pos)
            else:
                self._blocks[pos] = kind
                if facing:
                    self._facing[pos] = facing
                else:
                    self._facing.pop(pos, None)
        self._undo.append(step)
        self._redo.clear()
        self._manual_steps.append(step)
        return step

    def sync_from_game(self, timeout=4.0):
        """Wait for everything you queued to appear, then pick up what the player built or broke by hand in the game
        (creative mode in the tutorial maker). Returns the changes."""
        if self._game is None:
            return []
        end = _time.time() + timeout
        while self._runtime['queue'] and _time.time() < end and not _on_main_thread():
            _time.sleep(0.03)
        if _on_main_thread():
            return self._pull_from_game()
        result, done = [], threading.Event()

        def run():
            result.extend(self._pull_from_game())
            done.set()
        self._later(run)
        done.wait(max(0.5, end - _time.time()))
        return result

    def wait_idle(self, timeout=120.0):
        """Wait until everything you queued has appeared in the game. Returns True if it did."""
        end = _time.time() + timeout
        while self._game is not None and self._runtime['queue'] and _time.time() < end:
            if _on_main_thread():
                return False
            _time.sleep(0.03)
        return not self._runtime['queue']

    def take_manual(self):
        """The steps of hand-built changes noticed since last time (each is a list of changes), oldest first."""
        steps, self._manual_steps = self._manual_steps, []
        return steps

    def _begin_step(self):
        """Start recording what changes (so it can be undone as one step). Used by the live interpreter."""
        self._journal = []

    def _end_step(self):
        """Stop recording. Returns the recorded changes (and remembers them for undo() if there were any)."""
        step, self._journal = self._journal or [], None
        if step:
            self._undo.append(step)
            self._redo.clear()
        return step

    def undo(self):
        """Take back the last recorded step (blocks, creatures, signs). Returns False if there is nothing to undo."""
        if self._journal is not None:
            raise RuntimeError('undo() cannot run in the middle of a step.')
        if not self._undo:
            return False
        step = self._undo.pop()
        self._apply_step(step, forward=False)
        self._redo.append(step)
        return True

    def redo(self):
        """Put back the step that undo() took away. Returns False if there is nothing to redo."""
        if self._journal is not None:
            raise RuntimeError('redo() cannot run in the middle of a step.')
        if not self._redo:
            return False
        step = self._redo.pop()
        self._apply_step(step, forward=True)
        self._undo.append(step)
        return True

    def _apply_step(self, step, forward):
        for entry in (step if forward else reversed(step)):
            kind = entry[0]
            if kind == 'mob+' or kind == 'mob-':
                creature = entry[1]
                add = (kind == 'mob+') == forward
                if add and creature not in self._mobs:
                    self._mobs.append(creature)
                    npc_entry = getattr(creature, '_npc_entry', None)
                    if npc_entry is not None and npc_entry not in self._npcs:
                        self._npcs.append(npc_entry)
                    if self._game is not None:
                        self._later(lambda c=creature: c._attach(self._game))
                elif not add and creature in self._mobs:
                    creature.remove()
            elif kind == 'sign':
                pos, pages, facing = entry[1], entry[2], entry[3]
                if forward:
                    self._signs[pos] = pages
                    self.onclick_sign(pos, pages)
                else:
                    self._drop_sign(pos)
            else:
                pos, old_name, old_facing, new_name, new_facing = entry
                name, facing = (new_name, new_facing) if forward else (old_name, old_facing)
                if name is None:
                    self._blocks.pop(pos, None)
                    self._facing.pop(pos, None)
                else:
                    self._blocks[pos] = name
                    if facing:
                        self._facing[pos] = facing
                    else:
                        self._facing.pop(pos, None)
                if name != 'oak_sign':
                    self._drop_sign(pos)
                self._sync_block(pos)

    def _drop_sign(self, pos):
        """Forget a sign's words and its click (the block itself is handled by the caller)."""
        self._signs.pop(pos, None)
        self._hooks['click'].pop(pos, None)
        if self._game is not None:
            self._later(lambda: self._game.interaction.click_hooks.pop(self._gpos(pos), None))

    def onclick_sign(self, pos, pages):
        """Make the sign at pos readable again (used when a sign is put back by redo())."""
        turn = [0]

        def read():
            page = pages[turn[0] % len(pages)]
            self._show_text(page, min(40.0, max(6.0, len(page) / 9)))
            turn[0] += 1
        self.onclick(pos[0], pos[1], pos[2], read)

    def removeblock(self, x, y, z):
        """Take away the block at (x, y, z)."""
        self.placeblock(x, y, z, 'air')

    def getblock(self, x, y, z):
        """The name of the block at (x, y, z), or 'air' if it is empty."""
        x, y, z = self._check(x, y, z)
        return self._blocks.get((x, y, z), 'air')

    def fillblocks(self, x1, y1, z1, x2, y2, z2, id):
        """Fill every block in the box from (x1, y1, z1) to (x2, y2, z2), corners included."""
        _name_of(id)                                       # complain about a bad id before doing anything
        x1, y1, z1 = self._check(x1, y1, z1)
        x2, y2, z2 = self._check(x2, y2, z2)
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.placeblock(x, y, z, id)

    fill = fillblocks          # a shorter name

    def hollowbox(self, x1, y1, z1, x2, y2, z2, id):
        """Like fillblocks, but only the outside walls, floor and roof: a room you can walk into."""
        self.fillblocks(x1, y1, z1, x2, y2, z2, id)
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        z1, z2 = sorted((z1, z2))
        if x2 - x1 >= 2 and y2 - y1 >= 2 and z2 - z1 >= 2:
            self.fillblocks(x1 + 1, y1 + 1, z1 + 1, x2 - 1, y2 - 1, z2 - 1, 'air')

    def line(self, x1, y1, z1, x2, y2, z2, id):
        """A straight line of blocks between two points."""
        _name_of(id)
        steps = max(abs(x2 - x1), abs(y2 - y1), abs(z2 - z1), 1)
        for i in range(steps + 1):
            self.placeblock(round(x1 + (x2 - x1) * i / steps), round(y1 + (y2 - y1) * i / steps),
                       round(z1 + (z2 - z1) * i / steps), id)

    def sphere(self, cx, cy, cz, radius, id, hollow=False):
        """A ball of blocks centred on (cx, cy, cz). Parts that stick out of the plot are left out."""
        _name_of(id)
        r = radius
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                for z in range(cz - r, cz + r + 1):
                    d = ((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2) ** 0.5
                    if d <= r + 0.3 and not (hollow and d < r - 0.7) and self._inside(x, y, z):
                        self.placeblock(x, y, z, id)

    def clear(self):
        """Remove every block (and creature) you have placed."""
        for pos in list(self._blocks):
            if self._journal is not None:
                self._journal.append((pos, self._blocks[pos], self._facing.get(pos), None, None))
            del self._blocks[pos]
            self._facing.pop(pos, None)
            self._sync_block(pos)
        self._facing.clear()
        for creature in list(self._mobs):
            creature.remove()
        self._mobs.clear()
        self._signs.clear()
        self._npcs.clear()

    def count(self, id=None):
        """How many blocks you have placed (of one kind, if you give an id)."""
        if id is None:
            return len(self._blocks)
        name = _name_of(id)
        return sum(1 for b in self._blocks.values() if b == name)

    def replace(self, old, new, x1=None, y1=None, z1=None, x2=None, y2=None, z2=None):
        """Change every block called `old` into `new` (in a box if you give the six corner numbers).
        Returns how many were changed.  Example: w.replace('stone', 'nether_bricks')"""
        old_name, new_name = _name_of(old), _name_of(new)
        if old_name is None:
            raise ValueError("replace() changes blocks you have placed; use fill() to fill empty space.")
        box = None
        if x1 is not None:
            a, b = self._check(x1, y1, z1), self._check(x2, y2, z2)
            box = [(min(a[i], b[i]), max(a[i], b[i])) for i in range(3)]
        changed = 0
        for pos in [p for p, n in self._blocks.items() if n == old_name]:
            if box and not all(box[i][0] <= pos[i] <= box[i][1] for i in range(3)):
                continue
            facing = self._facing.get(pos)
            self.placeblock(*pos, new_name or 'air', facing if new_name else None)
            changed += 1
        return changed

    def copy(self, x1, y1, z1, x2, y2, z2):
        """Copy the blocks in a box so you can paste them somewhere else (see paste)."""
        a, b = self._check(x1, y1, z1), self._check(x2, y2, z2)
        low = tuple(min(a[i], b[i]) for i in range(3))
        high = tuple(max(a[i], b[i]) for i in range(3))
        blocks = {}
        for (x, y, z), name in self._blocks.items():
            if all(low[i] <= (x, y, z)[i] <= high[i] for i in range(3)):
                blocks[(x - low[0], y - low[1], z - low[2])] = (name, self._facing.get((x, y, z)))
        return Clip(blocks, tuple(high[i] - low[i] + 1 for i in range(3)))

    def paste(self, clip, x, y, z, rotate=0, mirror=None, air=False):
        """Put a Clip down with its lowest corner at (x, y, z). rotate (90, 180, 270) and mirror ('x' or 'z') turn it
        first. air=True also clears blocks where the clip has empty space."""
        if not isinstance(clip, Clip):
            raise TypeError('paste() needs a Clip made by copy().')
        if mirror:
            clip = clip.mirrored(mirror)
        if rotate:
            clip = clip.rotated(rotate)
        x, y, z = self._check(x, y, z)
        w, h, d = clip.size
        self._check(x + w - 1, y + h - 1, z + d - 1)                        # it all has to fit in the plot
        if air:
            for dx in range(w):
                for dy in range(h):
                    for dz in range(d):
                        self.placeblock(x + dx, y + dy, z + dz, 'air')
        for (dx, dy, dz), (name, facing) in clip.blocks.items():
            self.placeblock(x + dx, y + dy, z + dz, name, facing)

    def text(self, x, y, z, message, id='stone_bricks', size=1, axis='x'):
        """Write block letters. (x, y, z) is the bottom-left of the first letter, which is 5 blocks wide and 7 tall
        (times `size`). axis 'x' runs the writing along +x (readable from the default start, facing +z);
        axis 'z' runs it along +z. Returns how wide the writing is."""
        name = _name_of(id)
        cells, width = _x.text_cells(message, size)
        step = _along(axis)
        placed = [(self._check(x + step[0] * a, y + b, z + step[1] * a), name) for a, b in cells]    # check everything fits first
        for pos, block in placed:
            self.placeblock(*pos, block)
        return width

    def image(self, x, y, z, path, width=None, height=None, axis='x', palette=None):
        """Turn a picture file into a wall of blocks, using whichever block is closest in colour.
        (x, y, z) is the bottom-left corner. Give a width and/or height in blocks (otherwise it is up to 48 wide).
        palette=['stone', 'snow', ...] limits the blocks it may use. Returns (width, height)."""
        names = [_name_of(n) for n in palette] if palette else None
        cells, w, h = _x.image_cells(_userpath(path), width, height, names)
        step = _along(axis)
        placed = [(self._check(x + step[0] * a, y + b, z + step[1] * a), name) for a, b, name in cells]
        for pos, block in placed:
            self.placeblock(*pos, block)
        return w, h

    def portal(self, x, y, z, width=2, height=3, axis='x'):
        """A glowing Nether portal in an obsidian frame. (x, y, z) is the lowest corner of the whole frame,
        so the portal itself is `width` blocks wide and `height` tall inside it, and the frame is 2 bigger each way.
        axis 'x' makes the portal face north-south, axis 'z' makes it face east-west.
        (In the game a portal is for looking at: it does not take you anywhere.)"""
        if axis not in ('x', 'z'):
            raise ValueError("axis must be 'x' or 'z'.")
        if not (isinstance(width, int) and isinstance(height, int) and 2 <= width <= 21 and 3 <= height <= 21):
            raise ValueError('A portal is 2 to 21 blocks wide and 3 to 21 tall.')
        step = (1, 0) if axis == 'x' else (0, 1)
        cells = []
        for i in range(0, width + 2):
            for j in range(0, height + 2):
                edge = i in (0, width + 1) or j in (0, height + 1)
                cell = self._check(x + step[0] * i, y + j, z + step[1] * i)       # the whole frame has to fit in the plot
                cells.append((cell, 'obsidian' if edge else 'nether_portal'))
        for cell, kind in cells:
            self.placeblock(*cell, kind)

    def lever(self, x, y, z, on='floor'):
        """A lever. on='floor' stands on the ground; on='north' (etc.) hangs on a wall on that side."""
        self.placeblock(x, y, z, 'lever', _attach(on))

    def button(self, x, y, z, on='floor'):
        """A stone button (lets out a short redstone pulse)."""
        self.placeblock(x, y, z, 'stone_button', _attach(on))

    def torch(self, x, y, z, on='floor'):
        """A torch. on='floor' or the side the wall is on."""
        self.placeblock(x, y, z, 'torch', _attach(on))

    def lamp(self, x, y, z):
        """A redstone lamp: it lights up when redstone power reaches it."""
        self.placeblock(x, y, z, 'redstone_lamp')

    def pressureplate(self, x, y, z, kind='stone'):
        """A pressure plate ('stone' or 'oak') that sends a signal while something stands on it."""
        if kind not in ('stone', 'oak'):
            raise ValueError("kind must be 'stone' or 'oak'.")
        self.placeblock(x, y, z, f'{kind}_pressure_plate')

    def wire(self, x1, y1, z1, x2, y2, z2):
        """Redstone dust from one point to another along the ground: first along x, then along z.
        Both ends must be at the same height. Put your lever at one end and your lamp at the other."""
        if y1 != y2:
            raise ValueError('wire() runs along the ground: both ends need the same y.')
        self._check(x1, y1, z1)
        self._check(x2, y2, z2)
        step = 1 if x2 >= x1 else -1
        for x in range(x1, x2 + step, step):
            self.placeblock(x, y1, z1, 'redstone_wire')
        step = 1 if z2 >= z1 else -1
        for z in range(z1, z2 + step, step):
            self.placeblock(x2, y1, z, 'redstone_wire')

    def door(self, x, y, z, facing='north', open=False):
        """A wooden door two blocks tall (y is the bottom). facing is the side it faces: 'north', 'south', 'east' or 'west'."""
        if facing not in ('north', 'south', 'east', 'west'):
            raise ValueError("facing must be 'north', 'south', 'east' or 'west'.")
        f = facing + ('+' if open else '')
        self._check(x, y + 1, z)
        self.placeblock(x, y, z, 'oak_door_b', f)
        self.placeblock(x, y + 1, z, 'oak_door_t', f)

    def spawnmob(self, x, y, z, name='pig'):
        """Put a creature in your build, standing at (x, y, z): spawnmob(5, 1, 5, 'zombie'). Try 'pig', 'zombie', 'villager',
        'iron_golem', 'zombie_pigman', 'ghast'... (moblist() shows them all). Hostile ones will come after you in the game
        unless you use runplot(..., peaceful=True). (The older order, spawnmob('zombie', 5, 1, 5), still works.)"""
        from mobtypes import TYPES
        if self._networked:
            raise ValueError('Creatures are not shared in a class world yet, so spawnmob is not available here.')
        if isinstance(x, str):                                    # the older order: name first
            x, y, z, name = y, z, name, x
        key = str(name).strip().lower().replace(' ', '_')
        if key not in TYPES:
            close = difflib.get_close_matches(key, list(TYPES), n=3)
            hint = f' Did you mean {", ".join(repr(c) for c in close)}?' if close else ' Call moblist() to see them all.'
            raise ValueError(f'There is no creature called {name!r}.{hint}')
        x, y, z = self._check(x, y, z)
        creature = Creature(self, key, x, y, z)
        self._mobs.append(creature)
        if self._journal is not None:
            self._journal.append(('mob+', creature))
        if self._game is not None:
            self._later(lambda: creature._attach(self._game))
        return creature

    def removemobs(self):
        """Take away every creature you placed."""
        for creature in list(self._mobs):
            creature.remove()
        self._mobs.clear()

    def seed(self, number):
        """Make tree(), maze(), village() and friends repeatable: the same seed gives the same result."""
        self._rng.seed(number)

    def terrain(self, height, top='grass', under='dirt', depth=3, base='stone'):
        """Fill the whole plot with ground. `height` is a function you write: it takes (x, z) and gives how tall the
        ground is there. Example:  w.terrain(lambda x, z: 2 + 6 * w.noise(x, z, 8))"""
        if not callable(height):
            raise TypeError('terrain() needs a function: w.terrain(lambda x, z: 3 + 5 * w.noise(x, z))')
        names = [_name_of(n) for n in (top, under, base)]
        if None in names:
            raise ValueError("top, under and base need real blocks, not 'air'.")
        for x in range(self._plot[0]):
            for z in range(self._plot[2]):
                h = max(0, min(self._plot[1] - 1, int(round(height(x, z)))))
                for y in range(h + 1):
                    self.placeblock(x, y, z, names[0] if y == h else names[1] if y > h - depth else names[2])

    def _put_all(self, blocks_dict, facing_dict, ox, oy, oz, clip=True):
        """Place a generated structure at an offset. Pieces outside the plot are skipped (clip=True) or are an error."""
        for (dx, dy, dz), name in blocks_dict.items():
            pos = (ox + dx, oy + dy, oz + dz)
            if not self._inside(*pos):
                if clip:
                    continue
                self._check(*pos)
            self.placeblock(*pos, name, facing_dict.get((dx, dy, dz)))

    def tree(self, x, y, z, kind='oak', height=None):
        """A tree whose trunk starts at (x, y, z). kind: 'oak', 'birch', 'spruce', 'jungle' (or a wood you added with mod.addwood)."""
        if kind not in ('oak', 'birch', 'spruce', 'jungle') and f'{kind}_log' not in _names():
            raise ValueError("kind must be 'oak', 'birch', 'spruce' or 'jungle' (or a wood you added with addwood).")
        x, y, z = self._check(x, y, z)
        blocks, facing = _x.tree_blocks(kind, height, self._rng)
        self._put_all(blocks, facing, x, y, z)

    def house(self, x, y, z, width=7, depth=7, height=4, walls='oak_planks', roof='oak_planks', floor='cobblestone', door='north'):
        """A little house with a door, windows, a roof and a torch. (x, y, z) is its lowest corner (the floor).
        door: the side the door is on ('north' faces the default starting point)."""
        if door not in ('north', 'south', 'east', 'west'):
            raise ValueError("door must be 'north', 'south', 'east' or 'west'.")
        if width < 5 or depth < 5 or height < 3:
            raise ValueError('A house needs width and depth of at least 5 and a height of at least 3.')
        x, y, z = self._check(x, y, z)
        self._check(x + width - 1, y + height - 1, z + depth - 1)
        blocks, facing = _x.house_blocks(width, depth, height, _name_of(walls), _name_of(roof), _name_of(floor), door)
        self._put_all(blocks, facing, x, y, z)

    def maze(self, x, y, z, cols=8, rows=8, wall='stone_bricks', height=3, floor=None):
        """A random maze. It is (2 * cols + 1) blocks wide and (2 * rows + 1) deep, with an entrance on the north
        side (low z) and an exit on the far side. seed() makes the same maze again."""
        x, y, z = self._check(x, y, z)
        walls, width, depth = _x.maze_cells(cols, rows, self._rng)
        self._check(x + width - 1, y + height - 1, z + depth - 1)
        for dx in range(width):
            for dz in range(depth):
                if floor:
                    self.placeblock(x + dx, y, z + dz, floor)
                if walls[dx][dz]:
                    for dy in range(height):
                        self.placeblock(x + dx, y + (1 if floor else 0) + dy, z + dz, wall)

    def village(self, x, y, z, houses=4, spacing=10, seed=None):
        """A row of houses along a gravel street running east. (x, y, z) is the start of the street. Needs about
        (houses * spacing) blocks along x and 20 along z."""
        rng = random.Random(seed) if seed is not None else self._rng
        x, y, z = self._check(x, y, z)
        street = z + 9
        length = houses * spacing // 2 + 8
        for dx in range(length + 1):
            for dz in (0, 1):
                if self._inside(x + dx, y - 1, street + dz):
                    self.placeblock(x + dx, y - 1, street + dz, 'gravel')
        for i in range(houses):
            hx = x + 2 + (i // 2) * spacing
            north = i % 2 == 0                                    # houses on both sides of the street
            w, d = rng.choice((5, 7, 7, 9)), rng.choice((5, 7))
            hz = street - 1 - d if north else street + 3
            if not self._inside(hx, y, hz) or not self._inside(hx + w - 1, y + 5, hz + d - 1):
                continue
            self.house(hx, y, hz, w, d, rng.choice((4, 4, 5)), walls=rng.choice(('oak_planks', 'birch_planks', 'spruce_planks', 'bricks')),
                  roof=rng.choice(('oak_planks', 'spruce_planks', 'cobblestone')), door='south' if north else 'north')
            lx = hx + w + 1
            if self._inside(lx, y + 2, street - 1 if north else street + 2):
                for dy in range(3):
                    self.placeblock(lx, y + dy, street - 1 if north else street + 2, 'oak_fence')
                self.placeblock(lx, y + 3, street - 1 if north else street + 2, 'torch')

    def challenge(self, which=None):
        """Take on a challenge with this plot: a ready-made one ('house', 'tower'...), one from your challenges folder,
        or a .pcchallenge file. It prints the brief; build, then check() and submit(). (pc.challenges() lists them.)"""
        if which is None:
            challenges()
            return None
        task = _find_challenge(which)
        self._challenge[0] = task
        self._level[0] = None
        print(f'Challenge: {task.title}\n  {task.brief}')
        for hint in task.hints:
            print(f'  hint: {hint}')
        print('When you think it is done: check(). To hand it in: submit("your name").')
        return task

    def check(self, name=None):
        """Check your build against the challenge (or challenge-mode level, or teacher's checks). Prints what is still
        missing and gives your score. Returns True when everything passes."""
        if name is None and self._challenge[0] is None and self._level[0] is not None:
            number = self._level[0]
            problems = self._level_problems(number)
            if problems:
                self._failures[0] += 1
                print(f'Level {number}: not yet.')
                for problem in problems:
                    print('  -', problem)
                return False
            stars = _x.stars_for(self._failures[0])
            saved = _load_progress()
            saved[str(number)] = max(saved.get(str(number), 0), stars)
            _save_progress(saved)
            print(f'Level {number} complete!  [{_stars(stars)}]')
            if number < len(_x.LEVELS):
                print(f'Next: level({number + 1})  ({_x.LEVELS[number][0]})')
            else:
                print('That was the last level. You are a builder-coder!')
            return True
        task = _find_challenge(name) if name is not None else self._challenge[0]
        if task is None and self._assignment[0] is None:
            raise ValueError('Pick a challenge first, for example challenge("house") or level(1). challenges() and levels() list them.')
        results = self._results(task)
        title = task.title if task else self._assignment[0][0]
        print(f'{title}:')
        for r in results:
            print(f"  {'[x]' if r['ok'] else '[ ]'} {r['label']}" + (f"  ({r['detail']})" if r['detail'] and not r['ok'] else ''))
        passed = sum(1 for r in results if r['ok'])
        score, out_of = _pcplot.score_of(results, task.points if task else 10)
        print(f'Score: {score} / {out_of}  ({passed} of {len(results)} checks)')
        done = passed == len(results)
        print('All done! Hand it in with submit("your name").' if done else 'Not yet: fix the ones with [ ] and check() again.')
        return done

    def _results(self, task=None):
        """The results of the challenge's checks and the teacher's assignment checks, as [{'label','ok','detail'}]."""
        results = []
        if task is not None:
            results += _pcplot.run_checks(task.checks, self._blocks, self._plot, [[c.kind, *c.start] for c in self._mobs])
        if self._assignment[0] is not None:
            for description, function in self._assignment[0][1]:
                try:
                    ok, detail = bool(function()), ''
                except Exception as error:
                    ok, detail = False, f'this check had a problem: {error}'
                results.append({'label': description, 'ok': ok, 'detail': detail})
        return results

    def _show_text(self, text, seconds=6.0):
        print(text)
        if self._game is not None:
            self._later(lambda: self._game.message(str(text), seconds))

    def sign(self, x, y, z, text, facing='south'):
        """A sign you can read: the player right-clicks it and the words appear on screen. `text` can be a list of
        pages; each click shows the next page. (facing 'north'/'south' puts the board along x; 'east'/'west' along z.)"""
        if facing not in ('north', 'south', 'east', 'west'):
            raise ValueError("facing must be 'north', 'south', 'east' or 'west'.")
        pages = [text] if isinstance(text, str) else [str(t) for t in text]
        if not pages:
            raise ValueError('A sign needs some words.')
        x, y, z = self._check(x, y, z)
        self.placeblock(x, y, z, 'oak_sign', facing)
        self._signs[(x, y, z)] = pages
        if self._journal is not None:
            self._journal.append(('sign', (x, y, z), pages, facing))
        turn = [0]

        def read():
            page = pages[turn[0] % len(pages)]
            self._show_text(page, min(40.0, max(6.0, len(page) / 9)))
            turn[0] += 1
        self.onclick(x, y, z, read)

    def npc(self, x, y, z, name, lines, kind='villager'):
        """A character who stands still and says something when the player right-clicks them: npc(4, 1, 2, 'Guide', 'Hello!').
        `lines` is a sentence or a list of sentences (each click says the next one). Returns the Creature, so you can still
        give it orders. (The older order, npc('Guide', 4, 1, 2, 'Hello!'), still works.)"""
        if isinstance(x, str):                                    # the older order: name first
            x, y, z, name = y, z, name, x
        creature = self.spawnmob(x, y, z, kind)
        creature.label = name
        creature.stay()
        said = [lines] if isinstance(lines, str) else [str(t) for t in lines]
        if not said:
            raise ValueError('An npc needs something to say.')
        entry = {'creature': creature, 'name': name, 'lines': said}
        creature._npc_entry = entry
        self._npcs.append(entry)
        turn = [0]

        def talk():
            creature.say(said[turn[0] % len(said)], 5)
            turn[0] += 1
        creature.onclick(talk)
        return creature

    def chance(self, probability):
        """True with the given probability: chance(0.3) is True about 3 times in 10. (seed() makes it repeatable.)"""
        if not 0 <= probability <= 1:
            raise ValueError('chance() takes a number from 0 to 1.')
        return self._rng.random() < probability

    def coin(self):
        """'heads' or 'tails'."""
        return self._rng.choice(('heads', 'tails'))

    def choose(self, *options):
        """One of the options, picked at random: choose('oak', 'birch', 'spruce') or choose(my_list)."""
        if len(options) == 1 and isinstance(options[0], (list, tuple)):
            options = options[0]
        if not options:
            raise ValueError('choose() needs something to choose from.')
        return self._rng.choice(list(options))

    def randint(self, low, high):
        """A random whole number from low to high, both included."""
        return self._rng.randint(low, high)

    def has(self, id, how_many=1):
        """A ready-made check for assignment(): True when the build has at least `how_many` of that block."""
        name = _name_of(id)
        return lambda: self.count(name) >= how_many

    def assignment(self, title, checks):
        """For teachers: set homework. `checks` is a list of (description, function); each function returns True when that
        part is done. Students then call submit().

            w.assignment('A house', [('has a door', w.has('oak_door_b')),
                                     ('is big', lambda: w.count() > 100)])
        """
        prepared = []
        for item in checks:
            if not (isinstance(item, (tuple, list)) and len(item) == 2 and callable(item[1])):
                raise TypeError("Each check is a pair: ('what it checks', a_function_that_returns_True_or_False).")
            prepared.append((str(item[0]), item[1]))
        self._assignment[0] = (str(title), prepared)

    def submit(self, name=None, to=None, note=None, code=True):
        """Hand your build in for review. It is saved as a .pcplot file in the submissions folder
        (submissions/<challenge>/<your name>.pcplot), together with your check results and a copy of your program,
        so your teacher can open it and read it. Hand in again as often as you like: the newest one is reviewed.

        name   who you are (or set PYCRAFT_NAME). to: another folder, like a shared one your teacher gave you.
        note   a message for your teacher.   code=False leaves your program out."""
        who = name or self._student or os.environ.get('PYCRAFT_NAME')
        if not who and sys.stdin is not None and sys.stdin.isatty():
            who = input('Your name: ').strip()
        if not who:
            raise ValueError("Say who you are: submit('Sam'). (Or set PYCRAFT_NAME once.)")
        self._student = who
        task, level_number = self._challenge[0], self._level[0]
        results = self._results(task)
        if level_number is not None and task is None:
            problems = self._level_problems(level_number)
            results.append({'label': f'level {level_number}: {_x.LEVELS[level_number - 1][2]}', 'ok': not problems,
                            'detail': problems[0] if problems else ''})
        score = out_of = None
        if results:
            score, out_of = _pcplot.score_of(results, task.points if task else 10)
        challenge_id = task.id if task else (f'level-{level_number}' if level_number else 'free')
        source = None
        if code:
            try:
                import __main__
                path = getattr(__main__, '__file__', None)
                if path and os.path.getsize(path) < 200_000:
                    with open(path) as handle:
                        source = {'file': os.path.basename(path), 'text': handle.read()}
            except (OSError, UnicodeDecodeError):
                source = None
        folder = _pcplot.submissions_folder(to, _START_DIR)
        path, attempt = _pcplot.hand_in(self._data(), who, challenge_id, folder, note or '', results, score, out_of,
                                         level_number, source)
        print(f'Handed in (attempt {attempt}): {path}')
        if results:
            print(f"  Auto-check: {sum(1 for r in results if r['ok'])} of {len(results)} checks passed"
                  + (f' ({score} / {out_of})' if score is not None else ''))
        print('  Your teacher can open it with:  python3 review.py   (and you can read the feedback with w.feedback())')
        return str(path)

    def feedback(self, name=None, to=None):
        """Read what your teacher said about your latest hand-in of this challenge."""
        task = self._challenge[0]
        return feedback(name or self._student, task.id if task else None, to)

    def level(self, number):
        """Start challenge-mode level `number` (1-12): it clears your build, sets the plot and tells you what to do.
        Build it in your script, then call check(). Press C in the game to see the goal again, K to check your build."""
        if not isinstance(number, int) or not 1 <= number <= len(_x.LEVELS):
            raise ValueError(f'Pick a level from 1 to {len(_x.LEVELS)}. levels() lists them.')
        title, plot_size, goal, hint_text, _check_fn, _solution = _x.LEVELS[number - 1]
        self._hooks['enter'].clear()
        self._hooks['click'].clear()
        self._hooks['every'].clear()
        self._hooks['keys'].clear()
        self.clear()
        self.resize(*plot_size)
        self._level[0] = number
        self._failures[0] = 0
        self._challenge[0] = None
        print(f'\nLEVEL {number}: {title}\n  {goal}\n  (Stuck? hint() gives you a clue. When you are done: check())')

    def _level_problems(self, number):
        title, plot_size, goal, hint_text, check_fn, _solution = _x.LEVELS[number - 1]
        extra = {'hooks': {'enter': set(self._hooks['enter']), 'click': set(self._hooks['click']), 'keys': set(self._hooks['keys']),
                           'every': list(self._hooks['every'])}}
        return check_fn(dict(self._blocks), tuple(self._plot), extra)

    def hint(self):
        """A clue for the level you are on."""
        if self._level[0] is None:
            raise ValueError('Start a level first: level(1).')
        print('Hint:', _x.LEVELS[self._level[0] - 1][3])

    def solution(self, number=None):
        """For teachers: print one way to solve a level."""
        number = number or self._level[0]
        if not isinstance(number, int) or not 1 <= number <= len(_x.LEVELS):
            raise ValueError(f'Pick a level from 1 to {len(_x.LEVELS)}.')
        print(f'# Level {number}: {_x.LEVELS[number - 1][0]}\n{_x.LEVELS[number - 1][5]}')

    def _data(self):
        """Everything about this plot as plain data (what a .pcplot file holds)."""
        return {'format': _pcplot.FORMAT, 'version': _pcplot.VERSION, 'title': self.title, 'size': list(self._plot),
                'blocks': _pcplot.pack_blocks(self._blocks),
                'facing': [[x, y, z, f] for (x, y, z), f in self._facing.items()],
                'mobs': [[c.kind, *c.start] for c in self._mobs],
                'signs': [[x, y, z, list(pages)] for (x, y, z), pages in self._signs.items()],
                'npcs': [{'kind': n['creature'].kind, 'pos': list(n['creature'].start), 'name': n['name'], 'lines': n['lines']}
                         for n in self._npcs],
                'settings': {'time': self._time_setting[0], 'cycle': self._time_setting[1], 'weather': self._weather_setting[0],
                             'music': self._music_on[0], 'start': list(self._start[0]) if self._start[0] else None},
                'tutorial': self.tutorial,
                'meta': {}}

    def _restore(self, data):
        """Replace this plot with data from a .pcplot file (already checked by pcplot.validate)."""
        self.clear()
        self.resize(*data['size'])
        self.title = data.get('title', '')
        self.tutorial = data.get('tutorial')
        for pos, name in _pcplot.unpack_blocks(data['blocks']).items():
            self.placeblock(*pos, name)
        for x, y, z, f in data['facing']:
            if (x, y, z) in self._blocks:
                self._facing[(x, y, z)] = f
                self._sync_block((x, y, z))
        npc_spots = {tuple(n['pos']) for n in data['npcs']}
        for name, x, y, z in data['mobs']:
            if (x, y, z) not in npc_spots:
                self._mobs.append(Creature(self, name, x, y, z))
        for x, y, z, pages in data['signs']:
            if (x, y, z) in self._blocks:
                self.sign(x, y, z, pages, self._facing.get((x, y, z), 'south'))
        for n in data['npcs']:
            self.npc(n['name'] or 'Villager', *n['pos'], n['lines'], kind=n['kind'])
        settings = data.get('settings', {})
        if settings.get('time') is not None:
            try:
                self.settime(settings['time'], bool(settings.get('cycle')))
            except (ValueError, TypeError):
                pass
        if settings.get('weather') in ('clear', 'rain', 'snow', 'storm'):
            self.weather(settings['weather'])
        if settings.get('music') is not None:
            self._music_on[0] = bool(settings['music'])
        if isinstance(settings.get('start'), list) and len(settings['start']) == 3:
            self._start[0] = tuple(settings['start'])

    def save(self, filename):
        """Save your build to a .pcplot file (plain readable text) so you can load it later. Returns the file name.
        Signs, what characters say and the sky settings are saved too (the functions you wrote are not)."""
        path = _pcplot.write_plot(_userpath(filename), self._data())
        return str(path)

    def load(self, filename):
        """Load a build saved with save() (a .pcplot file), or an older save, or a share code. It replaces what you have.
        Loading never runs anything: the file is only data."""
        if isinstance(filename, str) and filename.strip().startswith(_x.CODE_PREFIX):
            return self.loadcode(filename)
        path = _userpath(filename)
        if not os.path.exists(path) and os.path.exists(path + '.pcplot'):
            path += '.pcplot'
        try:
            with open(path) as handle:
                content = handle.read()
        except OSError as error:
            raise ValueError(f'Could not open {str(filename)!r}: {error}') from None
        if content.strip().startswith(_x.CODE_PREFIX):
            return self.loadcode(content)
        data, warnings = _pcplot.read_plot(path, set(_names()), _mob_names())
        for warning in warnings:
            print('Note:', warning)
        self._restore(data)

    def share(self, filename=None):
        """Turn your build into a short piece of text (a share code) that a classmate can paste into loadcode().
        If you give a file name it is also written to that file."""
        code = _x.encode_build(self._data())
        if filename:
            with open(_userpath(filename), 'w') as f:
                f.write(code)
        print(f'Share code ({len(code)} characters). Your friend can use w.loadcode(code).')
        return code

    def loadcode(self, code):
        """Load a build from a share code made by share()."""
        data, warnings = _pcplot.validate(_x.decode_build(code), set(_names()), _mob_names())
        for warning in warnings:
            print('Note:', warning)
        self._restore(data)

    def settime(self, when, cycle=False):
        """Set the time of day: 'sunrise', 'morning', 'day', 'sunset', 'night', or a number (0 = sunrise,
        6000 = noon, 12000 = sunset, 18000 = midnight). cycle=True lets time keep passing (a day lasts 12 minutes)."""
        _ticks(when)
        self._time_setting[:] = [when, cycle]
        if self._game is not None:
            def apply():
                self._game.sky.set_time(_ticks(when))
                self._game.sky.frozen = not cycle
            self._later(apply)

    def weather(self, kind='rain'):
        """'clear', 'rain', 'snow' or 'storm' (rain with thunder and lightning). It fades in and out.
        Rain does not fall under a roof."""
        if kind not in ('clear', 'rain', 'snow', 'storm'):
            raise ValueError("weather must be 'clear', 'rain', 'snow' or 'storm'.")
        self._weather_setting[0] = kind
        if self._game is not None and self._runtime['weather'] is not None:
            self._later(lambda: self._runtime['weather'].set(kind))

    def music(self, on=True, volume=0.25):
        """Turn the background music on or off (and set how loud: 0 to 1)."""
        self._music_on[0] = bool(on)
        if self._game is not None:
            def apply():
                self._game.sound.set_music_volume(volume if on else 0.0)
            self._later(apply)

    def say(self, message, seconds=3.0):
        """Show a message on the screen (and in your terminal)."""
        print(message)
        if self._game is not None:
            self._later(lambda: self._game.message(str(message), seconds))

    def give(self, id, count=1):
        """Put something in the player's inventory: a block or an item ('diamond_sword', 'bread', 'bow'...)."""
        from items import ITEMS
        name = str(id).strip().lower().replace(' ', '_')
        if name not in ITEMS:
            close = difflib.get_close_matches(name, list(ITEMS), n=3)
            hint = f' Did you mean {", ".join(repr(c) for c in close)}?' if close else ''
            raise ValueError(f'There is no item called {id!r}.{hint}')
        self._gives.append((name, int(count)))
        if self._game is not None:
            self._later(lambda: self._game.inventory.add(name, int(count)))

    def spawnpoint(self, x, y, z):
        """Where the player starts, and comes back after falling out of the world. (Plot coordinates; it can be
        outside the plot, like z = -3 for in front of it.)"""
        self._start[0] = _numbers(x, y, z)
        if self._game is not None:
            def apply():
                self._game.player.spawn = _player_feet(*self._start[0])
            self._later(apply)

    def teleport(self, x, y, z):
        """Move the player to (x, y, z) in the plot. Before runplot() this is where they start."""
        x, y, z = _numbers(x, y, z)
        if self._game is None:
            self._start[0] = (x, y, z)
            return
        ox, oy, oz = self._origin if self._origin else (0, _FLOOR + 1, 0)
        self._later(lambda: setattr(self._game.player, 'position', (x + ox, y + oy - 0.48, z + oz)))

    def playerpos(self):
        """Where the player is, in plot coordinates (x, y, z), or where they will start if the game is not open."""
        if self._game is None:
            return self._start[0] or (self._plot[0] / 2, 0, -max(3, self._plot[0] // 4))
        p = self._game.player
        ox, oy, oz = self._origin if self._origin else (0, _FLOOR + 1, 0)
        return (round(p.x - ox, 1), round(p.y - oy + 0.5, 1), round(p.z - oz, 1))

    def playsound(self, name='click', volume=1.0):
        """Play a sound: 'levelup', 'pop', 'click', 'explode', 'door', 'orb', 'fire', 'lever', 'bow', 'break', 'enchant', 'fuse'."""
        if name not in _SOUNDS:
            raise ValueError(f"sounds you can use: {', '.join(_SOUNDS)}.")
        if self._game is not None:
            self._later(lambda: self._game.sound.play(_SOUNDS[name], volume))

    def onenter(self, x, y, z, function):
        """Run `function` when the player walks into the block space (x, y, z). The function can take no arguments,
        or (x, y, z). Inside it you can use the library: w.say("Hello!"), w.placeblock(...), w.teleport(...)."""
        _need_function(function)
        pos = self._check(x, y, z)
        self._hooks['enter'][pos] = function
        self._runtime['enter_state'].pop(pos, None)

    def onclick(self, x, y, z, function):
        """Run `function` when the player right-clicks the block at (x, y, z), even in adventure mode.
        There has to be a block there to click on."""
        _need_function(function)
        pos = self._check(x, y, z)
        self._hooks['click'][pos] = function
        if self._game is not None:
            self._later(lambda: self._game.interaction.click_hooks.__setitem__(self._gpos(pos), lambda: self._call(function, *pos)))

    def onkey(self, key, function):
        """Run `function` when a key is pressed, e.g. w.onkey('f', launch). Use letters or digits; avoid
        e, q and the number keys, which the game already uses."""
        _need_function(function)
        self._hooks['keys'][str(key).lower()] = function

    def every(self, seconds, function):
        """Run `function` again and again every `seconds` seconds while the game is open."""
        _need_function(function)
        if not isinstance(seconds, (int, float)) or seconds <= 0:
            raise ValueError('every() needs a number of seconds above 0.')
        self._hooks['every'].append([float(seconds), function])

    def goal(self, x, y, z, message='You win!'):
        """A finish line: when the player walks into (x, y, z) the message appears and a fanfare plays."""
        def won():
            self.say(message, 12)
            self.playsound('levelup')
        self.onenter(x, y, z, won)

    def screenshot(self, path=None):
        """Save a picture of the game window (only while it is open). Returns the file name."""
        path = path or os.path.join(self._runtime['gallery'] or '.', f"{self._runtime['name'] or 'build'}.png")
        if self._game is not None:
            self._later(lambda: _take_screenshot(path))
        return path



# things that need no plot are also reachable from one (w.noise(...), w.blocklist(), w.mirror(clip))
for _name, _function in (('levels', levels), ('progress', progress), ('reset_progress', reset_progress),
                         ('challenges', challenges), ('moblist', moblist), ('blocklist', blocklist), ('blockid', blockid),
                         ('noise', noise), ('makegallery', makegallery), ('rotate', rotate), ('mirror', mirror)):
    setattr(Plot, _name, staticmethod(_function))
Plot.BLOCKS = BLOCKS


# ---- making plots and running them -------------------------------------------------------------------------------

_current = [None]              # the plot whose game window is open right now
_opened = [False]              # the window has been opened once (Ursina can only start once per program)


def plot(x=16, y=16, z=16):
    """Make a building plot x blocks east-west, y high and z north-south: w = pc.plot(16, 16, 16)."""
    return Plot(x, y, z)


def challenge(which):
    """A new plot for a challenge: the right size, with the starting build in it, and the brief printed.
    `which` is a ready-made name ('house'), a challenge from your challenges folder, or a .pcchallenge file.
    Then build, w.check(), and w.submit('your name')."""
    task = _find_challenge(which)
    new = Plot(*(task.size or (16, 16, 16)))
    starter = task.starter_data()
    if starter is not None:
        data, _warnings = _pcplot.validate(starter, set(_names()), _mob_names())
        new._restore(data)
        if task.size:
            new.resize(*task.size)
    new.challenge(task)
    return new


def load(filename):
    """Open a .pcplot file as a new plot: w = pc.load('house.pcplot')."""
    new = Plot()
    new.load(filename)
    return new


def view(filename, **options):
    """Open a .pcplot file in the game to look around it (as a spectator by default)."""
    options.setdefault('mode', spectator)
    mode = options.pop('mode')
    opened = load(filename)
    if 'message' not in options:
        meta = _pcplot.read_meta(_userpath(filename)) or {}
        if meta.get('student'):
            options['message'] = f"{meta['student']} - {meta.get('challenge', '')} (attempt {meta.get('attempt', 1)})"
        elif opened.title:
            options['message'] = opened.title
    runplot(opened, mode, **options)


def level(number):
    """A new plot for challenge-mode level `number` (1-12), set up with the right size and goal: w = pc.level(3)."""
    new = Plot()
    new.level(number)
    return new


def solution(number):
    """For teachers: print one way to solve a level."""
    Plot().solution(number)


def _wants_argument(function):
    try:
        return len(inspect.signature(function).parameters) >= 1
    except (TypeError, ValueError):
        return False


def running():
    """True while the game window is open (use it to end your own loops: `while pc.running():`)."""
    shown = _current[0]
    return shown is not None and not shown._runtime['closed']


def wait(seconds):
    """Pause your script for a moment. Handy with live(), to watch a build appear block by block."""
    end = _time.time() + seconds
    while _time.time() < end:
        shown = _current[0]
        if shown is not None and shown._runtime['closed']:
            raise SystemExit
        _time.sleep(min(0.05, max(0.0, end - _time.time())))


def live(plot, script, **options):
    """Open the game and run `script` (a function you wrote) at the same time. Blocks you place in it
    appear in the game while you watch, so you can use pc.wait() to animate:

        def build():
            for i in range(10):
                w.placeblock(i, 0, 0, 'gold_block')
                pc.wait(0.3)
        pc.live(w, build)

    The other options are the same as runplot()."""
    if not callable(script):
        raise TypeError('live() needs a function: pc.live(w, build)')
    runplot(plot, script=script, **options)


def plot_world_data(plot, border=True, dimension='overworld'):
    """A plot as the game's world: ({game position: block name}, {game position: facing}, where the player starts).
    (runplot and the classroom server (lan.py host --plot) both use this.)"""
    px, py, pz = plot._plot
    modified = {_to_game(x, y, z): b for (x, y, z), b in plot._blocks.items()}      # y = 0 sits on the grass
    facing = {_to_game(x, y, z): f for (x, y, z), f in plot._facing.items()}
    if border:
        border_block = 'nether_bricks' if dimension == 'nether' else 'stone_bricks'
        for x in range(-1, px + 1):
            for z in (-1, pz):
                modified.setdefault((x, _FLOOR, z), border_block)
        for z in range(-1, pz + 1):
            for x in (-1, px):
                modified.setdefault((x, _FLOOR, z), border_block)
    start = plot._start[0]
    spawn = _player_feet(*start) if start else (px / 2, _FLOOR + 1.01, -max(3, px // 4))
    return modified, facing, spawn


def runplot(plot, mode='adventure', time=None, border=True, dimension='overworld', peaceful=False, gallery=None,
            name=None, script=None, message=None, allow_building=False, _screenshot=None, _seconds=6, _hook=None):
    """Open the game window and let you walk around your creation. Closing the window ends the program,
    so make this the last line.

    mode       'adventure' (the default): walk, swim and use doors, chests, furnaces, crafting tables, beds,
               levers and buttons, but you cannot place or break blocks.
               'spectator': fly through everything to look at your build (nothing can be touched or clicked).
               The game is always one of these two: it can never be changed to a mode that lets you build or break.
    time       'day', 'night', 'sunrise', 'sunset' or a number of ticks (0 = sunrise, 6000 = noon, 18000 = midnight).
               (plot.settime() before runplot() does the same, and can let the day pass.)
    border     draw a line of bricks around your plot so you can see where it ends
    dimension  'overworld' (grass and sky) or 'nether' (netherrack floor, red haze, no sunlight:
               light your build with glowstone or lava!)
    peaceful   True: nothing can hurt you, even the creatures you placed
    gallery    a folder: press F2 (or leave through the menu) to save a picture of your build there
    name       the picture's name, e.g. your own name
    message    a line shown on screen when the game starts"""
    pass
    if time is not None:
        plot._time_setting[0] = time
    time = plot._time_setting[0]
    _ticks(time)
    if mode == 'creative' and not allow_building:
        raise ValueError("The game is always adventure (walk around and use things) or spectator (fly around and look). "
                         "Creative mode is only for the tutorial maker, maketutorial.py.")
    if mode not in ('adventure', 'spectator', 'creative'):
        raise ValueError("mode must be 'adventure' (walk around and use things) or 'spectator' (fly around and look).")
    if _opened[0]:
        raise RuntimeError('The game window can only be opened once each time your program runs. '
                           'Run your program again to look at another plot (or put them side by side in one big plot).')
    if dimension not in ('overworld', 'nether'):
        raise ValueError("dimension must be 'overworld' or 'nether'.")

    if gallery:
        gallery = _userpath(gallery)                     # (before we move to the game's folder)
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    came_from = os.getcwd()
    os.chdir(here)                                   # the game finds its pictures and sounds from here

    _opened[0] = True
    from pathlib import Path
    import ursina
    from ursina import Ursina, color, window, camera, application
    from ursina import time as ursina_time
    from mac_fix import clear_leftover_shaders, fix_shaders, fix_ui_scale

    fix_shaders()
    icon = Path(ursina.__file__).parent / 'textures' / 'ursina.ico'
    app = Ursina(title='pycraft', icon=str(icon))
    clear_leftover_shaders()
    window.fps_counter.enabled = window.entity_counter.enabled = window.collider_counter.enabled = False
    window.exit_button.enabled = window.cog_button.enabled = False

    from game import Game
    from weather import Weather
    px, py, pz = plot._plot
    modified, facing, _spawn = plot_world_data(plot, border, dimension)
    folder = Path(tempfile.mkdtemp(prefix='pycraftworld_'))      # a throwaway folder: your saved games are never touched
    spawn = (px / 2, _FLOOR + 3 + 1, -4)
    game = Game(folder, 'pycraftWorld', seed=0, mode={'spectator': 'spectator', 'creative': 'creative'}.get(mode, 'survival'),
                modified=modified, facing=facing, flat_spawn=spawn, adventure=mode != 'creative',
                dimension=dimension)      # (locked: no building or breaking, except in the tutorial maker's creative mode)
    if mode == 'creative':
        game.menu.locked_mode = 'Creative'
        game.menu._update_mode_label()
    plot._authoring = bool(allow_building and mode == 'creative')
    if mode == 'spectator':
        game.menu.locked_mode = 'Spectator'
        game.menu._update_mode_label()
    game.save = lambda: None                                      # nothing is ever written to disk
    game.mobs.update_spawning = lambda dt: None
    for mob in game.mobs.mobs[:]:
        game.mobs.remove(mob)
    for creature in plot._mobs:                                        # the creatures you placed
        creature._attach(game)
    game.portals.update = lambda *args, **kwargs: None            # a portal here is for looking at
    if peaceful:
        game.player.damage = lambda *args, **kwargs: None
    for item, amount in plot._gives:
        game.inventory.add(item, amount)

    game.sky.set_time(_ticks(time))
    game.sky.frozen = not plot._time_setting[1]
    game.player.rotation_y = 0
    start = plot._start[0]
    game.player.position = _player_feet(*start) if start else (px / 2, _FLOOR + 1.01, -max(3, px // 4))
    game.player.spawn = game.player.position
    window.color = color.rgb32(135, 206, 235)
    if not plot._music_on[0]:
        game.sound.set_music_volume(0.0)
        game.sound._music_wait = 1e9

    weather_machine = Weather(game.sky, game.player, game.world, game.sound)
    weather_machine.set(plot._weather_setting[0])
    if plot._weather_setting[0] != 'clear':
        weather_machine.level = 0.9                                # (already raining when you arrive)
    plot._runtime.update(weather=weather_machine, queue=[], closed=False, gallery=gallery, name=name, enter_state={}, timers={})
    for pos, function in plot._hooks['click'].items():
        game_pos = _to_game(*pos)
        game.interaction.click_hooks[game_pos] = (lambda f=function, p=pos: plot._call(f, *p))
    plot._game = game
    _current[0] = plot
    import mods
    console_feed = getattr(plot, '_console', None)
    if console_feed is not None:                                        # press / in the game to type code (livecode.py)
        from gameconsole import GameConsole
        game.console = GameConsole(game, *console_feed)
    mod_runtime = mods.ModRuntime(game, schedule=plot._later)          # blocks and creatures from pc.mod() / pc.mob()
    if plot._menu_buttons:
        game.menu.add_buttons(plot._menu_buttons)
    if message:
        game.message(str(message), 10)
    if plot._level[0] is not None:
        game.message(f'Level {plot._level[0]}: {_x.LEVELS[plot._level[0] - 1][2]}   (C = goal, K = check)', 12)

    import __main__

    def tick(dt):
        plot._run_queue(dt)                                    # work your own thread asked for
        game.world.flush_dirty(0.006)
        mod_runtime.update(dt)
        if game.console is not None:
            game.console.update(dt)
        weather_machine.update(dt)
        if plot._authoring:
            plot._runtime['pull_timer'] = plot._runtime.get('pull_timer', 0.0) + dt
            if plot._runtime['pull_timer'] >= 2.0 and not plot._runtime['queue'] and plot._journal is None:
                plot._runtime['pull_timer'] = 0.0
                plot._pull_from_game()
        # walking into places
        p = game.player
        feet = _from_game(round(p.x), int((p.y + 0.5) // 1), round(p.z))
        inside_cells = {feet, (feet[0], feet[1] + 1, feet[2])}          # (your feet and head)
        if p.grounded:
            inside_cells.add((feet[0], feet[1] - 1, feet[2]))          # (and the block you stand on)
        for pos, function in list(plot._hooks['enter'].items()):
            now = pos in inside_cells
            if now and not plot._runtime['enter_state'].get(pos):
                plot._call(function, *pos)
            plot._runtime['enter_state'][pos] = now
        for entry in plot._hooks['every']:
            key = id(entry)
            plot._runtime['timers'][key] = plot._runtime['timers'].get(key, 0.0) + dt
            if plot._runtime['timers'][key] >= entry[0]:
                plot._runtime['timers'][key] = 0.0
                plot._call(entry[1])

    def update():
        fix_ui_scale()
        game.update()
        tick(ursina_time.dt)

    def level_key(key):
        """In challenge mode: C shows the goal again, K checks your build."""
        number = plot._level[0]
        if number is None or key not in ('c', 'k') or key in plot._hooks['keys']:
            return False
        title, _size, goal, _hint, _fn, _sol = _x.LEVELS[number - 1]
        if key == 'c':
            game.message(f'Level {number}: {goal}', 10)
        else:
            problems = plot._level_problems(number)
            if problems:
                game.message('Not yet: ' + problems[0], 8)
            else:
                game.message(f'Level {number} complete! Now run check() in your script to save your stars.', 10)
                game.sound.play('random/levelup', 0.8)
        return True

    def on_input(key):
        if game.console is not None and game.console.is_open:          # typing code: u, y, c, k... are letters, not shortcuts
            game.input(key)
            return
        if level_key(key) and not game.ui.active and not game.menu.is_open:
            return
        function = plot._hooks['keys'].get(key)
        if function is not None and not game.ui.active and not game.menu.is_open:
            plot._call(function)
            return
        if key == 'f2' and plot._runtime['gallery']:
            path = _take_screenshot(os.path.join(plot._runtime['gallery'], f"{plot._runtime['name'] or 'build'}.png"))
            game.message(f'Picture saved: {path}', 3)
            return
        game.input(key)

    __main__.input = on_input
    __main__.update = update

    real_quit = application.quit

    def quit_with_picture():
        plot._runtime['closed'] = True
        if plot._runtime['gallery']:
            try:
                path = _take_screenshot(os.path.join(plot._runtime['gallery'], f"{plot._runtime['name'] or 'build'}.png"))
                print(f'Picture saved: {path}')
            except Exception as error:                            # (never stop the game from closing)
                print('Could not save the picture:', error)
        real_quit()

    application.quit = quit_with_picture

    if script is not None:
        def run_script():
            try:
                script(plot) if _wants_argument(script) else script()
            except SystemExit:
                pass
            except Exception as error:
                print('\nYour live() function stopped because of a problem:')
                traceback.print_exc()
                plot.say(f'Your script stopped: {error}', 8)
        threading.Thread(target=run_script, daemon=True).start()

    if _hook:                                                    # (used for testing)
        from ursina import Sequence, Wait, Func
        Sequence(Wait(3), Func(_hook, game), Wait(1), Func(application.quit)).start()
    if _screenshot:                                              # (used for testing)
        from ursina import Sequence, Wait, Func

        def snap():
            application.base.screenshot(_screenshot, defaultFilename=False)
        Sequence(Wait(_seconds), Func(snap), Wait(0.5), Func(application.quit)).start()
    try:
        app.run()
    finally:
        plot._runtime['closed'] = True
        mod_runtime.close()
        weather_machine.clear()
        application.quit = real_quit
        plot._game = None
        _current[0] = None
        os.chdir(came_from)

Plot.wait = staticmethod(wait)
Plot.running = staticmethod(running)


# ---- mods: your own blocks, woods, items and creatures (see docs/README_mods.md) ------------------------------------

def mod(name='mod'):
    """Start a mod: m = pc.mod('my-mod'), then m.addblock('snad', 'snad.png'), m.addwood('purple', 'leaves.png')..."""
    import mods
    return mods.Mod(name)


def mob(base, name=None, mod=None):
    """A new creature made from an old one: golem = pc.mob(pc.golem, 'vine_golem'). Then .texture('skin.png'),
    .health(60), .spawncondition(pc.block_placement('shape.pcschem'))... See moblist() for the creatures.
    It belongs to the latest pc.mod() (or to mod=m), so m.save() keeps it."""
    import mods
    return mods.MobBuilder(base, name, mod=mod)


def loadmod(filename):
    """Add the blocks, wood, items and creatures of a .pcmod file (made with m.save('name.pcmod'))."""
    import mods
    return mods.load_pcmod(_userpath(filename))


def block_placement(pattern, consume=True, rotate=True):
    """A spawn condition: the creature appears when blocks are built in the shape of `pattern` (a .pcschem file)."""
    import mods
    return mods.block_placement(pattern, consume, rotate)


def near_block(block, radius=6, chance=0.15, limit=3):
    """A spawn condition: the creature appears now and then near these blocks."""
    import mods
    return mods.near_block(block, radius, chance, limit)


def on_block(block, chance=0.1, limit=3):
    """A spawn condition: the creature appears now and then standing on these blocks."""
    import mods
    return mods.on_block(block, chance, limit)


def at_night(chance=0.15, limit=4):
    """A spawn condition: the creature appears in the dark."""
    import mods
    return mods.at_night(chance, limit)


def anywhere(chance=0.1, limit=4):
    """A spawn condition: the creature appears now and then, anywhere."""
    import mods
    return mods.anywhere(chance, limit)


def paint(filename, like=None, skin=None, size=16):
    """Open the picture painter on a .png for your mod: pc.paint('snad.png', like='sand') starts from a copy of the sand block's
    picture, pc.paint('golem.png', skin='golem') from a creature's skin. It opens in its own window; save with Ctrl+S."""
    import painter
    return painter.open_window(_userpath(filename), like, skin, size)


def export_skin(creature, filename):
    """Copy a creature's skin so you can paint your own: pc.export_skin(pc.golem, 'golem.png')."""
    import mods
    return mods.export_skin(creature, _userpath(filename))


def export_texture(block, filename):
    """Copy a block's picture (16 x 16) so you can paint your own: pc.export_texture('sand', 'snad.png')."""
    import mods
    return mods.export_texture(block, _userpath(filename))


def schematic(plot, x1, y1, z1, x2, y2, z2, filename):
    """Save the blocks in a box of a plot as a .pcschem pattern: the same as plot.copy(...).save(filename)."""
    return plot.copy(x1, y1, z1, x2, y2, z2).save(filename)


_CREATURE_ALIASES = {'golem': 'iron_golem', 'pigman': 'zombie_pigman', 'lava_slime': 'magma_cube', 'cat': 'ocelot', 'dog': 'wolf'}


def __getattr__(name):
    """pc.golem, pc.zombie, pc.pig... are the creatures' names (so mob(pc.golem) reads nicely), and pc.stone, pc.oak_planks...
    are the blocks' names: w.fill(0, 0, 0, 5, 0, 5, pc.stone) is the same as w.fill(0, 0, 0, 5, 0, 5, 'stone')."""
    if name in _CREATURE_ALIASES:
        return _CREATURE_ALIASES[name]
    if not name.startswith('_') and name in _mob_names():
        return name
    if not name.startswith('_') and (name == 'air' or name in _names()):      # pc.stone, pc.oak_planks, pc.snad...
        return name
    close = [] if name.startswith('_') else difflib.get_close_matches(name, _names() + sorted(_mob_names()), n=3)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}' + (f'. Did you mean {", ".join(close)}?' if close else ''))

__all__ = ['plot', 'challenge', 'feedback', 'load', 'view', 'Challenge', 'require', 'level', 'solution', 'runplot', 'live', 'wait', 'running', 'adventure', 'spectator', 'Plot', 'Clip',
           'Creature', 'Turtle', 'BLOCKS', 'blocklist', 'blockid', 'moblist', 'noise', 'levels', 'progress',
           'reset_progress', 'challenges', 'makegallery', 'rotate', 'mirror', 'mod', 'mob', 'block_placement', 'near_block',
           'on_block', 'at_night', 'anywhere', 'export_skin', 'export_texture', 'schematic', 'paint', 'loadmod']
