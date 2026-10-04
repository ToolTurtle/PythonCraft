"""The teacher's class setup and the operations on a class world (no window)."""
import argparse
import json
import time
import unittest

import tests
import classtool
import classworld
import lan
import pcplot
import pycraft as pc
from classlayout import GROUND, Layout
from classworld import ClassSetup
from lanclient import LanClient
from tests import scratch


def make_setup(names=('Ann', 'Bo', 'Cy')):
    return ClassSetup.for_roster('Test class', list(names), 16, 16, 5, columns=2, extra=1)


def build_pcplot(path, fill='bricks'):
    w = pc.plot(8, 8, 8)
    w.fill(0, 0, 0, 3, 0, 3, fill)
    w.placeblock(1, 1, 1, 'gold_block')
    return w.save(str(path))


class Setup(unittest.TestCase):
    def test_a_plot_for_everyone_with_the_names_filled_in(self):
        setup = make_setup()
        self.assertEqual(len(setup.layout.plots), 4)                       # (three names and one spare)
        self.assertEqual([p.owner for p in setup.layout.plots], ['Ann', 'Bo', 'Cy', None])
        self.assertEqual(setup.layout.owner_of('bo').id, 2)

    def test_the_file_round_trip_and_bad_files(self):
        folder = scratch('classfiles')
        setup = make_setup()
        blocks, facing = {(0, 0, 0): 'bricks', (1, 0, 0): 'stone'}, {(1, 0, 0): 'north'}
        setup.template = {'blocks': blocks, 'facing': facing}
        path = setup.save(folder / 'a')
        self.assertEqual(path.suffix, '.pcclass')
        loaded = ClassSetup.load(path)
        self.assertEqual((loaded.name, loaded.roster, loaded.template['blocks'], loaded.template['facing']), ('Test class', ['Ann', 'Bo', 'Cy'], blocks, facing))
        self.assertEqual(loaded.layout.plot_by_id(3).owner, 'Cy')
        bad = folder / 'bad.pcclass'
        bad.write_text('{"format": "other"}')
        with self.assertRaisesRegex(ValueError, 'not a class setup'):
            ClassSetup.load(bad)
        bad.write_text('not json')
        with self.assertRaises(ValueError):
            ClassSetup.load(bad)
        with self.assertRaisesRegex(ValueError, 'Could not open'):
            ClassSetup.load(folder / 'missing.pcclass')

    def test_one_plot_each_and_new_names_join_the_roster(self):
        setup = make_setup()
        setup.set_owner(4, 'Ann')                                          # (Ann moves to plot 4: plot 1 is free again)
        self.assertEqual((setup.layout.plot_by_id(1).owner, setup.layout.plot_by_id(4).owner), (None, 'Ann'))
        setup.set_owner(1, 'Zed')
        self.assertIn('Zed', setup.roster)
        with self.assertRaises(ValueError):
            setup.set_owner(99, 'X')

    def test_the_world_has_the_plots_the_markers_and_the_starter_build(self):
        setup = make_setup()
        setup.template = {'blocks': {(0, 0, 0): 'gold_block', (50, 0, 0): 'stone'}, 'facing': {}}
        world = setup.build_world()
        first = setup.layout.plot_by_id(1)
        self.assertEqual(world.changes[(first.x1, GROUND + 1, first.z1)], ('gold_block', None))
        self.assertEqual(world.changes[(first.x1 - 1, GROUND, first.z1)], ('stone_bricks', None))
        self.assertNotIn((first.x1 + 50, GROUND + 1, first.z1), world.changes)       # (it does not fit in the plot: left out)
        self.assertEqual(world.flat_spawn, list(setup.layout.spawn))
        self.assertIs(world.layout, setup.layout)


class Operations(unittest.TestCase):
    def setUp(self):
        self.setup = make_setup()
        self.world = self.setup.build_world()
        self.plot = self.setup.layout.plot_by_id(1)

    def test_import_export_clear(self):
        folder = scratch('classops')
        source = build_pcplot(folder / 'build.pcplot')
        placed, skipped = classworld.import_pcplot(self.world, self.plot, source)
        self.assertEqual((placed, skipped), (17, 0))
        origin = classworld.plot_origin(self.plot)
        self.assertEqual(self.world.changes[(origin[0] + 1, origin[1] + 1, origin[2] + 1)], ('gold_block', None))
        out = classworld.export_plot(self.world, self.plot, folder / 'out.pcplot')
        again = pc.load(out)
        self.assertEqual((again.count('bricks'), again.count('gold_block')), (16, 1))
        self.assertEqual(classworld.clear(self.world, self.plot), 17)
        self.assertEqual(classworld.plot_blocks(self.world, self.plot), ({}, {}))
        self.assertIn((self.plot.x1 - 1, GROUND, self.plot.z1), self.world.changes)           # (the line round the plot stays)

    def test_a_plot_does_not_hold_what_does_not_fit_or_what_belongs_next_door(self):
        classworld.paste(self.world, self.plot, {(0, 0, 0): 'stone', (16, 0, 0): 'stone', (0, 0, 16): 'stone'})
        self.assertEqual(len(classworld.plot_blocks(self.world, self.plot)[0]), 1)
        other = self.setup.layout.plot_by_id(2)
        self.assertEqual(classworld.plot_blocks(self.world, other)[0], {})

    def test_handins_go_to_the_plot_of_their_owner(self):
        folder = scratch('classhand')
        for student, fill in (('Ann', 'bricks'), ('Bo', 'glass'), ('Stranger', 'stone')):
            w = pc.plot(8, 8, 8)
            w.fill(0, 0, 0, 1, 0, 1, fill)
            pcplot.hand_in(w._data(), student, 'house', folder)
        lines = classworld.import_handins(self.world, folder)
        self.assertTrue(any('Stranger' in line and 'no plot' in line for line in lines))
        ann = classworld.plot_blocks(self.world, self.setup.layout.owner_of('Ann'))[0]
        bo = classworld.plot_blocks(self.world, self.setup.layout.owner_of('Bo'))[0]
        self.assertEqual((set(ann.values()), set(bo.values())), ({'bricks'}, {'glass'}))
        self.assertEqual(classworld.import_handins(self.world, scratch('empty_hand')), ['There were no hand-ins to bring in.'])


class Commands(unittest.TestCase):
    def run_tool(self, *words):
        return classtool.main([str(w) for w in words])

    def test_the_whole_workflow_by_typing(self):
        folder = scratch('toolflow')
        self.assertEqual(self.run_tool('new', 'flow-class', '--roster', 'Ann, Bo, Cy', '--columns', 2, '--extra', 0), 0)
        path = classtool.CLASSES / 'flow-class.pcclass'
        self.assertTrue(path.exists())
        self.assertEqual(self.run_tool('show', path), 0)
        self.assertEqual(self.run_tool('assign', path, 3, 'Dee'), 0)
        self.assertEqual(ClassSetup.load(path).layout.plot_by_id(3).owner, 'Dee')
        self.assertEqual(self.run_tool('unassign', path, 3), 0)
        self.assertIsNone(ClassSetup.load(path).layout.plot_by_id(3).owner)
        source = build_pcplot(folder / 'tpl.pcplot')
        self.assertEqual(self.run_tool('template', path, source), 0)
        self.assertEqual(self.run_tool('world', path), 0)
        self.assertEqual(self.run_tool('import', path, 2, source), 0)
        out = folder / 'two.pcplot'
        self.assertEqual(self.run_tool('export', path, 2, out), 0)
        self.assertEqual(pc.load(str(out)).count('gold_block'), 1)
        self.assertEqual(self.run_tool('reset', path, 2, '--template'), 0)
        self.assertEqual(self.run_tool('reset', path, 99), 1)                             # (no such plot: a message, not a crash)
        self.assertEqual(self.run_tool('show', classtool.CLASSES / 'nothing.pcclass'), 1)

    def test_a_class_server_starts_from_the_setup_and_keeps_the_world(self):
        folder = scratch('toolserver')
        setup = make_setup()
        path = setup.save(folder / 'srv.pcclass')
        args = argparse.Namespace(class_file=str(path), world=None, plot=None, seed=None, fresh=False, mode='survival', pin='abcd12', code='x-y-11',
                                  port=0, bind='127.0.0.1', max=10, name='Srv', badwords=None, play=None)
        server, where = lan.start_server(args)
        try:
            client = LanClient('127.0.0.1', server.port, 'x-y-11', 'Ann')
            info = client.connect()
            self.assertEqual((info['mode'], len(info['plots']['plots']), info['plots']['plots'][0]['owner']), ('survival', 4, 'Ann'))
            client.send_pos(0.0, 4.0, 0.0, 0, 0)
            time.sleep(0.2)
            client.send_blocks([(2, 4, 2, 'bricks', None, None, None)])
            time.sleep(0.3)
            client.close()
        finally:
            server.stop()
        saved = json.loads(where.read_text())
        self.assertEqual(len(saved['layout']['plots']), 4)
        self.assertIn([2, 4, 2, 'bricks', None], saved['changes'])
        again = lan.make_world(argparse.Namespace(class_file=str(path), world=None, plot=None, seed=None, fresh=False, mode=None))[0]
        self.assertEqual(again.changes[(2, 4, 2)], ('bricks', None))                       # (the next time, the world is as it was left)

    def test_badwords_file(self):
        folder = scratch('bad')
        (folder / 'w.txt').write_text('# note\nsilly\n\nVery Silly\n')
        self.assertEqual(lan.load_badwords(folder / 'w.txt'), ['silly', 'Very Silly'])
        self.assertEqual(lan.load_badwords(folder / 'missing.txt'), [])
        self.assertIn('stupid', lan.load_badwords())


if __name__ == '__main__':
    unittest.main()
