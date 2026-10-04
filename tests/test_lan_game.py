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
            invoke(lambda: print('SERVER', server.world.changes.get(block), flush=True), delay=0.8)
    invoke(check, delay=4.5)

import lanplay
lanplay.play('127.0.0.1', server.port, 'maple-tiger-42', 'Sam', seconds=6, hook=hook)
server.stop()
'''


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
