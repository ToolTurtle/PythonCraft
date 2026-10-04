"""gameconsole - the in-game code prompt: press / to type Python (or a :command) while you play.

Used by livecode.py. Lines are run one after another on a helper thread, so blocks appear with the build delay;
what they print shows up here and in the terminal."""
import contextlib
import queue
import sys
import threading

from ursina import Entity, Text, camera, color, mouse
from ursina.prefabs.input_field import InputField

import cursor

LINES = 12                  # how many lines of output stay on screen


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
    def __init__(self, game, feed, prompt=lambda: 'pc> ', completer=None, indent=lambda: '',
                 title='Code  (Enter runs it, Tab completes, Esc closes)'):
        self.game, self.feed, self.prompt = game, feed, prompt
        self.completer, self.indent = completer, indent
        self._tab, self._hinted = None, None
        self.is_open = False
        self.history, self.history_at = [], 0
        self.lines = []                                   # (text, colour) newest last
        self._pending = ''
        self._incoming = queue.Queue()
        self._jobs = queue.Queue()
        self._skip_slash = False
        self.root = Entity(parent=camera.ui, enabled=False)
        Entity(parent=self.root, model='quad', scale=(1.5, .7), position=(0, .12, 1), color=color.black66)
        self.title = Text(title, parent=self.root, x=-.72, y=.455, scale=.9, color=color.rgb32(170, 170, 170))
        self.log = Text('', parent=self.root, x=-.72, y=.41, scale=.9, line_height=1.1, origin=(-.5, .5))
        self.label = Text('pc>', parent=self.root, x=-.72, y=-.07, scale=1.1, color=color.rgb32(120, 220, 120))
        self.field = InputField(parent=self.root, x=-.1, y=-.1, scale=(1.3, .05), character_limit=300, active=False)
        self.field.x = -.72 + .66 + .06
        self.field.submit_on = ['enter']
        self.field.on_submit = self._submit
        self.field.text_field.x = -.5
        real_input = self.field.input
        self.field.input = lambda key: None if key == 'tab' else real_input(key)      # (Tab completes; it must not leave the field)
        self.usage = Text('', parent=self.root, x=-.72, y=-.155, scale=.85, color=color.rgb32(120, 220, 120))
        self.names = Text('', parent=self.root, x=-.72, y=-.19, scale=.85, color=color.rgb32(170, 170, 170))
        threading.Thread(target=self._worker, daemon=True).start()

    # ---- opening and closing -----------------------------------------------------------------------------------------

    def open(self):
        if self.is_open:
            return
        self.is_open = True
        self.root.enabled = True
        self.game.player.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)
        self.label.text = self.prompt().strip()
        self._set_text(self.indent())
        self.field.active = True
        self._skip_slash = True                           # (the / that opened it must not be typed)

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        self.field.active = False
        self.root.enabled = False
        self.game.player.enabled = True
        mouse.locked = True
        cursor.set_hidden(True)
        self.closed_by_key = True

    def input(self, key):
        """Keys while the console is open (the field itself handles typing)."""
        if key == 'escape':
            self.close()
        elif key == 'tab' and self.completer is not None:
            text, self._tab = self.completer.tab(self.field.text, self._tab)
            self._set_text(text)
        elif key == 'up arrow' and self.history:
            self.history_at = max(0, self.history_at - 1)
            self._set_text(self.history[self.history_at])
        elif key == 'down arrow' and self.history:
            self.history_at = min(len(self.history), self.history_at + 1)
            self._set_text(self.history[self.history_at] if self.history_at < len(self.history) else '')

    def _set_text(self, text):
        self.field.text = text
        cursor_entity = self.field.text_field.cursor
        cursor_entity.x, cursor_entity.y = len(text), 0            # (the cursor goes to the end)

    # ---- running ---------------------------------------------------------------------------------------------------------

    def _submit(self):
        line = self.field.text
        self._set_text('')
        if line.strip():
            self.history.append(line)
        self.history_at = len(self.history)
        self._add(f'{self.prompt()}{line}', color.rgb32(120, 220, 120))
        self._jobs.put(line)
        self.field.active = True

    def _worker(self):
        while True:
            line = self._jobs.get()
            tee = _Tee(sys.stdout, lambda text: self._incoming.put(text))
            try:
                with contextlib.redirect_stdout(tee):
                    self.feed(line)
            except Exception as error:                    # (a command went wrong: say so, keep going)
                self._incoming.put(f'{type(error).__name__}: {error}\n')
            self._incoming.put(None)                      # (end of this line's output)

    def _add(self, text, colour=color.white):
        for piece in str(text).split('\n'):
            while len(piece) > 100:
                self.lines.append((piece[:100], colour))
                piece = '  ' + piece[100:]
            self.lines.append((piece, colour))
        self.lines = self.lines[-LINES:]
        self.log.text = '\n'.join(t for t, _c in self.lines)

    def update(self, dt):
        if self._skip_slash and self.is_open:
            self._skip_slash = False
            self.field.text = self.field.text.lstrip('/')
        if self.is_open and self.completer is not None and self.field.text != self._hinted:
            self._hinted = self.field.text
            try:
                usage, names = self.completer.hint(self.field.text)
            except Exception:                                  # (a hint must never get in the way of typing)
                usage, names = '', ''
            self.usage.text, self.names.text = usage, names
        while True:
            try:
                text = self._incoming.get_nowait()
            except queue.Empty:
                break
            if text is None:
                if self._pending.strip():
                    self._add(self._pending.rstrip('\n'), color.rgb32(255, 150, 150) if self._looks_bad(self._pending) else color.white)
                self._pending = ''
                self.label.text = self.prompt().strip()
                if not self.field.text.strip():
                    self._set_text(self.indent())              # (the next line of a block starts indented)
            else:
                self._pending += text

    @staticmethod
    def _looks_bad(text):
        return 'Error' in text.split(':')[0] or 'Traceback' in text
