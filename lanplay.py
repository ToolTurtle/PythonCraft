"""lanplay - play in a classroom (LAN) world: the game window, other players, chat, plots, code building and the teacher's tools.

    python3 lan.py join 192.168.1.23 maple-tiger-42 --name Sam

Keys:  T chat   / chat command   C code prompt (build in your plot with code)   P teacher panel (teachers)   X stop following
Chat commands: /help lists them. /claim gets you a plot, /home goes to it, /teacher PIN makes you a teacher.

What is shared: blocks (placed by hand or by code), where everybody is, chat, chests, and the world's own changes (water, falling sand,
fire, redstone), which one player's computer works out for the whole class. Wild animals are not in a class world yet."""
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
MODE_ORDER = ('adventure', 'survival', 'creative', 'spectator')
SKINS = ('steve', 'alex', 'ari', 'efe', 'kai', 'makena', 'noor', 'sunny', 'zuri')
CODE_HEIGHT = 48


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
    return dataclasses.replace(mobtypes.ZOMBIE, name=f'remote_{name}', title=name, textures={'main': skin_for(name)}, monster=False,
                               burns=False, drops=[], sound='', base='remote_player')


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
            self.goal_pitch = info.get('pitch', 0.0)
            self.walking_now = False
            self.rotation_y = self.goal_yaw
            self.tag = Text(info['name'] + ('  [T]' if info.get('teacher') else ''), parent=self, y=kind.height + 0.35, scale=9,
                            billboard=True, origin=(0, 0), color=color.yellow if info.get('teacher') else color.white)

        def set_teacher(self, teacher):
            self.tag.text = self.player_name + ('  [T]' if teacher else '')
            self.tag.color = color.yellow if teacher else color.white

        def update(self):
            dt = 1 / 20
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


def make_puppet_class():
    """An animal that is run on another player's computer: it stands where it is told and a hit on it is sent there."""
    from mobs import Mob

    class PuppetMob(Mob):
        def __init__(self, manager, kind, entry, hit):
            super().__init__(manager, kind, (entry[2], entry[3], entry[4]))
            self.net_id, self.send_hit = entry[0], hit
            self.goal, self.goal_yaw, self.walking_now = (entry[2], entry[3], entry[4]), entry[5], False
            self.rotation_y = entry[5]
            self.script_click = lambda: manager.player and None            # (feeding and trading are not shared yet)

        def update(self):
            dt = 1 / 20
            gx, gy, gz = self.goal
            blend = min(1.0, dt * 8)
            self.moving = self.walking_now
            self.wish_speed = 1.5
            self.position = (self.x + (gx - self.x) * blend, self.y + (gy - self.y) * blend, self.z + (gz - self.z) * blend)
            turn = (self.goal_yaw - self.rotation_y + 180) % 360 - 180
            self.rotation_y += turn * blend
            self.flash = max(0.0, self.flash - dt)
            self.target = None
            self._animate(dt)

        def hurt(self, from_position, damage=1):
            self.flash = 0.3                                              # (it flashes red now; the real one decides what happens)
            self.send_hit(self.net_id, damage)

    return PuppetMob


class Chat:
    """The chat lines at the bottom left, and the line you type into."""

    def __init__(self, game, send):
        from ursina import InputField, Text, camera
        self.game, self.send, self.is_open = game, send, False
        self.lines = []                                   # (time, text)
        self.history, self.history_at = [], 0
        self.text = Text('', parent=camera.ui, position=(-.7, -.28), origin=(-.5, -.5), scale=.9, line_height=1.1)
        self.field = InputField(parent=camera.ui, x=-.2, y=-.32, scale=(1.0, .045), character_limit=200, active=False, enabled=False)
        self.field.submit_on = ['enter']
        self.field.on_submit = self._submit
        self._shown = None
        self._opened_with = self._prefix = None

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
        from ursina import window
        left = -window.aspect_ratio / 2 + 0.02                        # (the left edge of the window, whatever its shape)
        self.text.x = left
        width = min(1.0, window.aspect_ratio - 0.1)
        self.field.scale_x = width
        self.field.x = left + width / 2
        if self.is_open and self._opened_with:
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
            self.text.origin = (-.5, -.5)                             # (a text that changes size must be lined up again)


def _grey():
    from ursina import color
    return color.rgb32(170, 170, 170)


class TeacherPanel:
    """The teacher's list of students with buttons: mode, freeze, mute, go to, bring, follow, and the class-wide switches.
    Every button just sends the same /command a teacher could type, so the server stays the one that decides."""

    PER_PAGE = 10

    def __init__(self, game, send, follow):
        from ursina import Button, Entity, InputField, Text, camera, color
        self.game, self.send, self.follow = game, send, follow
        self.is_open, self.page, self.players, self.locked, self.chat_on = False, 0, [], False, True
        self._dynamic = []
        self.root = Entity(parent=camera.ui, enabled=False, z=-2)
        Entity(parent=self.root, model='quad', scale=(1.62, .9), color=color.black66, z=1)
        Text('Class   (Esc closes)', parent=self.root, x=-.78, y=.4, scale=1.1)

        def button(text, x, y, width, action, tint=80):
            return Button(parent=self.root, text=text, x=x, y=y, scale=(width, .04), color=color.rgb32(tint, tint, tint),
                          highlight_color=color.rgb32(tint + 40, tint + 40, tint + 40), on_click=action, text_size=.75)

        self._button = button
        for number, mode in enumerate(MODE_ORDER):
            button(f'{mode.title()} (all)', -.6 + number * .185, .34, .175, lambda m=mode: self.send(f'/mode {m} all'))
        actions = (('Freeze all', '/freeze all'), ('Unfreeze all', '/unfreeze all'), ('Lock building', '/lock'), ('Unlock', '/unlock'),
                   ('Chat off', '/chat off'), ('Chat on', '/chat on'), ('Day', '/time day'), ('Night', '/time night'))
        for number, (label, command) in enumerate(actions):
            button(label, -.6 + number * .185, .29, .175, lambda c=command: self.send(c), 70)
        self.field = InputField(parent=self.root, x=-.3, y=.235, scale=(.9, .04), character_limit=200, active=False)
        button('Announce', .38, .235, .2, self._announce, 60)
        self.status = Text('', parent=self.root, x=-.78, y=.195, scale=.8)

    def _announce(self):
        text = self.field.text.strip()
        if text:
            self.send(f'/say {text}')
            self.field.text = ''

    def open(self):
        from ursina import mouse
        import cursor
        self.is_open = True
        self.root.enabled = True
        self.game.player.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)
        self.rebuild()

    def close(self):
        from ursina import mouse
        import cursor
        self.is_open = False
        self.root.enabled = False
        if not getattr(self.game, 'frozen', False):
            self.game.player.enabled = True
        mouse.locked = True
        cursor.set_hidden(True)

    def fit(self):
        from ursina import window
        self.root.scale = min(1.0, window.aspect_ratio / 1.7)             # (smaller on a narrow window, so nothing is cut off)

    def input(self, key):
        if key == 'escape':
            self.close()

    def update_roster(self, players, locked, chat_on):
        self.players, self.locked, self.chat_on = players, locked, chat_on
        if self.is_open:
            self.rebuild()

    def rebuild(self):
        from ursina import Text, destroy
        for entity in self._dynamic:
            destroy(entity)
        self._dynamic = []
        students = sorted(self.players, key=lambda p: (not p['teacher'], p['name'].lower()))
        pages = max(1, math.ceil(len(students) / self.PER_PAGE))
        self.page = min(self.page, pages - 1)
        self.status.text = (f"{len(self.players)} here    building {'LOCKED' if self.locked else 'open'}    chat {'on' if self.chat_on else 'OFF'}"
                            f"    page {self.page + 1} of {pages}")
        button = self._button
        for row, info in enumerate(students[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]):
            y = .15 - row * .047
            who = f"#{info['id']}"
            tag = ' [T]' if info['teacher'] else ''
            self._dynamic.append(Text(f"{info['name']}{tag}", parent=self.root, x=-.78, y=y + .01, scale=.85))
            plot = f"plot {info['plot']}" if info.get('plot') else ''
            self._dynamic.append(Text(plot, parent=self.root, x=-.5, y=y + .01, scale=.7))
            next_mode = MODE_ORDER[(MODE_ORDER.index(info['mode']) + 1) % len(MODE_ORDER)] if info['mode'] in MODE_ORDER else 'adventure'
            self._dynamic.append(button(info['mode'], -.3, y, .13, lambda w=who, m=next_mode: self.send(f'/mode {m} {w}')))
            self._dynamic.append(button('Unfreeze' if info['frozen'] else 'Freeze', -.16, y, .11,
                                        lambda w=who, f=info['frozen']: self.send(f"/{'unfreeze' if f else 'freeze'} {w}")))
            self._dynamic.append(button('Unmute' if info['muted'] else 'Mute', -.04, y, .1,
                                        lambda w=who, m=info['muted']: self.send(f"/{'unmute' if m else 'mute'} {w}")))
            self._dynamic.append(button('Go to', .07, y, .09, lambda w=who: (self.send(f'/tp {w}'), self.close())))
            self._dynamic.append(button('Bring', .17, y, .09, lambda w=who: self.send(f'/bring {w}')))
            self._dynamic.append(button('Follow', .27, y, .1, lambda i=info['id']: (self.follow(i), self.close())))
            self._dynamic.append(button('Code ' + ('on' if info['code'] else 'OFF'), .38, y, .12,
                                        lambda w=who, c=info['code']: self.send(f"/code {'off' if c else 'on'} {w}")))
            self._dynamic.append(button('Kick', .49, y, .08, lambda w=who: self.send(f'/kick {w}'), 110))
            if info.get('last'):
                self._dynamic.append(Text(info['last'], parent=self.root, x=-.78, y=y - .013, scale=.6, color=_grey()))
        if pages > 1:
            self._dynamic.append(button('Previous', -.1, -.4, .14, lambda: self._turn(-1)))
            self._dynamic.append(button('Next', .1, -.4, .14, lambda: self._turn(1)))

    def _turn(self, step):
        self.page += step
        self.rebuild()


def play(host, port, code, name, screenshot=None, seconds=6, hook=None):
    """Join a classroom world and play in it. Returns when the window is closed."""
    import os
    from mac_fix import clear_leftover_shaders, fix_shaders, fix_ui_scale

    fix_shaders()
    import ursina
    from ursina import Ursina, application, color, scene, window
    icon = Path(ursina.__file__).parent / 'textures' / 'ursina.ico'
    os.chdir(HERE)                                        # (the game finds its pictures and sounds from here)
    app = Ursina(title='PythonCraft class', icon=str(icon))
    clear_leftover_shaders()
    window.color = color.rgb32(135, 206, 235)
    window.fps_counter.enabled = window.entity_counter.enabled = window.collider_counter.enabled = False
    window.exit_button.enabled = window.cog_button.enabled = False

    import mods                                           # (the same mods as the server; missing .pcmod files are downloaded from it)
    mods.load_folder()
    from lanclient import LanClient, LanError
    client = LanClient(host, port, code, name)
    try:
        info = client.connect()
    except LanError as error:
        print(f'Could not join: {error}')
        return 1

    from classlayout import GROUND, Layout
    from game import Game
    from inventory import Stack
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
    world = game.world
    spot = (round(game.player.x), math.floor(game.player.y + 0.5), round(game.player.z))
    if world.solid_top(spot) > 0 or world.solid_top((spot[0], spot[1] + 1, spot[2])) > 0:
        game.unstuck()                                    # (a start inside a tree or a rock)

    Remote = make_remote_class()
    remotes = {}
    chat = Chat(game, client.chat)
    game.chat = chat
    state = {'last_pos': None, 'timer': 0.0, 'teacher': False, 'locked': False, 'mode': info['mode'], 'recent': {}, 'authority': False,
             'layout': Layout(), 'in_plot': None, 'follow': None, 'simbuf': {}, 'skip': set(), 'open_chest': None, 'code_plot': None,
             'session': None, 'tags': []}

    def console_open():
        return getattr(game, 'console', None) is not None and game.console.is_open

    # ---- the mode the server gave us ----------------------------------------------------------------------------------------------
    def apply_mode(mode, locked):
        base, build_locked, title = MODE_NAMES.get(mode, MODE_NAMES['adventure'])
        state['mode'], state['locked'] = mode, locked
        game.player.set_mode(base)
        game.player.build_locked = bool(locked or build_locked)
        game.menu.locked_mode = title + ' (set by the class)'
        game.menu._update_mode_label()

    def set_frozen(on):
        game.frozen = on
        game.player.enabled = not on and not chat.is_open and not console_open()
        if on:
            game.message('You are frozen. Listen to your teacher.', 4)

    apply_mode(info['mode'], info.get('locked', False))
    if info.get('time') is not None:
        game.sky.set_time(info['time'])
    for entry in info['players']:
        remotes[entry['id']] = Remote(game.mobs, entry)
        game.mobs.mobs.append(remotes[entry['id']])
    chat.add(f"You joined {info['server']} as {client.name}. Press T to chat, C for code, /help for commands.")
    pin = os.environ.pop('PYCRAFT_TEACHER_PIN', None)            # (set by the class window: join the game already as a teacher)
    if pin:
        client.chat(f'/teacher {pin}')

    # ---- sending what you do: blocks you place or break, blocks your code builds, and (for one player) what the world does ---------
    capture = {'on': False, 'touched': {}}
    real_set = world._set

    def recording_set(pos, kind):
        if capture['on']:
            if pos not in capture['touched']:
                capture['touched'][pos] = (world.get(pos), world.facing.get(pos))      # (what it was, in case the server says no)
        elif state['authority'] and pos not in state['skip'] and pos not in state['simbuf']:
            state['simbuf'][pos] = (world.get(pos), world.facing.get(pos))
        real_set(pos, kind)

    world._set = recording_set

    def run_captured(function, code=False):
        capture['on'], capture['touched'] = True, {}
        try:
            return function()
        finally:
            capture['on'] = False
            changes = []
            for pos, before in capture['touched'].items():
                now = (world.get(pos), world.facing.get(pos))
                if now != before:
                    changes.append((pos[0], pos[1], pos[2], now[0], now[1], before[0], before[1]))
                    state['recent'][pos] = (before, time.monotonic())
            if changes:
                client.send_blocks(changes, code=code)

    def wrap(method):
        def wrapper(*args, **kwargs):
            return run_captured(lambda: method(*args, **kwargs))
        return wrapper

    for name_ in ('_place', '_break', '_use'):
        setattr(game.interaction, name_, wrap(getattr(game.interaction, name_)))

    def apply_block(pos, name_, facing_):
        """Make a block the way the server says (it is not sent back). The computer that runs the world lets the neighbours react."""
        current = world.get(pos)
        if current == name_ and world.facing.get(pos) == facing_:
            return
        state['skip'].add(pos)
        try:
            notify = state['authority']
            if current is not None:
                world.remove(pos, notify=notify)
            if name_ is not None:
                world.place(pos, name_, facing_, notify=notify)
        finally:
            state['skip'].discard(pos)

    # ---- chests are shared when somebody closes one ----------------------------------------------------------------------------------
    def chest_to_world(x, y, z, items):
        stacks = [Stack(i[0], i[1], i[2]) if i else None for i in items]
        existing = world.chests.get((x, y, z))
        if existing is not None:
            existing[:] = stacks                              # (in place: a chest that is open right now shows it)
        else:
            world.chests[(x, y, z)] = stacks

    for x, y, z, items in info.get('chests', []):
        chest_to_world(x, y, z, items)
    real_open_chest, real_close = game.ui.open_chest, game.ui.close

    def open_chest(position):
        state['open_chest'] = position
        return real_open_chest(position)

    def close_ui():
        position, state['open_chest'] = state['open_chest'], None
        real_close()
        if position is not None and position in world.chests:
            items = [[s.name, s.count, s.damage] if s else None for s in world.chests[position]]
            client.send_chest(position[0], position[1], position[2], items)

    game.ui.open_chest, game.ui.close = open_chest, close_ui

    # ---- one computer runs the world's water, falling sand, fire and redstone for everybody ---------------------------------------------
    sims = [(game.fluids, 'update'), (game.falling, 'update'), (game.fire, 'update'), (game.redstone, 'update'), (game.plants, 'update'),
            (game.tnt, 'update')]
    originals = {id(obj): getattr(obj, attr) for obj, attr in sims}

    def set_authority(on):
        state['authority'] = on
        for obj, attr in sims:
            setattr(obj, attr, originals[id(obj)] if on else (lambda dt: None))
        if on and game.falling.check not in world.listeners:
            world.listeners.append(game.falling.check)
        if not on and game.falling.check in world.listeners:
            world.listeners.remove(game.falling.check)
        state['simbuf'].clear()
        for mob in (list(animals['puppets'].values()) if on else real_mobs()):      # (animals are now yours to run, or somebody else's)
            game.mobs.remove(mob)
        animals['puppets'].clear()
        animals['ids'].clear()

    Puppet = make_puppet_class()
    animals = {'puppets': {}, 'ids': {}, 'next': 1, 'killer': None, 'spawn_timer': 2.0, 'snap_timer': 0.0}
    real_drop = game.dropped.drop

    def drop_proxy(stack, position, *args, **kwargs):
        if animals['killer'] is not None:                                 # (what an animal dropped goes to the player who killed it)
            client.send_loot(animals['killer'], stack.name, stack.count)
            return None
        return real_drop(stack, position, *args, **kwargs)

    game.dropped.drop = drop_proxy

    def real_mobs():
        return [m for m in game.mobs.mobs if not isinstance(m, (Remote, Puppet))]

    def everyone():
        return [(game.player.x, game.player.z)] + [(r.x, r.z) for r in remotes.values()]

    def run_animals(dt):
        """(only the computer that runs the world) animals appear near every player, and what they do goes to everybody."""
        import random
        animals['spawn_timer'] -= dt
        if animals['spawn_timer'] <= 0:
            animals['spawn_timer'] = 4.0
            where = everyone()
            for px, pz in where:
                near = sum(1 for m in real_mobs() if math.hypot(m.x - px, m.z - pz) < 70)
                if near < 8:
                    for _ in range(8):                                     # (not every spot is grass in the open: try a few)
                        angle, distance = random.uniform(0, 2 * math.pi), random.uniform(14, 44)
                        if game.mobs._try_spawn_animal(int(px + math.cos(angle) * distance), int(pz + math.sin(angle) * distance)):
                            break
            for mob in real_mobs():                                        # (ones left far behind everybody go away)
                if all(math.hypot(mob.x - px, mob.z - pz) > 120 for px, pz in where):
                    game.mobs.remove(mob)
        animals['snap_timer'] -= dt
        if animals['snap_timer'] <= 0:
            animals['snap_timer'] = 0.2
            entries, animals['ids'] = [], {}
            for mob in real_mobs()[:200]:
                if not hasattr(mob, 'net_id'):
                    mob.net_id, animals['next'] = animals['next'], animals['next'] + 1
                animals['ids'][mob.net_id] = mob
                entries.append([mob.net_id, mob.kind.name, round(mob.x, 2), round(mob.y, 2), round(mob.z, 2), round(mob.rotation_y, 0),
                                1 if mob.moving else 0, max(0, round(mob.health))])
            client.send_mobs(entries)

    def show_animals(entries):
        """(everybody else) show the animals the world runner sent; the ones it no longer lists go away."""
        from mobtypes import TYPES
        seen = set()
        for entry in entries:
            ident = entry[0]
            seen.add(ident)
            puppet = animals['puppets'].get(ident)
            if puppet is None and entry[1] in TYPES:
                puppet = Puppet(game.mobs, TYPES[entry[1]], entry, client.send_mobhit)
                animals['puppets'][ident] = puppet
                game.mobs.mobs.append(puppet)
            if puppet is not None:
                puppet.goal, puppet.goal_yaw, puppet.walking_now = (entry[2], entry[3], entry[4]), entry[5], bool(entry[6])
        for ident in [i for i in animals['puppets'] if i not in seen]:
            game.mobs.remove(animals['puppets'].pop(ident))

    def hit_animal(message):
        mob = animals['ids'].get(message['id'])
        if mob is not None and mob in game.mobs.mobs and mob.health > 0:
            animals['killer'] = message['by']
            try:
                mob.hurt(tuple(message['pos']), damage=message['dmg'])
            finally:
                animals['killer'] = None

    set_authority(False)

    def flush_sim():
        buffered, state['simbuf'] = state['simbuf'], {}
        changes = []
        for pos, before in buffered.items():
            now = (world.get(pos), world.facing.get(pos))
            if now != before:
                changes.append((pos[0], pos[1], pos[2], now[0], now[1], before[0], before[1]))
        if changes:
            client.send_sim(changes)

    # ---- plots: name tags, who is where, and the code prompt that builds inside your plot --------------------------------------------
    from gameconsole import GameConsole
    from livecode import Session
    import pycraft

    class Current:
        """The completer of whichever code session is in use (it changes when you get a plot)."""

        def __getattr__(self, attribute):
            return getattr(state['session'].completer, attribute)

    def make_session(plot_info):
        if plot_info is None:
            width = depth = 8
            origin = (0, GROUND + 1, 0)
        else:
            width, depth = plot_info['x2'] - plot_info['x1'] + 1, plot_info['z2'] - plot_info['z1'] + 1
            origin = (plot_info['x1'], GROUND + 1, plot_info['z1'])
        plot = pycraft.plot(min(width, 256), CODE_HEIGHT, min(depth, 256))
        plot._game, plot._origin, plot._networked = game, origin, True
        plot._runtime.update(queue=[], closed=False, gallery=None, name=None, enter_state={}, timers={}, weather=None)
        if plot_info is None:
            plot._wrap_call = lambda function: game.message('You need a plot to build with code: type /claim in the chat.', 4)
        else:
            plot._wrap_call = lambda function: run_captured(function, code=True)
        session = Session(plot, delay=2)
        session.lan_plot = plot_info['id'] if plot_info else None
        return session

    def switch_session(plot_info):
        state['session'] = make_session(plot_info)
        state['code_plot'] = plot_info['id'] if plot_info else None

    def feed(line):
        """What is typed in the code prompt (a teacher can also say `plot 3` to work in another plot)."""
        text = line.strip()
        if state['teacher'] and text.lower().startswith('plot ') and text[5:].strip().isdigit():
            plot_info = next((p for p in state['layout'].to_json()['plots'] if p['id'] == int(text[5:])), None)
            if plot_info is None:
                print(f'There is no plot {text[5:].strip()}.')
            else:
                switch_session(plot_info)
                print(f"Your code now builds in plot {plot_info['id']}.")
            return
        if text:
            client.send_code(text[:200])
        state['session'].feed(line)

    switch_session(None)
    game.console = GameConsole(game, feed, lambda: state['session'].more_prompt if state['session'].__dict__.get('_buffer')
                               else state['session'].prompt, Current(),
                               lambda: state['session'].completer.indent_for(state['session'].__dict__.get('_buffer')),
                               lambda text: state['session'].needs_more(text),
                               title='Code  (builds in your plot. Enter runs, Tab completes, Shift+Enter new line, Esc closes)')

    def draw_tags():
        from ursina import Text, destroy
        for entity in state['tags']:
            destroy(entity)
        state['tags'] = []
        for plot_info in state['layout'].to_json()['plots']:
            cx = (plot_info['x1'] + plot_info['x2']) / 2
            label = f"Plot {plot_info['id']}\n{plot_info['owner'] or '(free: /claim)'}"
            state['tags'].append(Text(label, parent=scene, position=(cx, GROUND + 9, plot_info['z1'] - 1), billboard=True, scale=22,
                                      origin=(0, 0), color=color.yellow if plot_info['owner'] else color.white))

    def set_plots(message):
        state['layout'] = Layout.from_json({'plots': message.get('plots', []), 'border': message.get('border'), 'spawn': None})
        draw_tags()
        mine = state['layout'].owner_of(client.name)
        wanted = mine.id if mine else None
        if wanted != state['code_plot'] and not (state['teacher'] and state['code_plot'] is not None):
            switch_session(mine.to_json() if mine else None)

    if info.get('plots'):
        set_plots(info['plots'])

    # ---- the teacher's panel and following a student -----------------------------------------------------------------------------------
    def follow(player_id):
        if player_id in remotes:
            state['follow'] = player_id
            client.chat('/mode spectator me')
            chat.add('Following a student: press X to stop.')

    panel = TeacherPanel(game, client.chat, follow)
    game.lan = type('Lan', (), {'state': state, 'panel': panel, 'client': client, 'remotes': remotes,
                                'switch_session': staticmethod(switch_session), 'set_authority': staticmethod(set_authority)})()

    # ---- what the server sends ----------------------------------------------------------------------------------------------------------
    def handle(message):
        kind = message['t']
        if kind == 'pos':
            remote = remotes.get(message['id'])
            if remote is not None:
                remote.goal = (message['x'], message['y'], message['z'])
                remote.goal_yaw = message.get('yaw', 0.0)
                remote.goal_pitch = message.get('pitch', 0.0)
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
            if state['follow'] == message['id']:
                state['follow'] = None
        elif kind == 'blocks':
            for entry in message['c']:
                apply_block((entry[0], entry[1], entry[2]), entry[3], entry[4])
        elif kind == 'reject':
            for x, y, z in message['c']:
                before = state['recent'].pop((x, y, z), None)
                if before is not None:
                    apply_block((x, y, z), *before[0])
            game.message(message.get('why') or 'You cannot build here right now.', 3)
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
            game.message('You are a teacher. Press P for the class panel.' if state['teacher'] else 'You are a student again.', 5)
        elif kind == 'roster':
            panel.update_roster(message['players'], message.get('locked', False), message.get('chat', True))
            for entry in message['players']:
                remote = remotes.get(entry['id'])
                if remote is not None:
                    remote.set_teacher(entry['teacher'])
        elif kind == 'plots':
            set_plots(message)
        elif kind == 'authority':
            set_authority(bool(message.get('on')))
        elif kind == 'chest':
            chest_to_world(message['x'], message['y'], message['z'], message['items'])
        elif kind == 'mobs':
            if not state['authority']:
                show_animals(message['c'])
        elif kind == 'mobhit':
            if state['authority']:
                hit_animal(message)
        elif kind == 'loot':
            game.inventory.add(message['name'], message['count'])
            chat.add(f"You got {message['count']} {message['name'].replace('_', ' ')}.")
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
        session = state['session']
        if session is not None:
            session.plot._run_queue(dt)                       # (what your code builds, a few blocks each frame)
        if state['authority']:
            flush_sim()
            run_animals(dt)
        # following a student: stand behind them and look where they look
        if state['follow'] in remotes:
            remote = remotes[state['follow']]
            behind = math.radians(remote.rotation_y + 180)
            game.player.position = (remote.x + math.sin(behind) * 3.0, remote.y + 1.6, remote.z + math.cos(behind) * 3.0)
            game.player.rotation_y = remote.rotation_y
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
            plot = state['layout'].plot_at(round(player.x), round(player.z))
            ident = plot.id if plot else None
            if ident != state['in_plot']:
                state['in_plot'] = ident
                if plot is not None:
                    game.message(f"Plot {plot.id}: {plot.owner or 'free (type /claim)'}", 2)
        chat.update()
        chat.text.enabled = not (panel.is_open or console_open())            # (the chat lines would be in the way)
        panel.fit()
        if game.console is not None:
            game.console.update(dt)
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
        if panel.is_open:
            panel.input(key)
            return
        if console_open():
            game.input(key)
            return
        if not game.ui.active and not game.menu.is_open and not game.menu.just_closed() and not game.player.dead:
            if key == 't':
                chat.open('', 't')
                return
            if key == '/':
                chat.open('/', '/')
                return
            if key == 'c' and state['session'] is not None:
                game.console.open('c')
                return
            if key == 'p' and state['teacher']:
                panel.open()
                return
            if key == 'x' and state['follow'] is not None:
                state['follow'] = None
                client.chat('/mode creative me')
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
