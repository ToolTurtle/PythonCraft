"""The pause menu (Esc): settings you can change while playing."""
import time
from ursina import Entity, Text, Button, Slider, Vec2, camera, color, mouse, application

import cursor
import textures
from player import MODES

SLIDER_X = -0.1      # left end of every slider bar
ROW = 0.043          # vertical space between rows


class PauseMenu:
    def __init__(self, player, world, sound):
        self.player = player
        self.world = world
        self.sound = sound
        self.hide_while_open = []     # HUD pieces to hide while the menu is showing
        self.on_save = None           # set by game.py
        self.on_respawn = None
        self.locked_mode = None       # e.g. 'Adventure': the mode button then shows it and cannot be changed
        self.sky = None               # set by game.py
        self.on_quit = None
        self.sliders = {}             # name -> (slider, getter) so a loaded game can move them
        self.is_open = False
        self.closed_at = 0           # when we last closed, to ignore the click that closed us
        self.tint_sliders = {}       # 'grass' / 'foliage' -> [R, G, B sliders]
        self.swatches = {}

        self.root = Entity(parent=camera.ui, enabled=False)
        Entity(parent=self.root, model='quad', scale=(3, 2), color=color.black66, z=1)       # dim the game
        Entity(parent=self.root, model='quad', scale=(.95, .95), x=.075, y=0,
               color=color.rgb32(45, 45, 45), z=.5)                                             # panel
        Text('Paused', parent=self.root, origin=(0, 0), x=.075, y=.41, scale=2)

        y = .33
        self.sens_slider = self._slider('Mouse sensitivity', 5, 150, self.player.mouse_sensitivity[0], y,
                     lambda v: setattr(self.player, 'mouse_sensitivity', Vec2(v, v)))
        y -= ROW
        self.fov_slider = self._slider('Field of view', 60, 110, self.player.base_fov, y,
                     lambda v: setattr(self.player, 'base_fov', v))

        y -= ROW
        self.render_slider = self._slider('Render distance', 2, 12, self.world.render_distance, y,
                     self.world.set_render_distance)

        y -= ROW * 1.3
        self.sound_slider = self._slider('Sound volume', 0, 100, round(self.sound.volume * 100), y,
                     lambda v: setattr(self.sound, 'volume', v / 100))
        y -= ROW
        self.music_slider = self._slider('Music volume', 0, 100, round(self.sound.music_volume * 100), y,
                     lambda v: self.sound.set_music_volume(v / 100))

        y -= ROW * 1.4
        y = self._tint_group('grass', 'Grass', y)
        y -= ROW * .5
        y = self._tint_group('foliage', 'Leaves', y)

        y -= ROW * 1.2
        self._button('Resume', y, self.close, x=.075 - .16)
        self._button('Controls', y, self._toggle_controls, x=.075 + .16)
        y -= ROW * 1.4
        left, right = .075 - .16, .075 + .16                      # two buttons side by side
        self.mode_button = self._button('', y, self._cycle_mode, x=left)
        self._update_mode_label()
        self._button('Respawn', y, self._respawn, x=right)
        y -= ROW * 1.4
        self._button('Reset tints', y, self._reset_tints, x=left)
        self.time_button = self._button('', y, self._cycle_time, x=right)
        y -= ROW * 1.4
        self._button('Save game', y, lambda: self.on_save() if self.on_save else None, x=left)
        self._button('Save and quit', y, lambda: self.on_quit() if self.on_quit else application.quit(), x=right)
        self._build_controls_panel()

    # ---- the controls help ---------------------------------------------------------------------

    CONTROLS = [
        ('W A S D', 'walk'), ('Mouse', 'look around'), ('Space', 'jump (swim up, climb ladders, fly up)'),
        ('Shift', 'sneak (stay on edges; fly down; leave a vehicle)'), ('Ctrl, or tap W twice', 'sprint'),
        ('Left click (hold)', 'mine a block, or hit a creature'), ('Right click', 'place, use, open, eat (hold), draw a bow (hold)'),
        ('Middle click', 'pick the block you are looking at (creative)'), ('1 - 9, scroll', 'choose a hotbar slot'),
        ('E', 'inventory and crafting'), ('Q', 'drop one item'), ('Space twice (creative)', 'start and stop flying'),
        ('Esc', 'this menu'),
    ]

    def _build_controls_panel(self):
        self.controls = Entity(parent=self.root, enabled=False, z=-1)
        Entity(parent=self.controls, model='quad', scale=(.97, .95), x=.075, color=color.rgb32(30, 30, 30), z=-.04)
        Text('Controls', parent=self.controls, origin=(0, 0), x=.075, y=.33, z=-.05, scale=2)
        for i, (keys, what) in enumerate(self.CONTROLS):
            Text(keys, parent=self.controls, origin=(-.5, 0), x=-.33, y=.25 - i * .047, z=-.05, scale=1, color=color.rgb32(255, 215, 120))
            Text(what, parent=self.controls, origin=(-.5, 0), x=-.07, y=.25 - i * .047, z=-.05, scale=1)
        Button(parent=self.controls, text='Back', x=.075, y=-.36, z=-.05, scale=(.3, .045), color=color.rgb32(80, 80, 80),
               highlight_color=color.rgb32(120, 120, 120), on_click=self._toggle_controls)

    def _toggle_controls(self):
        self.controls.enabled = not self.controls.enabled

    # ---- building blocks -------------------------------------------------

    def _slider(self, label, low, high, value, y, on_change):
        slider = Slider(low, high, default=value, text=label, dynamic=True,
                        parent=self.root, x=SLIDER_X, y=y)
        slider.step = 1
        slider.on_value_changed = lambda: on_change(slider.value)
        return slider

    def _button(self, label, y, action, x=.075, width=.31):
        return Button(parent=self.root, text=label, x=x, y=y, scale=(width, .045),
                      color=color.rgb32(80, 80, 80), highlight_color=color.rgb32(120, 120, 120),
                      on_click=action)

    def _tint_group(self, name, label, y):
        """Three sliders (red, green, blue) that recolor `name` blocks live."""
        sliders = []
        for i, channel in enumerate('RGB'):
            slider = self._slider(f'{label} {channel}', 0, 255, textures.get_tint(name)[i], y,
                                  lambda v, i=i: self._set_channel(name, i, v))
            sliders.append(slider)
            y -= ROW
        self.tint_sliders[name] = sliders
        self.swatches[name] = Entity(parent=self.root, model='quad', scale=(.06, .06),
                                     x=SLIDER_X + .6, y=y + ROW * 2.4,
                                     color=color.rgb32(*textures.get_tint(name)))
        return y

    def refresh_sliders(self):
        """Move every slider to match the current settings (after loading a saved game)."""
        for slider, value in ((self.sens_slider, self.player.mouse_sensitivity[0]), (self.fov_slider, self.player.base_fov),
                              (self.render_slider, self.world.render_distance),
                              (self.sound_slider, self.sound.volume * 100), (self.music_slider, self.sound.music_volume * 100)):
            slider.value_setter(round(value), call_on_value_changed=False)
        for name, sliders in self.tint_sliders.items():
            for slider, value in zip(sliders, textures.get_tint(name)):
                slider.value_setter(value, call_on_value_changed=False)
            self.swatches[name].color = color.rgb32(*textures.get_tint(name))

    def _respawn(self):
        """Back to the world's spawn point with full health and food (also handy if you get stuck)."""
        self.close()
        if self.on_respawn:
            self.on_respawn()

    def _update_time_label(self):
        if self.sky is not None:
            self.time_button.text = f'Time: {self.sky.phase_name()}'

    def _cycle_time(self):
        """Jump to the next time of day (creative mode only, like a cheat)."""
        if self.sky is None or self.player.mode != 'creative':
            return
        from sky import PHASES
        ticks = list(PHASES.values())
        later = [t for t in ticks if t > self.sky.time + 200]
        self.sky.set_time(later[0] if later else ticks[0])
        self._update_time_label()

    def add_buttons(self, buttons):
        """Small extra buttons at the top of the menu: [(label, function), ...]. (pycraft's Undo and Redo use this.)"""
        for i, (label, function) in enumerate(buttons):
            self._button(label, .41, lambda f=function: f(), width=.13, x=-.29 + i * .15)

    # ---- game mode -------------------------------------------------------

    def _update_mode_label(self):
        shown = self.locked_mode or self.player.mode.title()
        self.mode_button.text = f'Mode: {shown}' + (' (locked)' if self.locked_mode else '')

    def _cycle_mode(self):
        if self.locked_mode:
            return
        next_mode = MODES[(MODES.index(self.player.mode) + 1) % len(MODES)]
        self.player.set_mode(next_mode)
        self._update_mode_label()

    # ---- changing the tint -----------------------------------------------

    def _set_channel(self, name, index, value):
        rgb = list(textures.get_tint(name))
        rgb[index] = int(value)
        self._apply_tint(name, rgb)

    def _apply_tint(self, name, rgb):
        textures.set_tint(name, rgb)
        self.swatches[name].color = color.rgb32(*rgb)
        self.world.retint()

    def _reset_tints(self):
        for name, rgb in self.world.biome.tints.items():
            if name not in self.tint_sliders:
                continue          # (water has no sliders)
            for slider, value in zip(self.tint_sliders[name], rgb):
                slider.value_setter(value, call_on_value_changed=False)
            self._apply_tint(name, rgb)

    # ---- opening and closing ---------------------------------------------

    def open(self):
        self._update_mode_label()
        self._update_time_label()
        self.is_open = True
        self.root.enabled = True
        for thing in self.hide_while_open:
            thing.enabled = False
        self.player.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)

    def close(self):
        if hasattr(self, 'controls'):
            self.controls.enabled = False
        self.is_open = False
        self.root.enabled = False
        for thing in self.hide_while_open:
            thing.enabled = True
        self.player.enabled = True
        mouse.locked = True
        cursor.set_hidden(True)
        self.closed_at = time.time()

    def toggle(self):
        self.close() if self.is_open else self.open()

    def just_closed(self):
        """True for a moment after closing, so the Resume click doesn't also break a block."""
        return time.time() - self.closed_at < 0.2
