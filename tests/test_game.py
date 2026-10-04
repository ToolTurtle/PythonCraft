"""Opens the real game for a few seconds (skip with PYCRAFT_NO_WINDOW=1): a mod block and creature, a pattern that spawns a
golem, the in-game prompt, a block that falls."""
import os
import subprocess
import sys
import unittest

import tests
from tests import ROOT, make_png, scratch

PROGRAM = '''
import sys
sys.path.insert(0, {root!r})
import pycraft as pc

m = pc.mod('gt')
m.addblock('gt_snad', {png!r}, like='sand')
m.addwood('purple', {png!r}, name='gt_plum')
golem = m.mob(pc.golem, 'gt_golem').health(60)
golem.spawncondition(pc.block_placement({pattern!r}))
w = pc.plot(16, 12, 16)
w.fill(0, 0, 0, 15, 0, 15, 'grass')
w.tree(3, 1, 3, 'gt_plum')
w.placeblock(8, 1, 8, 'gt_snad')
for pos in [(10, 1, 10), (10, 2, 10), (9, 2, 10), (11, 2, 10)]:
    w.placeblock(*pos, 'iron_block')

def check(game):
    kinds = [mob.kind.name for mob in game.mobs.mobs]
    print('MOBS', kinds)
    print('IRON', sum(1 for v in game.world.modified.values() if v == 'iron_block'))
    print('CONSOLE', game.console is not None)
    game.player.position = (8, 5, 8)                    # inside a block of the floor: stuck
    game.world.place((8, 5, 8), 'stone') if game.world.get((8, 5, 8)) is None else None
    game.unstuck()
    p = game.player
    cell = (round(p.x), int((p.y + 0.5) // 1), round(p.z))
    print('UNSTUCK', game.world.solid_top(cell) == 0 and game.world.solid_top((cell[0], cell[1] + 1, cell[2])) == 0
          and game.world.solid_top((cell[0], cell[1] - 1, cell[2])) > 0)

pc.runplot(w, pc.adventure, _hook=check)
'''


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class Boot(unittest.TestCase):
    def test_mods_in_the_real_game(self):
        import pycraft as pc
        folder = scratch('game')
        png = make_png(folder / 'p.png')
        shape = pc.plot(5, 5, 5)
        shape.fill(1, 0, 0, 1, 1, 0, 'iron_block')
        shape.fill(0, 1, 0, 2, 1, 0, 'iron_block')
        pattern = shape.copy(0, 0, 0, 2, 1, 0).save(str(folder / 't.pcschem'))
        script = folder / 'run.py'
        script.write_text(PROGRAM.format(root=str(ROOT), png=png, pattern=pattern))
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=180, cwd=str(folder))
        self.assertIn("MOBS ['gt_golem']", out.stdout, out.stdout[-800:] + out.stderr[-800:])      # the pattern turned into the golem
        self.assertIn('IRON 0', out.stdout)
        self.assertIn('UNSTUCK True', out.stdout)                                                    # the Unstuck button's move                                                          # and used up its blocks
        self.assertNotIn('Traceback', out.stderr)


if __name__ == '__main__':
    unittest.main()
