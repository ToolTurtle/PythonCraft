"""Saving and loading worlds.

A world is a folder inside saves/ with two files:
  level.json      who you are and what you carry: position, inventory, furnaces, animals, settings...
  blocks.json.gz  every block you changed. (The land itself is not saved: it is made again from the seed.)"""
import gzip
import json
import os
import re
import shutil
from pathlib import Path

# Where worlds are kept. Tests set PYTHONCRAFT_SAVES to a throwaway folder so real worlds are never touched.
SAVES = Path(os.environ.get('PYTHONCRAFT_SAVES') or Path(__file__).parent / 'saves')
VERSION = 1


def _slug(name):
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_') or 'world'


def new_folder(name):
    """A folder for a new world that doesn't exist yet."""
    base = SAVES / _slug(name)
    folder, number = base, 2
    while folder.exists():
        folder = base.with_name(f'{base.name}_{number}')
        number += 1
    return folder


def list_worlds():
    """Short descriptions of every saved world, most recently played first."""
    worlds = []
    for level_file in SAVES.glob('*/level.json'):
        try:
            info = json.loads(level_file.read_text())
            worlds.append({'path': level_file.parent, 'name': info['name'], 'seed': info['seed'],
                           'mode': info['player']['mode'], 'last_played': info['last_played']})
        except (OSError, ValueError, KeyError):
            continue                        # a broken save: skip it instead of crashing
    return sorted(worlds, key=lambda w: w['last_played'], reverse=True)


def _write(path, data):
    """Write to a temporary file first, so a crash never leaves a half-written save."""
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    os.replace(temporary, path)


def save(folder, level, modified, facing=None, flowing=None, dims=None):
    """`level` is a dict of plain values; `modified` maps (x, y, z) -> block name (or None for air);
    `facing` maps (x, y, z) -> the way an oriented block is turned."""
    folder.mkdir(parents=True, exist_ok=True)
    level = dict(level, version=VERSION)
    blocks = {'blocks': [[x, y, z, kind] for (x, y, z), kind in modified.items()],
              'facing': [[x, y, z, o] for (x, y, z), o in (facing or {}).items()],
              'flowing': [[x, y, z, n] for (x, y, z), n in (flowing or {}).items()],
              'dims': {name: {'blocks': [[x, y, z, kind] for (x, y, z), kind in d['modified'].items()],
                              'facing': [[x, y, z, o] for (x, y, z), o in d['facing'].items()],
                              'flowing': [[x, y, z, n] for (x, y, z), n in d['flowing'].items()]}
                       for name, d in (dims or {}).items()}}
    _write(folder / 'blocks.json.gz', gzip.compress(json.dumps(blocks).encode()))
    _write(folder / 'level.json', json.dumps(level, indent=1).encode())


def load(folder):
    """Returns (level, modified, facing, flowing)."""
    level = json.loads((folder / 'level.json').read_text())
    modified, facing, flowing = {}, {}, {}
    blocks_file = folder / 'blocks.json.gz'
    if blocks_file.exists():
        stored = json.loads(gzip.decompress(blocks_file.read_bytes()))
        if isinstance(stored, list):                      # (an older save: just the blocks)
            stored = {'blocks': stored, 'facing': [], 'flowing': []}
        for x, y, z, kind in stored['blocks']:
            modified[(x, y, z)] = kind
        for x, y, z, orient in stored['facing']:
            facing[(x, y, z)] = orient
        for x, y, z, n in stored.get('flowing', []):
            flowing[(x, y, z)] = n
    return level, modified, facing, flowing


def load_dims(folder):
    """The blocks of the other dimensions: {name: (modified, facing, flowing)}."""
    blocks_file = folder / 'blocks.json.gz'
    if not blocks_file.exists():
        return {}
    stored = json.loads(gzip.decompress(blocks_file.read_bytes()))
    if not isinstance(stored, dict):
        return {}
    return {name: ({(x, y, z): kind for x, y, z, kind in d['blocks']}, {(x, y, z): o for x, y, z, o in d['facing']},
                   {(x, y, z): n for x, y, z, n in d['flowing']})
            for name, d in stored.get('dims', {}).items()}


def delete(folder):
    shutil.rmtree(folder, ignore_errors=True)
