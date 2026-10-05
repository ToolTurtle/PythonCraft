"""Animals must stand on the ground where they appear. (They used to start inside a hillside and fall straight through the world.)"""
import os
import subprocess
import sys
import unittest

import tests
from tests import ROOT, scratch

SCRIPT = '''
import sys, tempfile, os, random
sys.path.insert(0, {root!r})
os.chdir({root!r})
from mac_fix import fix_shaders, clear_leftover_shaders
fix_shaders()
import ursina
from ursina import Ursina, application, invoke
app = Ursina(); clear_leftover_shaders()
from pathlib import Path
from game import Game
import __main__
bad = []
for seed in (5, 1, 7):
    game = Game(Path(tempfile.mkdtemp()), 'x', seed=seed, mode='survival')
    for mob in game.mobs.mobs[:]:
        game.mobs.remove(mob)
    random.seed(seed)
    made = 0
    while made < 20:
        if game.mobs._try_spawn_animal(random.randint(-45, 45), random.randint(-45, 45)):
            made += 1
    for mob in game.mobs.mobs:
        if mob._hits_block(mob.x, mob.y, mob.z):
            bad.append(('inside blocks at the start', seed, mob.kind.name, round(mob.x, 1), round(mob.y, 1), round(mob.z, 1)))
    print('SEED', seed, 'animals', len(game.mobs.mobs), flush=True)
# a creature put inside a block (a script can do this) is lifted out
from mobs import Mob
inside = game.mobs.add('pig', (0.0, game.world.height_at(0, 0) - 3.0, 0.0))
if inside._hits_block(inside.x, inside.y, inside.z):
    bad.append(('not lifted out',))
game.mobs.mobs[:] = [m for m in game.mobs.mobs if m is not inside]
__main__.update = lambda: game.update()
__main__.input = lambda key: None
def report():
    low = [(m.kind.name, round(m.y, 1)) for m in game.mobs.mobs if m.y < 20]
    print('FELL', low, flush=True)
    print('BAD', bad, flush=True)
invoke(report, delay=6.0)
invoke(application.quit, delay=7.0)
app.run()
'''


@unittest.skipIf(os.environ.get('PYCRAFT_NO_WINDOW'), 'PYCRAFT_NO_WINDOW is set')
class Spawning(unittest.TestCase):
    def test_animals_start_on_the_ground_and_stay_in_the_world(self):
        script = scratch('spawning') / 'run.py'
        script.write_text(SCRIPT.format(root=str(ROOT)))
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        text = out.stdout + out.stderr[-1500:]
        self.assertIn('FELL []', out.stdout, text)                           # nothing dropped through the ground
        self.assertIn('BAD []', out.stdout, text)                            # nothing started inside the ground
        self.assertNotIn('Traceback', out.stderr, text)


if __name__ == '__main__':
    unittest.main()
