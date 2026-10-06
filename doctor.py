"""doctor - check that PythonCraft will run here, and that a class can connect.

    python3 doctor.py                       check this computer: Python, packages, pictures and sounds, mods, saves, network
    python3 doctor.py listen                wait for other computers to connect (run this where the teacher's server will be)
    python3 doctor.py reach ADDRESS         from another computer: can I get to ADDRESS? (and is a class server running there?)

The usual reasons a class cannot connect: the computers are on different networks, the school network does not let computers talk to
each other (ask your IT person), the firewall on the server's computer blocked Python (allow it when it asks), or the address is wrong.
`listen` and `reach` show which it is."""
import ctypes.util
import importlib.util
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import netproto as proto

OK, NOTE, PROBLEM = 'ok', 'note', 'problem'
LABEL = {OK: 'OK     ', NOTE: 'NOTE   ', PROBLEM: 'PROBLEM'}


def check_python():
    version = sys.version_info
    if version < (3, 10):
        return [(PROBLEM, f'Python {version.major}.{version.minor} is too old.', 'Install Python 3.10 or newer (python.org).')]
    return [(OK, f'Python {version.major}.{version.minor}.{version.micro} ({platform.system()})', '')]


def install_hint(package, apt=None):
    """What to do about a missing package, in words that fit this computer."""
    if platform.system() == 'Linux':
        return 'Run ./setup_linux.sh (it installs what is needed)' + (f', or: sudo apt install {apt}' if apt else '') + '.'
    return f'pip3 install {package}' if package else ''


def check_packages():
    results = []
    for module, name, needed, package, apt in (('ursina', 'ursina (the game engine)', True, 'ursina', None),
                                               ('numpy', 'numpy', True, 'numpy', None),
                                               ('PIL', 'pillow (pictures)', True, 'pillow', None),
                                               ('pyperclip', 'pyperclip (copy and paste in text boxes)', False, 'pyperclip', None),
                                               ('tkinter', 'tkinter (the launcher, painter and class tool windows)', False, None, 'python3-tk')):
        if importlib.util.find_spec(module) is None:
            hint = install_hint(package, apt) if platform.system() == 'Linux' or package else 'On a Mac with Homebrew: brew install python-tk'
            results.append((PROBLEM if needed else NOTE, f'{name} is missing.', hint))
        else:
            results.append((OK, f'{name} is installed.', ''))
    return results


def check_assets():
    textures, sounds = HERE / 'assets' / 'textures', HERE / 'assets' / 'sounds'
    pictures = len(list(textures.glob('*.png'))) if textures.is_dir() else 0
    if pictures < 50:
        return [(PROBLEM, f'The pictures in assets/textures are missing ({pictures} found).',
                 'The folder assets/ is not part of the shared code (it comes from Minecraft). Copy the whole assets folder from a computer that works.')]
    results = [(OK, f'{pictures} block pictures found.', '')]
    if not (HERE / 'assets' / 'textures' / 'entity' / 'zombie.png').exists():
        results.append((PROBLEM, 'The creature pictures (assets/textures/entity) are missing.', 'Copy the whole assets folder from a computer that works.'))
    if not sounds.is_dir() or not any(sounds.iterdir()):
        results.append((NOTE, 'There are no sounds in assets/sounds: the game will be silent.', ''))
    if not list((HERE / 'assets' / 'textures' / 'entity').glob('player_*.png')):
        results.append((NOTE, 'No player skins (assets/textures/entity/player_*.png): other players in a class will look like zombies.', ''))
    return results


def check_mods():
    results, folder = [], HERE / 'mods'
    files = sorted(folder.glob('*.pcmod')) if folder.is_dir() else []
    programs = [p for p in sorted(folder.glob('*.py')) if not p.name.startswith(('_', '.'))] if folder.is_dir() else []
    if files:
        import mods
        for path in files:
            try:
                spec, _files, _sha = mods.read_pcmod(path)
                results.append((OK, f"mod {path.name}: fine ({len(mods.describe(spec))} additions).", ''))
            except mods.ModFileError as error:
                results.append((PROBLEM, f'mod {path.name} cannot be used: {error}', 'Ask who made it for a new one.'))
    if programs:
        results.append((NOTE, f"{len(programs)} mod program(s) in mods/ ({', '.join(p.name for p in programs)}). These are run when the game starts: keep only ones you trust.", ''))
    if not files and not programs:
        results.append((OK, 'No mods installed.', ''))
    return results


def check_saves():
    folder = Path(os.environ.get('PYTHONCRAFT_SAVES') or HERE / 'saves')
    if not folder.exists():
        return [(OK, 'No saved worlds yet (the folder is made when you save one).', '')]
    if not os.access(folder, os.W_OK):
        return [(PROBLEM, f'Cannot write to {folder}: saving will not work.', 'Check the folder is not read-only.')]
    return [(OK, f'{len([p for p in folder.iterdir() if p.is_dir()])} saved world(s) in {folder.name}/.', '')]


def local_addresses():
    found = []
    for probe in ('10.255.255.255', '192.168.255.255', '172.16.255.255'):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((probe, 1))
            address = sock.getsockname()[0]
            if address not in found and not address.startswith('127.'):
                found.append(address)
        except OSError:
            pass
        finally:
            sock.close()
    return found


def can_listen(kind, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if kind == 'tcp' else socket.SOCK_DGRAM)
    try:
        sock.bind(('', port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def check_network():
    results = []
    addresses = local_addresses()
    if not addresses:
        results.append((PROBLEM, 'This computer has no local network address: it is not on a network.', 'Connect to the school Wi-Fi or a network cable.'))
    else:
        results.append((OK, 'Address on the network: ' + ', '.join(addresses), 'Students use this to join a class you host here.'))
        private = [a for a in addresses if proto.is_local_address(a)]
        if not private:
            results.append((NOTE, 'This address is not a private (local) one. Class games only work between computers on a local network.', ''))
    if can_listen('tcp', proto.DEFAULT_PORT):
        results.append((OK, f'Port {proto.DEFAULT_PORT} is free: a class server can start here.', ''))
    else:
        results.append((NOTE, f'Port {proto.DEFAULT_PORT} is in use: a class server may already be running here (or use  lan.py host --port N).', ''))
    if not can_listen('udp', proto.DEFAULT_PORT + 1):
        results.append((NOTE, f'Port {proto.DEFAULT_PORT + 1} (finding servers automatically) is in use: that is fine if a server is running here.', ''))
    if platform.system() == 'Darwin':
        tool = '/usr/libexec/ApplicationFirewall/socketfilterfw'
        try:
            text = subprocess.run([tool, '--getglobalstate'], capture_output=True, text=True, timeout=5).stdout.strip()
            if 'enabled' in text.lower():
                results.append((NOTE, 'The Mac firewall is on. The first time a class server starts here the Mac asks whether Python may accept connections: choose Allow.', ''))
            elif text:
                results.append((OK, 'The Mac firewall is off.', ''))
        except (OSError, subprocess.SubprocessError):
            pass
    return results


def _os_name():
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if line.startswith('PRETTY_NAME='):
                return line.split('=', 1)[1].strip().strip('"')
    except OSError:
        pass
    return 'Linux'


def check_linux():
    """Things that only matter on Linux: a screen, X11 or Wayland, graphics, sound, copy and paste, the firewall."""
    if platform.system() != 'Linux':
        return []
    results = [(OK, _os_name(), '')]
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        results.append((PROBLEM, 'No screen was found (DISPLAY is not set): the game needs a desktop session.',
                        'Run it from the desktop of the computer, not over ssh or from a plain text login.'))
    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
        results.append((NOTE, 'This is a Wayland session. If the mouse does not turn the camera or the window misbehaves, log out and choose an X11 session '
                              '(Linux Mint Cinnamon uses X11 by default).', ''))
    if not (shutil.which('xclip') or shutil.which('xsel') or shutil.which('wl-copy')):
        results.append((NOTE, 'Copy and paste in the game\'s text boxes needs xclip.', 'sudo apt install xclip'))
    if not ctypes.util.find_library('openal'):
        results.append((NOTE, 'The sound library (OpenAL) is missing: the game will be silent.', 'sudo apt install libopenal1'))
    glxinfo = shutil.which('glxinfo')
    if glxinfo:
        try:
            text = subprocess.run([glxinfo, '-B'], capture_output=True, text=True, timeout=8).stdout
            renderer = re.search(r'OpenGL renderer string:\s*(.+)', text)
            version = re.search(r'OpenGL version string:\s*(\d+)\.(\d+)', text)
            if version and (int(version.group(1)), int(version.group(2))) < (3, 1):
                results.append((PROBLEM, f'The graphics only offer OpenGL {version.group(1)}.{version.group(2)}; the game needs 3.1 or newer.',
                                'Install the graphics driver for this computer (Linux Mint: Menu > Driver Manager).'))
            elif renderer and 'llvmpipe' in renderer.group(1).lower():
                results.append((NOTE, f'The graphics are drawn by the processor ({renderer.group(1).strip()}): the game will be slow.',
                                'On a virtual machine this is normal; on a real computer install the graphics driver (Menu > Driver Manager).'))
            elif renderer:
                results.append((OK, f'Graphics: {renderer.group(1).strip()}', ''))
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        results.append((NOTE, 'The graphics were not checked (glxinfo is not installed).', 'sudo apt install mesa-utils'))
    if shutil.which('ufw'):
        results.append((NOTE, 'A firewall (ufw) may be on. A computer that hosts a class has to let players in:',
                        f'sudo ufw allow {proto.DEFAULT_PORT}/tcp && sudo ufw allow {proto.DEFAULT_PORT + 1}/udp   (check with: sudo ufw status)'))
    return results


def run_all():
    results = []
    for title, check in (('This computer', check_python), ('Packages', check_packages), ('Pictures and sounds', check_assets), ('Mods', check_mods),
                         ('Saved worlds', check_saves), ('Network', check_network), ('Linux', check_linux)):
        found = check()
        if found:                                                  # (a check that does not apply here, like the Linux one on a Mac, says nothing)
            results.append((title, found))
    return results


def reach(host, port=proto.DEFAULT_PORT, timeout=4):
    """Can this computer reach a class server at host? Returns (status, what was found, what to try)."""
    try:
        sock = socket.create_connection((host, port), timeout)
    except OSError as error:
        reason = error.strerror or str(error)
        return [(PROBLEM, f'Could not connect to {host} port {port}: {reason}.',
                 'Check: the address is right; the server is running (lan.py host); both computers are on the same network; the server\'s firewall '
                 'allows Python; the school network lets computers talk to each other.')]
    results = [(OK, f'Connected to {host} port {port}.', '')]
    try:
        sock.settimeout(timeout)
        sock.sendall(proto.encode({'t': 'hello', 'v': proto.VERSION, 'name': 'doctor', 'code': '?', 'blocks': 'x'}))
        reply = b''
        while b'\n' not in reply:
            chunk = sock.recv(4096)
            if not chunk:
                break
            reply += chunk
        message = proto.decode(reply.split(b'\n')[0])
        if message['t'] == 'error':
            results.append((OK, f"A PythonCraft class server answered (it said: \"{message.get('m')}\" because this test has no room code).", 'Now join with the real room code.'))
        else:
            results.append((OK, 'Something answered.', ''))
    except (OSError, proto.ProtocolError):
        results.append((NOTE, 'It connected but did not answer like a class server. Is it something else on that port?', ''))
    finally:
        sock.close()
    return results


def listen(port=proto.DEFAULT_PORT, seconds=None, on_connection=None):
    """Wait for other computers to connect and say who did. (A server would use this port: stop this before starting one.)"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('', port))
    except OSError as error:
        server.close()
        return [(PROBLEM, f'Cannot listen on port {port}: {error.strerror or error}.', 'Is a class server already running here? Stop it first.')]
    server.listen(5)
    server.settimeout(0.5)
    found, end = [], (time.monotonic() + seconds) if seconds else None
    try:
        while end is None or time.monotonic() < end:
            try:
                connection, address = server.accept()
            except socket.timeout:
                continue
            connection.close()
            line = (OK, f'{address[0]} connected: that computer can reach this one.', '')
            found.append(line)
            if on_connection:
                on_connection(line)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return found


def show(results, title=None):
    if title:
        print(f'\n{title}')
    problems = 0
    for status, text, hint in results:
        print(f'  {LABEL[status]} {text}')
        if hint and status != OK:
            print(f'           -> {hint}')
        elif hint and status == OK and 'join' in hint.lower():
            print(f'           ({hint})')
        problems += status == PROBLEM
    return problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'listen':
        port = int(argv[1]) if len(argv) > 1 else proto.DEFAULT_PORT
        addresses = local_addresses() or ['(no network address found)']
        print(f'Waiting for connections on port {port}. On another computer run:  python3 doctor.py reach {addresses[0]}')
        print('(Ctrl+C stops.)')
        listen(port, on_connection=lambda line: print(f'  {LABEL[line[0]]} {line[1]}'))
        return 0
    if argv and argv[0] == 'reach':
        if len(argv) < 2:
            print('Say where: python3 doctor.py reach ADDRESS')
            return 2
        return 1 if show(reach(argv[1], int(argv[2]) if len(argv) > 2 else proto.DEFAULT_PORT), f'Reaching {argv[1]}') else 0
    problems = 0
    for title, results in run_all():
        problems += show(results, title)
    print('\nEverything looks fine.' if not problems else f'\n{problems} problem(s) to fix (see the lines marked PROBLEM).')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
