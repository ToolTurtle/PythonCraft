"""The classroom game with a real game window: another player appears, the teacher's orders arrive, blocks are shared both ways."""
import os
import subprocess
import sys
import unittest

import tests
from tests import ROOT, scratch

SCRIPT = '''
import sys, time, threading
sys.path.insert(0, {root!r})
import math
from lanserver import LanServer, WorldState
from lanclient import LanClient

server = LanServer(WorldState(seed=5, title='Test class'), pin='teach1', code='maple-tiger-42', host='127.0.0.1', port=0).start()
target = {{}}

def ann():
    me = None
    for _ in range(100):                                   # wait for Sam to be in the world
        time.sleep(0.1)
        found = [p for p in server.players.values() if p.name == 'Sam' and p.pos is not None]
        if found:
            me = found[0]
            break
    c = LanClient('127.0.0.1', server.port, 'maple-tiger-42', 'Ann')
    c.connect()
    c.chat('/teacher teach1')
    time.sleep(0.4)
    sx, sy, sz = me.pos
    for _ in range(8):
        c.send_pos(sx + 2, sy, sz + 2, 90, 0, True)
        time.sleep(0.1)
    c.chat('/mode survival Sam')
    time.sleep(0.4)
    block = (round(sx) + 1, round(sy) + 2, round(sz) + 1)
    target['block'] = block
    c.send_blocks([(block[0], block[1], block[2], 'gold_block', None)])
    time.sleep(6)
    c.close()

threading.Thread(target=ann, daemon=True).start()

def hook(game, client, remotes, chat):
    from ursina import invoke
    def check():
        block = target.get('block')
        print('REMOTES', len(remotes), flush=True)
        print('MODE', game.player.mode, game.player.build_locked, flush=True)
        print('SHARED', block is not None and game.world.get(block) == 'gold_block', flush=True)
        if block:
            game.interaction._break(block, 'gold_block')                # Sam breaks it: the server must hear
            invoke(lambda: print('SERVER', server.world.changes.get(block), flush=True), delay=2.5)
    invoke(check, delay=4.5)

import lanplay
lanplay.play('127.0.0.1', server.port, 'maple-tiger-42', 'Sam', seconds=9, hook=hook)
server.stop()
'''


CLASS_SCRIPT = '''
import sys, time, threading
sys.path.insert(0, {root!r})
from classlayout import Layout
from lanserver import LanServer, WorldState
from lanclient import LanClient

layout = Layout.grid(2, 1, width=16, depth=16, gap=5, names=['Sam'])
world = WorldState(0, 'Class', list(layout.spawn), {{pos: (name, None) for pos, name in layout.marker_blocks().items()}}, layout)
server = LanServer(world, pin='teach1', code='maple-tiger-42', host='127.0.0.1', port=0).start()
ann_events = []

def ann():
    for _ in range(100):
        time.sleep(0.1)
        if any(p.name == 'Sam' and p.pos is not None for p in server.players.values()):
            break
    c = LanClient('127.0.0.1', server.port, 'maple-tiger-42', 'Ann')
    c.connect()
    c.chat('/claim')
    while not c.closed:
        ann_events.extend(c.poll())
        time.sleep(0.05)

threading.Thread(target=ann, daemon=True).start()

def hook(game, client, remotes, chat):
    from ursina import invoke
    from inventory import Stack
    lan = game.lan
    session = lan.state['session']
    print('SESSION_PLOT', session.lan_plot, 'AUTHORITY', lan.state['authority'], 'TAGS', len(lan.state['tags']), flush=True)
    session.feed('fill 0 0 0 3 0 3 gold_block')
    session.feed('placeblock 6 5 6 sand')
    session.feed('placeblock 8 0 8 chest')
    game.player.position = (8, 5, 6)                                   # (next to the chest: the server only believes chests that are near)
    def use_chest():
        game.ui.open_chest((8, 4, 8))
        game.world.chests[(8, 4, 8)][0] = Stack('stone', 3)
        game.ui.close()
    invoke(use_chest, delay=0.7)
    lan.state['teacher'] = True
    lan.panel.update_roster([{{'id': 1, 'name': 'Sam', 'teacher': False, 'mode': 'adventure', 'frozen': False, 'muted': False, 'code': True, 'plot': 1, 'last': 'fill'}}], False, True)
    lan.panel.open()
    print('PANEL_ROWS', len(lan.panel._dynamic) > 5, flush=True)
    lan.panel.close()
    def check():
        print('GOLD', server.world.changes.get((0, 4, 0)), flush=True)
        print('CHEST', server.world.chests.get((8, 4, 8), [None])[0], flush=True)
        sand = [e for e in ann_events if e['t'] == 'blocks' and e.get('sim') and any(c[3] == 'sand' for c in e['c'])]
        print('SAND_SIM', bool(sand), flush=True)
        print('PLOT2', server.world.layout.plot_by_id(2).owner, flush=True)
        code_blocks = [e for e in ann_events if e['t'] == 'blocks' and e['by'] != 0 and not e.get('sim')]
        print('ANN_SAW_CODE_BLOCKS', len(code_blocks) > 0, flush=True)
    invoke(check, delay=4.5)

import lanplay
lanplay.play('127.0.0.1', server.port, 'maple-tiger-42', 'Sam', seconds=9, hook=hook)
server.stop()
'''


ANIMAL_SCRIPT = '''
import sys, time, threading
sys.path.insert(0, {root!r})
from classlayout import Layout
from lanserver import LanServer, WorldState
from lanclient import LanClient

layout = Layout.grid(2, 1, width=16, depth=16, gap=5)
world = WorldState(0, 'Class', list(layout.spawn), {{pos: (name, None) for pos, name in layout.marker_blocks().items()}}, layout)
server = LanServer(world, pin='teach1', code='maple-tiger-42', host='127.0.0.1', port=0).start()

def ann():
    for _ in range(100):
        time.sleep(0.1)
        if any(p.name == 'Sam' and p.pos is not None for p in server.players.values()):
            break
    c = LanClient('127.0.0.1', server.port, 'maple-tiger-42', 'Ann')
    c.connect()
    c.send_pos(layout.spawn[0], layout.spawn[1], layout.spawn[2], 0, 0)
    victim, seen = None, False
    end = time.time() + 40
    while time.time() < end and not c.closed:
        for e in c.poll():
            if e['t'] == 'mobs':
                ids = [m[0] for m in e['c']]
                if victim is None and ids:
                    seen = True
                    print('ANIMALS_SEEN', len(ids), sorted({{m[1] for m in e['c']}}), flush=True)
                    victim = ids[0]
                    c.send_mobhit(victim, 20)
                elif victim is not None and victim not in ids:
                    print('KILLED', True, flush=True)
                    return
        time.sleep(0.05)
    print('KILLED', False, 'seen', seen, flush=True)

threading.Thread(target=ann, daemon=True).start()
import lanplay
lanplay.play('127.0.0.1', server.port, 'maple-tiger-42', 'Sam', seconds=40, hook=lambda *a: None)
'''


PLOT_SCRIPT = '''
import sys, time, threading
sys.path.insert(0, {root!r})
from classworld import ClassSetup
from lanserver import LanServer
from lanclient import LanClient

setup = ClassSetup.for_roster('pm', [], 12, 12, 5, columns=2, extra=2, mode='survival', auto_claim=True)
server = LanServer(setup.build_world(), pin='teach1', code='maple-tiger-42', host='127.0.0.1', port=0, default_mode='survival').start()
flag = {{}}

def teacher():
    while not flag.get('go'):
        time.sleep(0.05)
    c = LanClient('127.0.0.1', server.port, 'maple-tiger-42', 'Tea')
    c.connect()
    c.chat('/teacher teach1')
    time.sleep(0.5)
    c.chat('/plotsize 20')
    time.sleep(8)

threading.Thread(target=teacher, daemon=True).start()

def hook(game, client, remotes, chat):
    from ursina import invoke
    lan = game.lan
    print('BEFORE', lan.state['layout'].plots[0].size, lan.state['session'].plot._plot[0], game.world.get((12, 3, 3)), flush=True)
    flag['go'] = True
    def check():
        plots = lan.state['layout'].plots
        print('AFTER_SIZE', plots[0].size, 'SESSION_WIDTH', lan.state['session'].plot._plot[0], flush=True)
        print('OLD_LINE', game.world.get((12, 3, 3)), 'NEW_LINE', game.world.get((20, 3, 3)), flush=True)
        lan.state['session'].feed('fill 15 0 0 18 0 0 gold_block')           # (only fits in the new, bigger plot)
        print('BUILT', game.world.get((15, 4, 0)), game.world.get((18, 4, 0)), flush=True)
    invoke(check, delay=4.0)

import lanplay
lanplay.play('127.0.0.1', server.port, 'maple-tiger-42', 'Sam', seconds=9, hook=hook)
'''


TYPED_SCRIPT = '''
import sys, time
sys.path.insert(0, {root!r})
from classworld import ClassSetup
from lanserver import LanServer

setup = ClassSetup.for_roster('pm', [], 16, 16, 5, columns=2, extra=2, mode='survival', auto_claim=False)
server = LanServer(setup.build_world(), pin='teach1', code='maple-tiger-42', host='127.0.0.1', port=0, default_mode='survival').start()

def hook(game, client, remotes, chat):
    import __main__
    from ursina import invoke
    c = game.console

    def typed(text, delay):
        def go():
            if not c.is_open:
                __main__.input('/')                                  # the / key opens the code prompt, as in live coding
            c._set_text(text)
            c.input('enter')
        invoke(go, delay=delay)

    print('READY', flush=True)
    typed('fill 0 0 0 1 0 0 stone', 0.3)                             # (no plot yet: refused, with a helpful line)
    def refused():
        print('OPEN', c.is_open, 'REFUSED', any('need a plot' in l for l in c.lines), 'NOTHING', (0, 4, 0) not in server.world.changes, flush=True)
    invoke(refused, delay=1.2)
    typed('claim', 1.5)                                              # (a plain word: sent to the class as /claim)
    def claimed():
        print('CLAIMED', server.world.layout.owner_of('Sam') is not None, flush=True)
    invoke(claimed, delay=3.0)
    typed('fill 0 0 0 1 0 0 stone', 3.4)
    def built():
        print('BUILT', server.world.changes.get((0, 4, 0)), server.world.changes.get((1, 4, 0)), flush=True)
        __main__.input('escape')
        __main__.input('u')                                          # U undoes, as in live coding
    invoke(built, delay=5.0)
    def undone():
        print('UNDONE', server.world.changes.get((0, 4, 0), ('never built',))[0], flush=True)
    invoke(undone, delay=6.0)
    def terminal():
        print('TERMINAL', server.world.changes.get((5, 4, 5)), flush=True)
    invoke(terminal, delay=8.5)

import lanplay
lanplay.play('127.0.0.1', server.port, 'maple-tiger-42', 'Sam', seconds=10, hook=hook)
'''


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class TypingCode(unittest.TestCase):
    def test_the_code_prompt_works_like_live_coding(self):
        import time
        folder = scratch('lan_typed')
        script = folder / 'run.py'
        script.write_text(TYPED_SCRIPT.format(root=str(ROOT)))
        process = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, cwd=str(ROOT))
        lines, started, wrote = [], time.time(), False
        try:
            for line in process.stdout:
                lines.append(line)
                if line.startswith('CLAIMED') and not wrote:
                    process.stdin.write('placeblock 5 0 5 gold_block\n')              # the terminal is a code prompt too
                    process.stdin.flush()
                    wrote = True
                if line.startswith('TERMINAL') or time.time() - started > 150:
                    break
        finally:
            process.kill()
            process.wait()
        text = ''.join(lines)
        self.assertIn('OPEN True REFUSED True NOTHING True', text, text[-800:])        # / opened the prompt; no plot: refused, nothing built
        self.assertIn('CLAIMED True', text, text[-800:])                                # the plain word claim went to the class
        self.assertIn("BUILT ('stone', None) ('stone', None)", text, text[-800:])     # code built in the plot
        self.assertIn('UNDONE None', text, text[-800:])                                 # U took it back (and the server knows: air now)
        self.assertIn("TERMINAL ('gold_block', None)", text, text[-800:])               # typing in the terminal built too


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class PlotMode(unittest.TestCase):
    def test_a_resize_reaches_a_student_in_the_game(self):
        folder = scratch('lan_plotmode')
        script = folder / 'run.py'
        script.write_text(PLOT_SCRIPT.format(root=str(ROOT)))
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=240, cwd=str(ROOT))
        text = out.stdout + out.stderr[-2500:]
        self.assertIn('BEFORE (12, 12) 12', out.stdout, text)                  # a plot of their own, 12 wide, from the moment they joined
        self.assertIn('AFTER_SIZE (20, 20) SESSION_WIDTH 20', out.stdout, text)   # the plot and the code prompt follow the teacher's change
        self.assertIn('OLD_LINE grass NEW_LINE stone_bricks', out.stdout, text)  # the line was redrawn where the plot now ends
        self.assertIn('BUILT gold_block gold_block', out.stdout, text)           # and code builds in the new part
        self.assertNotIn('Traceback', out.stderr, text)


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class Animals(unittest.TestCase):
    def test_animals_run_on_one_computer_and_everyone_sees_and_hits_them(self):
        folder = scratch('lan_animals')
        script = folder / 'run.py'
        script.write_text(ANIMAL_SCRIPT.format(root=str(ROOT)))
        # (the game quits when the other player is done: no need to wait out the whole run)
        process = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT))
        lines, import_time = [], __import__('time').time()
        try:
            for line in process.stdout:
                lines.append(line)
                if line.startswith('KILLED'):
                    break
                if __import__('time').time() - import_time > 120:
                    break
        finally:
            process.kill()
            process.wait()
        text = ''.join(lines)
        self.assertIn('ANIMALS_SEEN', text, text[-500:])                    # animals appeared and were sent to the other player
        self.assertIn('KILLED True', text, text[-500:])                     # a hit from the other player killed one on the runner's computer


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class ClassWorld(unittest.TestCase):
    def test_plots_code_sand_chests_and_the_panel(self):
        folder = scratch('lan_class')
        script = folder / 'run.py'
        script.write_text(CLASS_SCRIPT.format(root=str(ROOT)))
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=240, cwd=str(ROOT))
        text = out.stdout + out.stderr[-2500:]
        self.assertIn('SESSION_PLOT 1', out.stdout, text)                  # Sam owns plot 1: code goes there
        self.assertIn('AUTHORITY True', out.stdout, text)                   # the first player runs the world for everyone
        self.assertIn("GOLD ('gold_block', None)", out.stdout, text)        # the code built inside the plot, and the server has it
        self.assertIn("CHEST ['stone', 3, 0]", out.stdout, text)            # a closed chest is shared
        self.assertIn('SAND_SIM True', out.stdout, text)                    # the sand Sam's computer let fall reached another player
        self.assertIn('PLOT2 Ann', out.stdout, text)                        # Ann claimed the other plot
        self.assertIn('ANN_SAW_CODE_BLOCKS True', out.stdout, text)
        self.assertIn('PANEL_ROWS True', out.stdout, text)
        self.assertNotIn('Traceback', out.stderr, text)


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class LanGame(unittest.TestCase):
    def test_two_players_and_a_teacher(self):
        folder = scratch('lan_game')
        script = folder / 'run.py'
        script.write_text(SCRIPT.format(root=str(ROOT)))
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=240, cwd=str(ROOT))
        text = out.stdout + out.stderr[-1500:]
        self.assertIn('REMOTES 1', out.stdout, text)                    # Ann is in the world, as a body
        self.assertIn('MODE survival False', out.stdout, text)           # the teacher set Sam's mode, and building is allowed
        self.assertIn('SHARED True', out.stdout, text)                   # Ann's block arrived
        self.assertIn('SERVER (None, None)', out.stdout, text)           # and Sam's break reached the server
        self.assertNotIn('Traceback', out.stderr, text)


if __name__ == '__main__':
    unittest.main()
