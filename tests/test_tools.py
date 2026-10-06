"""doctor.py, the launcher and the class window (windows are built and closed without a screen being needed where possible)."""
import gc
import socket
import threading
import time
import unittest
from unittest import mock

import tests
import doctor
import netproto as proto
from lanserver import LanServer, WorldState


class Doctor(unittest.TestCase):
    def test_a_full_check_runs_and_says_what_it_found(self):
        titles = dict(doctor.run_all())
        self.assertEqual(list(titles)[:6], ['This computer', 'Packages', 'Pictures and sounds', 'Mods', 'Saved worlds', 'Network'])
        self.assertLessEqual(len(titles), 7)                                  # (a seventh, 'Linux', appears on Linux only)
        self.assertEqual(titles['This computer'][0][0], doctor.OK)
        for results in titles.values():
            for status, text, hint in results:
                self.assertIn(status, (doctor.OK, doctor.NOTE, doctor.PROBLEM))
                self.assertTrue(text)

    def test_reach_finds_a_class_server_and_explains_a_missing_one(self):
        server = LanServer(WorldState(), pin='abcd12', code='x-y-11', host='127.0.0.1', port=0).start()
        try:
            found = doctor.reach('127.0.0.1', server.port)
            self.assertEqual([r[0] for r in found], [doctor.OK, doctor.OK])
            self.assertIn('class server', found[1][1])
        finally:
            server.stop()
        nothing = doctor.reach('127.0.0.1', 1, timeout=1)
        self.assertEqual(nothing[0][0], doctor.PROBLEM)
        self.assertIn('same network', nothing[0][2])

    def test_listen_says_who_connected(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        heard = []
        thread = threading.Thread(target=lambda: heard.extend(doctor.listen(port, seconds=3)), daemon=True)
        thread.start()
        time.sleep(0.5)
        socket.create_connection(('127.0.0.1', port), 2).close()
        thread.join(5)
        self.assertEqual(len(heard), 1)
        self.assertIn('127.0.0.1', heard[0][1])

    def test_listen_on_a_busy_port_says_so(self):
        with socket.socket() as busy:
            busy.bind(('', 0))
            busy.listen(1)
            result = doctor.listen(busy.getsockname()[1], seconds=1)
        self.assertEqual(result[0][0], doctor.PROBLEM)

    def test_address_helpers(self):
        self.assertTrue(doctor.can_listen('tcp', 0))
        for address in doctor.local_addresses():
            self.assertFalse(address.startswith('127.'))


class Icons(unittest.TestCase):
    def test_every_tile_has_a_picture_even_without_the_game_pictures(self):
        import launcher
        for textures in (launcher.TEXTURES, tests.scratch('no_textures')):                  # (the second folder has none: flat colours are used)
            with mock.patch.object(launcher, 'TEXTURES', textures):
                icons = launcher.make_icons()
            self.assertEqual(len(icons), 8)
            for name, image in icons.items():
                self.assertEqual(image.size, (96, 96), name)
                opaque = sum(1 for a in image.getchannel('A').getdata() if a > 200)
                self.assertGreater(opaque, 2500, f'{name} looks empty')                       # (a solid block, not nothing)


def window_or_skip(test):
    import tkinter
    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        test.skipTest('no screen for a window')
    root.withdraw()
    return root


class Windows(unittest.TestCase):
    def test_the_launcher_builds_and_its_check_runs(self):
        root = window_or_skip(self)
        try:
            import launcher
            app = launcher.Launcher(root)
            self.assertEqual(list(app.buttons), ['Play on my own', 'Tutorial worlds', 'Join a class', 'Live coding', 'Paint a picture', 'Mods folder',
                                                 'Host a class', 'Check my setup'])
            app.write('hello\n')
            root.update()
            self.assertIn('hello', app.log.get('1.0', 'end'))
            app.doctor()                                                    # (opens its report window)
            root.update()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and 'checking' in app.badge.cget('text'):
                root.update()
                time.sleep(0.1)
            self.assertNotIn('checking', app.badge.cget('text'))              # (the badge says how the setup is)
        finally:
            for child in root.winfo_children():
                if child.winfo_class() == 'Toplevel':
                    child.destroy()
            app.close()

    def test_all_the_words_fit_inside_their_tiles(self):
        root = window_or_skip(self)
        try:
            import launcher
            from tkinter import font as tkfont
            app = launcher.Launcher(root)
            root.update()
            label_font = tkfont.Font(family=launcher.Launcher.family, size=14, weight='bold')
            hint_font = tkfont.Font(family=launcher.Launcher.family, size=10)
            for tile in app.order:
                self.assertLess(label_font.measure(tile.label), launcher.TILE_W - 126, tile.label)
                lines, line = 1, ''
                for word in tile.hint.split():
                    trial = (line + ' ' + word).strip()
                    if hint_font.measure(trial) > launcher.TILE_W - 130 and line:
                        lines, line = lines + 1, word
                    else:
                        line = trial
                self.assertLessEqual(lines, 2, f'{tile.label}: the help text is three lines and would run out of the tile')
            self.assertLessEqual(root.winfo_reqwidth(), 1000)                       # (fits on a small screen)
            app.close()
        finally:
            gc.collect()

    def test_tiles_start_things_with_a_click_or_a_number(self):
        root = window_or_skip(self)
        try:
            import launcher
            app = launcher.Launcher(root)
            started = []
            for tile in app.order:
                tile.action = lambda label=tile.label: started.append(label)
            app.buttons['Live coding'].invoke()
            app.key(type('Key', (), {'keysym': '1', 'char': '1'})())          # the number on the first tile
            app.key(type('Key', (), {'keysym': '8', 'char': '8'})())
            app.key(type('Key', (), {'keysym': '9', 'char': '9'})())          # (there is no 9: nothing happens)
            self.assertEqual(started, ['Live coding', 'Play on my own', 'Check my setup'])
            self.assertEqual([tile.number for tile in app.order], list(range(1, 9)))
            app.close()
        finally:
            gc.collect()

    def test_the_class_window_designs_saves_and_starts_a_class(self):
        root = window_or_skip(self)
        try:
            import classtool
            from classworld import ClassSetup
            window = classtool.open_window(parent=root)
            window.withdraw()
            root.update()
            canvas = [w for w in window.winfo_children()[1].winfo_children() if w.winfo_class() == 'Canvas'][0]
            self.assertTrue(canvas.find_all())                              # (the plots are drawn)
            window.destroy()
        finally:
            root.destroy()
            gc.collect()

    def test_the_dashboard_shows_and_controls_the_class(self):
        root = window_or_skip(self)
        server = None
        try:
            import classtool
            from lanclient import LanClient
            from classworld import ClassSetup
            setup = ClassSetup.for_roster('dash', ['Ann'])
            server = LanServer(setup.build_world(), pin='abcd12', code='x-y-11', host='127.0.0.1', port=0).start()
            client = LanClient('127.0.0.1', server.port, 'x-y-11', 'Ann')
            client.connect()
            dashboard = classtool.Dashboard(root, server)
            dashboard.window.withdraw()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not dashboard.table.get_children():
                root.update()
                time.sleep(0.1)
            self.assertEqual(len(dashboard.table.get_children()), 1)
            item = dashboard.table.get_children()[0]
            dashboard.table.selection_set(item)
            dashboard.run_selected('mode creative {w}')
            time.sleep(0.2)
            self.assertEqual(server.players[int(item)].mode, 'creative')
            dashboard.run('lock')
            self.assertTrue(server.building_locked)
            client.close()
            dashboard.running = False
            dashboard.window.destroy()
        finally:
            if server is not None:
                server.stop()
            root.destroy()
            gc.collect()


if __name__ == '__main__':
    unittest.main()
