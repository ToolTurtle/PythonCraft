"""gameconsole - the in-game code prompt: press / to type Python (or a plain command, or a :command) while you play.

It is a small editor with several lines. Enter runs what you typed, unless you are in the middle of a block (a line ending in
`:` like a for or an if, or brackets that are not closed): then Enter starts a new, indented line, and Enter on an empty line runs
the block. Shift+Enter always starts a new line. Tab completes, Up/Down on the first/last line bring back earlier code, Esc closes.

Used by livecode.py. Lines are run one after another on a helper thread, so blocks appear with the build delay; what they print
shows up here and in the terminal."""
import contextlib
import queue
import sys
import threading

from ursina import Entity, Text, camera, color, held_keys, mouse
from ursina.prefabs.text_field import TextField

import cursor

LINES = 10                  # how many lines of output stay on screen
EDIT_LINES = 6              # how many lines you can type at once


class _Tee:
    """Send printed text to the terminal and to the console."""

    def __init__(self, real, sink):
        self.real, self.sink = real, sink

    def write(self, text):
        self.real.write(text)
        self.sink(text)
        return len(text)

    def flush(self):
        self.real.flush()


class GameConsole:
    def __init__(self, game, feed, prompt=lambda: 'pc> ', completer=None, indent=lambda: '', needs_more=None,
                 title='Code  (Enter runs it, Tab completes, Shift+Enter new line, Esc closes)'):
        self.game, self.feed, self.prompt = game, feed, prompt
        self.completer, self.indent, self.needs_more = completer, indent, needs_more
        self.is_open = False
        self.history, self.history_at = [], 0
        self.lines = []                                   # output lines, newest last
        self._tab, self._hinted = None, None
        self._pending = ''
        self._incoming = queue.Queue()
        self._jobs = queue.Queue()
        self._skip_slash = False
        self.root = Entity(parent=camera.ui, enabled=False)
        Entity(parent=self.root, model='quad', scale=(1.5, .66), position=(0, .165, 1), color=color.black66)
        self.title = Text(title, parent=self.root, x=-.72, y=.455, scale=.85, color=color.rgb32(170, 170, 170))
        self.log = Text('', parent=self.root, x=-.72, y=.415, scale=.85, line_height=1.1, origin=(-.5, .5))
        self.label = Text('pc>', parent=self.root, x=-.72, y=.085, scale=1.1, color=color.rgb32(120, 220, 120))
        self.field = TextField(max_lines=EDIT_LINES, line_height=1.1)
        self.field.parent = self.root
        self.field.position = (-.62, .1, -.1)
        self.field.bg.scale = (1.34, 0.025 * 1.1 * EDIT_LINES)
        self.field.bg.color = color.black
        self.field.bg.collider = None
        self.field.shortcuts['newline'] = ()              # (Enter is handled here)
        self.field.shortcuts['indent'] = ()               # (Tab completes)
        self.field.active = False
        self.usage = Text('', parent=self.root, x=-.72, y=-.105, scale=.85, color=color.rgb32(120, 220, 120))
        self.names = Text('', parent=self.root, x=-.72, y=-.14, scale=.85, color=color.rgb32(170, 170, 170))
        threading.Thread(target=self._worker, daemon=True).start()

    # ---- the text being typed ---------------------------------------------------------------------------------------------

    @property
    def text(self):
        return self.field.text

    def _set_text(self, text):
        self.field.text = text
        lines = text.split('\n')
        self.field.cursor.y, self.field.cursor.x = len(lines) - 1, len(lines[-1])         # (the cursor goes to the end)
        self.field.render()

    def _where(self):
        """The line the cursor is on, and how far along it."""
        lines = self.field.text.split('\n')
        y = min(int(self.field.cursor.y), len(lines) - 1)
        return lines, y, min(int(self.field.cursor.x), len(lines[y]))

    def _new_line(self):
        """Break the line at the cursor; the new line starts with the indent the code needs."""
        lines, y, x = self._where()
        if len(lines) >= EDIT_LINES:
            return
        head, tail = lines[y][:x], lines[y][x:]
        indent = self.completer.indent_for([head]) if self.completer is not None else ''
        lines[y] = head
        lines.insert(y + 1, indent + tail)
        self.field.text = '\n'.join(lines)
        self.field.cursor.y, self.field.cursor.x = y + 1, len(indent)
        self.field.render()

    # ---- opening and closing -----------------------------------------------------------------------------------------------

    def open(self):
        if self.is_open:
            return
        self.is_open = True
        self.root.enabled = True
        self.game.player.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)
        self.field.active = True
        self._skip_slash = True                           # (the / that opened it must not be typed)
        self._hinted = None

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        self.field.active = False
        self.root.enabled = False
        self.game.player.enabled = True
        mouse.locked = True
        cursor.set_hidden(True)

    def input(self, key):
        """Keys while the console is open (the field itself handles typing)."""
        if key == 'escape':
            self.close()
        elif key == 'enter' or key == 'enter hold':
            text = self.field.text
            if held_keys['shift'] or (text.strip() and self.needs_more is not None and self.needs_more(text)):
                self._new_line()
            elif text.strip():
                self._submit()
        elif key == 'tab' and self.completer is not None:
            self._complete()
        elif key == 'up arrow' and self.history and int(self.field.cursor.y) == 0:
            self.history_at = max(0, self.history_at - 1)
            self._set_text(self.history[self.history_at])
        elif key == 'down arrow' and self.history and int(self.field.cursor.y) >= len(self.field.text.split('\n')) - 1:
            self.history_at = min(len(self.history), self.history_at + 1)
            self._set_text(self.history[self.history_at] if self.history_at < len(self.history) else '')

    def _complete(self):
        lines, y, x = self._where()
        line = lines[y]
        new_head, self._tab = self.completer.tab(line[:x], self._tab)
        lines[y] = new_head + line[x:]
        self.field.text = '\n'.join(lines)
        self.field.cursor.y, self.field.cursor.x = y, len(new_head)
        self.field.render()

    # ---- running ---------------------------------------------------------------------------------------------------------

    def _submit(self):
        text = self.field.text.rstrip()
        self._set_text('')
        self.history.append(text)
        self.history_at = len(self.history)
        for number, line in enumerate(text.split('\n')):
            self._add(('pc> ' if number == 0 else '... ') + line)
        self._jobs.put(text)

    def _worker(self):
        while True:
            text = self._jobs.get()
            tee = _Tee(sys.stdout, lambda piece: self._incoming.put(piece))
            try:
                with contextlib.redirect_stdout(tee):
                    for line in text.split('\n'):
                        self.feed(line)
                    self.feed('')                         # (an empty line ends a block that is still open)
            except Exception as error:                    # (a command went wrong: say so, keep going)
                self._incoming.put(f'{type(error).__name__}: {error}\n')
            self._incoming.put(None)                      # (end of this code's output)

    def _add(self, text):
        for piece in str(text).split('\n'):
            while len(piece) > 100:
                self.lines.append(piece[:100])
                piece = '  ' + piece[100:]
            self.lines.append(piece)
        self.lines = self.lines[-LINES:]
        self.log.text = '\n'.join(self.lines)

    def update(self, dt):
        from ursina import window
        self.root.scale = min(1.0, window.aspect_ratio / 1.56)         # (smaller on a narrow window, so nothing is cut off)
        if self._skip_slash and self.is_open:
            self._skip_slash = False
            if self.field.text.startswith('/'):
                self._set_text(self.field.text[1:])
        if self.is_open and self.completer is not None:
            lines, y, x = self._where()
            shown = lines[y][:x]
            if shown != self._hinted:
                self._hinted = shown
                try:
                    usage, names = self.completer.hint(shown)
                except Exception:                          # (a hint must never get in the way of typing)
                    usage, names = '', ''
                self.usage.text, self.names.text = usage, names
        while True:
            try:
                text = self._incoming.get_nowait()
            except queue.Empty:
                break
            if text is None:
                if self._pending.strip():
                    self._add(self._pending.rstrip('\n'))
                self._pending = ''
            else:
                self._pending += text
