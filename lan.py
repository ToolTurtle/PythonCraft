"""lan - play together on the classroom network (LAN only: nothing goes over the internet).

    python3 lan.py host                       start a class server with a new world (prints the room code and the teacher PIN)
    python3 lan.py host --world NAME          ... from one of your saved worlds (a copy: your save is never changed)
    python3 lan.py host --plot my.pcplot      ... from a pycraft plot or a tutorial world
    python3 lan.py host --play Ms-Lee         ... and also play in it on this computer
    python3 lan.py join                       look for a class server on this network and join it
    python3 lan.py join 192.168.1.23 maple-tiger-42 --name Sam
    python3 lan.py find                       list the class servers on this network

Anyone can be a teacher, wherever they sit: in the game type  /teacher PIN  (the PIN is shown where the server runs).
A teacher can then use /mode, /freeze, /lock, /mute, /kick, /tp, /bring, /say and /time (/help lists them).
Where the server runs you can type the same commands without the slash (for example:  mode creative all).

See docs/README_lan.md for the teacher's guide."""
import argparse
import os
import random
import socket
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import netproto as proto

LANWORLDS = Path(os.environ.get('PYCRAFT_LANWORLDS') or HERE / 'lanworlds')


def local_ips():
    """The addresses of this computer on the local network (found without sending anything)."""
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
    return found or ['127.0.0.1']


def make_world(args):
    """The world the server starts from, and where its changes are kept."""
    from lanserver import WorldState
    if args.plot:
        import pycraft
        plot = pycraft.load(args.plot)
        modified, facing, spawn = pycraft.plot_world_data(plot)
        changes = {pos: (name, facing.get(pos)) for pos, name in modified.items()}
        title = plot.title or Path(args.plot).stem
        return WorldState(0, title, list(spawn), changes), LANWORLDS / f'{Path(args.plot).stem}.lanworld.json'
    if args.world:
        import savegame
        folder = savegame.SAVES / args.world
        if not (folder / 'level.json').exists():
            raise SystemExit(f'There is no saved world called {args.world!r} in {savegame.SAVES}.')
        target = LANWORLDS / f'{args.world}.lanworld.json'
        if target.exists() and not args.fresh:
            return WorldState.load(target), target                # (the class world from last time)
        level, modified, facing, _flowing = savegame.load(folder)
        changes = {pos: (name, (facing or {}).get(pos)) for pos, name in modified.items()}
        return WorldState(level.get('seed', 0), level.get('name', args.world), None, changes), target
    seed = args.seed if args.seed is not None else random.randint(0, 99999)
    target = LANWORLDS / f'seed-{seed}.lanworld.json'
    if target.exists() and not args.fresh:
        return WorldState.load(target), target
    return WorldState(seed, f'Class world {seed}'), target


def host(args):
    from lanserver import LanServer
    world, save_path = make_world(args)
    import mods
    mods.load_folder()                                            # (the mods everyone needs: players must have the same ones)
    server = LanServer(world, pin=args.pin, code=args.code, host=args.bind, port=args.port, default_mode=args.mode,
                       max_players=args.max, save_path=save_path, name=args.name).start()
    print(f'\nClass server "{args.name}" is running ({world.title}).')
    for address in local_ips():
        print(f'  Join with:   python3 lan.py join {address} {server.code} --name YOURNAME      (or just: python3 lan.py join)')
    print(f'  Room code:   {server.code}')
    print(f'  Teacher PIN: {server.pin}      (a teacher types  /teacher {server.pin}  in the game; keep the PIN to yourselves)')
    print(f'  New players start in {args.mode} mode. The world is kept in {save_path}.')
    print('Type commands here (mode creative all, list, say Hello, lock...). Ctrl+C stops the server.\n')

    def console():
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                return
            try:
                for text in server.operator(line):
                    print(text)
            except Exception as error:                            # (a typo must not stop the server)
                print(f'{type(error).__name__}: {error}')

    if args.play:
        threading.Thread(target=console, daemon=True).start()
        import lanplay
        try:
            lanplay.play('127.0.0.1', server.port, server.code, args.play)
        finally:
            server.stop()
        return 0
    try:
        console()
    except KeyboardInterrupt:
        pass
    print('Stopping the server...')
    server.stop()
    return 0


def join(args):
    import lanclient
    host_name, code = args.host, args.code
    if not host_name:
        print('Looking for a class server on this network...')
        found = lanclient.find_servers()
        if not found:
            print('Found none. Ask your teacher for the address and the room code:  python3 lan.py join ADDRESS CODE')
            return 1
        if len(found) == 1:
            host_name, info = found[0]
            args.port = info['port']
            print(f"Found {info['name']} ({info['players']} players) at {host_name}.")
        else:
            for number, (address, info) in enumerate(found, start=1):
                print(f"  {number}. {info['name']}  ({info['players']} players)  {address}")
            choice = int(input('Which one? ') or '1')
            host_name, info = found[choice - 1]
            args.port = info['port']
    if not code:
        code = input('Room code (your teacher has it): ').strip()
    name = args.name or os.environ.get('PYCRAFT_NAME') or input('Your name: ').strip() or 'Player'
    import lanplay
    return lanplay.play(host_name, args.port, code, name)


def find(args):
    import lanclient
    found = lanclient.find_servers()
    if not found:
        print('No class servers found on this network.')
        return 1
    for address, info in found:
        print(f"{info['name']}  {address}:{info['port']}  ({info['players']} players)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='lan.py', description='Play together on the classroom network.')
    sub = parser.add_subparsers(dest='command', required=True)
    h = sub.add_parser('host', help='start a class server')
    h.add_argument('--world', help='start from a saved world (it is copied: your save is never changed)')
    h.add_argument('--plot', help='start from a .pcplot (a pycraft plot or tutorial world)')
    h.add_argument('--seed', type=int, help='the seed of a new world')
    h.add_argument('--fresh', action='store_true', help='ignore the class world kept from last time')
    h.add_argument('--pin', help='the teacher PIN (at least 4 characters; made up for you if you leave it out)')
    h.add_argument('--code', help='the room code (made up for you if you leave it out)')
    h.add_argument('--mode', default='adventure', choices=proto.MODES, help='the game mode new players start in (default adventure)')
    h.add_argument('--port', type=int, default=proto.DEFAULT_PORT)
    h.add_argument('--bind', default='0.0.0.0', help='the address to listen on (default: this computer\'s network)')
    h.add_argument('--max', type=int, default=40, help='how many players at most')
    h.add_argument('--name', default='PythonCraft class', help='the name students see when they look for it')
    h.add_argument('--play', metavar='NAME', help='also play in it here, as NAME')
    j = sub.add_parser('join', help='join a class server')
    j.add_argument('host', nargs='?', help='its address (leave out to look for it)')
    j.add_argument('code', nargs='?', help='the room code')
    j.add_argument('--name', help='your name in the game')
    j.add_argument('--port', type=int, default=proto.DEFAULT_PORT)
    sub.add_parser('find', help='list the class servers on this network')
    args = parser.parse_args(argv)
    if getattr(args, 'plot', None):
        args.plot = os.path.abspath(args.plot)                    # (the game must run from its own folder: find your file first)
    os.chdir(HERE)
    try:
        return {'host': host, 'join': join, 'find': find}[args.command](args)
    except ValueError as error:
        print(f'Problem: {error}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
