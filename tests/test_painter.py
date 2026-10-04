import unittest

import tests
from painter import Picture, hex_to_rgba, rgba_to_hex
from tests import make_png, scratch

RED, BLUE = (255, 0, 0, 255), (0, 0, 255, 255)


class Painting(unittest.TestCase):
    def test_paint_and_erase(self):
        p = Picture.blank(4)
        p.paint(1, 1, RED)
        self.assertEqual(p.pick(1, 1), RED)
        p.erase(1, 1)
        self.assertEqual(p.pick(1, 1)[3], 0)
        p.paint(9, 9, RED)                                # (outside: nothing happens)

    def test_mirror_paints_both_sides(self):
        p = Picture.blank(6)
        p.mirror = True
        p.paint(1, 2, RED)
        self.assertEqual((p.pick(1, 2), p.pick(4, 2)), (RED, RED))

    def test_a_line_has_no_gaps(self):
        p = Picture.blank(8)
        p.line(0, 0, 7, 3, lambda x, y: p.paint(x, y, RED))
        columns = {x for x in range(8) for y in range(8) if p.pick(x, y)[3]}
        self.assertEqual(columns, set(range(8)))

    def test_fill_stops_at_other_colours(self):
        p = Picture.blank(4)
        for y in range(4):
            p.paint(2, y, RED)                            # a wall down the middle
        self.assertEqual(p.fill(0, 0, BLUE), 8)
        self.assertEqual(p.pick(3, 0)[3], 0)
        self.assertEqual(p.fill(0, 0, BLUE), 0)

    def test_shading_keeps_see_through_pixels(self):
        p = Picture.blank(2)
        p.paint(0, 0, (100, 100, 100, 255))
        p.shade(0, 0, 20)
        p.shade(1, 1, 20)
        self.assertEqual(p.pick(0, 0), (120, 120, 120, 255))
        self.assertEqual(p.pick(1, 1)[3], 0)

    def test_undo_and_redo_whole_strokes(self):
        p = Picture.blank(4)
        p.checkpoint()
        p.paint(0, 0, RED)
        p.paint(1, 0, RED)
        self.assertTrue(p.undo())
        self.assertEqual((p.pick(0, 0)[3], p.pick(1, 0)[3]), (0, 0))
        self.assertTrue(p.redo())
        self.assertEqual(p.pick(1, 0), RED)
        self.assertFalse(Picture.blank(2).undo())

    def test_flip_and_clear(self):
        p = Picture.blank(4)
        p.paint(0, 0, RED)
        p.flip()
        self.assertEqual(p.pick(3, 0), RED)
        p.flip(vertical=True)
        self.assertEqual(p.pick(3, 3), RED)
        p.clear()
        self.assertEqual(p.common_colors(), [])

    def test_save_open_and_unsaved_changes(self):
        path = scratch('painter') / 'x.png'
        p = Picture.blank(4)
        p.paint(0, 0, BLUE)
        self.assertTrue(p.changed())
        p.save(path)
        self.assertFalse(p.changed())
        self.assertEqual(Picture.open(path).pick(0, 0), BLUE)

    def test_size_limits(self):
        with self.assertRaises(ValueError):
            Picture.blank(1000)
        Picture.open(make_png(scratch('painter') / 'big.png', size=(64, 32)))

    def test_colours(self):
        self.assertEqual(hex_to_rgba('#ff8000'), (255, 128, 0, 255))
        self.assertEqual(rgba_to_hex((255, 128, 0, 255)), '#ff8000')
        with self.assertRaises(ValueError):
            hex_to_rgba('red')


if __name__ == '__main__':
    unittest.main()
