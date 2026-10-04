import unittest

import tests
import pycraft as pc
from tests import scratch


class Blocks(unittest.TestCase):
    def setUp(self):
        self.w = pc.plot(12, 12, 12)

    def test_a_block_by_name_number_or_pc_name(self):
        w = self.w
        w.placeblock(0, 0, 0, 'stone')
        w.placeblock(1, 0, 0, pc.stone)
        w.placeblock(2, 0, 0, pc.blockid('stone'))
        w.placeblock(3, 0, 0, 'Oak Planks')
        self.assertEqual([w.getblock(x, 0, 0) for x in range(4)], ['stone', 'stone', 'stone', 'oak_planks'])

    def test_air_removes_and_id_is_optional(self):
        self.w.placeblock(0, 0, 0)
        self.assertEqual(self.w.getblock(0, 0, 0), 'stone')
        self.w.placeblock(0, 0, 0, pc.air)
        self.assertEqual(self.w.getblock(0, 0, 0), 'air')

    def test_a_wrong_name_suggests_the_right_one(self):
        with self.assertRaisesRegex(ValueError, "Did you mean 'stone'"):
            self.w.placeblock(0, 0, 0, 'stoone')
        with self.assertRaisesRegex(AttributeError, 'Did you mean stone'):
            pc.stoone

    def test_outside_the_plot_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'outside your plot'):
            self.w.placeblock(-1, 0, 0, 'stone')

    def test_fill_count_and_replace(self):
        self.w.fill(0, 0, 0, 2, 0, 2, 'stone')
        self.assertEqual(self.w.count('stone'), 9)
        self.w.replace('stone', 'bricks')
        self.assertEqual(self.w.count('bricks'), 9)

    def test_copy_paste_rotate(self):
        self.w.fill(0, 0, 0, 2, 0, 0, 'stone')
        clip = self.w.copy(0, 0, 0, 2, 0, 0)
        self.w.paste(clip, 5, 0, 5, rotate=90)
        self.assertEqual(self.w.count('stone'), 6)
        self.assertEqual(self.w.getblock(5, 0, 5), 'stone')
        self.assertEqual(self.w.getblock(5, 0, 7), 'stone')


class Creatures(unittest.TestCase):
    def test_coordinates_first_and_the_older_order(self):
        w = pc.plot(10, 10, 10)
        w.spawnmob(1, 1, 1, 'zombie')
        w.spawnmob('pig', 2, 1, 2)
        w.spawnmob(3, 1, 3)
        names = [repr(c) for c in w._mobs]
        self.assertIn('zombie', names[0])
        self.assertIn('pig', names[1])
        self.assertIn('pig', names[2])

    def test_npc_both_orders(self):
        w = pc.plot(10, 10, 10)
        w.npc(4, 1, 4, 'Guide', 'Hello')
        w.npc('Old', 5, 1, 5, ['a', 'b'])
        self.assertEqual([n['name'] for n in w._npcs], ['Guide', 'Old'])

    def test_unknown_creature(self):
        with self.assertRaisesRegex(ValueError, 'Did you mean'):
            pc.plot(5, 5, 5).spawnmob(1, 1, 1, 'zombi')

    def test_creature_names_on_pc(self):
        self.assertEqual((pc.zombie, pc.golem), ('zombie', 'iron_golem'))


class History(unittest.TestCase):
    def test_undo_and_redo(self):
        w = pc.plot(8, 8, 8)
        w._begin_step()
        w.placeblock(1, 1, 1, 'stone')
        w._end_step()
        self.assertTrue(w.undo())
        self.assertEqual(w.getblock(1, 1, 1), 'air')
        self.assertTrue(w.redo())
        self.assertEqual(w.getblock(1, 1, 1), 'stone')


class Files(unittest.TestCase):
    def test_save_and_load_a_plot(self):
        w = pc.plot(8, 8, 8)
        w.fill(0, 0, 0, 3, 0, 3, 'bricks')
        w.sign(1, 1, 1, ['hi'])
        path = w.save(str(scratch('plots') / 'a'))
        loaded = pc.load(path)
        self.assertEqual(loaded.count('bricks'), 16)
        self.assertEqual(loaded.dimensions, (8, 8, 8))

    def test_share_code_round_trip(self):
        w = pc.plot(6, 6, 6)
        w.fill(0, 0, 0, 1, 1, 1, 'gold_block')
        other = pc.plot(6, 6, 6)
        other.loadcode(w.share())
        self.assertEqual(other.count('gold_block'), 8)


if __name__ == '__main__':
    unittest.main()
