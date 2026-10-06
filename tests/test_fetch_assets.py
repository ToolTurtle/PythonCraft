"""fetch_assets.py: downloads the pictures and sounds. Tested against a pretend mirror (made here, served from this computer): nothing goes to the internet."""
import argparse
import functools
import http.server
import io
import json
import threading
import unittest
from pathlib import Path

import tests
import fetch_assets
from PIL import Image
from tests import ROOT, scratch

MANIFEST = fetch_assets.load_manifest()


def png(size=(4, 4), colour=(10, 20, 30, 255)):
    buffer = io.BytesIO()
    Image.new('RGBA', size, colour).save(buffer, 'PNG')
    return buffer.getvalue()


def make_mirror(name, skip=(), html=()):
    """A pretend mirror: <root>/26.2/assets/minecraft/<every path in the manifest>. `skip`: paths left out; `html`: paths that hold an error page."""
    root = scratch(name)
    base = root / '26.2' / 'assets' / 'minecraft'
    paths = set(MANIFEST['files'].values()) | {MANIFEST['derived_from']}
    for theirs in paths:
        if theirs in skip:
            continue
        target = base / theirs
        target.parent.mkdir(parents=True, exist_ok=True)
        if theirs in html:
            target.write_bytes(b'<html>404: Not Found</html>')
        elif theirs == MANIFEST['derived_from']:
            Image.new('RGBA', (64, 64), (90, 60, 30, 255)).save(target)
        elif theirs.endswith('.ogg'):
            target.write_bytes(b'OggS' + b'\0' * 40)
        else:
            target.write_bytes(png())
    return root


def args(dest, **options):
    values = dict(manifest=str(fetch_assets.MANIFEST), dest=str(dest), source=None, base_url=fetch_assets.DEFAULT_BASE, ref='26.2', yes=True, check=False,
                  force=False)
    values.update(options)
    return argparse.Namespace(**values)


def run(namespace, answer=None):
    lines = []
    code = fetch_assets.run(namespace, out=lines.append, ask=(lambda prompt: answer) if answer is not None else input)
    return code, '\n'.join(lines)


class TheList(unittest.TestCase):
    def test_the_manifest_lists_what_the_game_uses_and_only_safe_paths(self):
        files = MANIFEST['files']
        self.assertGreaterEqual(len(files), 500)
        for ours, theirs in files.items():
            self.assertTrue(ours.endswith(('.png', '.ogg')), ours)
            self.assertTrue(theirs.startswith(('textures/', 'sounds/')), theirs)
            self.assertNotIn('..', ours + theirs)
        self.assertIn('textures/dirt.png', files)
        self.assertIn('textures/chest_top.png', MANIFEST['derived'])
        self.assertTrue(any(name.startswith('sounds/') for name in files))

    def test_a_manifest_with_a_path_that_climbs_out_is_refused(self):
        bad = scratch('badmanifest') / 'm.json'
        bad.write_text(json.dumps({'files': {'../../evil.png': 'textures/block/dirt.png'}}))
        with self.assertRaisesRegex(fetch_assets.FetchError, 'not allowed'):
            fetch_assets.load_manifest(bad)
        bad.write_text(json.dumps({'files': {'textures/a.png': '/etc/passwd'}}))
        with self.assertRaises(fetch_assets.FetchError):
            fetch_assets.load_manifest(bad)
        bad.write_text('nonsense')
        with self.assertRaises(fetch_assets.FetchError):
            fetch_assets.load_manifest(bad)

    def test_what_counts_as_a_real_file(self):
        self.assertTrue(fetch_assets.looks_right('a.png', png()))
        self.assertTrue(fetch_assets.looks_right('a.ogg', b'OggS' + b'\0' * 20))
        for data in (b'<html>Not Found</html>', b'', b'\x89PNG', b'x' * 9_000_000):
            self.assertFalse(fetch_assets.looks_right('a.png', data))
        self.assertFalse(fetch_assets.looks_right('a.ogg', png()))
        self.assertFalse(fetch_assets.looks_right('a.txt', b'OggS' + b'\0' * 20))


class FromAFolder(unittest.TestCase):
    def test_copies_everything_and_makes_the_chest_faces(self):
        mirror, dest = make_mirror('mirror_a'), scratch('dest_a') / 'assets'
        code, text = run(args(dest, source=str(mirror / '26.2')))
        self.assertEqual(code, 0, text)
        for ours in MANIFEST['files']:
            self.assertTrue((dest / ours).exists(), ours)
        for name in ('chest_top.png', 'chest_front.png', 'chest_side.png'):
            with Image.open(dest / 'textures' / name) as picture:
                self.assertEqual(picture.size, (16, 16))
        self.assertIn('made chest_top.png', text)
        self.assertEqual(list(dest.rglob('*.part')), [])                              # (nothing half-written is left)
        self.assertFalse((dest / 'textures' / 'entity' / 'chest').exists())           # (the picture the chest faces come from is not kept)

    def test_a_second_run_does_nothing_and_force_does_it_again(self):
        mirror, dest = make_mirror('mirror_b'), scratch('dest_b') / 'assets'
        run(args(dest, source=str(mirror / '26.2')))
        code, text = run(args(dest, source=str(mirror / '26.2')))
        self.assertEqual((code, 'Nothing to do' in text), (0, True))
        marker = dest / 'textures' / 'dirt.png'
        marker.write_bytes(png(colour=(1, 1, 1, 255)))
        run(args(dest, source=str(mirror / '26.2')))
        self.assertEqual(marker.read_bytes(), png(colour=(1, 1, 1, 255)))              # (what is there is left alone)
        code, text = run(args(dest, source=str(mirror / '26.2'), force=True))
        self.assertEqual(marker.read_bytes(), png())                                   # (--force fetches it again)

    def test_check_only_reports(self):
        mirror, dest = make_mirror('mirror_c'), scratch('dest_c') / 'assets'
        code, text = run(args(dest, check=True))
        self.assertEqual(code, 1)
        self.assertIn('missing', text)
        self.assertFalse(dest.exists())
        run(args(dest, source=str(mirror / '26.2')))
        self.assertEqual(run(args(dest, check=True))[0], 0)

    def test_a_missing_file_is_reported_and_the_rest_is_kept(self):
        victim = next(iter(MANIFEST['files'].values()))
        mirror, dest = make_mirror('mirror_d', skip={victim}), scratch('dest_d') / 'assets'
        code, text = run(args(dest, source=str(mirror / '26.2')))
        self.assertEqual(code, 1)
        self.assertIn(victim, text)
        self.assertEqual(sum(1 for _ in dest.rglob('*.png')) + sum(1 for _ in dest.rglob('*.ogg')), len(MANIFEST['files']) - 1 + 3)
        self.assertIn('flat colours', text)


class Asking(unittest.TestCase):
    def test_nothing_is_downloaded_without_a_yes(self):
        mirror = make_mirror('mirror_e')
        for answer in ('n', '', 'maybe'):
            dest = scratch(f'dest_e_{answer or "empty"}') / 'assets'
            code, text = run(args(dest, source=str(mirror / '26.2'), yes=False), answer=answer)
            self.assertEqual(code, 2, text)
            self.assertFalse(dest.exists())
        self.assertIn('Mojang', text)                                                 # (and it said whose they are before asking)
        dest = scratch('dest_e_yes') / 'assets'
        self.assertEqual(run(args(dest, source=str(mirror / '26.2'), yes=False), answer='y')[0], 0)
        self.assertTrue((dest / 'textures' / 'dirt.png').exists())

    def test_no_keyboard_means_no(self):
        def no_keyboard(prompt):
            raise EOFError
        lines = []
        code = fetch_assets.run(args(scratch('dest_f') / 'assets', yes=False), out=lines.append, ask=no_keyboard)
        self.assertEqual(code, 2)


class FromTheWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.victim = sorted(MANIFEST['files'].values())[3]
        cls.fake_page = sorted(MANIFEST['files'].values())[7]
        cls.mirror = make_mirror('mirror_web', skip={cls.victim}, html={cls.fake_page})
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(cls.mirror))
        handler.log_message = lambda *a, **k: None
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_downloads_over_http_and_refuses_what_is_not_a_real_file(self):
        dest = scratch('dest_web') / 'assets'
        code, text = run(args(dest, base_url=self.url))
        self.assertEqual(code, 1, text)
        self.assertIn('not on the mirror', text)                                      # (404: said so)
        self.assertIn('not a real', text)                                             # (an error page where a picture should be: refused)
        by_theirs = {theirs: ours for ours, theirs in MANIFEST['files'].items()}
        self.assertFalse((dest / by_theirs[self.victim]).exists())
        self.assertFalse((dest / by_theirs[self.fake_page]).exists())                  # (not kept)
        self.assertEqual(sum(1 for p in dest.rglob('*') if p.suffix in ('.png', '.ogg')), len(MANIFEST['files']) - 2 + 3)

    def test_an_unreachable_server_is_a_message_not_a_crash(self):
        code, text = run(args(scratch('dest_none') / 'assets', base_url='http://127.0.0.1:1'))
        self.assertEqual(code, 1)
        self.assertIn('could not download', text)


class ExactlyWhatWeHave(unittest.TestCase):
    """If this computer has both the game's pictures and a copy of the mirror, fetching reproduces every file exactly."""

    def test_a_fetch_from_the_local_copy_is_identical(self):
        dump = ROOT / 'minecraft-assets-26.4-snapshot-2'
        if not (dump / 'assets' / 'minecraft').is_dir() or not (ROOT / 'assets' / 'textures' / 'dirt.png').exists():
            self.skipTest('no copy of the mirror here to compare with')
        dest = scratch('dest_exact') / 'assets'
        code, text = run(args(dest, source=str(dump)))
        self.assertEqual(code, 0, text)
        for ours in list(MANIFEST['files']) + list(MANIFEST['derived']):
            self.assertEqual((dest / ours).read_bytes(), (ROOT / 'assets' / ours).read_bytes(), ours)


class TheOtherFiles(unittest.TestCase):
    def test_our_own_files_are_kept_in_git_and_the_rest_is_not(self):
        import subprocess
        tracked = subprocess.run(['git', 'ls-files', 'assets'], capture_output=True, text=True, cwd=str(ROOT)).stdout.split()
        if not tracked and not (ROOT / '.git').exists():
            self.skipTest('not a git checkout')
        self.assertEqual(sorted(tracked), ['assets/blank_cursor.png', 'assets/textures/README.md'])


if __name__ == '__main__':
    unittest.main()
