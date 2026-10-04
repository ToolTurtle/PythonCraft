import unittest

import tests                                   # (sets up the scratch folders first)
import blocks
import items
from tests import make_png, scratch


class BlockTables(unittest.TestCase):
    def test_names_and_ids_agree(self):
        self.assertEqual(len(blocks.NAMES), len(set(blocks.NAMES)))
        for number, name in enumerate(blocks.NAMES):
            self.assertEqual(blocks.ID[name], number)
        self.assertLess(len(blocks.NAMES), blocks.TABLE_SIZE)

    def test_every_block_is_in_every_table(self):
        for table in (blocks.SOLID_TABLE, blocks.TRANSPARENT_TABLE, blocks.EMIT_TABLE):
            self.assertEqual(table.shape, (blocks.TABLE_SIZE,))

    def test_registering_a_block_grows_the_tables(self):
        before = len(blocks.NAMES)
        from ursina import color
        blocks.register_block('test_registered_block', {'hardness': 2.0, 'all': ['stone'], 'gravity': True, 'fallback': color.gray})
        self.assertEqual(len(blocks.NAMES), before + 1)
        number = blocks.ID['test_registered_block']
        self.assertTrue(blocks.GRAVITY_TABLE[number])
        self.assertTrue(blocks.SOLID_TABLE[number])
        self.assertIn('test_registered_block', items.ITEMS)                 # (and the item that places it)

    def test_items_that_place_blocks_name_real_blocks(self):
        for item in items.ITEMS.values():
            if item.places:
                self.assertIn(item.places, blocks.BLOCKS, item.name)


class Saves(unittest.TestCase):
    def test_tests_use_a_scratch_saves_folder(self):
        import savegame
        self.assertNotEqual(str(savegame.SAVES), str(tests.ROOT / 'saves'))

    def test_save_and_load_round_trip(self):
        import savegame
        folder = scratch('roundtrip')
        level = {'name': 'T', 'seed': 1, 'time': 100, 'days': 0}
        savegame.save(folder, level, {(1, 2, 3): 'stone', (4, 5, 6): None}, facing={(1, 2, 3): 'north'})
        loaded_level, modified, facing, _flowing = savegame.load(folder)
        self.assertEqual(loaded_level['name'], 'T')
        self.assertEqual(modified[(1, 2, 3)], 'stone')
        self.assertIsNone(modified[(4, 5, 6)])
        self.assertEqual(facing[(1, 2, 3)], 'north')


if __name__ == '__main__':
    unittest.main()
