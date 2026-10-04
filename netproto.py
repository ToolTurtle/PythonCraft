"""netproto - the rules of the classroom network (LAN) game, with no game window in it.

Messages are one JSON object per line over TCP. Everything that arrives is checked: how big it is, what it says, what numbers
and names it holds. Nothing a player sends is ever run as code.

Safety rules in one place:
  - only computers on the same local network (private addresses) may connect, never the internet
  - a room code is needed to join, and a teacher PIN (kept only as a salted hash) to become a teacher
  - messages are small, rate limited, and checked field by field"""
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time

VERSION = 1
DEFAULT_PORT = 25570
MAX_LINE = 65536                       # the longest message accepted (bytes)
MAX_BLOCKS_PER_MESSAGE = 64
MAX_NAME = 16
MAX_CHAT = 200
HEIGHT = 128
LIMIT = 30_000_000                     # the world is this big at most, in every direction
MODES = ('adventure', 'survival', 'creative', 'spectator')
WORDS = ('maple', 'tiger', 'river', 'cloud', 'panda', 'robin', 'stone', 'amber', 'cedar', 'otter', 'lemon', 'comet', 'daisy',
         'eagle', 'frost', 'gecko', 'hazel', 'ivory', 'jolly', 'koala', 'lotus', 'mango', 'noble', 'olive', 'pearl', 'quill')


class ProtocolError(ValueError):
    """A message that is not allowed (and why)."""


# ---- who may connect ----------------------------------------------------------------------------------------------------

def is_local_address(address):
    """True for addresses on a local network (192.168.x.x, 10.x.x.x, 172.16-31.x.x), this computer, or link-local."""
    try:
        ip = ipaddress.ip_address(str(address).split('%')[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local


def make_code():
    """A room code people can say out loud: two words and two digits, like maple-tiger-42."""
    return f'{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.randbelow(90) + 10}'


def make_pin():
    return f'{secrets.randbelow(900000) + 100000}'


def hash_pin(pin, salt=None):
    """(salt, hash) of a PIN. The PIN itself is never kept."""
    salt = salt or secrets.token_bytes(16)
    return salt, hashlib.scrypt(str(pin).encode('utf-8'), salt=salt, n=2 ** 12, r=8, p=1, dklen=32)


def check_pin(pin, salt, expected):
    return hmac.compare_digest(hash_pin(pin, salt)[1], expected)


def same_code(typed, real):
    return hmac.compare_digest(str(typed).strip().lower().encode(), str(real).strip().lower().encode())


# ---- messages ---------------------------------------------------------------------------------------------------------------

def encode(message):
    data = json.dumps(message, separators=(',', ':')).encode('utf-8') + b'\n'
    if len(data) > MAX_LINE:
        raise ProtocolError('that message is too big')
    return data


def decode(line):
    """Turn one received line into a message (a dict with a 't' that says what it is), or raise ProtocolError."""
    if len(line) > MAX_LINE:
        raise ProtocolError('message too long')
    try:
        message = json.loads(line.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        raise ProtocolError('not a message') from None
    if not isinstance(message, dict) or not isinstance(message.get('t'), str) or len(message['t']) > 16:
        raise ProtocolError('not a message')
    return message


def clean_name(text, taken=()):
    """A safe player name: letters, digits, spaces, _ and -, up to 16, and not one already in use."""
    name = re.sub(r'[^A-Za-z0-9 _-]', '', str(text or '')).strip()[:MAX_NAME].strip() or 'Player'
    unique, number = name, 2
    taken = {t.lower() for t in taken}
    while unique.lower() in taken:
        suffix = str(number)
        unique = name[:MAX_NAME - len(suffix)] + suffix
        number += 1
    return unique


def clean_chat(text):
    """Chat text without control characters, not too long."""
    return re.sub(r'[\x00-\x1f\x7f]', '', str(text))[:MAX_CHAT].strip()


def number(value, low=-LIMIT, high=LIMIT, integer=False):
    """A number inside limits (booleans, text and NaN are refused)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError('expected a number')
    if isinstance(value, float) and (value != value or value in (float('inf'), float('-inf'))):
        raise ProtocolError('expected a number')
    if integer and int(value) != value:
        raise ProtocolError('expected a whole number')
    if not low <= value <= high:
        raise ProtocolError('number out of range')
    return int(value) if integer else float(value)


def _block_and_facing(name, facing, known_blocks):
    if name is not None and (not isinstance(name, str) or name not in known_blocks):
        raise ProtocolError(f'unknown block {str(name)[:30]!r}')
    if facing is not None and (not isinstance(facing, str) or len(facing) > 12):
        raise ProtocolError('bad facing')
    return name, facing


def block_change(entry, known_blocks):
    """[x, y, z, name or None, facing or None] (and, if the sender says what was there before, [..., old name, old facing])
    -> ((x, y, z), name or None, facing or None, (old name, old facing) or None), checked."""
    if not isinstance(entry, (list, tuple)) or len(entry) not in (5, 7):
        raise ProtocolError('a block change is [x, y, z, block, facing]')
    x, y, z = (number(entry[0], integer=True), number(entry[1], 0, HEIGHT - 1, integer=True), number(entry[2], integer=True))
    name, facing = _block_and_facing(entry[3], entry[4], known_blocks)
    previous = _block_and_facing(entry[5], entry[6], known_blocks) if len(entry) == 7 else None
    return (x, y, z), name, facing, previous


def chest_items(entries, known_items):
    """The 27 slots of a chest: each None or [item, count, damage], checked."""
    if not isinstance(entries, list) or len(entries) != 27:
        raise ProtocolError('a chest has 27 slots')
    out = []
    for entry in entries:
        if entry is None:
            out.append(None)
            continue
        if not (isinstance(entry, (list, tuple)) and len(entry) == 3) or not isinstance(entry[0], str) or entry[0] not in known_items:
            raise ProtocolError('bad chest item')
        out.append([entry[0], number(entry[1], 1, 64, integer=True), number(entry[2], 0, 5000, integer=True)])
    return out


def parse_span(word):
    """'5m' -> 300 (seconds), '30s', '2h', 'all' -> None (everything), '20' -> ('count', 20). Raises ValueError."""
    word = str(word).strip().lower()
    if word == 'all':
        return None
    if word.isdigit():
        return ('count', int(word))
    match = re.fullmatch(r'(\d+)([smh])', word)
    if not match:
        raise ValueError('say how far back: 30s, 5m, 2h, a number of changes like 20, or all')
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600}[match.group(2)]


def blocks_hash(names):
    """A short fingerprint of the set of blocks (the order does not matter), so two computers can tell they have the same mods."""
    return hashlib.sha1('\n'.join(sorted(names)).encode()).hexdigest()[:10]


class Bucket:
    """Allows `rate` things a second, with a burst of `burst`. Use .take() before doing the thing."""

    def __init__(self, rate, burst):
        self.rate, self.burst, self.level, self.at = rate, burst, burst, time.monotonic()

    def take(self, cost=1.0):
        now = time.monotonic()
        self.level = min(self.burst, self.level + (now - self.at) * self.rate)
        self.at = now
        if self.level >= cost:
            self.level -= cost
            return True
        return False
