"""lanplay - play in a classroom (LAN) world: the game window, other players, chat and the teacher's orders.

    python3 lan.py join 192.168.1.23 maple-tiger-42 --name Sam

Press T (or /) to chat. Slash commands: /list, /help, and /teacher PIN to become a teacher (a teacher can then use
/mode, /freeze, /lock, /mute, /kick, /tp, /bring, /say and /time; /help lists them).

What is shared: the blocks players place and break, where everybody is, and chat. Things that move by themselves (animals,
water, fire) are not shared yet: this world has no wild animals so everyone sees the same thing."""
import math
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

POS_INTERVAL = 0.1
MODE_NAMES = {'adventure': ('survival', True, 'Adventure'), 'survival': ('survival', False, 'Survival'),
              'creative': ('creative', False, 'Creative'), 'spectator': ('spectator', True, 'Spectator')}
SKINS = ('steve', 'alex', 'ari', 'efe', 'kai', 'makena', 'noor', 'sunny', 'zuri')


def skin_for(name):
    """One of the standard skins, always the same one for the same name."""
    skins_folder = HERE / 'assets' / 'textures' / 'entity'
    chosen = SKINS[sum(ord(c) for c in name) % len(SKINS)]
    for candidate in (f'player_{chosen}.png', 'player_steve.png', 'zombie.png'):
        if (skins_folder / candidate).exists():
            return candidate


def remote_player_type(name):
    """A creature type that looks like a player with this name's skin."""
    import dataclasses
    import mobtypes
    kind = dataclasses.replace(mobtypes.ZOMBIE, name=f'remote_{name}', title=name, textures={'main': skin_for(name)}, monster=False,
                               burns=False, drops=[], sound='', base='remote_player')
    return kind


def make_remote_class():
    """The body of another player (built here so the game's classes are only imported when the window is used)."""
    from mobs import Mob
    from ursina import Text, color

    class RemotePlayer(Mob):
        """Another player: stands where the server says, walks with the usual arm and leg swing, cannot be hurt."""

        def __init__(self, manager, info):
            kind = remote_player_type(info['name'])
            super().__init__(manager, kind, (info['x'], info['y'], info['z']))
            self.player_id, self.player_name = info['id'], info['name']
            self.goal = (info['x'], info['y'], info['z'])
            self.goal_yaw = info.get('yaw', 0.0)
            self.walking_now = False
            self.rotation_y = self.goal_yaw
            self.tag = Text(info['name'] + ('  [T]' if info.get('teacher') else ''), parent=self, y=kind.height + 0.35, scale=9,
                            billboard=True, origin=(0, 0), color=color.yellow if info.get('teacher') else color.white)

        def set_teacher(self, teacher):
            self.tag.text = self.player_name + ('  [T]' if teacher else '')
            self.tag.color = color.yellow if teacher else color.white

        def update(self):
            dt = min(1 / 20, 0.05)
            gx, gy, gz = self.goal
            blend = min(1.0, dt * 14)
            self.moving = self.walking_now
            self.wish_speed = 2.0
            self.position = (self.x + (gx - self.x) * blend, self.y + (gy - self.y) * blend, self.z + (gz - self.z) * blend)
            turn = (self.goal_yaw - self.rotation_y + 180) % 360 - 180
            self.rotation_y += turn * blend
            self.target = None
            self._animate(dt)

        def hurt(self, *args, **kwargs):
            pass                                              # (nobody hurts a classmate)

    return RemotePlayer


class Chat:
    """The chat lines at the bottom left, and the line you type into."""

    def __init__(self, game, send):
        from ursina import Entity, InputField, Text, camera, color
        self.game, self.send, self.is_open = game, send, False
        self.lines = []                                   # (time, text)
        self.history, self.history_at = [], 0
        self.text = Text('', parent=camera.ui, position=(-.85, -.16), origin=(-.5, .5), scale=.9, line_height=1.1)
        self.field = InputField(parent=camera.ui, x=-.35, y=-.34, scale=(1.0, .045), character_limit=200, active=False, enabled=False)
        self.field.submit_on = ['enter']
        self.field.on_submit = self._submit
        self._shown = None

    def add(self, text):
        self.lines.append((time.monotonic(), text))
        self.lines = self.lines[-40:]

    def open(self, prefix='', key=None):
        from ursina import mouse
        import cursor
        self.is_open = True
        self.field.enabled = True
        self.field.text = prefix
        self.field.text_field.cursor.x = len(prefix)
        self.field.active = True
        self.game.player.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)
        self._opened_with, self._prefix = key, prefix

    def close(self):
        from ursina import mouse
        import cursor
        self.is_open = False
        self.field.active = False
        self.field.enabled = False
        if not getattr(self.game, 'frozen', False):
            self.game.player.enabled = True
        mouse.locked = True
        cursor.set_hidden(True)

    def input(self, key):
        if key == 'escape':
            self.close()
        elif key == 'up arrow' and self.history:
            self.history_at = max(0, self.history_at - 1)
            self.field.text = self.history[self.history_at]
            self.field.text_field.cursor.x = len(self.field.text)
        elif key == 'down arrow' and self.history:
            self.history_at = min(len(self.history), self.history_at + 1)
            self.field.text = self.history[self.history_at] if self.history_at < len(self.history) else ''
            self.field.text_field.cursor.x = len(self.field.text)

    def _submit(self):
        text = self.field.text.strip()
        self.field.text = ''
        if text:
            self.history.append(text)
            self.history_at = len(self.history)
            self.send(text)
        self.close()

    def update(self):
        if self.is_open and getattr(self, '_opened_with', None):
            key, self._opened_with = self._opened_with, None
            if self.field.text == self._prefix + key:                  # (the key that opened the chat must not be typed)
                self.field.text = self._prefix
                self.field.text_field.cursor.x = len(self._prefix)
        now = time.monotonic()
        visible = [text for stamp, text in self.lines[-8:] if self.is_open or now - stamp < 12]
        shown = '\n'.join(visible)
        if shown != self._shown:
            self._shown = shown
            self.text.text = shown
            self.text.origin = (-.5, .5)                              # (a text that changes size must be lined up again)
            self.text.x = -.85


def play(host, port, code, name, screenshot=None, seconds=6, hook=None):
    """Join a classroom world and play in it. Returns when the window is closed."""
    import os
    from mac_fix import clear_leftover_shaders, fix_shaders, fix_ui_scale

    fix_shaders()
    import ursina
    from ursina import Ursina, application, camera, color, window
    icon = Path(ursina.__file__).parent / 'textures' / 'ursina.ico'
    os.chdir(HERE)                                        # (the game finds its pictures and sounds from here)
    app = Ursina(title='PythonCraft class', icon=str(icon))
    clear_leftover_shaders()
    window.color = color.rgb32(135, 206, 235)
    window.fps_counter.enabled = window.entity_counter.enabled = window.collider_counter.enabled = False
    window.exit_button.enabled = window.cog_button.enabled = False

    import mods                                           # (the same mods as the server, or it says so)
    mods.load_folder()
    from lanclient import LanClient, LanError
    client = LanClient(host, port, code, name)
    try:
        info = client.connect()
    except LanError as error:
        print(f'Could not join: {error}')
        return 1

    from game import Game
    modified = {(c[0], c[1], c[2]): c[3] for c in info['changes']}
    facing = {(c[0], c[1], c[2]): c[4] for c in info['changes'] if c[4]}
    flat = tuple(info['flat_spawn']) if info.get('flat_spawn') else None
    folder = Path(tempfile.mkdtemp(prefix='pythoncraft_lan_'))
    game = Game(folder, info['title'], seed=info['seed'], mode='survival', modified=modified, facing=facing, flat_spawn=flat)
    game.save = lambda: None                              # (a class world is kept by the server, not on this computer)
    game.mobs.update_spawning = lambda dt: None           # (no wild animals: they would not be the same on every computer)
    for mob in game.mobs.mobs[:]:
        game.mobs.remove(mob)
    game.frozen = False
    spot = (round(game.player.x), math.floor(game.player.y + 0.5), round(game.player.z))
    if game.world.solid_top(spot) > 0 or game.world.solid_top((spot[0], spot[1] + 1, spot[2])) > 0:
        game.unstuck()                                    # (a start inside a tree or a rock)

    Remote = make_remote_class()
    remotes = {}
    chat = Chat(game, client.chat)
    game.chat = chat
    state = {'last_pos': None, 'timer': 0.0, 'teacher': False, 'locked': False, 'mode': info['mode'], 'recent': {}}

    # ---- the mode the server gave us ----------------------------------------------------------------------------------------------
    def apply_mode(mode, locked, frozen=None):
        base, build_locked, title = MODE_NAMES.get(mode, MODE_NAMES['adventure'])
        state['mode'], state['locked'] = mode, locked
        game.player.set_mode(base)
        game.player.build_locked = bool(locked or build_locked)
        game.menu.locked_mode = title + ' (set by the class)'
        game.menu._update_mode_label()

    def set_frozen(on):
        game.frozen = on
        game.player.enabled = not on and not chat.is_open
        if on:
            game.message('You are frozen. Listen to your teacher.', 4)

    apply_mode(info['mode'], info.get('locked', False))
    if info.get('time') is not None:
        game.sky.set_time(info['time'])
    for entry in info['players']:
        remotes[entry['id']] = Remote(game.mobs, entry)
        game.mobs.mobs.append(remotes[entry['id']])
    chat.add(f"You joined {info['server']} as {client.name}. Press T to chat, /help for commands.")

    # ---- sending what you do ----------------------------------------------------------------------------------------------------
    world = game.world
    capture = {'on': False, 'touched': {}}
    real_set = world._set

    def recording_set(pos, kind):
        if capture['on'] and pos not in capture['touched']:
            capture['touched'][pos] = (world.get(pos), world.facing.get(pos))     # (what it was, in case the server says no)
        real_set(pos, kind)

    world._set = recording_set

    def wrap(method):
        def wrapper(*args, **kwargs):
            capture['on'], capture['touched'] = True, {}
            try:
                return method(*args, **kwargs)
            finally:
                capture['on'] = False
                changes = []
                for pos, before in capture['touched'].items():
                    now = (world.get(pos), world.facing.get(pos))
                    if now != before:
                        changes.append((pos[0], pos[1], pos[2], now[0] if now[0] != 'air' else None, now[1]))
                        state['recent'][pos] = (before, time.monotonic())
                if changes:
                    client.send_blocks(changes)
        return wrapper

    for name_ in ('_place', '_break', '_use'):
        setattr(game.interaction, name_, wrap(getattr(game.interaction, name_)))

    def apply_block(pos, name_, facing_):
        """Make a block the way the server says (this is not echoed back)."""
        current = world.get(pos)
        if current == name_ and world.facing.get(pos) == facing_:
            return
        if current is not None:
            world.remove(pos)
        if name_ is not None:
            world.place(pos, name_, facing_)

    # ---- what the server sends --------------------------------------------------------------------------------------------------
    def handle(message):
        kind = message['t']
        if kind == 'pos':
            remote = remotes.get(message['id'])
            if remote is not None:
                remote.goal = (message['x'], message['y'], message['z'])
                remote.goal_yaw = message.get('yaw', 0.0)
                remote.walking_now = bool(message.get('v'))
        elif kind == 'join':
            entry = message['p']
            if entry['id'] not in remotes:
                remotes[entry['id']] = Remote(game.mobs, entry)
                game.mobs.mobs.append(remotes[entry['id']])
        elif kind == 'leave':
            remote = remotes.pop(message['id'], None)
            if remote is not None:
                game.mobs.remove(remote)
        elif kind == 'blocks':
            for x, y, z, name_, facing_ in message['c']:
                apply_block((x, y, z), name_, facing_)
        elif kind == 'reject':
            for x, y, z in message['c']:
                before = state['recent'].pop((x, y, z), None)
                if before is not None:
                    apply_block((x, y, z), *before[0])
            game.message('You cannot build here right now.', 2)
        elif kind == 'chat':
            chat.add(f"{'[T] ' if message.get('teacher') else ''}{message['from']}: {message['m']}")
        elif kind == 'say':
            chat.add(message['m'])
        elif kind == 'announce':
            game.message(f"{message.get('from', 'Teacher')}: {message['m']}", 10)
            chat.add(f"** {message['m']}")
        elif kind == 'mode':
            apply_mode(message['mode'], message.get('locked', False))
            if message.get('frozen') is not None and bool(message['frozen']) != game.frozen:
                set_frozen(bool(message['frozen']))
        elif kind == 'freeze':
            set_frozen(bool(message.get('on')))
        elif kind == 'tp':
            game.player.position = (message['x'], message['y'], message['z'])
            game.player.velocity_y = 0
            game.player._peak_y = game.player.y
        elif kind == 'time':
            game.sky.set_time(message['ticks'])
        elif kind == 'role':
            state['teacher'] = bool(message.get('teacher'))
            game.message('You are a teacher.' if state['teacher'] else 'You are a student again.', 4)
        elif kind == 'closed' or kind == 'kick':
            game.message(message.get('m', 'Disconnected.'), 8)
            chat.add(message.get('m', 'Disconnected.'))
            if kind == 'closed':
                state['gone'] = time.monotonic()

    import __main__

    def tick(dt):
        for message in client.poll():
            handle(message)
        for pos in [p for p, (_, stamp) in state['recent'].items() if time.monotonic() - stamp > 4]:
            state['recent'].pop(pos, None)
        state['timer'] += dt
        if state['timer'] >= POS_INTERVAL and not client.closed:
            state['timer'] = 0.0
            player = game.player
            now = (round(player.x, 2), round(player.y, 2), round(player.z, 2), round(player.rotation_y, 0),
                   round(player.camera_pivot.rotation_x, 0))
            last = state['last_pos']
            if now != last:
                moving = last is not None and (now[0], now[2]) != (last[0], last[2])
                client.send_pos(player.x, player.y, player.z, player.rotation_y, player.camera_pivot.rotation_x, moving)
                state['last_pos'], state['was_moving'] = now, moving
            elif state.get('was_moving'):
                client.send_pos(player.x, player.y, player.z, player.rotation_y, player.camera_pivot.rotation_x, False)
                state['was_moving'] = False
        chat.update()
        if state.get('gone') and time.monotonic() - state['gone'] > 6:
            application.quit()

    def update():
        fix_ui_scale()
        game.update()
        tick(ursina.time.dt)

    def on_input(key):
        if chat.is_open:
            chat.input(key)
            return
        if not game.ui.active and not game.menu.is_open and not game.menu.just_closed() and not game.player.dead:
            if key == 't':
                chat.open('', 't')
                return
            if key == '/':
                chat.open('/', '/')
                return
        game.input(key)

    __main__.input = on_input
    __main__.update = update
    real_quit = application.quit

    def leave():
        client.close()
        real_quit()

    application.quit = leave
    if hook is not None:                                  # (used for testing)
        from ursina import Func, Sequence, Wait
        Sequence(Wait(3), Func(hook, game, client, remotes, chat), Wait(seconds), Func(application.quit)).start()
    if screenshot:
        from ursina import Func, Sequence, Wait

        def snap():
            application.base.screenshot(screenshot, defaultFilename=False)
        Sequence(Wait(seconds), Func(snap), Wait(0.5), Func(application.quit)).start()
    try:
        app.run()
    finally:
        client.close()
        application.quit = real_quit
    return 0
