"""review - the teacher's tool for looking at what students handed in.

    python3 review.py                      a menu: pick a hand-in, open it in the game, read the code, give a score
    python3 review.py list                 a table of every hand-in
    python3 review.py show Sam             one student's checks, note and code
    python3 review.py open Sam             open Sam's build in the game (you fly around it)
    python3 review.py grade Sam 8 "Nice bridge!"       give a score and a comment
    python3 review.py export               write grades.csv (for a spreadsheet)
    python3 review.py view some.pcplot     open any .pcplot file in the game

Where hand-ins are: the folder `submissions` (or --folder, or the PYCRAFT_SUBMISSIONS setting). Add --challenge bridge to
look at one challenge only. Students read your comment with w.feedback().

A hand-in is only data. The program a student handed in is shown as text here and is never run."""
import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pcplot                                         # (no game window needed for anything except opening a build)


def status_of(sub):
    review = sub['review']
    if review is None:
        return 'new'
    return 'reviewed' if int(review.get('attempt', 1)) >= int(sub['attempt']) else 'resubmitted'


def folder_of(args):
    return pcplot.submissions_folder(args.folder)


def pick(subs, name, challenge=None):
    """The hand-in for a student's name (and challenge, if there are several)."""
    wanted = pcplot.slug(name).lower()
    matches = [s for s in subs if pcplot.slug(s['student']).lower() == wanted and (challenge is None or s['challenge'] == challenge)]
    if not matches:
        print(f'No hand-in from {name!r}' + (f' for {challenge}' if challenge else '') + '. Try: python3 review.py list')
        return None
    if len(matches) > 1:
        print(f"{name} has handed in {len(matches)} challenges ({', '.join(m['challenge'] for m in matches)}): add --challenge.")
        return None
    return matches[0]


def table(subs):
    if not subs:
        print('No hand-ins yet.')
        return
    print(f"\n {'#':>2}  {'challenge':14} {'student':16} {'try':>3} {'auto':>7} {'blocks':>6}  {'status':11} handed in")
    for number, s in enumerate(subs, start=1):
        auto = f"{s['score']}/{s['out_of']}" if s['score'] is not None else '-'
        final = f"  teacher: {s['review']['score']}/{s['review']['out_of']}" if s['review'] and s['review'].get('score') is not None else ''
        print(f" {number:>2}  {s['challenge'][:14]:14} {s['student'][:16]:16} {s['attempt']:>3} {auto:>7} {s['blocks']:>6}  "
              f"{status_of(s):11} {s['submitted'].replace('T', ' ')}{final}")
    print()


def show(sub, full_code=False):
    print(f"\n{sub['student']} - {sub['challenge']} (attempt {sub['attempt']}, handed in {sub['submitted'].replace('T', ' ')})")
    print(f"  {sub['blocks']} blocks" + (f", level {sub['level']}" if sub['level'] else '') + f"   file: {sub['path']}")
    if sub['note']:
        print(f"  Note from the student: {sub['note']}")
    if sub['results']:
        print('  Automatic checks:')
        for r in sub['results']:
            print(f"    {'[x]' if r['ok'] else '[ ]'} {r['label']}" + (f"  ({r['detail']})" if r.get('detail') and not r['ok'] else ''))
        if sub['score'] is not None:
            print(f"    Score: {sub['score']} / {sub['out_of']}")
    review = sub['review']
    if review:
        print(f"  Your review (attempt {review.get('attempt')}): {review.get('score')} / {review.get('out_of')}  {review.get('comment', '')}")
    code = sub['code']
    if code and code.get('text'):
        lines = code['text'].split('\n')
        shown = lines if full_code else lines[:25]
        print(f"\n  Program ({code.get('file', '?')}, {len(lines)} lines; shown as text only, never run):")
        for number, line in enumerate(shown, start=1):
            print(f'    {number:3} | {line}')
        if not full_code and len(lines) > 25:
            print(f'        ... {len(lines) - 25} more lines: python3 review.py code {sub["student"]}')
    print()


def open_in_game(path, student='', challenge='', attempt=''):
    """Open a build in the game. It runs in its own process, so this menu is still here when you close the window."""
    message = f'{student} - {challenge} (attempt {attempt})' if student else ''
    code = ('import sys; sys.path.insert(0, %r); import pycraft; pycraft.view(%r, message=%r)' % (str(HERE), str(path), message))
    subprocess.run([sys.executable, '-c', code], cwd=str(HERE))


def grade(sub, score, comment, out_of=None, reviewer=''):
    out_of = out_of if out_of is not None else (sub['out_of'] or 10)
    pcplot.write_review(sub['path'], score, out_of, comment, reviewer, sub['attempt'])
    print(f"Saved: {sub['student']} {score} / {out_of}. They can read it with w.feedback().")


def export(subs, destination):
    with open(destination, 'w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['challenge', 'student', 'attempt', 'auto_score', 'auto_out_of', 'teacher_score', 'teacher_out_of',
                         'comment', 'status', 'handed_in'])
        for s in subs:
            r = s['review'] or {}
            writer.writerow([s['challenge'], s['student'], s['attempt'], s['score'], s['out_of'], r.get('score'), r.get('out_of'),
                             r.get('comment', ''), status_of(s), s['submitted']])
    print(f'Wrote {destination} ({len(subs)} rows).')


def ask_number(text, default=None):
    answer = input(text).strip()
    if not answer:
        return default
    try:
        return float(answer) if '.' in answer else int(answer)
    except ValueError:
        print('That is not a number.')
        return default


def menu(args):
    reviewer = os.environ.get('PYCRAFT_REVIEWER', '')
    while True:
        subs = pcplot.list_submissions(folder_of(args), args.challenge)
        print(f'\nHAND-INS in {folder_of(args)}')
        table(subs)
        if not subs:
            return
        choice = input('Pick a number to look at it (e = export grades, q = quit): ').strip().lower()
        if choice in ('q', 'quit', ''):
            return
        if choice == 'e':
            export(subs, 'grades.csv')
            continue
        if not (choice.isdigit() and 1 <= int(choice) <= len(subs)):
            print(f'Type a number from 1 to {len(subs)}.')
            continue
        sub = subs[int(choice) - 1]
        show(sub)
        while True:
            action = input('[o] open in game   [c] all the code   [g] give a score   [b] back > ').strip().lower()
            if action == 'o':
                open_in_game(sub['path'], sub['student'], sub['challenge'], sub['attempt'])
            elif action == 'c':
                show(sub, full_code=True)
            elif action == 'g':
                score = ask_number(f"Score (out of {sub['out_of'] or 10}, Enter to skip): ")
                if score is None:
                    continue
                comment = input('Comment for the student: ').strip()
                if not reviewer:
                    reviewer = input('Your name (shown to the student): ').strip()
                grade(sub, score, comment, None, reviewer)
                sub = next((s for s in pcplot.list_submissions(folder_of(args), args.challenge) if s['path'] == sub['path']), sub)
            else:
                break


def main(argv=None):
    parser = argparse.ArgumentParser(prog='review.py', description='Look at what students handed in, and give feedback.')
    parser.add_argument('command', nargs='?', default='menu', choices=['menu', 'list', 'show', 'code', 'open', 'grade', 'export', 'view'])
    parser.add_argument('target', nargs='?', help='a student name (or a .pcplot file for "view")')
    parser.add_argument('score', nargs='?', help='for "grade": the score')
    parser.add_argument('comment', nargs='?', default='', help='for "grade": your comment')
    parser.add_argument('--folder', help='the hand-in folder (default: submissions)')
    parser.add_argument('--challenge', help='only this challenge')
    parser.add_argument('--out-of', type=float, help='for "grade": the top score (default: the challenge points)')
    parser.add_argument('--reviewer', default=os.environ.get('PYCRAFT_REVIEWER', ''), help='your name, shown to the student')
    args = parser.parse_args(argv)

    if args.command == 'menu':
        return menu(args)
    if args.command == 'view':
        if not args.target:
            parser.error('view needs a .pcplot file')
        return open_in_game(args.target)
    subs = pcplot.list_submissions(folder_of(args), args.challenge)
    if args.command == 'list':
        return table(subs)
    if args.command == 'export':
        return export(subs, 'grades.csv')
    if not args.target:
        parser.error(f'{args.command} needs a student name')
    sub = pick(subs, args.target, args.challenge)
    if sub is None:
        return 1
    if args.command == 'show':
        show(sub)
    elif args.command == 'code':
        show(sub, full_code=True)
    elif args.command == 'open':
        open_in_game(sub['path'], sub['student'], sub['challenge'], sub['attempt'])
    elif args.command == 'grade':
        try:
            score = float(args.score) if args.score and '.' in args.score else int(args.score)
        except (TypeError, ValueError):
            parser.error('grade needs a score, like: review.py grade Sam 8 "Nice!"')
        out_of = int(args.out_of) if args.out_of and float(args.out_of).is_integer() else args.out_of
        grade(sub, score, args.comment, out_of, args.reviewer)
    return 0


if __name__ == '__main__':
    sys.exit(main())
