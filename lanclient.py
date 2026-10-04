"""lanclient - the player's side of the classroom (LAN) game, with no game window in it (lanplay.py adds the window).

    client = LanClient('192.168.1.20', 25570, 'maple-tiger-42', 'Sam')
    info = client.connect()          # joins and receives the world; raises LanError with a plain message if it cannot
    for event in client.poll(): ...  # what happened since last time: other players, block changes, chat, teacher orders
"""
import base64
import json
import os
import queue
import socket
import tempfile
import threading
from pathlib import Path

import netproto as proto
from netproto import ProtocolError


class LanError(Exception):
    """Could not join, or was removed. The message is written for a student to read."""


class LanClient:
    def __init__(self, host, port, code, name, blocks_hash=None, auto_mods=True):
        import blocks
        self.host, self.port, self.code, self.name = host, int(port), code, name
        self.auto_mods = auto_mods
        self.blocks_hash = blocks_hash or proto.blocks_hash(list(blocks.BLOCKS))
        self.sock = None
        self.events = queue.Queue()
        self.closed = False
        self.reason = ''
        self.id = None
        self.teacher = False
        self._buffer = b''
        self._lock = threading.Lock()

    # ---- joining -----------------------------------------------------------------------------------------------------

    def connect(self, timeout=10):
        """Join the game. Returns what the server said (the world, who is here); the blocks players changed are in info['changes']."""
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout)
        except OSError as error:
            raise LanError(f'Could not reach {self.host}: {error.strerror or error}. Is the server running, and are you on the same network?') from None
        self.sock.settimeout(timeout)
        self.send({'t': 'hello', 'v': proto.VERSION, 'name': self.name, 'code': self.code, 'blocks': self.blocks_hash})
        info, changes, chests, plots = None, [], [], None
        try:
            return self._join(info, changes, chests, plots)
        except LanError:
            self.close()
            raise

    def _join(self, info, changes, chests, plots):
        while True:
            message = self._read_one()
            kind = message['t']
            if kind in ('error', 'kick'):
                self.close()
                raise LanError(str(message.get('m', 'The server said no.')))
            if kind == 'needmods':
                self._get_mods(message.get('mods', []))               # (the server offers what this computer is missing)
                self.send({'t': 'hello', 'v': proto.VERSION, 'name': self.name, 'code': self.code, 'blocks': self.blocks_hash})
            elif kind == 'welcome':
                info = message
            elif kind == 'world':
                changes.extend(message.get('c', []))
            elif kind == 'chests':
                chests.extend(message.get('c', []))
            elif kind == 'plots':
                plots = message
            elif kind == 'ready':
                break
            elif info is not None and kind in ('say', 'join', 'leave', 'pos', 'blocks', 'chat'):
                self.events.put(message)                    # (things that happened while the world was arriving)
        if info is None:
            raise LanError('The server did not send a world.')
        info['changes'], info['chests'], info['plots'] = changes, chests, plots
        self.id, self.name = info['id'], info['name']
        self.sock.settimeout(None)
        threading.Thread(target=self._reader, daemon=True).start()
        return info

    def _get_mods(self, offered):
        """Download the mods the server has that this computer lacks (.pcmod files hold data only, and each is checked before it is
        used), load them for this game, and work out what blocks there are now."""
        import blocks
        import mods
        if not self.auto_mods:
            raise LanError('The host\'s mods are not all installed here: ' + ', '.join(m.get('name', '?') for m in offered)
                           + '. Install the same .pcmod files (modtool.py install).')
        if not isinstance(offered, list) or len(offered) > 40:
            raise LanError('The server offered too many mods.')
        folder = Path(os.environ.get('PYCRAFT_MODCACHE') or Path(__file__).resolve().parent / 'mods' / '.cache') / 'downloads'
        folder.mkdir(parents=True, exist_ok=True)
        for entry in offered:
            sha, size = str(entry.get('sha', '')), entry.get('size', 0)
            if not sha.isalnum() or len(sha) > 20 or not isinstance(size, int) or size > mods.MAX_TOTAL:
                raise LanError('The server offered a mod that does not look right.')
            path = folder / f'{sha}.pcmod'
            if not path.exists():
                self.send({'t': 'getmod', 'sha': sha})
                chunks, wanted = {}, None
                while wanted is None or len(chunks) < wanted:
                    message = self._read_one()
                    if message['t'] in ('error', 'kick'):
                        raise LanError(str(message.get('m', 'The server said no.')))
                    if message['t'] == 'modfile' and message.get('sha') == sha:
                        wanted = int(message['of'])
                        if wanted > 2000:
                            raise LanError('A mod from the server was too big.')
                        chunks[int(message['i'])] = base64.b64decode(message['data'])
                temporary = Path(tempfile.mkdtemp()) / 'download.pcmod'
                temporary.write_bytes(b''.join(chunks[i] for i in range(wanted)))
                try:
                    _spec, _files, real = mods.read_pcmod(temporary)            # (data only, and checked)
                except mods.ModFileError as error:
                    raise LanError(f'A mod from the server is not good: {error}') from None
                if real != sha:
                    raise LanError('A mod from the server did not arrive properly.')
                path.write_bytes(temporary.read_bytes())
            try:
                mods.load_pcmod(path)
            except mods.ModFileError as error:
                raise LanError(f'A mod from the server could not be used: {error}') from None
        self.blocks_hash = proto.blocks_hash(list(blocks.BLOCKS))

    def _read_one(self):
        while b'\n' not in self._buffer:
            try:
                data = self.sock.recv(65536)
            except (socket.timeout, OSError):
                raise LanError('The server stopped answering.') from None
            if not data:
                raise LanError('The server closed the connection.')
            self._buffer += data
            if len(self._buffer) > proto.MAX_LINE * 8:
                raise LanError('The server sent too much.')
        line, _, self._buffer = self._buffer.partition(b'\n')
        try:
            return proto.decode(line)
        except ProtocolError:
            return {'t': 'ignored'}

    def _reader(self):
        try:
            while not self.closed:
                message = self._read_one()
                if message['t'] == 'role':
                    self.teacher = bool(message.get('teacher'))
                self.events.put(message)
                if message['t'] == 'kick':
                    self.reason = str(message.get('m', ''))
                    break
        except (LanError, OSError):
            pass
        finally:
            self.closed = True
            self.events.put({'t': 'closed', 'm': self.reason or 'Disconnected from the game.'})

    # ---- using it ---------------------------------------------------------------------------------------------------

    def poll(self, limit=500):
        """Everything that arrived since the last time (up to `limit` messages), oldest first."""
        out = []
        while len(out) < limit:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                break
        return out

    def send(self, message):
        try:
            data = proto.encode(message)
            with self._lock:
                self.sock.sendall(data)
        except (OSError, ProtocolError, AttributeError):
            self.closed = True

    def send_pos(self, x, y, z, yaw, pitch, moving=False):
        self.send({'t': 'pos', 'x': round(x, 3), 'y': round(y, 3), 'z': round(z, 3), 'yaw': round(yaw, 1), 'pitch': round(pitch, 1),
                   'v': bool(moving)})

    def send_blocks(self, changes, code=False):
        """changes: [(x, y, z, block name or None, facing or None[, old block, old facing]), ...]. code=True: built by the player's code."""
        for start in range(0, len(changes), proto.MAX_BLOCKS_PER_MESSAGE):
            message = {'t': 'blocks', 'c': [list(c) for c in changes[start:start + proto.MAX_BLOCKS_PER_MESSAGE]]}
            if code:
                message['code'] = True
            self.send(message)

    def send_sim(self, changes):
        """(only the computer that runs the world) blocks that changed by themselves: water, sand, fire, redstone."""
        for start in range(0, len(changes), proto.MAX_BLOCKS_PER_MESSAGE * 4):
            self.send({'t': 'sim', 'c': [list(c) for c in changes[start:start + proto.MAX_BLOCKS_PER_MESSAGE * 4]]})

    def send_mobs(self, entries):
        """(only the computer that runs the world) where the animals are: [[id, kind, x, y, z, yaw, moving, health], ...]"""
        self.send({'t': 'mobs', 'c': entries})

    def send_mobhit(self, ident, damage):
        self.send({'t': 'mobhit', 'id': ident, 'dmg': damage})

    def send_loot(self, to, name, count):
        self.send({'t': 'loot', 'to': to, 'name': name, 'count': count})

    def send_chest(self, x, y, z, items):
        self.send({'t': 'chest', 'x': x, 'y': y, 'z': z, 'items': items})

    def send_code(self, text):
        """What this player typed in the code prompt (so a teacher can see it)."""
        self.send({'t': 'code', 'm': text})

    def chat(self, text):
        self.send({'t': 'chat', 'm': text})

    def close(self):
        self.closed = True
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass


def find_servers(timeout=1.5, address='255.255.255.255'):
    """Look for classroom servers on this network. Returns [(ip, {'name', 'port', 'players'})]."""
    found = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.3)
        import time
        end = time.monotonic() + timeout
        sock.sendto(b'pycraft-find', (address, proto.DEFAULT_PORT + 1))
        while time.monotonic() < end:
            try:
                data, source = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if not proto.is_local_address(source[0]):
                continue
            try:
                info = json.loads(data.decode())
                found[source[0]] = {'name': str(info['name'])[:40], 'port': int(info['port']), 'players': int(info['players'])}
            except (ValueError, KeyError, TypeError):
                continue
    except OSError:
        pass
    finally:
        sock.close()
    return list(found.items())
