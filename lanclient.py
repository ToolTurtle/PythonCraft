"""lanclient - the player's side of the classroom (LAN) game, with no game window in it (lanplay.py adds the window).

    client = LanClient('192.168.1.20', 25570, 'maple-tiger-42', 'Sam')
    info = client.connect()          # joins and receives the world; raises LanError with a plain message if it cannot
    for event in client.poll(): ...  # what happened since last time: other players, block changes, chat, teacher orders
"""
import json
import queue
import socket
import threading

import netproto as proto
from netproto import ProtocolError


class LanError(Exception):
    """Could not join, or was removed. The message is written for a student to read."""


class LanClient:
    def __init__(self, host, port, code, name, blocks_hash=None):
        import blocks
        self.host, self.port, self.code, self.name = host, int(port), code, name
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
        info, changes = None, []
        while True:
            message = self._read_one()
            kind = message['t']
            if kind in ('error', 'kick'):
                self.close()
                raise LanError(str(message.get('m', 'The server said no.')))
            if kind == 'welcome':
                info = message
            elif kind == 'world':
                changes.extend(message.get('c', []))
            elif kind == 'ready':
                break
            elif info is not None and kind in ('say', 'join', 'leave', 'pos', 'blocks', 'chat'):
                self.events.put(message)                    # (things that happened while the world was arriving)
        if info is None:
            raise LanError('The server did not send a world.')
        info['changes'] = changes
        self.id, self.name = info['id'], info['name']
        self.sock.settimeout(None)
        threading.Thread(target=self._reader, daemon=True).start()
        return info

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

    def send_blocks(self, changes):
        """changes: [(x, y, z, block name or None, facing or None), ...]"""
        for start in range(0, len(changes), proto.MAX_BLOCKS_PER_MESSAGE):
            self.send({'t': 'blocks', 'c': [list(c) for c in changes[start:start + proto.MAX_BLOCKS_PER_MESSAGE]]})

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
