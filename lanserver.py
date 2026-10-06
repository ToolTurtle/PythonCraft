"""lanserver - the classroom (LAN) game server. It holds the world, the rules and who is a teacher. It has no game window.

    python3 lan.py host                    start a server (see lan.py for the options)

Anyone can be a teacher, wherever they sit: a player types /teacher PIN in the game. The server checks the PIN (kept only as a
salted hash, with limits on guessing) and then lets that player change game modes, freeze, lock building, mute, kick, teleport,
roll back a player's changes, look after the student plots and make announcements. The server itself is not special: it can be run
by one computer while the teacher plays on another.

Everything a player sends is checked here (see netproto.py); the server never runs anything a player sends."""
import asyncio
import base64
import collections
import json
import re
import threading
import time
from pathlib import Path

import netproto as proto
from classlayout import GROUND, GROUND_BLOCK, Layout
from netproto import Bucket, ProtocolError

TOGGLES = {'oak_door_b', 'oak_door_t', 'lever', 'lever_on', 'stone_button', 'bed', 'oak_trapdoor'}
DISCOVERY_PORT = proto.DEFAULT_PORT + 1
STUDENT_COMMANDS = {'claim', 'home', 'plots'}
HISTORY_LIMIT = 20000
MOD_CHUNK = 24000
HELP_STUDENT = ('/list  who is here   /teacher PIN  become a teacher   /help\n'
                '/claim  get a plot   /home  go to your plot   /plots  who has which plot')
HELP_TEACHER = ('/mode MODE [who|all]  adventure, survival, creative or spectator   /default MODE  for new players\n'
                '/freeze [who|all]  /unfreeze [who|all]   /lock  /unlock  building for everyone   /code on|off [who|all]  code building\n'
                '/mute who|all  /unmute who|all   /chat on|off  all students   /kick who [why]   /tp who  /bring who|all  /goto N\n'
                '/history [who]  who changed what   /undo who 5m|30s|20|all  put back what they changed   /code who  what they typed\n'
                '/assign who N  /unassign who|N  /claim   /plots   /say text  announce   /time day|night|noon|sunrise|sunset\n'
                '/plotsize W [D] [clear]  all plots that size   /resize N W [D] [clear]  one plot   /addplot  one more plot\n'
                '/list   /teacher off')


def plot_area(bounds):
    """A stand-in plot for a rectangle (x1, z1, x2, z2): something that can say whether a spot is inside it."""
    from classlayout import Plot
    return Plot(0, *bounds)


class NeedMods(Exception):
    """The player's mods differ, but the server can offer the .pcmod files they are missing."""


class WorldState:
    """The world as the server knows it: how it starts (a seed or a built world), every block players changed, the plots."""

    def __init__(self, seed=0, title='Class world', flat_spawn=None, changes=None, layout=None, chests=None):
        self.seed, self.title, self.flat_spawn = int(seed), str(title), flat_spawn
        self.changes = dict(changes or {})                # (x, y, z) -> (block name or None, facing or None)
        self.layout = layout                              # a Layout (plots and border) or None
        self.chests = dict(chests or {})                  # (x, y, z) -> 27 slots of None or [item, count, damage]
        self.dirty = False

    def to_json(self):
        return {'format': 'lanworld', 'seed': self.seed, 'title': self.title, 'flat_spawn': self.flat_spawn,
                'changes': [[x, y, z, name, facing] for (x, y, z), (name, facing) in self.changes.items()],
                'layout': self.layout.to_json() if self.layout else None,
                'chests': [[x, y, z, items] for (x, y, z), items in self.chests.items()]}

    @classmethod
    def from_json(cls, data):
        changes = {}
        for x, y, z, name, facing in data.get('changes', []):
            changes[(x, y, z)] = (name, facing)
        layout = Layout.from_json(data['layout']) if data.get('layout') else None
        chests = {(x, y, z): items for x, y, z, items in data.get('chests', [])}
        return cls(data.get('seed', 0), data.get('title', 'Class world'), data.get('flat_spawn'), changes, layout, chests)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.to_json()))
        temporary.replace(path)
        self.dirty = False

    @classmethod
    def load(cls, path):
        return cls.from_json(json.loads(Path(path).read_text()))


class Conn:
    """One connected player."""

    def __init__(self, ident, writer, address):
        self.id, self.writer, self.address = ident, writer, address
        self.name = 'Player'
        self.teacher = False
        self.mode = 'adventure'
        self.frozen = self.muted = False
        self.can_code = True
        self.pos = None                                   # (x, y, z) as last reported
        self.yaw = self.pitch = 0.0
        self.joined = False
        self.bad = 0                                      # messages that were not allowed
        self.pin_failures, self.pin_locked_until = 0, 0.0
        self.mod_requests = 0
        self.code_log = collections.deque(maxlen=20)      # (time, what they typed in the code prompt)
        self.msg_bucket, self.pos_bucket = Bucket(120, 240), Bucket(40, 60)
        self.block_bucket, self.chat_bucket = Bucket(300, 600), Bucket(1.0, 5)
        self.hit_bucket = Bucket(8, 16)

    def info(self):
        x, y, z = self.pos or (0, 0, 0)
        return {'id': self.id, 'name': self.name, 'teacher': self.teacher, 'mode': self.mode, 'x': x, 'y': y, 'z': z,
                'yaw': self.yaw, 'pitch': self.pitch}


class LanServer:
    def __init__(self, world, pin=None, code=None, host='0.0.0.0', port=0, default_mode='adventure', max_players=40,
                 save_path=None, known_blocks=None, name='PythonCraft class', mods_dir=None, chat_log=None, badwords=()):
        import blocks
        self.world = world
        self.pin = str(pin) if pin else proto.make_pin()
        if len(self.pin) < 4:
            raise ValueError('The teacher PIN needs at least 4 characters.')
        self.pin_salt, self.pin_hash = proto.hash_pin(self.pin)
        self.code = code or proto.make_code()
        self.host, self.port = host, port
        if default_mode not in proto.MODES:
            raise ValueError(f'default_mode must be one of {", ".join(proto.MODES)}.')
        self.default_mode, self.max_players, self.save_path = default_mode, max_players, save_path
        self.known_blocks = set(known_blocks) if known_blocks is not None else set(blocks.BLOCKS)
        self.blocks_hash = proto.blocks_hash(known_blocks if known_blocks is not None else list(blocks.BLOCKS))
        import items as _items
        import mobtypes
        self.known_items = set(_items.ITEMS)
        self.known_mobs = set(mobtypes.TYPES)
        self.name = name
        self.players = {}                                 # id -> Conn
        self.next_id = 1
        self.building_locked = False
        self.chat_locked = False
        self.time_ticks = None
        self.auth_failures = []                           # times of wrong PINs (all players together)
        self.auth_locked_until = 0.0
        self.history = []                                 # what players changed: dicts, oldest first (for /history and /undo)
        self.authority = None                             # the player whose computer runs water, falling sand... for everybody
        self.chat_log = Path(chat_log) if chat_log else None
        self.set_badwords(badwords)
        self.mods = self._scan_mods(mods_dir)
        self.loop = self.server = self.thread = self._stop = None
        self.log_lines = []

    # ---- running ---------------------------------------------------------------------------------------------------------------

    def start(self):
        """Run the server on its own thread. Returns when it is listening (self.port is then the real port)."""
        ready = threading.Event()
        errors = []

        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self._serve(ready))
            except Exception as error:                    # (could not start: tell the caller)
                errors.append(error)
                ready.set()
            finally:
                self.loop.close()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        ready.wait(10)
        if errors:
            raise errors[0]
        return self

    async def _serve(self, ready):
        self._stop = asyncio.Event()
        self.server = await asyncio.start_server(self._handle, self.host, self.port, limit=proto.MAX_LINE)
        self.port = self.server.sockets[0].getsockname()[1]
        tasks = [asyncio.ensure_future(self._autosave()), asyncio.ensure_future(self._roster_loop())]
        self._start_discovery()
        ready.set()
        await self._stop.wait()
        for task in tasks:
            task.cancel()
        if self._udp is not None:
            self.loop.remove_reader(self._udp.fileno())
        for conn in list(self.players.values()):
            conn.writer.close()
        self.server.close()
        await self.server.wait_closed()
        self.save()

    def stop(self):
        if self.loop is not None and self._stop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._stop.set)
        if self.thread is not None:
            self.thread.join(5)
        self._stop_discovery()

    def save(self):
        if self.save_path and self.world.dirty:
            self.world.save(self.save_path)

    async def _autosave(self):
        while True:
            await asyncio.sleep(30)
            self.save()

    async def _roster_loop(self):
        while True:
            await asyncio.sleep(4)
            self.send_roster()

    def log(self, text):
        self.log_lines.append(text)
        del self.log_lines[:-200]

    def chatlog(self, text):
        """One line in the chat log file (if there is one): what was said, who joined, what teachers did."""
        if self.chat_log is None:
            return
        try:
            self.chat_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.chat_log, 'a', encoding='utf-8') as handle:
                handle.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {text}\n')
        except OSError:
            pass

    # ---- finding the server on the network (a broadcast answer: name, port and player count; never the room code) ---------------

    def _start_discovery(self):
        import socket
        self._udp = None
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', DISCOVERY_PORT))
            sock.setblocking(False)
            self.loop.add_reader(sock.fileno(), self._answer_discovery)
            self._udp = sock
        except OSError:
            sock.close()                                  # (another server here already answers: fine)

    def _answer_discovery(self):
        try:
            data, address = self._udp.recvfrom(64)
            if data.strip() == b'pycraft-find' and proto.is_local_address(address[0]):
                reply = {'name': self.name, 'port': self.port, 'players': len(self.players), 'v': proto.VERSION}
                self._udp.sendto(json.dumps(reply).encode(), address)
        except OSError:
            pass

    def _stop_discovery(self):
        if getattr(self, '_udp', None) is not None:
            try:
                self._udp.close()
            except OSError:
                pass
            self._udp = None

    # ---- word filter and mods on offer ------------------------------------------------------------------------------------------------

    def set_badwords(self, words):
        words = sorted({w.strip().lower() for w in words if w and w.strip() and not w.strip().startswith('#')}, key=len, reverse=True)
        self._filter = re.compile(r'\b(' + '|'.join(re.escape(w) for w in words) + r')\b', re.IGNORECASE) if words else None

    def filter_text(self, text):
        """(text with the filtered words starred out, whether anything was filtered)"""
        if self._filter is None:
            return text, False
        out, count = self._filter.subn(lambda m: '*' * len(m.group(0)), text)
        return out, count > 0

    def _scan_mods(self, mods_dir):
        """The .pcmod files in the mods folder, checked (they hold data only), that players missing them can download."""
        found = []
        if not mods_dir or not Path(mods_dir).is_dir():
            return found
        import mods
        for path in sorted(Path(mods_dir).glob('*.pcmod')):
            try:
                spec, _files, sha = mods.read_pcmod(path)
            except mods.ModFileError:
                continue
            found.append({'name': spec['name'], 'sha': sha, 'size': path.stat().st_size, 'path': str(path)})
        return found

    # ---- talking to players -------------------------------------------------------------------------------------------------------

    def send(self, conn, message):
        try:
            if conn.writer.is_closing():
                return
            if conn.writer.transport.get_write_buffer_size() > 4_000_000:        # (a player who cannot keep up is dropped)
                conn.writer.close()
                return
            conn.writer.write(proto.encode(message))
        except (ConnectionError, ProtocolError, RuntimeError, OSError):
            pass

    def broadcast(self, message, skip=None):
        for conn in list(self.players.values()):
            if conn is not skip and conn.joined:
                self.send(conn, message)

    def tell(self, conn, text):
        self.send(conn, {'t': 'say', 'm': text})

    def tell_teachers(self, text):
        for conn in list(self.players.values()):
            if conn.teacher:
                self.tell(conn, text)

    def locked_for(self, conn):
        """Can this player not build by hand right now?"""
        if conn.frozen or conn.mode in ('adventure', 'spectator'):
            return True
        return self.building_locked and not conn.teacher

    def send_mode(self, conn):
        self.send(conn, {'t': 'mode', 'mode': conn.mode, 'locked': self.locked_for(conn), 'frozen': conn.frozen})

    def plots_message(self):
        layout = self.world.layout
        if layout is None:
            return {'t': 'plots', 'plots': [], 'border': None}
        return {'t': 'plots', 'plots': [p.to_json() for p in layout.plots], 'border': list(layout.border) if layout.border else None}

    def send_plots(self):
        self.broadcast(self.plots_message())

    def roster(self):
        layout, rows = self.world.layout, []
        for conn in self.players.values():
            plot = layout.owner_of(conn.name) if layout else None
            rows.append({'id': conn.id, 'name': conn.name, 'teacher': conn.teacher, 'mode': conn.mode, 'frozen': conn.frozen,
                         'muted': conn.muted, 'code': conn.can_code, 'plot': plot.id if plot else None,
                         'last': conn.code_log[-1][1][:60] if conn.code_log else ''})
        return rows

    def send_roster(self):
        """The class list for every teacher (it feeds the teacher panel in the game)."""
        if any(c.teacher for c in self.players.values()):
            message = {'t': 'roster', 'players': self.roster(), 'locked': self.building_locked, 'chat': not self.chat_locked}
            for conn in list(self.players.values()):
                if conn.teacher:
                    self.send(conn, message)

    def _elect_authority(self):
        """One player's computer runs water, falling sand, fire and redstone for everybody (the others only watch)."""
        wanted = min(self.players) if self.players else None
        if wanted == self.authority:
            return
        old = self.players.get(self.authority)
        self.authority = wanted
        if old is not None:
            self.send(old, {'t': 'authority', 'on': False})
        if wanted is not None:
            self.send(self.players[wanted], {'t': 'authority', 'on': True})

    # ---- a player connecting ---------------------------------------------------------------------------------------------------------

    async def _handle(self, reader, writer):
        address = (writer.get_extra_info('peername') or ('?', 0))[0]
        conn = Conn(self.next_id, writer, address)
        self.next_id += 1
        try:
            if not proto.is_local_address(address):
                self.send(conn, {'t': 'error', 'm': 'This game is only for computers on the same network.'})
                return
            if len(self.players) >= self.max_players:
                self.send(conn, {'t': 'error', 'm': 'The class is full.'})
                return
            deadline = time.monotonic() + 180
            while not conn.joined:                         # (hello, and perhaps downloading mods first)
                try:
                    line = await asyncio.wait_for(reader.readline(), max(1, min(15, deadline - time.monotonic())))
                    if time.monotonic() > deadline or not line:
                        return
                    message = proto.decode(line)
                    if message['t'] == 'hello':
                        self._hello(conn, message)
                    elif message['t'] == 'getmod':
                        self._send_mod(conn, message)
                    else:
                        raise ProtocolError('Say hello first.')
                except NeedMods as needed:
                    self.send(conn, {'t': 'needmods', 'mods': needed.args[0]})
                except (asyncio.TimeoutError, asyncio.LimitOverrunError, ValueError, ProtocolError) as error:
                    self.send(conn, {'t': 'error', 'm': str(error) if isinstance(error, ProtocolError) else 'Say hello first.'})
                    return
            while True:
                try:
                    line = await reader.readline()
                except (asyncio.LimitOverrunError, ValueError):
                    self.send(conn, {'t': 'kick', 'm': 'You sent a message that was too big.'})
                    break
                if not line:
                    break
                if not conn.msg_bucket.take():
                    conn.bad += 1
                    if conn.bad > 20:
                        self.send(conn, {'t': 'kick', 'm': 'Too many messages.'})
                        break
                    continue
                try:
                    self._message(conn, proto.decode(line))
                except ProtocolError:
                    conn.bad += 1
                    if conn.bad >= 10:
                        self.send(conn, {'t': 'kick', 'm': 'Too many messages that were not allowed.'})
                        break
                if writer.is_closing():
                    break
        except (ConnectionError, OSError, asyncio.IncompleteReadError):
            pass
        finally:
            self._leave(conn)
            try:
                writer.close()
            except (OSError, RuntimeError):
                pass

    def _hello(self, conn, hello):
        if hello.get('v') != proto.VERSION:
            raise ProtocolError('This game is a different version. Update PythonCraft.')
        if not proto.same_code(hello.get('code', ''), self.code):
            raise ProtocolError('That room code is not right.')
        if hello.get('blocks') != self.blocks_hash:
            if self.mods:
                raise NeedMods([{'name': m['name'], 'sha': m['sha'], 'size': m['size']} for m in self.mods])
            raise ProtocolError('Your mods are not the same as the host\'s (different blocks). Install the same .pcmod files.')
        conn.name = proto.clean_name(hello.get('name'), [c.name for c in self.players.values()])
        conn.mode = self.default_mode
        self.players[conn.id] = conn
        conn.joined = True
        world, layout = self.world, self.world.layout
        spawn = list(layout.spawn) if layout and layout.spawn else None
        self.send(conn, {'t': 'welcome', 'id': conn.id, 'name': conn.name, 'seed': world.seed, 'title': world.title,
                         'flat_spawn': world.flat_spawn, 'spawn': spawn, 'mode': conn.mode, 'locked': self.locked_for(conn),
                         'time': self.time_ticks, 'server': self.name, 'chat': not self.chat_locked,
                         'players': [c.info() for c in self.players.values() if c is not conn],
                         'count': len(world.changes)})
        changes = [[x, y, z, name, facing] for (x, y, z), (name, facing) in world.changes.items()]
        for start in range(0, len(changes), 500):
            self.send(conn, {'t': 'world', 'c': changes[start:start + 500]})
        if world.chests:
            self.send(conn, {'t': 'chests', 'c': [[x, y, z, items] for (x, y, z), items in world.chests.items()]})
        self.send(conn, self.plots_message())
        self.send(conn, {'t': 'ready'})
        self._elect_authority()
        self.broadcast({'t': 'join', 'p': conn.info()}, skip=conn)
        self.broadcast({'t': 'say', 'm': f'{conn.name} joined.'}, skip=conn)
        if layout and layout.plots and layout.auto_claim and layout.owner_of(conn.name) is None:
            self._give_plot(conn)                                          # (plot mode: everyone who joins gets a plot of their own)
        mine = layout.owner_of(conn.name) if layout else None
        self.tell(conn, 'Welcome! /help shows the commands. A teacher types /teacher PIN.'
                  + (f' Your plot is number {mine.id}: /home takes you there.' if mine else
                     (' Type /claim to get a plot to build in.' if layout and layout.plots else '')))
        self.log(f'{conn.name} joined from {conn.address}')
        self.chatlog(f'* {conn.name} joined')
        self.send_roster()

    def _send_mod(self, conn, message):
        """A player is missing a mod and asks for it (only the .pcmod files this server offers, which hold data only)."""
        conn.mod_requests += 1
        if conn.mod_requests > 30:
            raise ProtocolError('too many downloads')
        sha = str(message.get('sha', ''))
        offered = next((m for m in self.mods if m['sha'] == sha), None)
        if offered is None:
            raise ProtocolError('that mod is not on offer')
        data = Path(offered['path']).read_bytes()
        chunks = [data[i:i + MOD_CHUNK] for i in range(0, len(data), MOD_CHUNK)] or [b'']
        for number, chunk in enumerate(chunks):
            self.send(conn, {'t': 'modfile', 'sha': sha, 'i': number, 'of': len(chunks), 'data': base64.b64encode(chunk).decode()})

    def _leave(self, conn):
        if self.players.pop(conn.id, None) is not None and conn.joined:
            self.broadcast({'t': 'leave', 'id': conn.id})
            self.broadcast({'t': 'say', 'm': f'{conn.name} left.'})
            self.log(f'{conn.name} left')
            self.chatlog(f'* {conn.name} left')
            self._elect_authority()
            self.send_roster()

    # ---- what players send --------------------------------------------------------------------------------------------------------------

    def _message(self, conn, message):
        kind = message['t']
        if kind == 'pos':
            self._position(conn, message)
        elif kind == 'blocks':
            self._blocks(conn, message)
        elif kind == 'sim':
            self._sim(conn, message)
        elif kind == 'chat':
            self._chat(conn, proto.clean_chat(message.get('m', '')))
        elif kind == 'mobs':
            self._mobs(conn, message)
        elif kind == 'mobhit':
            self._mobhit(conn, message)
        elif kind == 'loot':
            self._loot(conn, message)
        elif kind == 'chest':
            self._chest(conn, message)
        elif kind == 'code':
            text = proto.clean_chat(message.get('m', ''))
            if text:
                conn.code_log.append((time.time(), text))
        elif kind == 'roster':
            if conn.teacher:
                self.send_roster()
        elif kind == 'ping':
            self.send(conn, {'t': 'pong'})
        else:
            raise ProtocolError('unknown message')

    def _position(self, conn, message):
        if not conn.pos_bucket.take():
            return
        x, y, z = (proto.number(message.get('x')), proto.number(message.get('y'), -10 ** 7, 10 ** 7), proto.number(message.get('z')))
        y = max(-64.0, min(1000.0, y))                               # (a player who falls out of the world is shown at the bottom, not refused)
        yaw, pitch = proto.number(message.get('yaw', 0), -100000, 100000), proto.number(message.get('pitch', 0), -100000, 100000)
        moving = bool(message.get('v', False))
        if conn.frozen:
            return
        layout = self.world.layout
        if layout and layout.border and not conn.teacher and not layout.inside_border(x, z):
            bx1, bz1, bx2, bz2 = layout.border                       # (back inside the border: the edge is as far as anyone goes)
            self.send(conn, {'t': 'tp', 'x': min(max(x, bx1 + 1), bx2 - 1), 'y': y, 'z': min(max(z, bz1 + 1), bz2 - 1)})
            self.tell(conn, 'That is the edge of the class world.')
            return
        conn.pos, conn.yaw, conn.pitch = (x, y, z), yaw, pitch
        self.broadcast({'t': 'pos', 'id': conn.id, 'x': x, 'y': y, 'z': z, 'yaw': yaw, 'pitch': pitch, 'v': moving}, skip=conn)

    def _blocks(self, conn, message):
        entries = message.get('c')
        if not isinstance(entries, list) or len(entries) > proto.MAX_BLOCKS_PER_MESSAGE:
            raise ProtocolError('too many block changes at once')
        by_code = bool(message.get('code'))
        if not conn.block_bucket.take(max(1, len(entries))):
            self.send(conn, {'t': 'reject', 'c': [e[:3] for e in entries if isinstance(e, list) and len(e) >= 3], 'why': 'Slow down a little.'})
            return
        accepted, refused, why = [], [], ''
        for entry in entries:
            pos, name, facing, previous = proto.block_change(entry, self.known_blocks)
            reason = self._why_not(conn, pos, name, by_code)
            if reason is None:
                accepted.append(list(entry[:5]))
                self._record(conn, pos, name, facing, previous, 'code' if by_code else 'hand')
            else:
                refused.append(list(pos))
                why = why or reason
        if accepted:
            self.world.dirty = True
            self.broadcast({'t': 'blocks', 'by': conn.id, 'c': accepted}, skip=conn)
        if refused:
            self.send(conn, {'t': 'reject', 'c': refused, 'why': why})

    def _record(self, conn, pos, name, facing, previous, via):
        """Keep a change: the world now has it, and /history and /undo can find it."""
        before = self.world.changes.get(pos) or previous                 # (what the server knew, else what the player saw)
        self.world.changes[pos] = (name, facing)
        self.history.append({'time': time.time(), 'who': conn.name, 'pos': pos, 'prev': before, 'new': (name, facing), 'via': via,
                             'undone': False})
        del self.history[:-HISTORY_LIMIT]

    def _why_not(self, conn, pos, name, by_code=False):
        """None if this player may make this change, else a short reason to show them."""
        if conn.frozen:
            return 'You are frozen.'
        if conn.mode == 'spectator':
            return 'You are only looking in spectator mode.'
        layout = self.world.layout
        if layout and layout.border and not conn.teacher and not layout.inside_border(pos[0], pos[2]):
            return 'That is outside the class world.'
        own = layout.owner_of(conn.name) if layout else None
        if by_code:
            if not conn.can_code and not conn.teacher:
                return 'Building with code is turned off for you.'
            if self.building_locked and not conn.teacher:
                return 'Building is locked.'
            if conn.teacher:
                return None
            if not layout or not layout.plots:                          # (a world without plots, as in live coding: code builds near you)
                if conn.pos is None or max(abs(pos[0] - conn.pos[0]), abs(pos[2] - conn.pos[2])) > 80 or abs(pos[1] - conn.pos[1]) > 80:
                    return 'Code builds near where you are standing.'
                return None
            if own is None:
                return 'You need a plot to build with code: type /claim.'
            if not own.contains(pos[0], pos[2]):
                return 'Code can only build inside your own plot.'
            return None
        if conn.pos is None or max(abs(pos[0] - conn.pos[0]), abs(pos[1] - conn.pos[1]), abs(pos[2] - conn.pos[2])) > 12:
            return 'That is too far away.'
        if conn.mode == 'adventure':
            return None if name in TOGGLES else 'You are in adventure mode: you cannot build.'
        if conn.teacher:
            return None
        if self.building_locked:
            return None if name in TOGGLES else 'Building is locked.'
        if layout and layout.plots and name not in TOGGLES:
            if own is None:
                return 'You need a plot to build in: type /claim.'
            if not own.contains(pos[0], pos[2]):
                other = layout.plot_at(pos[0], pos[2])
                return f"This is {other.owner}'s plot." if other and other.owner else 'You can only build in your own plot.'
        return None

    def _sim(self, conn, message):
        """The computer that runs the world's water, sand, fire and redstone reports what changed (nobody else may)."""
        if conn.id != self.authority:
            raise ProtocolError('not the one running the world')
        entries = message.get('c')
        if not isinstance(entries, list) or len(entries) > proto.MAX_BLOCKS_PER_MESSAGE * 4:
            raise ProtocolError('too many changes at once')
        accepted = []
        for entry in entries:
            try:
                pos, name, facing, _previous = proto.block_change(entry, self.known_blocks)
            except ProtocolError:
                continue                                              # (the world sometimes changes at its very edge: not the sender's fault)
            self.world.changes[pos] = (name, facing)
            accepted.append(list(entry[:5]))
        if accepted:
            self.world.dirty = True
            self.broadcast({'t': 'blocks', 'by': 0, 'sim': True, 'c': accepted}, skip=conn)

    def _mobs(self, conn, message):
        """The computer that runs the world says where the animals are (nobody else may); everybody else shows them."""
        if conn.id != self.authority:
            raise ProtocolError('not the one running the world')
        entries = message.get('c')
        if not isinstance(entries, list) or len(entries) > 200:
            raise ProtocolError('too many creatures')
        clean = []
        for entry in entries:                                        # (a creature that fell out of the world, or one this server does not know,
            try:                                                     # is left out: that is not the sender's fault and must never get them removed)
                if not isinstance(entry, (list, tuple)) or len(entry) != 8 or not isinstance(entry[1], str) or entry[1] not in self.known_mobs:
                    continue
                clean.append([proto.number(entry[0], 0, 10 ** 9, integer=True), entry[1], proto.number(entry[2]), proto.number(entry[3], -64, 1000),
                              proto.number(entry[4]), proto.number(entry[5], -100000, 100000), 1 if entry[6] else 0,
                              proto.number(entry[7], 0, 5000)])
            except ProtocolError:
                continue
        if clean or not entries:
            self.broadcast({'t': 'mobs', 'c': clean}, skip=conn)

    def _mobhit(self, conn, message):
        """A player hit a creature that the authority runs: pass it to the authority (who works out what happens)."""
        if not conn.hit_bucket.take() or conn.frozen or conn.mode == 'spectator' or conn.pos is None:
            return
        ident, damage = proto.number(message.get('id'), 0, 10 ** 9, integer=True), proto.number(message.get('dmg'), 0, 30)
        authority = self.players.get(self.authority)
        if authority is not None and authority is not conn:
            self.send(authority, {'t': 'mobhit', 'by': conn.id, 'id': ident, 'dmg': damage, 'pos': list(conn.pos)})

    def _loot(self, conn, message):
        """What a creature dropped goes straight to the player who killed it."""
        if conn.id != self.authority:
            raise ProtocolError('not the one running the world')
        target = self.players.get(proto.number(message.get('to'), 0, 10 ** 9, integer=True))
        name = message.get('name')
        if target is None or not isinstance(name, str) or name not in self.known_items:
            return
        self.send(target, {'t': 'loot', 'name': name, 'count': proto.number(message.get('count', 1), 1, 64, integer=True)})

    def _chest(self, conn, message):
        pos = (proto.number(message.get('x'), integer=True), proto.number(message.get('y'), 0, proto.HEIGHT - 1, integer=True),
               proto.number(message.get('z'), integer=True))
        items = proto.chest_items(message.get('items'), self.known_items)
        if conn.frozen or conn.mode == 'spectator' or conn.pos is None:
            return
        if max(abs(pos[0] - conn.pos[0]), abs(pos[1] - conn.pos[1]), abs(pos[2] - conn.pos[2])) > 12:
            return
        if all(i is None for i in items):
            self.world.chests.pop(pos, None)
        else:
            self.world.chests[pos] = items
        self.world.dirty = True
        self.broadcast({'t': 'chest', 'x': pos[0], 'y': pos[1], 'z': pos[2], 'items': items}, skip=conn)

    def _chat(self, conn, text):
        if not text:
            return
        if not conn.chat_bucket.take():
            self.tell(conn, 'Slow down a little.')
            return
        if text.startswith('/'):
            replies = self.command(conn, text[1:])
            word = text.split()[0].lower()
            if conn.teacher and word != '/teacher':                       # (never write a PIN down, not even a wrong one)
                self.chatlog(f'* {conn.name} (teacher) used {word} {" ".join(text.split()[1:3])}'.rstrip())
            for line in replies:
                self.tell(conn, line)
            return
        if conn.muted:
            self.tell(conn, 'You are muted.')
            return
        if self.chat_locked and not conn.teacher:
            self.tell(conn, 'Chat is turned off right now.')
            return
        shown, flagged = (text, False) if conn.teacher else self.filter_text(text)
        if flagged:
            self.tell_teachers(f'[filtered] {conn.name} said: {text}')
            self.chatlog(f'{conn.name} [filtered]: {text}')
        else:
            self.chatlog(f'{conn.name}: {text}')
        self.broadcast({'t': 'chat', 'from': conn.name, 'teacher': conn.teacher, 'm': shown})
        self.log(f'{conn.name}: {shown}')

    # ---- commands: /teacher for everyone, the rest for teachers -----------------------------------------------------------------------

    def command(self, actor, line):
        """Run a command typed by a player (a Conn) or by the person running the server (actor=None). Returns lines to show them."""
        word, _, rest = line.strip().partition(' ')
        word, rest = word.lower(), rest.strip()
        is_teacher = actor is None or actor.teacher
        if word == 'help':
            return [HELP_STUDENT] + ([HELP_TEACHER] if is_teacher else [])
        if word == 'list':
            return [', '.join(f"{c.name}{' [teacher]' if c.teacher else ''} ({c.mode})" for c in self.players.values()) or 'Nobody yet.']
        if word == 'teacher':
            return self._teacher(actor, rest)
        handler = getattr(self, f'_cmd_{word}', None)
        if handler is None:
            return [f'I do not know /{word}. /help shows the commands.']
        if word not in STUDENT_COMMANDS and not is_teacher:
            return ['Only a teacher can do that. (A teacher types /teacher and the PIN.)']
        try:
            result = handler(actor, rest) or []
            self.send_roster()
            return result
        except ValueError as error:
            return [str(error)]

    def _teacher(self, conn, pin):
        if conn is None:
            return ['You are running the server: you already have teacher powers here.']
        if pin.lower() == 'off':
            conn.teacher = False
            self.send(conn, {'t': 'role', 'teacher': False})
            self.send_mode(conn)
            return ['You are not a teacher any more.']
        if conn.teacher:
            return ['You are already a teacher.']
        now = time.monotonic()
        if now < conn.pin_locked_until or now < self.auth_locked_until:
            return ['Too many wrong tries. Wait a minute.']
        if not pin or not proto.check_pin(pin, self.pin_salt, self.pin_hash):
            conn.pin_failures += 1
            self.auth_failures = [t for t in self.auth_failures if now - t < 300] + [now]
            if conn.pin_failures >= 5:
                conn.pin_locked_until, conn.pin_failures = now + 60, 0
            if len(self.auth_failures) >= 20:
                self.auth_locked_until = now + 300
            self.log(f'wrong teacher PIN from {conn.name}')
            return ['That is not the PIN.']
        conn.teacher, conn.pin_failures = True, 0
        conn.mode = 'creative'
        layout = self.world.layout
        mine = layout.owner_of(conn.name) if layout else None
        if mine is not None and layout.auto_claim and not self._built_in([mine]):
            mine.owner = None                                              # (a teacher builds anywhere: their empty plot goes back for a student)
            self.world.dirty = True
            self.send_plots()
        self.send(conn, {'t': 'role', 'teacher': True})
        self.send_mode(conn)
        self.broadcast({'t': 'say', 'm': f'{conn.name} is a teacher now.'})
        self.log(f'{conn.name} became a teacher')
        self.chatlog(f'* {conn.name} became a teacher')
        self.send_roster()
        return ['You are a teacher. /help shows what you can do. (You start in creative mode.)']

    def find(self, who, actor=None):
        """The players a word stands for: a name (or the start of one), 'all' (every student) or 'me'."""
        who = who.strip()
        if who.startswith('#') and who[1:].isdigit():                 # (#3: exactly player number 3, whatever their name looks like)
            found = self.players.get(int(who[1:]))
            if found is None:
                raise ValueError(f'There is nobody with number {who[1:]}.')
            return [found]
        if who.lower() == 'all':
            return [c for c in self.players.values() if not c.teacher]
        if who.lower() == 'me' and actor is not None:
            return [actor]
        matches = [c for c in self.players.values() if c.name.lower() == who.lower()]
        if not matches and who:
            matches = [c for c in self.players.values() if c.name.lower().startswith(who.lower())]
        if not matches:
            raise ValueError(f'There is nobody called {who!r}. /list shows who is here.' if who else 'Say who: a name, all or me.')
        if len(matches) > 1:
            raise ValueError(f'{who!r} could be {", ".join(c.name for c in matches)}: type more of the name.')
        return matches

    def _cmd_mode(self, actor, rest):
        words = rest.split()
        if not words or words[0].lower() not in proto.MODES:
            raise ValueError(f'/mode MODE [who|all]   where MODE is {", ".join(proto.MODES)}')
        mode = words[0].lower()
        targets = self.find(' '.join(words[1:]) or 'all', actor)
        for conn in targets:
            conn.mode = mode
            self.send_mode(conn)
            if conn is not actor:
                self.tell(conn, f'Your game mode is now {mode}.')
        return [f'{len(targets)} player(s) are now in {mode} mode.']

    def _cmd_default(self, actor, rest):
        if rest.lower() not in proto.MODES:
            raise ValueError(f'/default MODE   where MODE is {", ".join(proto.MODES)}')
        self.default_mode = rest.lower()
        return [f'New players will start in {self.default_mode} mode.']

    def _cmd_freeze(self, actor, rest, on=True):
        targets = self.find(rest or 'all', actor)
        for conn in targets:
            conn.frozen = on
            self.send_mode(conn)
            self.send(conn, {'t': 'freeze', 'on': on})
            if conn is not actor:
                self.tell(conn, 'You are frozen. Listen to your teacher.' if on else 'You can move again.')
        return [f"{len(targets)} player(s) {'frozen' if on else 'unfrozen'}."]

    def _cmd_unfreeze(self, actor, rest):
        return self._cmd_freeze(actor, rest, on=False)

    def _cmd_lock(self, actor, rest, on=True):
        self.building_locked = on
        for conn in self.players.values():
            self.send_mode(conn)
        self.broadcast({'t': 'say', 'm': 'Building is locked.' if on else 'You can build again.'})
        return []

    def _cmd_unlock(self, actor, rest):
        return self._cmd_lock(actor, rest, on=False)

    def _cmd_mute(self, actor, rest, on=True):
        targets = self.find(rest, actor)
        for conn in targets:
            conn.muted = on
            self.tell(conn, 'You are muted.' if on else 'You can chat again.')
        return [f"{', '.join(c.name for c in targets) or 'Nobody'} {'muted' if on else 'unmuted'}."]

    def _cmd_unmute(self, actor, rest):
        return self._cmd_mute(actor, rest, on=False)

    def _cmd_chat(self, actor, rest):
        if rest.lower() not in ('on', 'off'):
            raise ValueError('/chat on  or  /chat off   (turns chat on or off for all students)')
        self.chat_locked = rest.lower() == 'off'
        self.broadcast({'t': 'say', 'm': 'Chat is turned off.' if self.chat_locked else 'Chat is on again.'})
        return []

    def _cmd_kick(self, actor, rest):
        who, _, why = rest.partition(' ')
        targets = [c for c in self.find(who, actor) if c is not actor]
        for conn in targets:
            self.send(conn, {'t': 'kick', 'm': why.strip() or 'You were removed by the teacher.'})
            conn.writer.close()
        return [f"Removed {', '.join(c.name for c in targets) or 'nobody'}."]

    def _cmd_say(self, actor, rest):
        if not rest:
            raise ValueError('/say what?')
        self.broadcast({'t': 'announce', 'm': proto.clean_chat(rest), 'from': actor.name if actor else 'Teacher'})
        return []

    def _cmd_tp(self, actor, rest):
        if actor is None:
            raise ValueError('Only a teacher in the game can go to a player.')
        target = self.find(rest, actor)[0]
        if target.pos is None:
            raise ValueError(f'{target.name} has not moved yet.')
        self.send(actor, {'t': 'tp', 'x': target.pos[0], 'y': target.pos[1], 'z': target.pos[2]})
        return [f'Going to {target.name}.']

    def _cmd_bring(self, actor, rest):
        if actor is None or actor.pos is None:
            raise ValueError('Only a teacher in the game can bring players to them.')
        targets = [c for c in self.find(rest or 'all', actor) if c is not actor]
        for index, conn in enumerate(targets):
            self.send(conn, {'t': 'tp', 'x': actor.pos[0] + 1.5 + (index % 5) * 0.8, 'y': actor.pos[1], 'z': actor.pos[2] + 1.5 + (index // 5) * 0.8})
        return [f'Brought {len(targets)} player(s).']

    def _cmd_time(self, actor, rest):
        ticks = {'sunrise': 0, 'morning': 1000, 'day': 1000, 'noon': 6000, 'sunset': 12000, 'night': 14000, 'midnight': 18000}
        word = rest.lower()
        if word in ticks:
            value = ticks[word]
        elif word.isdigit():
            value = int(word) % 24000
        else:
            raise ValueError('/time day, night, noon, sunrise, sunset or a number')
        self.time_ticks = value
        self.broadcast({'t': 'time', 'ticks': value})
        return []

    # ---- who changed what, and putting it back ----------------------------------------------------------------------------------------

    def _cmd_history(self, actor, rest):
        now = time.time()
        if not rest:
            recent = collections.Counter(e['who'] for e in self.history if now - e['time'] < 600 and not e['undone'])
            total = collections.Counter(e['who'] for e in self.history if not e['undone'])
            if not total:
                return ['Nobody has changed anything yet.']
            return ['Changes (last 10 minutes / all):'] + [f'  {name}: {recent.get(name, 0)} / {count}' for name, count in total.most_common()]
        name = self._player_name(rest)
        entries = [e for e in self.history if e['who'].lower() == name.lower() and not e['undone']]
        if not entries:
            return [f'{name} has not changed anything.']
        lines = [f'{name}: {len(entries)} change(s). The latest:']
        for entry in entries[-6:]:
            x, y, z = entry['pos']
            lines.append(f"  {int(now - entry['time'])}s ago  ({x}, {y}, {z})  {entry['new'][0] or 'air'}  ({entry['via']})")
        return lines

    def _player_name(self, word):
        """The name of a player now here (or who changed things earlier): a name or the start of one."""
        word = word.strip()
        names = {c.name for c in self.players.values()} | {e['who'] for e in self.history}
        exact = [n for n in names if n.lower() == word.lower()]
        matches = exact or [n for n in names if n.lower().startswith(word.lower())]
        if not matches:
            raise ValueError(f'There is nobody called {word!r}.')
        if len(matches) > 1:
            raise ValueError(f'{word!r} could be {", ".join(sorted(matches))}: type more of the name.')
        return matches[0]

    def _cmd_undo(self, actor, rest):
        words = rest.split()
        if not words:
            raise ValueError('/undo who 5m   (30s, 5m, 2h, a number of changes like 20, or all)')
        name = self._player_name(words[0])
        try:
            span = proto.parse_span(words[1]) if len(words) > 1 else 300
        except ValueError as error:
            raise ValueError(f'/undo {name} how far back? {error}') from None
        mine = [e for e in reversed(self.history) if e['who'].lower() == name.lower() and not e['undone']]
        if isinstance(span, tuple):
            mine = mine[:span[1]]
        elif span is not None:
            mine = [e for e in mine if time.time() - e['time'] <= span]
        restored, skipped, changes = 0, 0, []
        for entry in mine:                                            # (newest first, so each position ends as it was before)
            current = self.world.changes.get(entry['pos'])
            if entry['prev'] is None or current != entry['new']:
                skipped += 1                                          # (somebody built over it since, or it is not known what was there)
                continue
            before = entry['prev']
            self.world.changes[entry['pos']] = before
            entry['undone'] = True
            restored += 1
            changes.append([entry['pos'][0], entry['pos'][1], entry['pos'][2], before[0], before[1]])
        for start in range(0, len(changes), proto.MAX_BLOCKS_PER_MESSAGE):
            self.broadcast({'t': 'blocks', 'by': 0, 'c': changes[start:start + proto.MAX_BLOCKS_PER_MESSAGE]})
        if restored:
            self.world.dirty = True
        who = self.players.get(next((c.id for c in self.players.values() if c.name.lower() == name.lower()), -1))
        if who is not None:
            self.tell(who, f'Your teacher put back {restored} of your changes.')
        self.chatlog(f'* undo {name}: put back {restored}, skipped {skipped}')
        return [f'Put back {restored} change(s) by {name}.' + (f' ({skipped} could not be: built over since, or unknown.)' if skipped else '')]

    # ---- code building -----------------------------------------------------------------------------------------------------------------

    def _cmd_code(self, actor, rest):
        words = rest.split()
        if words and words[0].lower() in ('on', 'off'):
            targets = self.find(words[1] if len(words) > 1 else 'all', actor)
            for conn in targets:
                conn.can_code = words[0].lower() == 'on'
                self.tell(conn, 'You can build with code.' if conn.can_code else 'Building with code is turned off.')
            return [f"Building with code is {words[0].lower()} for {len(targets)} player(s)."]
        if not words:
            raise ValueError('/code on|off [who|all]   or   /code who  to see what they typed')
        target = self.find(words[0], actor)[0]
        if not target.code_log:
            return [f'{target.name} has not typed any code.']
        return [f'{target.name} typed:'] + [f'  {text}' for _stamp, text in list(target.code_log)[-8:]]

    # ---- plots -----------------------------------------------------------------------------------------------------------------------------

    def _give_plot(self, conn):
        """The next free plot, or (in a grid) a new one, becomes this player's."""
        layout = self.world.layout
        free = layout.free_plots()
        if free:
            plot = free[0]
        elif layout.grid_info is not None:
            old = layout.marker_blocks()
            plot = layout.add_plot()
            self._repaint(old)
        else:
            return None
        plot.owner = conn.name
        self.world.dirty = True
        self.send_plots()
        return plot

    def _repaint(self, old_markers):
        """The plots moved or changed size: draw the lines and paths again, for everyone (what is not a line or a path is plain ground)."""
        layout = self.world.layout
        new = layout.marker_blocks()
        changes = []
        for (x, y, z) in set(old_markers) | set(new):
            wanted = new.get((x, y, z))
            current = self.world.changes.get((x, y, z))
            if (current[0] if current else GROUND_BLOCK) == (wanted or GROUND_BLOCK):
                continue
            if wanted is None:
                self.world.changes.pop((x, y, z), None)
            else:
                self.world.changes[(x, y, z)] = (wanted, None)
            changes.append([x, y, z, wanted or GROUND_BLOCK, None])
        self._broadcast_changes(changes)
        self.world.dirty = True

    def _broadcast_changes(self, changes):
        for start in range(0, len(changes), proto.MAX_BLOCKS_PER_MESSAGE):
            self.broadcast({'t': 'blocks', 'by': 0, 'c': changes[start:start + proto.MAX_BLOCKS_PER_MESSAGE]})

    def _built_in(self, plot_list):
        """The positions of everything that is built in these plots (above the ground)."""
        return [pos for pos, (name, _f) in self.world.changes.items() if name and pos[1] > GROUND and any(p.contains(pos[0], pos[2]) for p in plot_list)]

    def _remove_builds(self, positions):
        changes = []
        for pos in positions:
            del self.world.changes[pos]
            changes.append([pos[0], pos[1], pos[2], None, None])
        self._broadcast_changes(changes)
        self.world.dirty = True

    def _sizes(self, words, usage):
        numbers = [w for w in words if w.isdigit()]
        flags = [w.lower() for w in words if not w.isdigit()]
        if not numbers or len(numbers) > 2 or any(f != 'clear' for f in flags):
            raise ValueError(usage)
        width = int(numbers[0])
        return width, int(numbers[1]) if len(numbers) > 1 else width, 'clear' in flags

    def _cmd_plotsize(self, actor, rest):
        layout = self._layout()
        width, depth, clear = self._sizes(rest.split(), '/plotsize W [D] [clear]   makes every plot W wide and D deep (D is W if left out)')
        built = self._built_in(layout.plots)
        if built and not clear:
            raise ValueError(f'{len(built)} blocks are built in the plots, and the plots would move. Say  /plotsize {width} {depth} clear  to remove what is built '
                             f'and go ahead, or  /resize N {width} {depth}  to change one plot where it is.')
        old = layout.marker_blocks()
        layout.relayout(width, depth)
        if built:
            self._remove_builds(built)
        self._repaint(old)
        self.send_plots()
        for conn in list(self.players.values()):
            plot = layout.owner_of(conn.name)
            if plot is not None and not conn.teacher:
                self._send_home(conn, plot)
        return [f'Every plot is {width} x {depth} now.' + (f' ({len(built)} blocks were removed.)' if built else '')]

    def _cmd_resize(self, actor, rest):
        layout = self._layout()
        words = rest.split()
        if not words or not words[0].isdigit():
            raise ValueError('/resize N W [D] [clear]   makes plot N W wide and D deep, keeping its corner (the far side moves)')
        plot = layout.plot_by_id(int(words[0]))
        if plot is None:
            raise ValueError(f'There is no plot {words[0]}.')
        width, depth, clear = self._sizes(words[1:], '/resize N W [D] [clear]')
        old = layout.marker_blocks()
        was = (plot.x1, plot.z1, plot.x2, plot.z2)
        layout.resize_plot(plot, width, depth)
        left_out = [pos for pos in self._built_in([plot_area(was)]) if not plot.contains(pos[0], pos[2])]      # (built in the old plot, outside the new one)
        if left_out and clear:
            self._remove_builds(left_out)
        self._repaint(old)
        self.send_plots()
        note = ''
        if left_out:
            note = f' {len(left_out)} blocks were removed.' if clear else f' {len(left_out)} blocks are outside it now and stay as they are (/resize {plot.id} {width} {depth} clear removes them).'
        return [f'Plot {plot.id} is {width} x {depth} now.' + note]

    def _cmd_addplot(self, actor, rest):
        layout = self._layout()
        old = layout.marker_blocks()
        plot = layout.add_plot()
        self._repaint(old)
        self.world.dirty = True
        self.send_plots()
        return [f'Plot {plot.id} added. ({len(layout.plots)} plots now.)']

    def _layout(self):
        layout = self.world.layout
        if layout is None or not layout.plots:
            raise ValueError('This world has no student plots.')
        return layout

    def _cmd_plots(self, actor, rest):
        layout = self._layout()
        return [f"plot {p.id}: {p.owner or '(free)'}" for p in layout.plots]

    def _cmd_claim(self, actor, rest):
        layout = self._layout()
        if actor is None:
            raise ValueError('Only a player can claim a plot. (To give one out: /assign NAME N)')
        if layout.owner_of(actor.name):
            return [f'You already have plot {layout.owner_of(actor.name).id}. /home takes you there.']
        if not layout.self_claim and not actor.teacher:
            raise ValueError('Ask your teacher for a plot.')
        free = layout.free_plots()
        if rest:
            plot = layout.plot_by_id(int(rest)) if rest.isdigit() else None
            if plot is None or plot.owner:
                raise ValueError(f'Plot {rest} is not free. /plots shows which are.')
        elif free:
            plot = free[0]
        else:
            raise ValueError('All the plots are taken. Ask your teacher.')
        plot.owner = actor.name
        self.world.dirty = True
        self.send_plots()
        self._send_home(actor, plot)
        return [f'Plot {plot.id} is yours. Build anywhere inside the stone-brick line.']

    def _send_home(self, conn, plot):
        x, z = plot.center
        self.send(conn, {'t': 'tp', 'x': plot.x1 + 1.5, 'y': GROUND + 1.01, 'z': plot.z1 - 1.5 if plot.z1 > 2 else plot.z1 + 1.5})

    def _cmd_home(self, actor, rest):
        layout = self._layout()
        plot = layout.owner_of(actor.name) if actor else None
        if plot is None:
            raise ValueError('You do not have a plot yet: type /claim.')
        self._send_home(actor, plot)
        return [f'Going to plot {plot.id}.']

    def _cmd_goto(self, actor, rest):
        layout = self._layout()
        plot = layout.plot_by_id(rest) if rest.isdigit() else None
        if plot is None:
            raise ValueError('/goto N   where N is a plot number (/plots lists them)')
        if actor is None:
            raise ValueError('Only a teacher in the game can go to a plot.')
        self._send_home(actor, plot)
        return [f'Going to plot {plot.id}.']

    def _cmd_assign(self, actor, rest):
        layout = self._layout()
        words = rest.rsplit(' ', 1)
        if len(words) != 2 or not words[1].isdigit():
            raise ValueError('/assign NAME N   gives plot N to NAME (they do not have to be here yet)')
        name = proto.clean_name(words[0])
        for conn in self.players.values():                           # (a name typed in short means the player who is here)
            if conn.name.lower().startswith(words[0].lower()) and not any(c.name.lower() == words[0].lower() for c in self.players.values()):
                name = conn.name
                break
        old = layout.owner_of(name)
        if old is not None:
            old.owner = None
        plot = layout.assign(int(words[1]), name)
        self.world.dirty = True
        self.send_plots()
        return [f'Plot {plot.id} belongs to {name} now.']

    def _cmd_unassign(self, actor, rest):
        layout = self._layout()
        plot = layout.plot_by_id(rest) if rest.isdigit() else layout.owner_of(rest)
        if plot is None:
            raise ValueError('/unassign NAME   or   /unassign N')
        old, plot.owner = plot.owner, None
        self.world.dirty = True
        self.send_plots()
        return [f'Plot {plot.id} is free again (it was {old}\'s).']

    # ---- the person running the server ---------------------------------------------------------------------------------------------------

    def snapshot(self):
        """The class as it is now, for a window that shows it (safe to call from another thread)."""
        return asyncio.run_coroutine_threadsafe(self._snapshot(), self.loop).result(3)

    async def _snapshot(self):
        layout = self.world.layout
        return {'roster': self.roster(), 'locked': self.building_locked, 'chat': not self.chat_locked, 'log': list(self.log_lines[-40:]),
                'plots': [p.to_json() for p in layout.plots] if layout else [], 'code': self.code, 'pin': self.pin, 'port': self.port}

    def operator(self, line):
        """A command typed on the server's own keyboard (it always has teacher powers). Returns the answer lines."""
        line = line.strip().lstrip('/')
        if not line:
            return []
        future = asyncio.run_coroutine_threadsafe(self._operator(line), self.loop)
        return future.result(5)

    async def _operator(self, line):
        result = self.command(None, line)
        self.chatlog(f'* operator: {line.split()[0]}')
        return result
