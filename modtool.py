"""modtool - look at, check and install .pcmod files (mods you or your students made).

    python3 modtool.py info my.pcmod          what the mod adds (nothing in it is run)
    python3 modtool.py check my.pcmod         is it a good mod file? (also checks every block, item and creature loads)
    python3 modtool.py install my.pcmod       copy it into the game's mods/ folder, so PythonCraft loads it at start
    python3 modtool.py review                 list the mods students handed in (submissions/mods/<name>/)
    python3 modtool.py review --folder DIR    look somewhere else

A .pcmod holds data only (names, settings, pictures, patterns): opening one never runs code, so it is safe to open a
student's mod. (A mod written as a .py program is different: read it before you run it.)"""
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def info(path):
    import mods
    spec, files, sha = mods.read_pcmod(path)
    print(f"\n{spec.get('title') or spec['name']}   ({spec['name']}, {len(files)} files, id {sha})")
    if spec.get('description'):
        print(f"  {spec['description']}")
    for line in mods.describe(spec):
        print('  -', line)
    print()


def check(path):
    """Read the file, then really add it to the game's lists in a scratch folder to see that every step works."""
    import mods
    info(path)
    with tempfile.TemporaryDirectory() as cache:
        mods.load_pcmod(path, cache=cache)
    print('OK: this mod file is good.')


def install(path):
    import mods
    mods.read_pcmod(path)                                           # (refuse a bad file)
    target = HERE / 'mods' / Path(path).name
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        print(f'{target.name} is already in mods/: it was replaced.')
    shutil.copyfile(path, target)
    print(f'Installed: {target}. PythonCraft loads it the next time it starts.')


def review(folder=None):
    import mods
    root = Path(folder or os.environ.get('PYCRAFT_SUBMISSIONS') or 'submissions') / 'mods'
    if not root.is_dir():
        print(f'No mods handed in yet (looked in {root}).')
        return 1
    found = 0
    for student in sorted(p for p in root.iterdir() if p.is_dir()):
        for path in sorted(student.glob('*.pcmod')):
            found += 1
            try:
                spec, _files, _sha = mods.read_pcmod(path)
            except mods.ModFileError as error:
                print(f'\n{student.name} / {path.name}:  NOT A GOOD MOD FILE: {error}')
                continue
            print(f"\n{student.name} / {path.name}" + (f"   \"{spec['description']}\"" if spec.get('description') else ''))
            for line in mods.describe(spec):
                print('   -', line)
    if not found:
        print('No mods handed in yet.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='modtool.py', description='Look at, check and install .pcmod files.')
    parser.add_argument('command', choices=['info', 'check', 'install', 'review'])
    parser.add_argument('file', nargs='?', help='a .pcmod file')
    parser.add_argument('--folder', help='for review: the submissions folder')
    args = parser.parse_args(argv)
    import mods
    try:
        if args.command == 'review':
            return review(args.folder)
        if not args.file:
            parser.error(f'{args.command} needs a .pcmod file')
        {'info': info, 'check': check, 'install': install}[args.command](args.file)
    except mods.ModFileError as error:
        print(f'Problem: {error}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
