"""Running on Linux (Linux Mint and friends): what can be checked from any computer."""
import ast
import os
import re
import subprocess
import unittest
from unittest import mock

import tests
import doctor
from tests import ROOT


class Scripts(unittest.TestCase):
    def test_the_shell_scripts_are_valid_and_executable(self):
        for name in ('setup_linux.sh', 'pythoncraft.sh'):
            path = ROOT / name
            self.assertTrue(os.access(path, os.X_OK), f'{name} is not executable')
            self.assertEqual(subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True).returncode, 0, name)
            self.assertTrue(path.read_text().startswith('#!/usr/bin/env bash'))

    def test_setup_dry_run_says_what_it_would_do_and_changes_nothing(self):
        before = (ROOT / '.venv').exists()
        out = subprocess.run([str(ROOT / 'setup_linux.sh'), '--dry-run', '--no-apt', '--desktop'], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        for words in ('would run: python3 -m venv .venv', 'pip install -r requirements.txt', 'pythoncraft.desktop', 'doctor.py'):
            self.assertIn(words, out.stdout)
        self.assertEqual((ROOT / '.venv').exists(), before)
        offline = subprocess.run([str(ROOT / 'setup_linux.sh'), '--dry-run', '--no-apt', '--wheels', 'wheels'], capture_output=True, text=True, timeout=60)
        self.assertIn('--no-index --find-links wheels', offline.stdout)
        self.assertNotIn('--upgrade pip', offline.stdout)                            # (nothing is fetched from the internet)
        for bad_args in (['--nonsense'], ['--wheels']):
            self.assertEqual(subprocess.run([str(ROOT / 'setup_linux.sh')] + bad_args, capture_output=True, text=True).returncode, 2)

    def test_the_launcher_script_knows_its_words(self):
        text = (ROOT / 'pythoncraft.sh').read_text()
        for word, script in (('play', 'main.py'), ('live', 'livecode.py'), ('host', 'lan.py host'), ('join', 'lan.py join'), ('class', 'classtool.py'),
                             ('doctor', 'doctor.py'), ('paint', 'painter.py'), ('test', 'run_tests.py')):
            self.assertRegex(text, rf'{word}\)\s+exec "\$PY" {re.escape(script)}')
        out = subprocess.run([str(ROOT / 'pythoncraft.sh'), 'doctor'], capture_output=True, text=True, timeout=120)
        self.assertIn('This computer', out.stdout)                                  # (it really runs doctor.py)
        self.assertEqual(subprocess.run([str(ROOT / 'pythoncraft.sh'), 'nonsense'], capture_output=True, text=True).returncode, 2)

    def test_the_requirements_name_what_the_code_imports(self):
        names = {line.split('#')[0].strip().split('>')[0].split('=')[0].lower() for line in (ROOT / 'requirements.txt').read_text().splitlines()
                 if line.split('#')[0].strip()}
        self.assertEqual(names, {'ursina', 'numpy', 'pillow'})
        imported = set()
        for path in ROOT.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split('.')[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    imported.add(node.module.split('.')[0])
        for module in ('ursina', 'numpy', 'PIL', 'panda3d'):
            self.assertIn(module, imported)
        for third_party in ('requests', 'scipy', 'pygame', 'yaml', 'pandas'):             # (nothing else may sneak in that is not in requirements.txt)
            self.assertNotIn(third_party, imported)


class OldPython(unittest.TestCase):
    """Linux Mint 21 has Python 3.10, Mint 22 has 3.12: nothing newer than 3.10 may be used."""

    def test_every_file_is_valid_for_python_3_10(self):
        skip = ('minecraft-assets', 'assets', 'saves', '.git', '__pycache__', 'drafts', 'lanworlds', '.venv')
        for path in sorted(ROOT.rglob('*.py')):
            if any(part.startswith(skip) or part in skip for part in path.relative_to(ROOT).parts):
                continue
            try:
                ast.parse(path.read_text(), feature_version=(3, 10))
            except SyntaxError as error:
                self.fail(f'{path.relative_to(ROOT)} line {error.lineno}: {error.msg} (needs a newer Python than 3.10)')

    def test_no_newer_library_pieces(self):
        newer = {('datetime', 'UTC'), ('itertools', 'batched'), ('asyncio', 'TaskGroup'), ('asyncio', 'timeout'), ('typing', 'Self')}
        for path in ROOT.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and (node.value.id, node.attr) in newer:
                    self.fail(f'{path.name} line {node.lineno}: {node.value.id}.{node.attr} needs Python 3.11 or newer')
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = node.module if isinstance(node, ast.ImportFrom) else None
                    names = [a.name for a in node.names]
                    if 'tomllib' in names or module == 'tomllib':
                        self.fail(f'{path.name}: tomllib needs Python 3.11')


class DoctorOnLinux(unittest.TestCase):
    def check(self, env, which=None, find_library='openal', system='Linux'):
        which = which or {}
        with mock.patch('doctor.platform.system', return_value=system), mock.patch.dict(os.environ, env, clear=True), \
                mock.patch('doctor.shutil.which', side_effect=lambda name: which.get(name)), \
                mock.patch('doctor.ctypes.util.find_library', return_value=find_library):
            return doctor.check_linux()

    def test_nothing_to_say_on_other_systems(self):
        self.assertEqual(self.check({}, system='Darwin'), [])

    def test_no_screen_is_a_problem_with_a_plain_answer(self):
        results = self.check({})
        problems = [r for r in results if r[0] == doctor.PROBLEM]
        self.assertTrue(problems and 'DISPLAY' in problems[0][1])
        self.assertFalse(self.check({'DISPLAY': ':0'}) and any(r[0] == doctor.PROBLEM for r in self.check({'DISPLAY': ':0'})))

    def test_wayland_and_missing_helpers_are_explained(self):
        results = self.check({'WAYLAND_DISPLAY': 'wayland-0', 'XDG_SESSION_TYPE': 'wayland'}, find_library=None)
        text = ' '.join(r[1] + ' ' + r[2] for r in results)
        for words in ('Wayland', 'X11', 'xclip', 'libopenal1', 'mesa-utils'):
            self.assertIn(words, text)
        self.assertNotIn('Wayland', ' '.join(r[1] for r in self.check({'DISPLAY': ':0', 'XDG_SESSION_TYPE': 'x11'}, which={'xclip': '/usr/bin/xclip'})))

    def test_slow_or_old_graphics_are_caught(self):
        def graphics(text):
            with mock.patch('doctor.subprocess.run', return_value=mock.Mock(stdout=text)):
                return self.check({'DISPLAY': ':0'}, which={'glxinfo': '/usr/bin/glxinfo', 'xclip': 'x'})
        old = graphics('OpenGL renderer string: Old GPU\nOpenGL version string: 2.1 Mesa 20\n')
        self.assertTrue(any(r[0] == doctor.PROBLEM and 'OpenGL 2.1' in r[1] for r in old))
        soft = graphics('OpenGL renderer string: llvmpipe (LLVM 15)\nOpenGL version string: 4.5 Mesa 23\n')
        self.assertTrue(any(r[0] == doctor.NOTE and 'slow' in r[1] for r in soft))
        good = graphics('OpenGL renderer string: Intel UHD Graphics 620\nOpenGL version string: 4.6 Mesa 23\n')
        self.assertTrue(any(r[0] == doctor.OK and 'Intel' in r[1] for r in good))

    def test_the_firewall_commands_are_given(self):
        results = self.check({'DISPLAY': ':0'}, which={'ufw': '/usr/sbin/ufw', 'xclip': 'x'})
        text = ' '.join(r[2] for r in results)
        self.assertIn('ufw allow 25570/tcp', text)
        self.assertIn('ufw allow 25571/udp', text)

    def test_install_hints_fit_the_computer(self):
        with mock.patch('doctor.platform.system', return_value='Linux'):
            self.assertIn('setup_linux.sh', doctor.install_hint('ursina'))
            self.assertIn('sudo apt install python3-tk', doctor.install_hint(None, 'python3-tk'))
        with mock.patch('doctor.platform.system', return_value='Darwin'):
            self.assertEqual(doctor.install_hint('ursina'), 'pip3 install ursina')


class PainterShortcuts(unittest.TestCase):
    def test_a_system_that_does_not_know_command_does_not_stop_the_painter(self):
        import tkinter
        import painter

        class Root:
            def __init__(self):
                self.bound = []

            def bind(self, sequence, function):
                if 'Command' in sequence:
                    raise tkinter.TclError(f'bad event type or keysym "Command"')
                self.bound.append(sequence)

        root = Root()
        painter.bind_shortcuts(root, None, None, None)
        self.assertEqual(root.bound, ['<Control-s>', '<Control-z>', '<Control-Z>'])


if __name__ == '__main__':
    unittest.main()
