"""classlayout - how a class world is laid out: student plots, who owns which, the border, and the blocks that mark them.

This module is plain data and arithmetic (no game window). The class server uses it to decide who may build where, and the
teacher's class tool (classtool.py) uses it to design a class world.

A plot is a rectangle on the ground (x1..x2, z1..z2, both ends included) that goes up to the top of the world.
Owners are names: a teacher can pre-assign names from a roster, or students /claim a free plot."""
import json
import re

GROUND = 3                    # the top layer of a flat class world (a plot's y = 0 is the block above it)
HEIGHT = 128


class Plot:
    def __init__(self, ident, x1, z1, x2, z2, owner=None, label=''):
        self.id, self.owner, self.label = int(ident), owner, label
        self.x1, self.x2 = min(int(x1), int(x2)), max(int(x1), int(x2))
        self.z1, self.z2 = min(int(z1), int(z2)), max(int(z1), int(z2))

    def contains(self, x, z):
        return self.x1 <= x <= self.x2 and self.z1 <= z <= self.z2

    @property
    def size(self):
        return (self.x2 - self.x1 + 1, self.z2 - self.z1 + 1)

    @property
    def center(self):
        return ((self.x1 + self.x2) / 2, (self.z1 + self.z2) / 2)

    def to_json(self):
        return {'id': self.id, 'x1': self.x1, 'z1': self.z1, 'x2': self.x2, 'z2': self.z2, 'owner': self.owner, 'label': self.label}


class Layout:
    def __init__(self, plots=None, border=None, spawn=None, self_claim=True):
        self.plots = list(plots or [])
        self.border = border                           # (x1, z1, x2, z2) or None: nobody (but teachers) goes or builds outside it
        self.spawn = spawn                             # (x, y, z) where players start
        self.self_claim = bool(self_claim)             # may students /claim a free plot themselves?

    # ---- who owns what -----------------------------------------------------------------------------------------------

    def plot_at(self, x, z):
        for plot in self.plots:
            if plot.contains(x, z):
                return plot
        return None

    def plot_by_id(self, ident):
        for plot in self.plots:
            if plot.id == int(ident):
                return plot
        return None

    def owner_of(self, name):
        """The plot this name owns (the first one), or None."""
        low = str(name).lower()
        for plot in self.plots:
            if plot.owner and plot.owner.lower() == low:
                return plot
        return None

    def free_plots(self):
        return [p for p in self.plots if not p.owner]

    def assign(self, ident, name):
        plot = self.plot_by_id(ident)
        if plot is None:
            raise ValueError(f'There is no plot {ident}.')
        plot.owner = name
        return plot

    def inside_border(self, x, z):
        if self.border is None:
            return True
        x1, z1, x2, z2 = self.border
        return x1 <= x <= x2 and z1 <= z <= z2

    # ---- making a layout ---------------------------------------------------------------------------------------------------

    @classmethod
    def grid(cls, columns, rows, width=16, depth=16, gap=5, margin=14, names=()):
        """A grid of equal plots with paths between them, a border around everything, and a start in front. `names` fills in owners."""
        if not (1 <= columns <= 20 and 1 <= rows <= 20 and 4 <= width <= 128 and 4 <= depth <= 128 and 3 <= gap <= 30):
            raise ValueError('A grid is 1 to 20 plots across and down, each 4 to 128 blocks wide, with paths 3 to 30 wide.')
        plots, number = [], 1
        for row in range(rows):
            for column in range(columns):
                x1, z1 = column * (width + gap), row * (depth + gap)
                owner = names[number - 1] if number - 1 < len(names) and names[number - 1] else None
                plots.append(Plot(number, x1, z1, x1 + width - 1, z1 + depth - 1, owner))
                number += 1
        total_x, total_z = columns * (width + gap) - gap, rows * (depth + gap) - gap
        border = (-margin, -margin - 4, total_x + margin - 1, total_z + margin - 1)
        spawn = (total_x / 2, GROUND + 1.01, -margin / 2 - 2)
        return cls(plots, border, spawn)

    def marker_blocks(self):
        """{(x, y, z): block name}: a ring of stone bricks around every plot, gravel on the paths between them. (The ground itself
        comes from the flat world.)"""
        blocks = {}
        if not self.plots:
            return blocks
        y = GROUND
        for plot in self.plots:
            for x in range(plot.x1 - 1, plot.x2 + 2):
                blocks[(x, y, plot.z1 - 1)] = 'stone_bricks'
                blocks[(x, y, plot.z2 + 1)] = 'stone_bricks'
            for z in range(plot.z1 - 1, plot.z2 + 2):
                blocks[(plot.x1 - 1, y, z)] = 'stone_bricks'
                blocks[(plot.x2 + 1, y, z)] = 'stone_bricks'
        x_min, x_max = min(p.x1 for p in self.plots) - 1, max(p.x2 for p in self.plots) + 1
        z_min, z_max = min(p.z1 for p in self.plots) - 1, max(p.z2 for p in self.plots) + 1
        for x in range(x_min, x_max + 1):
            for z in range(z_min, z_max + 1):
                if (x, y, z) not in blocks and self.plot_at(x, z) is None:
                    blocks[(x, y, z)] = 'gravel'
        return blocks

    # ---- keeping it ---------------------------------------------------------------------------------------------------------

    def to_json(self):
        return {'plots': [p.to_json() for p in self.plots], 'border': list(self.border) if self.border else None,
                'spawn': list(self.spawn) if self.spawn else None, 'self_claim': self.self_claim}

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, dict):
            raise ValueError('This is not a class layout.')
        plots = []
        for entry in data.get('plots', []):
            plots.append(Plot(entry['id'], entry['x1'], entry['z1'], entry['x2'], entry['z2'], entry.get('owner'), entry.get('label', '')))
        border = tuple(data['border']) if data.get('border') else None
        spawn = tuple(data['spawn']) if data.get('spawn') else None
        return cls(plots, border, spawn, data.get('self_claim', True))

    def describe(self):
        lines = []
        for plot in self.plots:
            lines.append(f"plot {plot.id}: {plot.owner or '(free)'}  x {plot.x1}..{plot.x2}, z {plot.z1}..{plot.z2}")
        return lines


def clean_roster(text):
    """Names from a pasted list (one per line, or separated by commas): safe player names, no duplicates, in order."""
    names, seen = [], set()
    for piece in re.split(r'[\n,;]+', str(text)):
        name = re.sub(r'[^A-Za-z0-9 _-]', '', piece).strip()[:16].strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names
