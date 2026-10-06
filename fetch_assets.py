"""fetch_assets - download the game's pictures and sounds (the folder assets/) from a public mirror of Minecraft's resources.

    python3 fetch_assets.py                     ask first, then download what is missing (about 6 MB, 500 small files)
    python3 fetch_assets.py --yes               do not ask
    python3 fetch_assets.py --check             only say what is missing
    python3 fetch_assets.py --force             download everything again
    python3 fetch_assets.py --from FOLDER       copy from a folder you already have instead of the internet
                                                (a checkout of the mirror: it has assets/minecraft/textures inside)
    python3 fetch_assets.py --ref 26.2          which version of the mirror to use (a branch or tag name)

The files belong to Mojang Studios / Microsoft, not to this project (see NOTICE). They are fetched from a public mirror for use on this computer
only: do not publish or hand them out. Only the files in assets_manifest.json are fetched (the ones the game uses), each is checked to be a real
picture or sound before it is kept, and nothing is ever run.

The mirror: https://github.com/InventivetalentDev/minecraft-assets  (default version: 26.2)"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'assets_manifest.json'
DEFAULT_REF = '26.2'
DEFAULT_BASE = 'https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets'
MAX_BYTES = 8_000_000                  # no single file is anywhere near this: a bigger one is not what we asked for
SOURCE_ORDER = ('textures/block/', 'textures/item/', 'textures/entity/', 'textures/environment/', 'textures/gui/')
LATCH = {(7, 4): (60, 60, 60, 255), (7, 5): (200, 200, 200, 255), (7, 6): (60, 60, 60, 255), (8, 4): (60, 60, 60, 255), (8, 5): (60, 60, 60, 255), (8, 6): (60, 60, 60, 255)}          # the little latch drawn on the front of the chest

NOTICE = '''These are Minecraft's own pictures and sounds. They belong to Mojang Studios / Microsoft, not to this project.
They will be fetched from a public mirror (github.com/InventivetalentDev/minecraft-assets) for use on THIS computer only:
do not publish them or hand them out. (See the file NOTICE.)'''


class FetchError(Exception):
    """Something went wrong with getting the files (the message says what to do)."""


# ---- the list of files ------------------------------------------------------------------------------------------------------------

def load_manifest(path=MANIFEST):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise FetchError(f'Cannot read {path}: {error}') from None
    if not isinstance(data.get('files'), dict) or not data['files']:
        raise FetchError(f'{path} does not list any files.')
    for ours, theirs in data['files'].items():
        if ours.startswith(('/', '..')) or '..' in ours.split('/') or theirs.startswith(('/', '..')) or '..' in theirs.split('/'):
            raise FetchError(f'{path} has a path that is not allowed: {ours!r}')
    return data


def make_manifest(dump, assets=None):
    """(Maintenance, needs a checkout of the mirror.) Work out which file in the mirror each file of our assets/ came from, by comparing contents."""
    dump, assets = Path(dump), Path(assets or HERE / 'assets')
    root = dump / 'assets' / 'minecraft'
    if not root.is_dir():
        raise FetchError(f'{dump} does not look like a checkout of the mirror (no assets/minecraft inside).')
    index = {}
    for folder in (root / 'textures', root / 'sounds'):
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path.suffix in ('.png', '.ogg'):
                index.setdefault(hashlib.md5(path.read_bytes()).hexdigest(), []).append(path.relative_to(root).as_posix())
    files, own = {}, []
    for path in sorted(assets.rglob('*')):
        if not path.is_file() or path.suffix not in ('.png', '.ogg'):
            continue
        ours = path.relative_to(assets).as_posix()
        found = index.get(hashlib.md5(path.read_bytes()).hexdigest())
        if not found:
            own.append(ours)
            continue
        found.sort(key=lambda name: (next((i for i, prefix in enumerate(SOURCE_ORDER) if name.startswith(prefix)), 99), len(name), name))
        files[ours] = found[0]
    return {'about': 'Which file in the mirror each file of assets/ comes from (see fetch_assets.py). Only paths, no pictures.',
            'made_from': json.loads((dump / 'version.json').read_text()).get('id', '?') if (dump / 'version.json').exists() else '?',
            'files': files, 'derived': {name: 'made by fetch_assets.py from other files' for name in own if name.startswith('textures/chest_')},
            'derived_from': 'textures/entity/chest/normal.png',
            'ours': [name for name in own if not name.startswith('textures/chest_')]}


# ---- getting one file -------------------------------------------------------------------------------------------------------------------

def looks_right(path, data):
    """Is this really a picture or a sound (and not an error page the server sent instead)?"""
    if len(data) > MAX_BYTES or len(data) < 8:
        return False
    if path.endswith('.png'):
        return data[:8] == b'\x89PNG\r\n\x1a\n'
    if path.endswith('.ogg'):
        return data[:4] == b'OggS'
    return False


def read_source(source, theirs, base_url, ref, timeout=30):
    """The bytes of one file from the mirror (a folder on this computer, or a web address)."""
    if source is not None:
        path = Path(source) / 'assets' / 'minecraft' / theirs
        try:
            return path.read_bytes()
        except OSError:
            raise FetchError(f'not in the folder: {theirs}') from None
    url = f'{base_url.rstrip("/")}/{ref}/assets/minecraft/{theirs}'
    request = urllib.request.Request(url, headers={'User-Agent': 'PythonCraft-fetch-assets'})
    last = None
    for _attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as reply:
                return reply.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise FetchError(f'not on the mirror (version {ref}): {theirs}') from None
            last = error
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            last = error
    raise FetchError(f'could not download {theirs}: {last}')


def save(destination, data):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix='.part')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fetch(dest, manifest, source=None, base_url=DEFAULT_BASE, ref=DEFAULT_REF, force=False, workers=8, progress=None):
    """Get every file in the manifest that is not in `dest` yet. Returns (fetched, already_there, problems)."""
    dest = Path(dest)
    todo, there = [], 0
    for ours, theirs in manifest['files'].items():
        if (dest / ours).exists() and not force:
            there += 1
        else:
            todo.append((ours, theirs))
    problems, fetched = [], 0

    def one(pair):
        ours, theirs = pair
        data = read_source(source, theirs, base_url, ref)
        if not looks_right(ours, data):
            raise FetchError(f'what came back for {theirs} is not a real {"picture" if ours.endswith(".png") else "sound"}')
        save(dest / ours, data)
        return ours

    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if source is not None else workers) as pool:
        futures = {pool.submit(one, pair): pair for pair in todo}
        for number, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            try:
                future.result()
                fetched += 1
            except FetchError as error:
                problems.append(str(error))
            if progress and (number % 25 == 0 or number == len(todo)):
                progress(number, len(todo))
    return fetched, there, problems


# ---- the files made from other files ------------------------------------------------------------------------------------------------------

def make_derived(dest, reader, source_path, force=False):
    """The three chest faces are cut out of the chest's entity picture (and the front gets a small latch). `reader(path)` gets that picture from the
    mirror (it is not kept). Returns the names made."""
    from PIL import Image
    import io
    dest = Path(dest)
    wanted = {name: dest / 'textures' / name for name in ('chest_top.png', 'chest_front.png', 'chest_side.png')}
    if all(p.exists() for p in wanted.values()) and not force:
        return []
    try:
        data = reader(source_path)
        if not looks_right(source_path, data):
            return []
        with Image.open(io.BytesIO(data)) as opened:
            sheet = opened.convert('RGBA')
    except (FetchError, OSError):
        return []                                                    # (the picture to make them from is not there: the game uses flat colours)

    def stack(top, bottom):
        out = Image.new('RGBA', (top.width, top.height + bottom.height))
        out.paste(top, (0, 0))
        out.paste(bottom, (0, top.height))
        return out

    top = sheet.crop((14, 0, 28, 14)).resize((16, 16), Image.NEAREST)
    front = stack(sheet.crop((14, 14, 28, 19)), sheet.crop((14, 33, 28, 43))).resize((16, 16), Image.NEAREST)
    for position, colour in LATCH.items():
        front.putpixel(position, colour)
    side = stack(sheet.crop((0, 14, 14, 19)), sheet.crop((0, 33, 14, 43))).resize((16, 16), Image.NEAREST)
    made = []
    for name, image in (('chest_top.png', top), ('chest_front.png', front), ('chest_side.png', side)):
        if force or not wanted[name].exists():
            wanted[name].parent.mkdir(parents=True, exist_ok=True)
            image.save(wanted[name])
            made.append(name)
    return made


# ---- the command ----------------------------------------------------------------------------------------------------------------------------

def run(args, out=print, ask=input):
    manifest = load_manifest(args.manifest)
    dest = Path(args.dest)
    missing = [ours for ours in manifest['files'] if not (dest / ours).exists()]
    missing += [name for name in manifest.get('derived', {}) if not (dest / name).exists()]

    def reader(theirs):
        return read_source(args.source, theirs, args.base_url, args.ref)

    if args.check:
        total = len(manifest['files']) + len(manifest.get('derived', {}))
        out(f'{total - len(missing)} of {total} files are in {dest}' + (f', {len(missing)} missing.' if missing else '.'))
        return 1 if missing else 0
    if not missing and not args.force:
        out(f'Nothing to do: all {len(manifest["files"])} pictures and sounds are already in {dest}.')
        made = make_derived(dest, reader, manifest.get('derived_from', ''))
        if made:
            out(f'Made {", ".join(made)}.')
        return 0
    where = f'the folder {args.source}' if args.source else f'{args.base_url} (version {args.ref})'
    out(NOTICE if not args.source else 'Copying pictures and sounds from a folder you already have. (They belong to Mojang Studios / Microsoft: do not hand them out.)')
    if not args.yes:
        try:
            answer = ask(f'\nFetch {len(missing) if not args.force else len(manifest["files"])} files from {where}? [y/N] ').strip().lower()
        except EOFError:
            answer = ''
        if answer not in ('y', 'yes'):
            out('Nothing was fetched. (Use --yes to skip this question.)')
            return 2
    try:
        fetched, there, problems = fetch(dest, manifest, args.source, args.base_url, args.ref, args.force,
                                         progress=lambda done, total: out(f'  {done} / {total}'))
    except KeyboardInterrupt:
        out('Stopped. Run it again to carry on where it left off.')
        return 130
    made = make_derived(dest, reader, manifest.get('derived_from', ''), args.force)
    out(f'Fetched {fetched} file(s)' + (f', {there} were already there' if there else '') + (f'; made {", ".join(made)}' if made else '') + '.')
    if problems:
        out(f'{len(problems)} file(s) could not be fetched (the game uses flat colours for pictures that are missing):')
        for line in problems[:12]:
            out('  - ' + line)
        if len(problems) > 12:
            out(f'  ... and {len(problems) - 12} more')
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='fetch_assets.py', description="Download the game's pictures and sounds (assets/).")
    parser.add_argument('--yes', '-y', action='store_true', help='do not ask first')
    parser.add_argument('--check', action='store_true', help='only say what is missing')
    parser.add_argument('--force', action='store_true', help='fetch everything again, even what is here')
    parser.add_argument('--from', dest='source', metavar='FOLDER', help='copy from a checkout of the mirror you already have, instead of the internet')
    parser.add_argument('--ref', default=DEFAULT_REF, help=f'the mirror version: a branch or tag name (default {DEFAULT_REF})')
    parser.add_argument('--base-url', default=DEFAULT_BASE, help=argparse.SUPPRESS)
    parser.add_argument('--dest', default=str(HERE / 'assets'), help=argparse.SUPPRESS)
    parser.add_argument('--manifest', default=str(MANIFEST), help=argparse.SUPPRESS)
    parser.add_argument('--make-manifest', metavar='FOLDER', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.make_manifest:
            manifest = make_manifest(args.make_manifest)
            Path(args.manifest).write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
            print(f'Wrote {args.manifest}: {len(manifest["files"])} files, {len(manifest["derived"])} made from others, {len(manifest["ours"])} ours.')
            return 0
        return run(args)
    except FetchError as error:
        print(f'Problem: {error}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
