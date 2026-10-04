"""maketutorial - make a tutorial world in CREATIVE mode: build by hand, or code it live.

    python3 maketutorial.py my-lesson          start making a tutorial world called my-lesson
    python3 maketutorial.py my-lesson --size 60 14 24

The game opens in creative mode: fly (double-tap Space), press E for every block, left-click breaks, right-click
places. Anything you build by hand is kept, and written as code (fill / placeblock lines) in the sign's code page.
This terminal is a Python prompt like livecode.py, so you can also type code: blocks appear one at a time, and
:undo / :redo work on both. A tutorial world is a row of EXHIBITS, each with a SIGN in front that shows the code that
built it. To make one:

    tutorial> w.fill(X, 1, 9, X + 4, 3, 9, 'bricks')           build something (X is where the next exhibit starts)
    tutorial> :sign A wall | fill() fills a whole box.          put a sign in front, showing the code you just typed

Then describe the lesson and keep it:

    tutorial> :title Tutorial 6: Walls        :level 1        :summary Build walls with fill.
    tutorial> :step Walk along the exhibits.  :try Make the wall taller.
    tutorial> :guide Welcome! | Right-click the signs.
    tutorial> :save

It is saved in tutorials/ (see: python3 tutorialworld.py).  Type :help at the prompt for every command."""
import argparse
import atexit
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pcplot
from livecode import Session
from pycraft_extras import fill_code

FIRST_X = 6
GAP = 12

HELP = '''
This game is in CREATIVE mode: fly (double-tap Space), E = every block, left-click breaks, right-click places.
What you build by hand is kept too (and shown as code on the sign). Or build with Python at the prompt (w is your plot,
pc is pycraft, X is where the next exhibit starts). Then:

  :sign TITLE | WHY      put a sign in front of what you built (by hand or by code) since the last sign. Page 1
                         shows the title and the WHY; page 2 shows the code (hand-built blocks become fill / placeblock
                         lines). X moves along to the next exhibit spot.
  :title TEXT            the name of the tutorial          :level N     1 = beginner, 2 = builder, 3 = coder
  :summary TEXT          one line: what it teaches
  :step TEXT             add something to do in the world (:unstep removes the last one)
  :try TEXT              add a thing to try afterwards     (:untry removes the last one)
  :guide LINE | LINE     what the Guide character at the start says
  :status                what is set so far and the exhibits made
  :save                  keep it in the tutorials folder (you can keep saving as you go)

and the same commands as livecode.py:  :undo [n]  :redo [n]  :delay N  :clear  :history  :tp X Y Z  :fly  :walk
:blocks WORD  :export FILE.py  :run FILE.py  :quit.   In the game: U = undo, Y = redo (or the Esc menu).
'''


def bake(source, x):
    """Replace the helper variable X by its number, so the code on a sign can be run on its own."""
    return re.sub(r'\bX\b', str(x), source)


class TutorialSession(Session):
    prompt = 'tutorial> '

    def __init__(self, plot, name, folder, delay=4):
        self.name, self.folder = name, Path(folder)
        self.meta = {'title': name.replace('-', ' ').title(), 'level': 1, 'summary': '', 'steps': [], 'try_it': []}
        x, y, z = plot.dimensions
        setup = [f"w.fill(0, 0, 0, {x - 1}, 0, {z - 1}, 'grass')"]
        super().__init__(plot, delay, setup)
        self.guide_lines = ['Welcome!', 'Right-click the signs to see the code that built each exhibit.']
        self.guide = plot.npc('Guide', 4, 1, 2, list(self.guide_lines))
        self.guide_entry = plot._npcs[-1]
        plot.spawnpoint(5, 1, -3)
        self.commands.update({
            'sign': self.cmd_sign, 'title': self.cmd_title, 'level': self.cmd_level, 'summary': self.cmd_summary,
            'step': self.cmd_step, 'unstep': self.cmd_unstep, 'try': self.cmd_try, 'untry': self.cmd_untry,
            'guide': self.cmd_guide, 'status': self.cmd_status, 'save': self.cmd_save_tutorial, 'finish': self.cmd_save_tutorial})
        self.namespace['X'] = FIRST_X

    # ---- X moves along as signs are made -----------------------------------------------------------------------------

    def current_x(self):
        for entry in reversed(self.history):
            if entry.get('sign'):
                return entry['sign']['next_x']
        return FIRST_X

    def sync_manual(self, strict=False):
        """Pick up blocks the player built or broke by hand in the game, as steps in the history (and as code)."""
        if strict and not self.plot.wait_idle(120):
            print('(The build is still going. Wait for it to finish, then try again.)')
        self.plot.sync_from_game()
        for step in self.plot.take_manual():
            cells = {entry[0]: entry[3] for entry in step}
            facings = {entry[0]: entry[4] for entry in step if entry[4]}
            code = fill_code(cells, facings)
            self.history.append({'source': '\n'.join(code), 'changed': True, 'ok': True, 'positions': set(cells), 'manual': True})
            self.redo_groups.clear()
            print(f'(You built or broke {len(cells)} block(s) by hand: it is a step you can :undo.)')

    def feed(self, line):
        strict = line.strip().split(' ')[0] in (':sign', ':save', ':finish', ':status', ':export')
        self.sync_manual(strict)
        super().feed(line)
        self.namespace['X'] = self.current_x()

    # ---- the exhibits, worked out from what you typed -------------------------------------------------------------------

    def exhibits(self):
        """([exhibits made so far], [the entries typed since the last sign])."""
        made, group = [], []
        for entry in self.history:
            if entry.get('sign'):
                made.append(dict(entry['sign'], code=entry['sign']['code']))
                group = []
            elif entry['ok']:
                group.append(entry)
        return made, group

    def program(self, runplot=True):
        x, y, z = self.plot.dimensions
        lines = ['import pycraft as pc', 'import math, random', '', f'w = pc.plot({x}, {y}, {z})'] + self.setup_lines
        made, pending = self.exhibits()
        for exhibit in made:
            lines += [f"# {exhibit['title']}: {exhibit['why']}", exhibit['code']]
        if pending:
            lines += [bake(e['source'], self.current_x()) for e in pending]
        if runplot:
            lines += ['', 'pc.runplot(w, pc.adventure)']
        return '\n'.join(lines) + '\n'

    # ---- :sign ---------------------------------------------------------------------------------------------------------------

    def cmd_sign(self, rest):
        title, _, why = rest.partition('|')
        title, why = title.strip(), why.strip()
        if not title:
            raise ValueError('Give the sign a title: :sign A wall | fill() fills a whole box.')
        _made, pending = self.exhibits()
        built = [e for e in pending if e['changed']]
        if not built:
            raise ValueError('Build something first (by hand in the game, or type some code), then :sign.')
        x_now = self.current_x()
        code = '\n'.join(bake(e['source'], x_now) for e in pending)
        code_lines = code.split('\n')
        shown_code = code if len(code_lines) <= 14 else '\n'.join(code_lines[:14] + [f'# ... and {len(code_lines) - 14} more lines'])
        positions = [p for e in built for p in e['positions']]
        sx, sy, sz = self.plot.dimensions
        min_x, max_x = min(p[0] for p in positions), max(p[0] for p in positions)
        min_z, max_z = min(p[2] for p in positions), max(p[2] for p in positions)
        spot_x, spot_z = (min_x + max_x) // 2, min_z - 4
        if spot_z < 1:
            spot_z = min(sz - 1, max_z + 3)
        spot_x = max(0, min(sx - 1, spot_x))
        while (spot_x, 1, spot_z) in self.plot._blocks and spot_x < sx - 1:
            spot_x += 1
        sign = {'title': title, 'why': why, 'code': code, 'pos': (spot_x, 1, spot_z), 'next_x': max_x + GAP // 2 + 1}

        def make():
            self.plot.placeblock(spot_x, 0, spot_z, 'stone_bricks')
            self.plot.sign(spot_x, 1, spot_z, [f'{title}\n{why}' if why else title, shown_code], 'south')

        if self.run_function(f'# sign: {title}', make):
            self.history[-1]['sign'] = sign
            self.namespace['X'] = self.current_x()
            print(f"Sign made at {sign['pos']}. The next exhibit can start at X = {sign['next_x']}.")

    # ---- the lesson's words ------------------------------------------------------------------------------------------------

    def cmd_title(self, rest):
        if not rest:
            raise ValueError('Say the title: :title Tutorial 6: Walls')
        self.meta['title'] = rest[:120]

    def cmd_level(self, rest):
        if not rest.isdigit() or not 1 <= int(rest) <= 3:
            raise ValueError('The level is 1 (beginner), 2 (builder) or 3 (coder).')
        self.meta['level'] = int(rest)

    def cmd_summary(self, rest):
        self.meta['summary'] = rest[:600]

    def cmd_step(self, rest):
        if not rest:
            raise ValueError('Say what to do in the world: :step Walk along the exhibits.')
        self.meta['steps'].append(rest[:400])

    def cmd_unstep(self, rest):
        if self.meta['steps']:
            print(f"Removed: {self.meta['steps'].pop()}")

    def cmd_try(self, rest):
        if not rest:
            raise ValueError('Say what to try: :try Make the wall taller.')
        self.meta['try_it'].append(rest[:400])

    def cmd_untry(self, rest):
        if self.meta['try_it']:
            print(f"Removed: {self.meta['try_it'].pop()}")

    def cmd_guide(self, rest):
        lines = [t.strip() for t in rest.split('|') if t.strip()]
        if not lines:
            raise ValueError('Say what the Guide says: :guide Welcome! | Right-click the signs.')
        self.guide_entry['lines'][:] = lines                    # (the Guide reads this very list)
        self.guide_lines = lines

    def cmd_status(self, rest):
        m = self.meta
        made, pending = self.exhibits()
        print(f"\n  Title:   {m['title']}\n  Level:   {m['level']}\n  Summary: {m['summary'] or '(not set: :summary ...)'}")
        print(f"  Guide:   {' | '.join(self.guide_lines)}")
        for label, key in (('Steps', 'steps'), ('Try it', 'try_it')):
            print(f'  {label}:' + ('' if m[key] else ' (none)'))
            for item in m[key]:
                print(f'    - {item}')
        print(f'  Exhibits made: {len(made)}' + ''.join(f"\n    {i}. {e['title']}" for i, e in enumerate(made, start=1)))
        if any(e['changed'] for e in pending):
            print('  (You have built something since the last sign: :sign Title | why)')
        print(f'  Next exhibit starts at X = {self.current_x()}\n')

    # ---- keeping it ----------------------------------------------------------------------------------------------------------

    def tutorial_data(self):
        """The plot's data with the tutorial notes filled in."""
        self.plot.title = self.meta['title']
        self.plot.tutorial = {'level': self.meta['level'], 'summary': self.meta['summary'], 'steps': list(self.meta['steps']),
                              'try_it': list(self.meta['try_it']), 'code': self.program()}
        return self.plot._data()

    def save_to(self, folder, name):
        path = pcplot.write_plot(Path(folder) / f'{name}.pcplot', self.tutorial_data())
        return path

    def cmd_save_tutorial(self, rest):
        made, _pending = self.exhibits()
        if not made:
            print('Note: there are no exhibits yet (build something and :sign it). Saving anyway.')
        if not self.meta['summary']:
            print('Note: no summary yet (:summary what it teaches).')
        path = self.save_to(self.folder, self.name)
        print(f'Saved: {path}\nWalk around it any time with:  python3 tutorialworld.py play {self.name}')

    def cmd_help(self, rest):
        print(HELP)

    def cmd_save(self, rest):                                    # (overridden by the tutorial :save above)
        self.cmd_save_tutorial(rest)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='maketutorial.py', description='Make a tutorial world by coding it live.')
    parser.add_argument('name', help='a name for the tutorial, like my-lesson (letters, digits, - and _)')
    parser.add_argument('--size', nargs=3, type=int, default=[52, 14, 24], metavar=('X', 'Y', 'Z'))
    parser.add_argument('--delay', type=float, default=4, help='ticks between blocks (20 = one second)')
    parser.add_argument('--folder', help='where to save (default: the tutorials folder)')
    parser.add_argument('--no-autosave', action='store_true')
    parser.add_argument('--script', help=argparse.SUPPRESS)
    parser.add_argument('--screenshot', help=argparse.SUPPRESS)
    parser.add_argument('--seconds', type=float, default=6, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    import pycraft as pc
    import tutorialworld
    name = pcplot.slug(args.name, 'my-tutorial')
    folder = Path(args.folder) if args.folder else tutorialworld.FOLDER
    plot = pc.plot(*args.size)
    x, _y, z = plot.dimensions
    plot.fill(0, 0, 0, x - 1, 0, z - 1, 'grass')
    session = TutorialSession(plot, name, folder, args.delay)
    if not args.no_autosave:
        def keep():
            if session.history:
                try:
                    drafts = Path('drafts') / 'maketutorial'
                    session.save_to(drafts, name)
                    print(f"\n(Your work was kept in {drafts}/{name}.pcplot. Use :save next time to put it in {folder}.)")
                except OSError:
                    pass
        atexit.register(keep)

    def run():
        if args.script:
            import time
            for line in Path(args.script).read_text().split('\n'):
                time.sleep(0.15)
                session.feed(line)
        else:
            print(f'\nMaking the tutorial world "{name}" in CREATIVE mode.\n'
                  f'Build by hand in the game (double-tap Space to fly, E for blocks) or type code here; then :sign Title | why.\n'
                  f':help for everything. The Guide stands at the start; exhibits go in a row (X = where the next one starts).\n')
            session.repl(banner=False)

    options = {'mode': 'creative', 'allow_building': True,
               'message': 'Creative mode: build by hand, or type code in the terminal'}
    if args.screenshot:
        options.update(_screenshot=args.screenshot, _seconds=args.seconds)
    pc.live(plot, run, **options)


if __name__ == '__main__':
    main()
