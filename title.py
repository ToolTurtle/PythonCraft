"""The title screen: pick a saved world, or make a new one."""
import hashlib
import random
import time as pytime

from ursina import Button, Entity, Text, application, camera, color, held_keys, mouse

import cursor
import savegame

PANEL = color.rgb32(45, 45, 45)
BUTTON = color.rgb32(80, 80, 80)
BUTTON_HOVER = color.rgb32(120, 120, 120)
CHOSEN = color.rgb32(70, 110, 160)
MAX_ROWS = 5


def seed_from_text(text):
    """Letters and numbers both make a seed. (Same text, same world, every time.)"""
    text = text.strip()
    if not text:
        return random.randrange(1_000_000)
    if text.lstrip('-').isdigit():
        return abs(int(text)) % 1_000_000
    return int(hashlib.md5(text.encode()).hexdigest(), 16) % 1_000_000


def ago(seconds):
    for limit, unit, size in ((60, 'seconds', 1), (3600, 'minutes', 60), (86400, 'hours', 3600)):
        if seconds < limit:
            return f'{int(seconds // size)} {unit} ago'
    return f'{int(seconds // 86400)} days ago'


class TextField:
    """A box you can click and type in."""

    def __init__(self, parent, label, y, text='', maximum=20):
        self.maximum = maximum
        self.text = text
        self.focused = False
        Text(label, parent=parent, origin=(-0.5, 0), x=-0.3, y=y + 0.045, scale=0.9)
        self.button = Button(parent=parent, text='', y=y, scale=(0.6, 0.05), color=BUTTON, highlight_color=BUTTON,
                             on_click=self.focus)
        self.fields = None            # set by the screen, so clicking one field un-focuses the others
        self.redraw()

    def focus(self):
        for field in self.fields or [self]:
            field.focused = field is self
            field.redraw()

    def redraw(self):
        self.button.text = self.text + ('_' if self.focused else '')
        self.button.color = CHOSEN if self.focused else BUTTON

    def key(self, key):
        if not self.focused:
            return
        if key == 'backspace':
            self.text = self.text[:-1]
        elif key == 'space':
            self.text += ' '
        elif len(key) == 1 and (key.isalnum() or key in '-_.'):
            self.text += key.upper() if held_keys['left shift'] or held_keys['right shift'] else key
        self.text = self.text[:self.maximum]
        self.redraw()


class TitleScreen:
    def __init__(self, on_open, on_create):
        self.on_open, self.on_create = on_open, on_create
        self.root = Entity(parent=camera.ui)
        Entity(parent=self.root, model='quad', scale=(3, 2), color=color.rgb32(30, 30, 35), z=2)
        Entity(parent=self.root, model='quad', scale=(0.8, 0.92), color=PANEL, z=1)
        Text('PythonCraft', parent=self.root, origin=(0, 0), y=0.37, scale=3.5)

        self.worlds = []
        self.selected = None
        self.list_root = Entity(parent=self.root)
        self.delete_armed = False
        self.buttons_root = Entity(parent=self.root)
        self.play = self._button('Play selected world', -0.14, -0.28, self._play, 0.36)
        self.new = self._button('New world', 0.19, -0.28, self.show_new, 0.28)
        self.delete = self._button('Delete', -0.14, -0.35, self._delete, 0.36)
        self._button('Quit', 0.19, -0.35, application.quit, 0.28)
        self.empty_text = Text('No saved worlds yet. Make one!', parent=self.root, origin=(0, 0), y=0.15, scale=1.2)

        # The "new world" form
        self.form = Entity(parent=self.root, enabled=False, z=-1)
        Entity(parent=self.form, model='quad', scale=(0.8, 0.92), color=PANEL, z=0.5)
        Text('Create a new world', parent=self.form, origin=(0, 0), y=0.3, scale=2)
        self.name_field = TextField(self.form, 'World name', 0.17, 'New World')
        self.seed_field = TextField(self.form, 'Seed (leave empty for a random world)', 0.03, '', 16)
        self.name_field.fields = self.seed_field.fields = [self.name_field, self.seed_field]
        self.mode = 'survival'
        self.mode_button = Button(parent=self.form, text='', y=-0.1, scale=(0.6, 0.05), color=BUTTON,
                                  highlight_color=BUTTON_HOVER, on_click=self._cycle_mode)
        self._update_mode_text()
        Button(parent=self.form, text='Create world', y=-0.2, scale=(0.6, 0.055), color=BUTTON,
               highlight_color=BUTTON_HOVER, on_click=self._create)
        Button(parent=self.form, text='Cancel', y=-0.28, scale=(0.6, 0.055), color=BUTTON,
               highlight_color=BUTTON_HOVER, on_click=self.hide_new)

        self.loading = Text('Loading...', parent=camera.ui, origin=(0, 0), scale=3, enabled=False, z=-5)
        self.refresh()

    def _button(self, label, x, y, action, width):
        return Button(parent=self.buttons_root, text=label, x=x, y=y, scale=(width, 0.05), color=BUTTON,
                      highlight_color=BUTTON_HOVER, on_click=action)

    # ---- the list of worlds ----------------------------------------------

    def refresh(self):
        for child in list(self.list_root.children):
            child.disable()
            from ursina import destroy
            destroy(child)
        self.worlds = savegame.list_worlds()
        self.selected = 0 if self.worlds else None
        self.delete_armed = False
        self.delete.text = 'Delete'
        for i, world in enumerate(self.worlds[:MAX_ROWS]):
            played = ago(max(1, pytime.time() - world['last_played']))
            Button(parent=self.list_root, text=f"{world['name']}   -   {world['mode']}   -   {played}",
                   y=0.24 - i * 0.075, scale=(0.7, 0.062), color=BUTTON, highlight_color=BUTTON_HOVER,
                   on_click=lambda i=i: self._select(i))
        self._paint()
        self.empty_text.enabled = not self.worlds

    def _select(self, index):
        self.selected = index
        self.delete_armed = False
        self.delete.text = 'Delete'
        self._paint()

    def _paint(self):
        for i, button in enumerate(self.list_root.children):
            button.color = CHOSEN if i == self.selected else BUTTON
        self.play.enabled = self.delete.enabled = self.selected is not None

    # ---- buttons ---------------------------------------------------------

    def _play(self):
        if self.selected is not None:
            self.on_open(self.worlds[self.selected]['path'])

    def _delete(self):
        if self.selected is None:
            return
        if not self.delete_armed:                  # first click only asks "are you sure?"
            self.delete_armed = True
            self.delete.text = 'Really delete?'
            return
        savegame.delete(self.worlds[self.selected]['path'])
        self.refresh()

    def show_new(self):
        self.form.enabled = True
        self.name_field.text, self.seed_field.text = 'New World', ''
        self.name_field.focus()

    def hide_new(self):
        self.form.enabled = False

    def _cycle_mode(self):
        self.mode = {'survival': 'creative', 'creative': 'survival'}[self.mode]
        self._update_mode_text()

    def _update_mode_text(self):
        self.mode_button.text = f'Game mode: {self.mode.title()}'

    def _create(self):
        name = self.name_field.text.strip() or 'New World'
        self.on_create(name, seed_from_text(self.seed_field.text), self.mode)

    # ---- showing, hiding, keys -------------------------------------------

    def show(self):
        self.root.enabled = True
        self.form.enabled = False
        self.loading.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)
        self.refresh()

    def hide(self):
        self.root.enabled = False
        self.loading.enabled = False

    def show_loading(self):
        self.root.enabled = False
        self.loading.enabled = True

    def input(self, key):
        if self.form.enabled:
            self.name_field.key(key)
            self.seed_field.key(key)

    def update(self):
        pass
