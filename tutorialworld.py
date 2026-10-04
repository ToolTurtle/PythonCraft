"""tutorialworld - walk around worlds that teach you pycraft.

    python3 tutorialworld.py                 a menu: pick a tutorial world and walk around it
    python3 tutorialworld.py list            the tutorial worlds
    python3 tutorialworld.py play 0-coordinates   open one (a name like 2-loops, or a number from the list)
    python3 tutorialworld.py info 2-loops         what it teaches and what to try
    python3 tutorialworld.py code 2-loops         the program that builds it (you can run it and change it)
    python3 tutorialworld.py export 2-loops       write that program to a file (2-loops.py)
    python3 tutorialworld.py save my.py      run your own program and keep its world as a tutorial
    python3 tutorialworld.py new my-lesson   a starter program for making a tutorial of your own

Tutorial worlds are .pcplot files in the folder `tutorials/`. In a tutorial world you walk around; every exhibit has a SIGN
in front of it (right-click it) that shows the code that built the exhibit, and a Guide character who says what to do.
Make your own: write a pycraft program, then `python3 tutorialworld.py save my.py`. (See docs/README_tutorials.md.)"""
import argparse
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pcplot

FOLDER = Path(os.environ.get('PYCRAFT_TUTORIALS') or HERE / 'tutorials')

STARTER = '''import sys, os
sys.path.insert(0, {root!r})
import pycraft as pc

# A tutorial of your own. Run it to look at it:    python3 {file}
# Keep it as a tutorial world:                     python3 tutorialworld.py save {file}

w = pc.plot(40, 14, 20)
w.title = {title!r}
w.fill(0, 0, 0, 39, 0, 19, 'grass')
w.npc('Guide', 4, 1, 2, ['Welcome!', 'Right-click the signs to see the code.'])
w.spawnpoint(5, 1, -3)

# An exhibit: build something, then put a sign in front of it showing the code.
w.fill(10, 1, 9, 14, 3, 9, 'bricks')
w.sign(12, 1, 5, ['A wall', "w.fill(10, 1, 9, 14, 3, 9, 'bricks')"])

w.tutorial = {{
    'level': 1,
    'summary': 'What this world teaches, in one line.',
    'steps': ['Walk to the first exhibit.', 'Right-click its sign.'],
    'try_it': ['Change the wall to a different block.'],
    'code': '',        # optional: the program that builds it (shown by "code" and "export")
}}

pc.runplot(w, pc.adventure)
'''


def slug(name):
    return pcplot.slug(name, 'tutorial')


def tutorials(folder=None):
    """The tutorial worlds: a list of dicts, in the order they should be taken."""
    folder = Path(folder or FOLDER)
    found = []
    for path in sorted(folder.glob('*.pcplot')) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        info = pcplot.clean_tutorial(data.get('tutorial')) or {'level': 1, 'summary': '', 'steps': [], 'try_it': [], 'code': ''}
        blocks = data.get('blocks')
        count = sum(len(v) // 3 for v in blocks.values()) if isinstance(blocks, dict) else 0
        found.append({'path': path, 'name': path.stem, 'title': data.get('title') or path.stem, 'blocks': count, **info})
    found.sort(key=lambda t: (t['name']))
    return found


def find(selection, folder=None):
    """A tutorial by its number in the list, its name (2-loops) or a part of its name."""
    items = tutorials(folder)
    if str(selection).isdigit() and 1 <= int(selection) <= len(items):
        return items[int(selection) - 1]
    exact = [t for t in items if t['name'] == str(selection)]
    partial = [t for t in items if str(selection).lower() in t['name'].lower() or str(selection).lower() in t['title'].lower()]
    chosen = exact or partial
    if len(chosen) == 1:
        return chosen[0]
    if not chosen:
        print(f'There is no tutorial {selection!r}. Try: python3 tutorialworld.py list')
    else:
        print(f"{selection!r} matches more than one: {', '.join(t['name'] for t in chosen)}")
    return None


def table(items):
    if not items:
        print(f'No tutorial worlds in {FOLDER}. (Make them with: python3 examples/make_tutorials.py)')
        return
    print(f"\n  #  {'level':5} {'world':22} what it teaches")
    for number, t in enumerate(items, start=1):
        print(f"  {number:>1}  {t['level']:^5} {t['name'][:22]:22} {t['summary']}")
    print()


def info(t):
    print(f"\n{t['title']}   (level {t['level']}, {t['blocks']} blocks)")
    if t['summary']:
        print(f"  {t['summary']}")
    if t['steps']:
        print('\n  In the world:')
        for step in t['steps']:
            print(f'    - {step}')
    if t['try_it']:
        print('\n  Try it:')
        for task in t['try_it']:
            print(f'    - {task}')
    if t['code']:
        print(f"\n  The program that builds it:  python3 tutorialworld.py code {t['name']}   (or export)")
    print()


def run_world(path, screenshot=None, seconds=6):
    """Open a tutorial world in this program (the game window ends the program when you close it)."""
    import pycraft
    world = pycraft.load(path)
    title = world.title or Path(path).stem
    options = {'peaceful': True, 'message': f'{title}: right-click the signs to see the code'}
    if screenshot:
        options.update(_screenshot=screenshot, _seconds=seconds)
    pycraft.runplot(world, pycraft.adventure, **options)


def play(t):
    """Open a tutorial world in the game. It runs in its own process, so a menu is still here when you close it."""
    info(t)
    subprocess.run([sys.executable, str(Path(__file__).resolve()), '_run', str(t['path'])], cwd=str(HERE))


def program_of(t):
    if not t['code']:
        print(f"{t['name']} has no program stored in it. (The author can add one in w.tutorial['code'].)")
        return None
    return t['code']


def save_program(script, name=None, folder=None):
    """Run a pycraft program (yours) without opening the game, and keep the world it was going to show as a tutorial."""
    script = Path(script)
    if not script.is_file():
        print(f'There is no file {str(script)!r}.')
        return None
    import pycraft

    class Captured(Exception):
        pass

    caught = {}

    def capture(plot, *args, **kwargs):
        caught['plot'] = plot
        raise Captured

    real = pycraft.runplot, pycraft.live
    pycraft.runplot = capture
    pycraft.live = lambda plot, script_function, **kwargs: capture(plot)
    sys.path.insert(0, str(script.resolve().parent))
    print(f'Running {script} (this runs your program, without opening the game)...')
    try:
        runpy.run_path(str(script), run_name='__main__')
    except Captured:
        pass
    finally:
        pycraft.runplot, pycraft.live = real
    plot = caught.get('plot')
    if plot is None:
        print('Your program never reached pc.runplot(w, ...), so there is no world to keep. Put it as the last line.')
        return None
    name = slug(name or script.stem)
    plot.title = plot.title or name.replace('-', ' ').title()
    if plot.tutorial is None:
        plot.tutorial = {'level': 1, 'summary': '', 'steps': [], 'try_it': [], 'code': script.read_text()[:30000]}
    elif not plot.tutorial.get('code'):
        plot.tutorial['code'] = script.read_text()[:30000]
    destination = Path(folder or FOLDER)
    path = pcplot.write_plot(destination / f'{name}.pcplot', plot._data())
    print(f'Saved as a tutorial world: {path}\nWalk around it with: python3 tutorialworld.py play {name}')
    return path


def menu():
    while True:
        items = tutorials()
        print('\nTUTORIAL WORLDS')
        table(items)
        if not items:
            return
        choice = input('Which one? (a number, i + number for info, q to quit) ').strip().lower()
        if choice in ('q', 'quit', ''):
            return
        wants_info = choice.startswith('i')
        number = choice[1:].strip() if wants_info else choice
        t = find(number)
        if t is None:
            continue
        if wants_info:
            info(t)
        else:
            play(t)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='tutorialworld.py', description='Walk around worlds that teach pycraft.')
    parser.add_argument('command', nargs='?', default='menu',
                        choices=['menu', 'list', 'play', 'info', 'code', 'export', 'save', 'new', '_run'])
    parser.add_argument('target', nargs='?', help='a tutorial (number or name), or a program file for "save", or a name for "new"')
    parser.add_argument('name', nargs='?', help='for "save": the name to keep it under; for "export": the file to write')
    parser.add_argument('--folder', help='the tutorials folder (default: tutorials/)')
    parser.add_argument('--screenshot', help=argparse.SUPPRESS)
    parser.add_argument('--seconds', type=float, default=6, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    global FOLDER
    if args.folder:
        FOLDER = Path(args.folder)

    if args.command == 'menu':
        return menu()
    if args.command == 'list':
        return table(tutorials())
    if args.command == '_run':
        return run_world(args.target, args.screenshot, args.seconds)
    if args.command == 'new':
        if not args.target:
            parser.error('new needs a name, like: tutorialworld.py new my-lesson')
        name = slug(args.target)
        path = Path(f'{name}.py')
        if path.exists():
            print(f'{path} already exists.')
            return 1
        path.write_text(STARTER.format(root=str(HERE), file=str(path), title=name.replace('-', ' ').title()))
        print(f'Wrote {path}. Run it with: python3 {path}   Keep it with: python3 tutorialworld.py save {path}')
        return 0
    if args.command == 'save':
        if not args.target:
            parser.error('save needs your program file')
        return 0 if save_program(args.target, args.name, FOLDER) else 1
    if not args.target:
        parser.error(f'{args.command} needs a tutorial (a number or a name)')
    t = find(args.target)
    if t is None:
        return 1
    if args.command == 'info':
        info(t)
    elif args.command == 'play':
        play(t)
    elif args.command in ('code', 'export'):
        code = program_of(t)
        if code is None:
            return 1
        if args.command == 'code':
            print(code)
        else:
            target = Path(args.name or f"{t['name']}.py")
            if target.exists():
                print(f'{target} already exists: choose another name.')
                return 1
            body = code.replace('import pycraft as pc\n', f'import sys\nsys.path.insert(0, {str(HERE)!r})\nimport pycraft as pc\n', 1)
            target.write_text(body)
            print(f'Wrote {target}. Run it with: python3 {target}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
