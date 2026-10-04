"""lanserver - the classroom (LAN) game server. It holds the world, the rules and who is a teacher. It has no game window.

    python3 lan.py host                    start a server (see lan.py for the options)

Anyone can be a teacher, wherever they sit: a player types /teacher PIN in the game. The server checks the PIN (kept only as a
salted hash, with limits on guessing) and then lets that player change game modes, freeze, lock building, mute, kick, teleport and
make announcements. The server itself is not special: it can be run by one computer while the teacher plays on another.

Everything a player sends is checked here (see netproto.py); the server never runs anything a player sends."""
import asyncio
import json
import threading
import time
from pathlib import Path

import netproto as proto
from netproto import Bucket, ProtocolError

TOGGLES = {'oak_door_b', 'oak_door_t', 'lever', 'lever_on', 'stone_button', 'bed', 'oak_trapdoor'}
DISCOVERY_PORT = proto.DEFAULT_PORT + 1
HELP_STUDENT = ('/list  who is here   /teacher PIN  become a teacher   /help')
HELP_TEACHER = ('/mode MODE [who|all]  adventure, survival, creative or spectator   /default MODE  for new players\n'
                '/freeze [who|all]  /unfreeze [who|all]   /lock  /unlock  building for everyone\n'
                '/mute who  /unmute who   /kick who [why]   /tp who  go to a player   /bring who|all  bring players to you\n'
                '/say text  announce to everyone   /time day|night|noon|sunrise|sunset   /list   /teacher off')


class WorldState:
    """The world as the server knows it: how it starts (a seed or a built world) and every block players changed."""

    def __init__(self, seed=0, title='Class world', flat_spawn=None, changes=None):
        self.seed, self.title, self.flat_spawn = int(seed), str(title), flat_spawn
        self.changes = dict(changes or {})                # (x, y, z) -> (block name or None, facing or None)
        self.dirty = False

    def to_json(self):
        return {'format': 'lanworld', 'seed': self.seed, 'title': self.title, 'flat_spawn': self.flat_spawn,
                'changes': [[x, y, z, name, facing] for (x, y, z), (name, facing) in self.changes.items()]}

    @classmethod
    def from_json(cls, data):
        changes = {}
        for x, y, z, name, facing in data.get('changes', []):
            changes[(x, y, z)] = (name, facing)
        return cls(data.get('seed', 0), data.get('title', 'Class world'), data.get('flat_spawn'), changes)

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
        self.pos = None                                   # (x, y, z) as last reported
        self.yaw = self.pitch = 0.0
        self.joined = False
        self.bad = 0                                      # messages that were not allowed
        self.pin_failures, self.pin_locked_until = 0, 0.0
        self.msg_bucket, self.pos_bucket = Bucket(120, 240), Bucket(40, 60)
        self.block_bucket, self.chat_bucket = Bucket(300, 600), Bucket(1.0, 5)

    def info(self):
        x, y, z = self.pos or (0, 0, 0)
        return {'id': self.id, 'name': self.name, 'teacher': self.teacher, 'mode': self.mode, 'x': x, 'y': y, 'z': z,
                'yaw': self.yaw, 'pitch': self.pitch}


class LanServer:
    def __init__(self, world, pin=None, code=None, host='0.0.0.0', port=0, default_mode='adventure', max_players=40,
                 save_path=None, known_blocks=None, name='PythonCraft class'):
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
        self.name = name
        self.players = {}                                 # id -> Conn
        self.next_id = 1
        self.building_locked = False
        self.time_ticks = None
        self.auth_failures = []                           # times of wrong PINs (all players together)
        self.auth_locked_until = 0.0
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
        autosave = asyncio.ensure_future(self._autosave())
        self._start_discovery()
        ready.set()
        await self._stop.wait()
        autosave.cancel()
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

    def log(self, text):
        self.log_lines.append(text)
        del self.log_lines[:-200]

    # ---- finding the server on the network (a broadcast answer: name, port and player count; never the room code) -------------

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

    def locked_for(self, conn):
        """Can this player not build right now?"""
        if conn.frozen or conn.mode in ('adventure', 'spectator'):
            return True
        return self.building_locked and not conn.teacher

    def send_mode(self, conn):
        self.send(conn, {'t': 'mode', 'mode': conn.mode, 'locked': self.locked_for(conn), 'frozen': conn.frozen})

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
            try:
                first = await asyncio.wait_for(reader.readline(), 10)
                hello = proto.decode(first)
                self._hello(conn, hello)
            except (asyncio.TimeoutError, ProtocolError, asyncio.LimitOverrunError, ValueError) as error:
                self.send(conn, {'t': 'error', 'm': str(error) if isinstance(error, ProtocolError) else 'Say hello first.'})
                return
            except (ConnectionError, OSError):
                return
            if conn.joined is False:
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
        if hello.get('t') != 'hello' or hello.get('v') != proto.VERSION:
            raise ProtocolError('This game is a different version. Update PythonCraft.')
        if not proto.same_code(hello.get('code', ''), self.code):
            raise ProtocolError('That room code is not right.')
        if hello.get('blocks') != self.blocks_hash:
            raise ProtocolError('Your mods are not the same as the host\'s (different blocks). Install the same .pcmod files.')
        conn.name = proto.clean_name(hello.get('name'), [c.name for c in self.players.values()])
        conn.mode = self.default_mode
        self.players[conn.id] = conn
        conn.joined = True
        world = self.world
        self.send(conn, {'t': 'welcome', 'id': conn.id, 'name': conn.name, 'seed': world.seed, 'title': world.title,
                         'flat_spawn': world.flat_spawn, 'mode': conn.mode, 'locked': self.locked_for(conn),
                         'time': self.time_ticks, 'server': self.name,
                         'players': [c.info() for c in self.players.values() if c is not conn],
                         'count': len(world.changes)})
        changes = [[x, y, z, name, facing] for (x, y, z), (name, facing) in world.changes.items()]
        for start in range(0, len(changes), 500):
            self.send(conn, {'t': 'world', 'c': changes[start:start + 500]})
        self.send(conn, {'t': 'ready'})
        self.broadcast({'t': 'join', 'p': conn.info()}, skip=conn)
        self.broadcast({'t': 'say', 'm': f'{conn.name} joined.'}, skip=conn)
        self.tell(conn, 'Welcome! /help shows the commands. A teacher types /teacher PIN.')
        self.log(f'{conn.name} joined from {conn.address}')

    def _leave(self, conn):
        if self.players.pop(conn.id, None) is not None and conn.joined:
            self.broadcast({'t': 'leave', 'id': conn.id})
            self.broadcast({'t': 'say', 'm': f'{conn.name} left.'})
            self.log(f'{conn.name} left')

    # ---- what players send --------------------------------------------------------------------------------------------------------------

    def _message(self, conn, message):
        kind = message['t']
        if kind == 'pos':
            if not conn.pos_bucket.take():
                return
            x, y, z = (proto.number(message.get('x')), proto.number(message.get('y'), -64, 1000), proto.number(message.get('z')))
            yaw, pitch = proto.number(message.get('yaw', 0), -100000, 100000), proto.number(message.get('pitch', 0), -100000, 100000)
            moving = bool(message.get('v', False))
            if conn.frozen:
                return
            conn.pos, conn.yaw, conn.pitch = (x, y, z), yaw, pitch
            self.broadcast({'t': 'pos', 'id': conn.id, 'x': x, 'y': y, 'z': z, 'yaw': yaw, 'pitch': pitch, 'v': moving}, skip=conn)
        elif kind == 'blocks':
            self._blocks(conn, message)
        elif kind == 'chat':
            self._chat(conn, proto.clean_chat(message.get('m', '')))
        elif kind == 'ping':
            self.send(conn, {'t': 'pong'})
        else:
            raise ProtocolError('unknown message')

    def _blocks(self, conn, message):
        entries = message.get('c')
        if not isinstance(entries, list) or len(entries) > proto.MAX_BLOCKS_PER_MESSAGE:
            raise ProtocolError('too many block changes at once')
        if not conn.block_bucket.take(max(1, len(entries))):
            self.send(conn, {'t': 'reject', 'c': [e[:3] for e in entries if isinstance(e, list) and len(e) >= 3]})
            return
        accepted, refused = [], []
        for entry in entries:
            pos, name, facing = proto.block_change(entry, self.known_blocks)
            if self._may_change(conn, pos, name):
                accepted.append(entry)
                self.world.changes[pos] = (name, facing)
            else:
                refused.append(list(pos))
        if accepted:
            self.world.dirty = True
            self.broadcast({'t': 'blocks', 'by': conn.id, 'c': accepted}, skip=conn)
        if refused:
            self.send(conn, {'t': 'reject', 'c': refused})

    def _may_change(self, conn, pos, name):
        if conn.pos is None or conn.frozen or conn.mode == 'spectator':
            return False
        if max(abs(pos[0] - conn.pos[0]), abs(pos[1] - conn.pos[1]), abs(pos[2] - conn.pos[2])) > 12:
            return False                                    # (nobody reaches that far)
        if conn.mode == 'adventure':
            return name in TOGGLES                           # (open doors and flick levers, nothing else)
        if self.building_locked and not conn.teacher:
            return name in TOGGLES
        return True

    def _chat(self, conn, text):
        if not text:
            return
        if not conn.chat_bucket.take():
            self.tell(conn, 'Slow down a little.')
            return
        if text.startswith('/'):
            for line in self.command(conn, text[1:]):
                self.tell(conn, line)
            return
        if conn.muted:
            self.tell(conn, 'You are muted.')
            return
        self.broadcast({'t': 'chat', 'from': conn.name, 'teacher': conn.teacher, 'm': text})
        self.log(f'{conn.name}: {text}')

    # ---- commands: /teacher for everyone, the rest for teachers ----------------------------------------------------------------------

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
        if not is_teacher:
            return ['Only a teacher can do that. (A teacher types /teacher and the PIN.)']
        try:
            return handler(actor, rest) or []
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
        self.send(conn, {'t': 'role', 'teacher': True})
        self.send_mode(conn)
        self.broadcast({'t': 'say', 'm': f'{conn.name} is a teacher now.'})
        self.log(f'{conn.name} became a teacher')
        return ['You are a teacher. /help shows what you can do. (You start in creative mode.)']

    def find(self, who, actor=None):
        """The players a word stands for: a name (or the start of one), 'all' (every student) or 'me'."""
        who = who.strip()
        if who.lower() == 'all':
            return [c for c in self.players.values() if not c.teacher]
        if who.lower() == 'me' and actor is not None:
            return [actor]
        matches = [c for c in self.players.values() if c.name.lower() == who.lower()]
        matches = matches or [c for c in self.players.values() if c.name.lower().startswith(who.lower())] if who else matches
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
        targets = self.find(words[1] if len(words) > 1 else 'all', actor)
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
        return [f"{', '.join(c.name for c in targets)} {'muted' if on else 'unmuted'}."]

    def _cmd_unmute(self, actor, rest):
        return self._cmd_mute(actor, rest, on=False)

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

    # ---- the person running the server ---------------------------------------------------------------------------------------------------

    def operator(self, line):
        """A command typed on the server's own keyboard (it always has teacher powers). Returns the answer lines."""
        line = line.strip().lstrip('/')
        if not line:
            return []
        future = asyncio.run_coroutine_threadsafe(self._operator(line), self.loop)
        return future.result(5)

    async def _operator(self, line):
        return self.command(None, line)
