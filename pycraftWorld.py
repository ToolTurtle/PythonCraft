"""pycraftWorld - build a Minecraft-style world by writing Python: the quick, one-plot way.

    import pycraftWorld as w

    w.size(16, 16, 16)              # how big your building plot is (x, y, z)
    w.placeblock(0, 0, 0, 'stone')  # put a block down
    w.fillblocks(0, 0, 0, 15, 0, 15, 'grass')   # fill a whole box of blocks
    w.show()                        # open the game and walk around your creation!

This is the same library as `pycraft`, with one plot made for you. Everything here is a method of that plot:
`w.placeblock(...)` is `plot.placeblock(...)`. When you want several plots, or like objects, use `pycraft`:

    import pycraft as pc
    w = pc.plot(16, 16, 16)
    w.placeblock(0, 0, 0, 'stone')
    pc.runplot(w, pc.adventure)

Coordinates: x goes east, y goes UP, z goes south. (0, 0, 0) is the corner of your plot, standing on the ground.
A block's id is its name ('stone', 'oak_planks', ...) or its number. Call w.blocklist() to see them all.
"""
import sys as _sys

import pycraft as _pc
from pycraft import (BLOCKS, Clip, Creature, Turtle, adventure, spectator, blockid, blocklist, challenges, levels,
                     makegallery, mirror, moblist, noise, progress, reset_progress, rotate, running, wait, _FLOOR)

_plot = _pc.plot(16, 16, 16)           # the plot this module builds in

# every public method of the plot becomes a function of this module: w.placeblock(...)
_SKIP = {'resize', 'wait', 'running', 'BLOCKS'}
for _name in dir(_plot):
    if not _name.startswith('_') and _name not in _SKIP and callable(getattr(_plot, _name)):
        globals()[_name] = getattr(_plot, _name)

size = _plot.resize                    # (the plot's resize() is called size() here)
solution = _plot.solution

# the plot's insides, for tests and curious people
_blocks, _facing, _mobs, _hooks, _gives, _start = _plot._blocks, _plot._facing, _plot._mobs, _plot._hooks, _plot._gives, _plot._start
_level, _challenge, _failures, _runtime = _plot._level, _plot._challenge, _plot._failures, _plot._runtime


def __getattr__(name):
    if name == '_game':
        return _plot._game
    raise AttributeError(name)


def show(time=None, border=True, dimension='overworld', peaceful=False, mode='adventure', gallery=None, name=None,
         script=None, **testing):
    """Open the game window and let you walk around your creation. Closing the window ends the program,
    so make this the last line.
    (Same options as pycraft.runplot: mode 'adventure' or 'spectator', time, dimension, peaceful, gallery, name.)"""
    _pc.runplot(_plot, mode, time=time, border=border, dimension=dimension, peaceful=peaceful, gallery=gallery, name=name,
                script=script, **testing)


def live(script, **options):
    """Open the game and run `script` (a function you wrote) at the same time; see pycraft.live()."""
    if not callable(script):
        raise TypeError('live() needs a function: w.live(build)')
    show(script=script, **options)


__all__ = ['size', 'show', 'live', 'wait', 'running', 'BLOCKS', 'Clip', 'Creature', 'Turtle', 'blockid', 'blocklist',
           'challenges', 'levels', 'makegallery', 'mirror', 'moblist', 'noise', 'progress', 'reset_progress', 'rotate',
           'solution'] + [n for n in dir(_plot) if not n.startswith('_') and n not in _SKIP and callable(getattr(_plot, n))]
