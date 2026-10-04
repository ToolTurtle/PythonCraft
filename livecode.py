"""livecode - code a world live: type Python and watch it appear in the game.

    python3 livecode.py                  a 32 x 16 x 32 plot with grass, and a prompt
    python3 livecode.py --delay 10       slower building (ticks between blocks; 20 ticks = 1 second)
    python3 livecode.py --size 48 20 48  a bigger plot
    python3 livecode.py --load my.pcplot start from a saved world

The game window opens, and this terminal becomes a Python prompt:

    pc> w.fill(5, 1, 5, 9, 3, 9, 'bricks')
    pc> for i in range(8):
    ...     w.placeblock(i, 1 + i, 3, 'cobblestone')
    ...

Press / in the game to type here instead of in the terminal (Enter runs a line, Esc closes it).
Blocks are placed one after another, 4 ticks (a fifth of a second) apart, so you can watch. Everything you type is a
step you can take back with  :undo  (and bring back with  :redo).  Type  :help  for the list of commands.
In the game: press U to undo and Y to redo, or use the Undo / Redo buttons at the top of the Esc menu.

`w` is your plot (the same as in a pycraft program), `pc` is pycraft. The game closes when you close its window."""
import argparse
import atexit
import code
import math
import os
import random
import re
import shlex
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

HELP = '''
Type Python at the pc> prompt (w is your plot, pc is pycraft). Commands start with a colon:

  :undo [n]        take back the last step(s)          (in the game: press U, or Esc menu > Undo)
  :redo [n]        put back what you undid             (in the game: press Y, or Esc menu > Redo)
  :delay N         ticks between blocks (4 = a fifth of a second, 20 = one second, 0 = instant)
  :clear           remove everything you built (it can be undone)
  :save NAME       keep the world as NAME.pcplot       :load NAME   open a saved world (undoable)
  :export FILE.py  write everything you typed as a program you can run
  :run FILE.py     run a file of code here (undoable as one step)
  :history         what you have typed so far
  :tp X Y Z        move yourself to a place in the plot
  unstuck          move to the nearest free spot if you are stuck inside blocks (also: the Unstuck button in the Esc menu)
  :fly / :walk     fly around (spectator) / walk again
  :blocks WORD     find block names that contain WORD
  paint FILE.png   open the picture painter (--like BLOCK or --skin CREATURE to start from a copy)
  :help            this list          :quit   close the game
'''


class Session:
    """The interpreter behind livecode.py: runs what you type, records each step, and handles :commands."""

    prompt, more_prompt = 'pc> ', '... '

    def __init__(self, plot, delay=4, setup_lines=()):
        import pycraft
        self.pycraft = pycraft
        self.plot = plot
        self.namespace = {'pc': pycraft, 'w': plot, 'math': math, 'random': random, '__name__': '__livecode__'}
        self.interpreter = code.InteractiveInterpreter(self.namespace)
        self.interpreter.showtraceback = self._show_error
        self.interpreter.showsyntaxerror = self._show_syntax_error
        self.history = []              # [{'source', 'changed', 'ok', 'positions'}], oldest first
        self.redo_groups = []          # groups of history entries that undo took away
        self.setup_lines = list(setup_lines)
        self._failed = False
        self.commands = {'undo': self.cmd_undo, 'redo': self.cmd_redo, 'delay': self.cmd_delay, 'clear': self.cmd_clear,
                         'save': self.cmd_save, 'load': self.cmd_load, 'export': self.cmd_export, 'run': self.cmd_run,
                         'history': self.cmd_history, 'tp': self.cmd_tp, 'fly': self.cmd_fly, 'walk': self.cmd_walk,
                         'blocks': self.cmd_blocks, 'paint': self.cmd_paint, 'unstuck': self.cmd_unstuck, 'help': self.cmd_help, 'quit': self.cmd_quit, 'exit': self.cmd_quit}
        for name in dir(plot):                                   # fill(...) works as well as w.fill(...)
            if not name.startswith('_') and name not in self.namespace and callable(getattr(plot, name)):
                self.namespace[name] = getattr(plot, name)
        from autocomplete import Completer
        self.completer = Completer(self)
        plot.delay(delay)
        plot.onkey('u', self.undo)
        plot.onkey('y', self.redo)
        plot.add_menu_button('Undo', self.undo)
        plot.add_menu_button('Redo', self.redo)
        plot._console = (self.feed, lambda: self.more_prompt if self.__dict__.get('_buffer') else self.prompt,
                         self.completer, lambda: self.completer.indent_for(self.__dict__.get('_buffer')), self.needs_more)   # press / in the game

    # ---- errors in a friendly, short form ----------------------------------------------------------------------

    def _show_error(self, *args, **kwargs):
        self._failed = True
        kind, value = sys.exc_info()[:2]
        print(f'{kind.__name__}: {value}')

    def _show_syntax_error(self, *args, **kwargs):
        self._failed = True
        kind, value = sys.exc_info()[:2]
        line = getattr(value, 'text', '') or ''
        print(f"SyntaxError: {getattr(value, 'msg', value)}" + (f'   in: {line.strip()}' if line else ''))

    # ---- running what you type ------------------------------------------------------------------------------------

    def execute(self, source):
        """Run Python. Returns True if more lines are needed (a block that is not finished yet)."""
        self._failed = False
        self.plot._begin_step()
        try:
            more = self.interpreter.runsource(source)
        finally:
            step = self.plot._end_step()
        if more:
            return True
        positions = set()
        for entry in step:
            if entry[0] == 'sign':
                positions.add(entry[1])
            elif isinstance(entry[0], tuple):
                positions.add(entry[0])
        self.history.append({'source': source.rstrip(), 'changed': bool(step), 'ok': not self._failed, 'positions': positions})
        if step:
            self.redo_groups.clear()                                  # (only something that builds replaces what you undid)
        return False

    def run_function(self, label, function):
        """Run a Python function as one undoable step (used by :load, :clear and the tutorial maker)."""
        self._failed = False
        self.plot._begin_step()
        try:
            function()
        except Exception as error:
            self._failed = True
            print(f'{type(error).__name__}: {error}')
        finally:
            step = self.plot._end_step()
        positions = {entry[0] for entry in step if isinstance(entry[0], tuple)}
        self.history.append({'source': label, 'changed': bool(step), 'ok': not self._failed, 'positions': positions})
        if step:
            self.redo_groups.clear()
        return not self._failed

    # ---- undo / redo ------------------------------------------------------------------------------------------------

    def undo(self, count=1):
        undone = 0
        for _ in range(count):
            trailing = []
            while self.history and not self.history[-1]['changed']:
                trailing.append(self.history.pop())            # lines that built nothing (like x = 5) go with it
            if not self.history or not self.plot.undo():
                self.history.extend(reversed(trailing))
                break
            group = [self.history.pop()] + trailing
            self.redo_groups.append(list(reversed(group)))
            undone += 1
        return undone

    def redo(self, count=1):
        redone = 0
        for _ in range(count):
            if not self.redo_groups or not self.plot.redo():
                break
            self.history.extend(self.redo_groups.pop())
            redone += 1
        return redone

    # ---- the program you have typed ------------------------------------------------------------------------------------

    def program(self, runplot=True):
        """Everything you typed (that worked, and was not undone) as a pycraft program."""
        x, y, z = self.plot.dimensions
        lines = ['import pycraft as pc', 'import math, random', '', f'w = pc.plot({x}, {y}, {z})'] + self.setup_lines + ['']
        lines += [entry['source'] for entry in self.history if entry['ok']]
        if runplot:
            lines += ['', 'pc.runplot(w, pc.adventure)']
        return '\n'.join(lines) + '\n'

    # ---- :commands -----------------------------------------------------------------------------------------------------

    def command(self, line):
        word, _, rest = line.lstrip(':').strip().partition(' ')
        function = self.commands.get(word.lower())
        if function is None:
            names = ', '.join(':' + n for n in sorted(self.commands))
            print(f'I do not know :{word}. These work: {names}')
            return
        try:
            function(rest.strip())
        except (ValueError, TypeError, OSError) as error:
            print(f'{type(error).__name__}: {error}')

    def cmd_help(self, rest):
        print(HELP)

    def cmd_quit(self, rest):
        print('Closing the game...')
        from ursina import application
        self.plot._later(application.quit)

    def cmd_undo(self, rest):
        count = int(rest) if rest.isdigit() else 1
        done = self.undo(count)
        print(f'Undone {done} step(s).' if done else 'Nothing to undo.')

    def cmd_redo(self, rest):
        count = int(rest) if rest.isdigit() else 1
        done = self.redo(count)
        print(f'Redone {done} step(s).' if done else 'Nothing to redo.')

    def cmd_delay(self, rest):
        if not rest:
            print(f'The delay is {round(self.plot._build_delay * 20)} ticks between blocks.')
            return
        ticks = float(rest)
        self.plot.delay(ticks)
        print(f'Blocks now appear {ticks:g} ticks apart' + (' (instantly).' if ticks == 0 else '.'))

    def cmd_clear(self, rest):
        self.run_function('w.clear()', self.plot.clear)

    def cmd_save(self, rest):
        name = rest or 'livecode-world'
        print(f'Saved: {self.plot.save(name)}')

    def cmd_load(self, rest):
        if not rest:
            raise ValueError('Say which one: :load NAME')
        self.run_function(f'w.load({rest!r})', lambda: self.plot.load(rest))

    def cmd_export(self, rest):
        target = Path(rest or 'livecode-program.py')
        if target.suffix != '.py':
            target = target.with_suffix('.py')
        header = f'import sys\nsys.path.insert(0, {str(HERE)!r})\n'
        target.write_text(header + self.program())
        print(f'Wrote {target}. Run it with: python3 {target}')

    def cmd_run(self, rest):
        path = Path(rest)
        if not path.is_file():
            raise ValueError(f'There is no file {rest!r}.')
        text = path.read_text()
        self.run_function(text.rstrip(), lambda: exec(compile(text, str(path), 'exec'), self.namespace))

    def cmd_history(self, rest):
        if not self.history:
            print('Nothing typed yet.')
        for number, entry in enumerate(self.history, start=1):
            first, *more = entry['source'].split('\n')
            print(f"{number:3} {'' if entry['ok'] else '(failed) '}{first}" + (f'   ... +{len(more)} lines' if more else ''))

    def cmd_tp(self, rest):
        x, y, z = (float(v) for v in rest.split())
        self.plot.teleport(x, y, z)

    def cmd_fly(self, rest):
        self._set_mode('spectator')

    def cmd_walk(self, rest):
        self._set_mode('survival')

    def _set_mode(self, mode):
        game = self.plot._game
        if game is not None:
            self.plot._later(lambda: game.player.set_mode(mode))
        print('You are flying (it goes through everything). :walk to come back.' if mode == 'spectator' else 'Walking again.')

    def cmd_paint(self, rest):
        words = rest.split()
        if not words:
            raise ValueError('Say which picture: paint snad.png   (or: paint snad.png --like sand   /   paint golem.png --skin golem)')
        options = {'like': None, 'skin': None}
        for flag in ('like', 'skin'):
            if f'--{flag}' in words:
                at = words.index(f'--{flag}')
                options[flag] = words[at + 1] if at + 1 < len(words) else None
                del words[at:at + 2]
        print(f'Opening the painter on {self.pycraft.paint(words[0], **options)} (save with Ctrl+S, then use it in your mod).')

    def cmd_unstuck(self, rest):
        game = self.plot._game
        if game is None:
            print('The game is not open.')
            return
        self.plot._later(game.unstuck)

    def cmd_blocks(self, rest):
        names = [n for n in self.pycraft.BLOCKS if rest.lower() in n]
        print(', '.join(names) if names else f'No block has {rest!r} in its name.')

    # ---- the prompt ------------------------------------------------------------------------------------------------------

    def _setup_readline(self):
        """Arrow keys, history, Tab completion and auto-indent in the terminal (where readline exists)."""
        try:
            import readline
        except ImportError:
            return
        readline.parse_and_bind('bind ^I rl_complete' if 'libedit' in (readline.__doc__ or '') else 'tab: complete')
        readline.set_completer_delims(' \t\n')
        cache = {}

        def completer(text, state):
            if state == 0:
                line = readline.get_line_buffer()[:readline.get_endidx()]
                begin = readline.get_begidx()
                start, candidates = self.completer.completions(line, force=True)
                cache['matches'] = [line[begin:start] + c for c in candidates] if start >= begin else []
            matches = cache.get('matches', [])
            return matches[state] if state < len(matches) else None

        readline.set_completer(completer)

        def indent():
            buffer = self.__dict__.get('_buffer')
            if buffer:
                readline.insert_text(self.completer.indent_for(buffer))
                readline.redisplay()

        try:
            readline.set_pre_input_hook(indent)
        except (AttributeError, OSError):
            pass

    def repl(self, banner=True):
        self._setup_readline()
        if banner:
            print('\nLive coding. w is your plot. Try:  w.fill(5, 1, 5, 9, 3, 9, "bricks")      :help for more\n')
        self._buffer = []
        while True:
            try:
                line = input(self.more_prompt if self._buffer else self.prompt)
            except EOFError:
                print()
                return
            except KeyboardInterrupt:
                print('\n(cancelled)')
                self._buffer = []
                continue
            self.feed(line)

    def translate(self, line):
        """`placeblock 0 0 0 stone` -> `w.placeblock(0, 0, 0, 'stone')`: a plain command without brackets or quotes.
        Returns None if the line is not written that way (so it is treated as Python)."""
        text = line.strip()
        if not text or any(c in text for c in '([{='):
            return None                                           # (brackets or = mean it is Python already)
        try:
            words = shlex.split(text)                              # "hi there" stays one word
        except ValueError:
            return None
        name = words[0]
        if name.startswith('_') or not callable(getattr(self.plot, name, None)) or self.namespace.get(name, getattr(self.plot, name)) != getattr(self.plot, name):
            return None
        arguments = []
        params = self.completer._params(name)
        for position, word in enumerate(words[1:]):
            param = params[position] if position < len(params) else None
            numeric = param is not None and (re.fullmatch(r'[xyzc]\d?|c[xyz]|radius|width|depth|height|count|how_many|size|cols|rows|houses|'
                                                          r'spacing|seconds|volume|ticks|degrees|number|scale|probability|low|high', param.name)
                                              or isinstance(param.default, (int, float)) and not isinstance(param.default, bool))
            if numeric and word.isidentifier() and word not in ('True', 'False', 'None'):
                arguments.append(word)                               # (a number in a variable: i)
                continue
            if (word in ('True', 'False', 'None') or re.fullmatch(r'(pc|w|math|random)\.[\w.]+', word)
                    or (word.isidentifier() and word in self.namespace and not callable(self.namespace[word]))     # a variable: i
                    or re.fullmatch(r'[A-Za-z_]\w*[+\-*/%][\w.+\-*/%]*|\d[\w.]*[+\-*/%][\w.+\-*/%]*', word)):   # a sum: i+1
                arguments.append(word)                               # (already Python)
                continue
            try:
                arguments.append(repr(int(word)))
                continue
            except ValueError:
                pass
            try:
                arguments.append(repr(float(word)))
                continue
            except ValueError:
                pass
            arguments.append(repr(word))
        return f"w.{name}({', '.join(arguments)})"

    def needs_more(self, text):
        """Should Enter add another line (True) or run what is typed (False)? A block (a line ending in :) goes on until a blank
        line; brackets and quotes that are not closed yet go on too; anything else runs."""
        import codeop
        lines = text.split('\n')
        if len(lines) > 1 and not lines[-1].strip():
            return False
        stripped = [line.strip() for line in lines if line.strip()]
        if not stripped or stripped[0].startswith(':'):
            return False
        if any(line.endswith(':') and not line.startswith('#') for line in stripped):
            return True
        plain = [line[:len(line) - len(line.lstrip())] + (self.translate(line) or line.strip()) for line in lines]
        try:
            return codeop.compile_command('\n'.join(plain) + '\n') is None
        except (SyntaxError, ValueError, OverflowError):
            return False                                           # (a mistake: run it, so the message appears)

    def feed(self, line):
        """One line typed at the prompt: a :command, Python, or part of a block that is not finished yet."""
        buffer = self.__dict__.setdefault('_buffer', [])
        if not buffer:
            word = line.strip().split(' ')[0] if line.strip() else ''
            if word in self.commands and not line.strip()[len(word):].lstrip()[:1] in ('=', '(', '.'):
                self.command(':' + line.strip())                      # `undo`, `tp 5 1 5`: the colon is optional
                return
        translated = self.translate(line)
        if translated:
            print('  ->', translated)
            line = line[:len(line) - len(line.lstrip())] + translated
        if not buffer and line.strip().startswith(':'):
            self.command(line.strip())
            return
        if not buffer and not line.strip():
            return
        line = self.completer.fix_indent(buffer, line)           # auto-indent inside a block
        buffer.append(line)
        if not self.execute('\n'.join(buffer)):
            buffer.clear()
        elif not line.strip():                                  # a blank line ends an unfinished block
            buffer.clear()


def autosave(session, folder):
    """Keep what you did if the window is closed without saving."""
    if not session.history:
        return
    try:
        folder.mkdir(parents=True, exist_ok=True)
        session.plot.save(str(folder / 'last'))
        (folder / 'last.py').write_text(f'import sys\nsys.path.insert(0, {str(HERE)!r})\n' + session.program())
        print(f'\n(Your work was kept in {folder}/last.pcplot and last.py)')
    except OSError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog='livecode.py', description='Code a world live: type Python and watch it appear.')
    parser.add_argument('--size', nargs=3, type=int, default=[32, 16, 32], metavar=('X', 'Y', 'Z'), help='the plot size')
    parser.add_argument('--delay', type=float, default=4, help='ticks between blocks (default 4; 20 = one second)')
    parser.add_argument('--load', help='start from a .pcplot file')
    parser.add_argument('--no-floor', action='store_true', help='start with an empty plot instead of grass')
    parser.add_argument('--no-autosave', action='store_true')
    parser.add_argument('--nether', action='store_true', help='build in the Nether')
    parser.add_argument('--script', help=argparse.SUPPRESS)          # lines to run at the start (for testing)
    parser.add_argument('--screenshot', help=argparse.SUPPRESS)
    parser.add_argument('--seconds', type=float, default=6, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    import pycraft as pc
    plot = pc.load(args.load) if args.load else pc.plot(*args.size)
    setup = []
    if not args.load and not args.no_floor:
        x, _y, z = plot.dimensions
        plot.fill(0, 0, 0, x - 1, 0, z - 1, 'netherrack' if args.nether else 'grass')
        setup.append(f"w.fill(0, 0, 0, {x - 1}, 0, {z - 1}, {'netherrack' if args.nether else 'grass'!r})")
    if not args.load:
        plot.spawnpoint(plot.dimensions[0] / 2, 1, -4)
    plot._start[0] = plot._start[0] or (plot.dimensions[0] / 2, 1, -4)
    session = Session(plot, args.delay, setup)
    if not args.no_autosave:
        atexit.register(autosave, session, Path('drafts') / 'livecode')

    def run():
        if args.script:
            for line in Path(args.script).read_text().split('\n'):
                time.sleep(0.15)
                session.feed(line)
        else:
            session.repl()

    options = {'peaceful': True, 'dimension': 'nether' if args.nether else 'overworld'}
    if args.screenshot:
        options.update(_screenshot=args.screenshot, _seconds=args.seconds)
    pc.live(plot, run, **options)


if __name__ == '__main__':
    main()
