"""classworld - a teacher's class setup (the .pcclass file) and the operations on a class world: lay out the plots, give them to students,
paste a starter build into every plot, bring students' hand-ins into their plots, export a plot to edit it, reset a plot.

Plain data and arithmetic, no game window (classtool.py is the window on top of it; `python3 classtool.py help` does the same by typing).

A .pcclass file holds: the class name, the roster (names), the plot layout, the game mode new students start in, and an optional starter
build to paste into each plot. The class WORLD (what players have built) is kept by the server in lanworlds/NAME.lanworld.json."""
import json
from pathlib import Path

import pcplot
from classlayout import GROUND, Layout, clean_roster
from lanserver import WorldState

FORMAT = 'pcclass'
VERSION = 1
PLOT_HEIGHT = 48                       # how tall a plot's code area is (and how much of a plot is exported)


class ClassSetup:
    def __init__(self, name='My class', roster=(), layout=None, mode='adventure', self_claim=True, template=None, auto_claim=False):
        self.name = str(name)[:60] or 'My class'
        self.roster = list(roster)
        self.layout = layout or Layout.grid(1, 1)
        self.mode = mode
        self.self_claim = bool(self_claim)
        self.auto_claim = bool(auto_claim)             # everyone who joins gets a plot at once (and the grid grows if needed): plot mode
        self.template = template                       # {'blocks': {(x, y, z): name}, 'facing': {(x, y, z): facing}} in plot coordinates, or None

    # ---- making one ----------------------------------------------------------------------------------------------------------

    @classmethod
    def for_roster(cls, name, names, width=16, depth=16, gap=5, columns=None, extra=2, mode='adventure', auto_claim=False):
        """A grid with a plot for everyone on the roster (and `extra` spare ones), the names filled in."""
        names = clean_roster('\n'.join(names)) if not isinstance(names, str) else clean_roster(names)
        total = max(1, len(names) + extra)
        columns = columns or max(1, min(8, round(total ** 0.5 + 0.49)))
        rows = -(-total // columns)
        layout = Layout.grid(columns, rows, width, depth, gap, names=names)
        layout.plots = layout.plots[:total]                              # (exactly as many plots as asked for: the grid may have empty places at the end)
        layout.refit()
        layout.self_claim = True
        return cls(name, names, layout, mode, auto_claim=auto_claim)

    def set_owner(self, plot_id, name):
        plot = self.layout.plot_by_id(plot_id)
        if plot is None:
            raise ValueError(f'There is no plot {plot_id}.')
        if name:
            clean = clean_roster(name)
            name = clean[0] if clean else None
            old = self.layout.owner_of(name) if name else None
            if old is not None and old is not plot:
                old.owner = None                       # (one plot each)
        plot.owner = name or None
        if name and name.lower() not in [r.lower() for r in self.roster]:
            self.roster.append(name)

    # ---- the file --------------------------------------------------------------------------------------------------------------

    def to_json(self):
        template = None
        if self.template:
            template = {'blocks': pcplot.pack_blocks(self.template['blocks']),
                        'facing': [[x, y, z, f] for (x, y, z), f in self.template.get('facing', {}).items()]}
        return {'format': FORMAT, 'version': VERSION, 'name': self.name, 'roster': self.roster, 'layout': self.layout.to_json(),
                'mode': self.mode, 'self_claim': self.self_claim, 'auto_claim': self.auto_claim, 'template': template}

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, dict) or data.get('format') != FORMAT:
            raise ValueError('This is not a class setup file (.pcclass).')
        if data.get('version') != VERSION:
            raise ValueError(f"This class file is version {data.get('version')!r}; this game reads version {VERSION}.")
        layout = Layout.from_json(data['layout'])
        template = None
        if data.get('template'):
            template = {'blocks': pcplot.unpack_blocks(data['template']['blocks']),
                        'facing': {(x, y, z): f for x, y, z, f in data['template'].get('facing', [])}}
        mode = data.get('mode', 'adventure')
        return cls(data.get('name', 'My class'), clean_roster('\n'.join(map(str, data.get('roster', [])))), layout,
                   mode if mode in ('adventure', 'survival', 'creative', 'spectator') else 'adventure', data.get('self_claim', True), template, data.get('auto_claim', False))

    def save(self, path):
        path = Path(path)
        if path.suffix != '.pcclass':
            path = path.with_suffix('.pcclass')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1))
        return path

    @classmethod
    def load(cls, path):
        try:
            return cls.from_json(json.loads(Path(path).read_text()))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError(f'Could not open {str(path)!r}: {error}') from None

    # ---- the world -----------------------------------------------------------------------------------------------------------------

    def build_world(self):
        """The class world to start from: a flat world with the plot markers, and the starter build in every plot."""
        self.layout.self_claim = self.self_claim
        self.layout.auto_claim = self.auto_claim
        changes = {pos: (name, None) for pos, name in self.layout.marker_blocks().items()}
        world = WorldState(0, self.name, list(self.layout.spawn), changes, self.layout)
        if self.template:
            for plot in self.layout.plots:
                paste(world, plot, self.template['blocks'], self.template.get('facing'))
        return world


# ---- operations on a class world --------------------------------------------------------------------------------------------------

def plot_origin(plot):
    """Where a plot's (0, 0, 0) is in the world: its corner, on the block above the ground."""
    return plot.x1, GROUND + 1, plot.z1


def clear(world, plot):
    """Remove everything built in a plot (the ground and the line around it stay)."""
    removed = 0
    for pos in [p for p in world.changes if plot.contains(p[0], p[2]) and p[1] > GROUND]:
        del world.changes[pos]
        removed += 1
    world.dirty = True
    return removed


def paste(world, plot, blocks, facing=None, clear_first=False):
    """Put blocks (plot coordinates) into a plot. Anything outside the plot is left out. Returns (placed, left out)."""
    if clear_first:
        clear(world, plot)
    ox, oy, oz = plot_origin(plot)
    width, depth = plot.size
    placed = skipped = 0
    for (x, y, z), name in blocks.items():
        if not (0 <= x < width and 0 <= z < depth and 0 <= y < 120 - GROUND):
            skipped += 1
            continue
        world.changes[(ox + x, oy + y, oz + z)] = (name, (facing or {}).get((x, y, z)))
        placed += 1
    world.dirty = True
    return placed, skipped


def plot_blocks(world, plot):
    """What is built in a plot, in plot coordinates: ({(x, y, z): block name}, {(x, y, z): facing})."""
    ox, oy, oz = plot_origin(plot)
    blocks, facing = {}, {}
    for (x, y, z), (name, face) in world.changes.items():
        if name and plot.contains(x, z) and y > GROUND:
            blocks[(x - ox, y - oy, z - oz)] = name
            if face:
                facing[(x - ox, y - oy, z - oz)] = face
    return blocks, facing


def export_plot(world, plot, path):
    """Write what is built in a plot as a .pcplot you can open, edit with the usual pycraft tools and import again."""
    import pycraft
    blocks, facing = plot_blocks(world, plot)
    width, depth = plot.size
    height = min(100, max([y for (_x, y, _z) in blocks] + [7]) + 1)
    sheet = pycraft.plot(min(width, 256), height, min(depth, 256))
    sheet._blocks.update(blocks)
    sheet._facing.update(facing)
    sheet.title = f"Plot {plot.id}" + (f" ({plot.owner})" if plot.owner else '')
    return sheet.save(str(path))


def read_pcplot(path):
    """The blocks and facings of a .pcplot file (plot coordinates), checked."""
    import blocks as game_blocks
    data, _warnings = pcplot.read_plot(path, set(game_blocks.BLOCKS), None)
    blocks = pcplot.unpack_blocks(data['blocks'])
    facing = {}
    for entry in data.get('facing', []):
        if isinstance(entry, (list, tuple)) and len(entry) == 4:
            facing[(entry[0], entry[1], entry[2])] = entry[3]
    return blocks, facing


def import_pcplot(world, plot, path, clear_first=True):
    """Put a .pcplot file into a plot. Returns (placed, left out)."""
    blocks, facing = read_pcplot(path)
    return paste(world, plot, blocks, facing, clear_first=clear_first)


def import_handins(world, folder, challenge=None, clear_first=True):
    """Bring each student's newest hand-in (from submissions/) into the plot that student owns. Returns a list of lines saying what happened."""
    lines, done = [], set()
    for entry in pcplot.list_submissions(folder, challenge):                 # (newest first)
        student = entry['student']
        if student.lower() in done:
            continue
        done.add(student.lower())
        plot = world.layout.owner_of(student)
        if plot is None:
            lines.append(f'{student}: has no plot, so the hand-in was not used.')
            continue
        try:
            placed, skipped = import_pcplot(world, plot, entry['path'], clear_first)
        except (ValueError, pcplot.PlotFileError) as error:
            lines.append(f'{student}: could not be used ({error}).')
            continue
        lines.append(f'{student}: {placed} blocks into plot {plot.id}' + (f' ({skipped} did not fit)' if skipped else '') + '.')
    return lines or ['There were no hand-ins to bring in.']
