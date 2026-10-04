"""The live-coding prompt: plain commands, :commands, indent, undo, and autocomplete."""
import contextlib
import io
import unittest
from unittest import mock

import tests
import pycraft as pc
from livecode import Session


def make():
    plot = pc.plot(16, 16, 16)
    return plot, Session(plot, delay=0)


def say(session, *lines):
    """Type lines at the prompt and return what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for line in lines:
            session.feed(line)
    return out.getvalue()


class PlainCommands(unittest.TestCase):
    def test_plain_python_and_the_short_python_forms_agree(self):
        plot, s = make()
        say(s, 'placeblock 1 1 1 stone', "placeblock(2, 1, 1, 'stone')", "w.placeblock(3, 1, 1, 'stone')", 'placeblock 4 1 1 pc.stone')
        self.assertEqual(plot.count('stone'), 4)

    def test_it_shows_the_python_it_made(self):
        _, s = make()
        self.assertIn("w.placeblock(1, 1, 1, 'stone')", say(s, 'placeblock 1 1 1 stone'))

    def test_quoted_words_stay_together(self):
        plot, s = make()
        self.assertIn("'hi there'", say(s, 'say "hi there"'))

    def test_the_new_order_for_creatures(self):
        plot, s = make()
        say(s, 'spawnmob 2 1 2 zombie', 'spawnmob 3 1 3')
        self.assertEqual(len(plot._mobs), 2)

    def test_a_wrong_block_name_is_explained_not_a_crash(self):
        plot, s = make()
        self.assertIn("Did you mean 'stone'", say(s, 'placeblock 1 1 1 stoone'))
        self.assertEqual(plot.count(), 0)

    def test_python_lines_are_left_alone(self):
        plot, s = make()
        say(s, 'x = 3', 'count = 5', 'placeblock x 1 1 stone')
        self.assertEqual(plot.getblock(3, 1, 1), 'stone')
        self.assertEqual(s.namespace['count'], 5)                     # (a variable called count is not the command)

    def test_blocks_with_indent_variables_and_sums(self):
        plot, s = make()
        say(s, 'for i in range(3):', 'placeblock i+2 1 1 stone', 'placeblock i 2 1 bricks', '')
        self.assertEqual(plot.count('stone'), 3)
        self.assertEqual(plot.count('bricks'), 3)

    def test_else_steps_back(self):
        plot, s = make()
        say(s, 'for i in range(2):', 'if i:', 'placeblock i 1 1 stone', 'else:', 'placeblock i 1 2 bricks', '')
        self.assertEqual((plot.getblock(1, 1, 1), plot.getblock(0, 1, 2)), ('stone', 'bricks'))

    def test_commands_without_the_colon(self):
        plot, s = make()
        say(s, 'placeblock 1 1 1 stone', 'undo')
        self.assertEqual(plot.count(), 0)
        say(s, 'redo')
        self.assertEqual(plot.count(), 1)

    def test_clear_is_undoable(self):
        plot, s = make()
        say(s, 'fill 0 0 0 2 0 2 stone', ':clear')
        self.assertEqual(plot.count(), 0)
        say(s, ':undo')
        self.assertEqual(plot.count(), 9)

    def test_export_writes_a_program_that_runs(self):
        plot, s = make()
        say(s, 'fill 0 0 0 1 0 1 stone', 'x = 1')
        program = s.program(runplot=False)
        self.assertIn("w.fill(0, 0, 0, 1, 0, 1, 'stone')", program)
        namespace = {}
        exec(compile(program, 'prog', 'exec'), namespace)
        self.assertEqual(namespace['w'].count('stone'), 4)

    def test_paint_starts_the_painter_window(self):
        _, s = make()
        with mock.patch('painter.open_window') as opened:
            say(s, 'paint snad.png --like sand')
        self.assertEqual(opened.call_args.args[0].endswith('snad.png'), True)
        self.assertEqual(opened.call_args.args[1], 'sand')


class Autocomplete(unittest.TestCase):
    def setUp(self):
        _, s = make()
        self.c = s.completer

    def names(self, line):
        return self.c.completions(line, force=True)[1]

    def test_commands_blocks_creatures(self):
        self.assertIn('placeblock', self.names('pl'))
        self.assertEqual(self.names('placeblock 0 0 0 oak_pl')[0], 'oak_planks')
        self.assertIn('zombie', self.names('spawnmob 1 1 1 zom'))
        self.assertIn(':undo', self.names(':un'))
        self.assertIn('pc.obsidian', self.names('pc.obs'))
        self.assertIn('w.fill', self.names('w.fil'))

    def test_the_right_kind_of_name_for_each_argument(self):
        self.assertIn('rain', self.names('weather ra'))
        self.assertIn('birch', self.names('tree 1 1 1 bi'))
        self.assertEqual(self.names('placeblock 1 1 1 stone nor'), ['north'])
        self.assertIn('diamond_sword', self.names('give diamond_sw'))

    def test_misspellings_and_substrings(self):
        self.assertIn('cobblestone', self.names('placeblock 0 0 0 blest'))          # (contains it)
        self.assertIn('stone', self.names('placeblock 0 0 0 stoen'))                # (close to it)

    def test_inside_quotes_and_calls(self):
        self.assertIn('bricks', self.names('fill(0, 0, 0, 1, 1, 1, "bri'))
        self.assertIn("'bricks'", self.names('fill(0, 0, 0, 1, 1, 1, bri'))

    def test_tab_adds_the_quote_and_the_comma_or_bracket(self):
        self.assertEqual(self.c.tab('placeblock(1, 1, 1, "stone')[0], 'placeblock(1, 1, 1, "stone", ')
        self.assertEqual(self.c.tab('fill(0, 0, 0, 1, 1, 1, "oak_pla')[0], 'fill(0, 0, 0, 1, 1, 1, "oak_planks")')
        self.assertEqual(self.c.tab('fill(0, 0, 0, 1, 1, 1, pc.oak_pl')[0], 'fill(0, 0, 0, 1, 1, 1, pc.oak_planks)')
        self.assertEqual(self.c.tab('placeblock 0 0 0 oak_pla')[0], 'placeblock 0 0 0 oak_planks')       # (no commas in plain commands)

    def test_tab_again_goes_through_the_choices(self):
        line, state = self.c.tab('placeblock 0 0 0 stone_')
        seen = {line}
        for _ in range(3):
            line, state = self.c.tab(line, state)
            seen.add(line)
        self.assertGreater(len(seen), 2)

    def test_hint_shows_how_the_command_is_written(self):
        usage, names = self.c.hint('placeblock 0 0 0 sto')
        self.assertEqual(usage, 'placeblock x y z [id] [facing]')
        self.assertTrue(names.startswith('stone'))

    def test_indent_rules(self):
        c = self.c
        self.assertEqual(c.indent_for(['for i in range(3):']), '    ')
        self.assertEqual(c.indent_for(['for i in x:', '    a']), '    ')
        self.assertEqual(c.indent_for(['if x:', '    break']), '')
        self.assertEqual(c.fix_indent(['for i in x:'], 'placeblock i 1 1'), '    placeblock i 1 1')
        self.assertEqual(c.fix_indent(['if x:', '    a'], 'else:'), 'else:')
        self.assertEqual(c.fix_indent(['if x:', '    a'], '    keep'), '    keep')


if __name__ == '__main__':
    unittest.main()
