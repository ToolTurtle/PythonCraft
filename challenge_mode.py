"""Challenge mode: 12 levels that teach building with code, from one block to a castle.

    python3 challenge_mode.py              pick a level from a menu
    python3 challenge_mode.py 5            start level 5 directly
    python3 challenge_mode.py progress     show your stars
    python3 challenge_mode.py solution 5   (for teachers) one way to solve level 5
    python3 challenge_mode.py reset        forget all stars

Each level makes a small file in the folder my_levels/. Write your code in it, run it, and the game opens.
It tells you if the level is done and gives you stars (fewer 'not yet's = more stars)."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pycraft_extras as extras                    # (no game window needed for the menu)

LEVELS_DIR = Path(os.environ.get('PYCRAFT_LEVELS_DIR') or 'my_levels')
PROGRESS = Path(os.environ.get('PYCRAFTWORLD_PROGRESS') or 'pycraft_progress.json')

TEMPLATE = '''# Challenge mode - level {n}: {title}
#
# GOAL: {goal}
#
# Write your code in the space below, then run this file:   python3 {run_path}
# In the game:  C shows the goal again,  K checks your build.  (w.hint() prints a clue here.)
import os, sys
sys.path.insert(0, {root!r})
os.environ.setdefault('PYCRAFTWORLD_PROGRESS', {progress!r})      # (so your stars are kept in one place)
import pycraft as pc

w = pc.level({n})          # w is your plot: build with w.placeblock(...), w.fill(...) and so on

# ---- your code goes here (use w.) ---------------------------------------------------------------



# ---- ------------------------------------------------------------------------------------------------

w.check()                          # tells you what is missing, or gives you your stars
pc.runplot(w, pc.adventure)        # walk around your build (closing the window ends the program)
'''


def stars():
    import json
    try:
        return json.loads(PROGRESS.read_text())
    except (OSError, ValueError):
        return {}


def show_menu():
    saved = stars()
    print('\nCHALLENGE MODE\n')
    for number, level in enumerate(extras.LEVELS, start=1):
        got = saved.get(str(number), 0)
        print(f'  {number:2}.  [{"*" * got}{"-" * (3 - got)}]  {level[0]}')
    print()


def make_file(number):
    title, _size, goal = extras.LEVELS[number - 1][:3]
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    path = LEVELS_DIR / f'level_{number:02}.py'
    if not path.exists():
        path.write_text(TEMPLATE.format(n=number, title=title, goal=goal, root=str(HERE), run_path=path,
                                         progress=str(PROGRESS.resolve())))
    return path


def start(number):
    path = make_file(number)
    title, _size, goal = extras.LEVELS[number - 1][:3]
    print(f'\nLevel {number}: {title}\n  {goal}\n\nYour file: {path}\nOpen it, write your code where it says, save it.')
    answer = input('Run it now? (y = yes, Enter = later) ').strip().lower()
    if answer.startswith('y'):
        subprocess.run([sys.executable, str(path)])


def main(argv):
    if argv and argv[0] == 'progress':
        show_menu()
    elif argv and argv[0] == 'reset':
        PROGRESS.unlink(missing_ok=True)
        print('Stars cleared.')
    elif argv and argv[0] == 'solution':
        number = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 0
        if not 1 <= number <= len(extras.LEVELS):
            print('Usage: python3 challenge_mode.py solution <level 1-12>')
            return
        print(f'# Level {number}: {extras.LEVELS[number - 1][0]}\n{extras.LEVELS[number - 1][5]}')
    elif argv and argv[0].isdigit() and 1 <= int(argv[0]) <= len(extras.LEVELS):
        start(int(argv[0]))
    elif argv:
        print(__doc__)
    else:
        while True:
            show_menu()
            choice = input('Which level? (a number, or q to quit) ').strip().lower()
            if choice in ('q', 'quit', ''):
                return
            if choice.isdigit() and 1 <= int(choice) <= len(extras.LEVELS):
                start(int(choice))
            else:
                print('Type a number from 1 to', len(extras.LEVELS))


if __name__ == '__main__':
    main(sys.argv[1:])
