import json
import subprocess
import sys
import unittest

import tests
import blocks
import mobtypes
import mods
import pycraft as pc
from tests import ROOT, make_png, scratch


def mod(name):
    return pc.mod(name)


class Blocks(unittest.TestCase):
    def setUp(self):
        self.folder = scratch('mods_blocks')
        self.png = make_png(self.folder / 'a.png')
        mods.ACTIVE.clear()

    def test_a_new_block_works_in_a_plot(self):
        mod('t1').addblock('tm_snad', self.png, like='sand')
        self.assertIn('tm_snad', blocks.BLOCKS)
        self.assertTrue(blocks.GRAVITY_TABLE[blocks.ID['tm_snad']])           # it falls like sand
        w = pc.plot(5, 5, 5)
        w.placeblock(1, 1, 1, pc.tm_snad)
        self.assertEqual(w.getblock(1, 1, 1), 'tm_snad')

    def test_mistakes_give_helpful_messages(self):
        m = mod('t2')
        m.addblock('tm_one', self.png)
        cases = [
            (lambda: m.addblock('tm_one', self.png), 'already'),
            (lambda: m.addblock('Bad-Name!', self.png), 'small letters'),
            (lambda: m.addblock('tm_two', str(self.folder / 'missing.png')), 'cannot find'),
            (lambda: m.addblock('tm_two', self.png, like='sandd'), 'Did you mean sand'),
            (lambda: m.addblock('tm_two', self.png, hardnes=2), 'Did you mean hardness'),
            (lambda: m.addblock('tm_two', self.png, hardness='hard'), 'wrong kind of value'),
            (lambda: m.addblock('tm_two', self.png, gravity=3), 'True or False'),
        ]
        for call, words in cases:
            with self.assertRaisesRegex(ValueError, words):
                call()
        self.assertNotIn('tm_two', blocks.BLOCKS)

    def test_a_text_file_is_not_a_picture(self):
        bad = self.folder / 'bad.png'
        bad.write_text('not a picture')
        with self.assertRaisesRegex(ValueError, 'not a picture'):
            mod('t3').addblock('tm_bad', str(bad))

    def test_wood_family_and_trees(self):
        wood = mod('t4').addwood('purple', make_png(self.folder / 'leaves.png'), name='tm_plum')
        for part in ('log', 'planks', 'leaves', 'sapling', 'slab', 'stairs', 'fence'):
            self.assertIn(f'{wood}_{part}', blocks.BLOCKS)
        w = pc.plot(12, 12, 12)
        w.tree(5, 1, 5, 'tm_plum')
        self.assertGreater(w.count('tm_plum_log'), 3)
        self.assertGreater(w.count('tm_plum_leaves'), 5)
        with self.assertRaises(ValueError):
            w.tree(5, 1, 5, 'tm_nonexistent')

    def test_colours(self):
        self.assertEqual(mods.parse_color('purple'), (130, 60, 170))
        self.assertEqual(mods.parse_color('#aa3355'), (170, 51, 85))
        self.assertEqual(mods.parse_color((10, 20, 300)), (10, 20, 255))
        with self.assertRaisesRegex(ValueError, 'Did you mean'):
            mods.parse_color('purpel')


class Creatures(unittest.TestCase):
    def setUp(self):
        mods.ACTIVE.clear()
        mods.SPAWN_RULES.clear()

    def test_made_from_another_creature(self):
        g = pc.mob(pc.golem, 'tm_vine_golem').health(60).scale(2)
        self.assertEqual((g.kind.health, g.kind.base), (60, 'iron_golem'))
        self.assertEqual(pc.tm_vine_golem, 'tm_vine_golem')
        king = pc.mob(g, 'tm_golem_king').health(100)                      # based on one you made
        self.assertEqual((king.kind.base, king.kind.scale), ('iron_golem', 2.0))
        again = pc.mob(pc.tm_vine_golem, 'tm_golem_two')                   # or on its name
        self.assertEqual(again.kind.health, 60)
        self.assertEqual(mobtypes.TYPES['iron_golem'].health, 100)         # the original is not changed

    def test_mistakes(self):
        with self.assertRaisesRegex(ValueError, 'Did you mean golem'):
            pc.mob('golm')
        pc.mob(pc.zombie, 'tm_dup')
        with self.assertRaisesRegex(ValueError, 'already'):
            pc.mob(pc.zombie, 'tm_dup')
        with self.assertRaisesRegex(ValueError, 'spawn condition'):
            pc.mob(pc.zombie, 'tm_x').spawncondition('at night')

    def test_a_skin_must_exist_and_fit(self):
        folder = scratch('mods_skin')
        g = pc.mob(pc.zombie, 'tm_skinned')
        with self.assertRaisesRegex(ValueError, 'cannot find'):
            g.texture(str(folder / 'no.png'))
        with self.assertRaisesRegex(ValueError, 'needs'):
            g.texture(make_png(folder / 'wrong.png', size=(10, 10)))

    def test_spawnable_by_hand(self):
        pc.mob(pc.pig, 'tm_pig2')
        w = pc.plot(6, 6, 6)
        w.spawnmob(1, 1, 1, 'tm_pig2')
        self.assertEqual(len(w._mobs), 1)


class Patterns(unittest.TestCase):
    def setUp(self):
        self.folder = scratch('mods_pattern')
        w = pc.plot(6, 6, 6)
        w.fill(1, 0, 0, 1, 1, 0, 'iron_block')
        w.fill(0, 1, 0, 2, 1, 0, 'iron_block')          # a T
        self.file = w.copy(0, 0, 0, 2, 1, 0).save(str(self.folder / 't.pcschem'))

    class FakeWorld:
        def __init__(self, cells):
            self.cells = cells

        def get(self, pos):
            return self.cells.get(pos)

    def test_found_in_every_rotation(self):
        cond = pc.block_placement(self.file)
        base = {(0, 0, 0): 'iron_block', (0, 1, 0): 'iron_block', (-1, 1, 0): 'iron_block', (1, 1, 0): 'iron_block'}
        for turns in range(4):
            cells = dict(base)
            for _ in range(turns):
                cells = {(-z, y, x): n for (x, y, z), n in cells.items()}
            world = self.FakeWorld({(x + 5, y + 5, z + 5): n for (x, y, z), n in cells.items()})
            pos = next(p for p in world.cells)
            self.assertIsNotNone(cond.find(world, pos), f'turned {turns} times')

    def test_not_found_when_a_block_is_missing_or_wrong(self):
        cond = pc.block_placement(self.file)
        cells = {(5, 5, 5): 'iron_block', (5, 6, 5): 'iron_block', (4, 6, 5): 'iron_block'}
        self.assertIsNone(cond.find(self.FakeWorld(cells), (5, 5, 5)))
        cells[(6, 6, 5)] = 'stone'
        self.assertIsNone(cond.find(self.FakeWorld(cells), (5, 5, 5)))

    def test_pattern_file_problems(self):
        with self.assertRaisesRegex(ValueError, 'cannot find'):
            pc.block_placement(str(self.folder / 'none.pcschem')).rotations()
        bad = self.folder / 'bad.pcschem'
        bad.write_text('hello')
        with self.assertRaisesRegex(ValueError, 'not a pattern'):
            pc.block_placement(str(bad)).rotations()
        bad.write_text(json.dumps({'format': 'pcschem', 'blocks': {'not_a_block': [0, 0, 0]}}))
        with self.assertRaisesRegex(ValueError, 'do not exist'):
            pc.block_placement(str(bad)).rotations()


class PcmodFiles(unittest.TestCase):
    def test_save_then_load_in_a_fresh_program(self):
        folder = scratch('mods_pcmod')
        png = make_png(folder / 'p.png')
        mods.ACTIVE.clear()
        m = pc.mod('tm_round')
        m.addblock('tm_rb', png, like='sand')
        m.addwood('blue', png, name='tm_rwood')
        m.additem('tm_ritem', png, food=2)
        m.recipe(['XX', 'XX'], {'X': 'tm_rb'}, 'tm_ritem')
        w = pc.plot(5, 5, 5)
        w.fill(0, 0, 0, 1, 0, 0, 'iron_block')
        g = m.mob(pc.golem, 'tm_rgolem').health(77).hostile().drops([('tm_ritem', 1, 2)])
        g.spawncondition(pc.block_placement(w.copy(0, 0, 0, 1, 0, 0))).spawncondition(pc.near_block('tm_rb'))
        path = m.save(str(folder / 'round.pcmod'))
        check = (
            "import sys; sys.path.insert(0, %r)\n"
            "import pycraft as pc, blocks, mobtypes, mods, items\n"
            "m = pc.loadmod(%r)\n"
            "print('RESULT', 'tm_rb' in blocks.BLOCKS, 'tm_rwood_log' in blocks.BLOCKS, 'tm_ritem' in items.ITEMS,\n"
            "      mobtypes.TYPES['tm_rgolem'].health, mobtypes.TYPES['tm_rgolem'].monster, len(mods.SPAWN_RULES))\n"
            % (str(ROOT), path))
        out = subprocess.run([sys.executable, '-c', check], capture_output=True, text=True, timeout=120)
        self.assertIn('RESULT True True True 77 True 2', out.stdout, out.stdout + out.stderr)


if __name__ == '__main__':
    unittest.main()
