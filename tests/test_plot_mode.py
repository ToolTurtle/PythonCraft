"""Plot mode: a flat world where everyone has a plot, and the teacher can change the sizes."""
import argparse
import json
import time
import unittest

import tests
import lan
from classlayout import GROUND, GROUND_BLOCK, Layout, MAX_PLOT
from classworld import ClassSetup
from lanclient import LanClient
from lanserver import LanServer, WorldState
from tests import scratch
from tests.test_lan import messages, wait_for


class Geometry(unittest.TestCase):
    def test_resizing_all_plots_keeps_the_owners_and_the_grid(self):
        layout = Layout.grid(2, 2, 12, 12, 5, names=['Ann', 'Bo'])
        layout.relayout(20, 14)
        self.assertEqual([(p.owner, p.size) for p in layout.plots][:2], [('Ann', (20, 14)), ('Bo', (20, 14))])
        self.assertEqual((layout.plot_by_id(2).x1, layout.plot_by_id(3).z1), (25, 19))
        self.assertTrue(layout.inside_border(layout.plots[-1].x2, layout.plots[-1].z2))            # (the border grew with them)

    def test_one_more_plot_goes_in_the_next_place(self):
        layout = Layout.grid(2, 1, 12, 12, 5)
        plot = layout.add_plot('Cy')
        self.assertEqual((plot.id, plot.x1, plot.z1, plot.owner), (3, 0, 17, 'Cy'))
        self.assertIsNone(layout.plot_at(0, 16))                                                    # (the path between the rows)

    def test_one_plot_can_grow_only_where_there_is_room(self):
        layout = Layout.grid(2, 1, 12, 12, 5)
        layout.resize_plot(layout.plot_by_id(1), 14, 10)
        self.assertEqual(layout.plot_by_id(1).size, (14, 10))
        with self.assertRaisesRegex(ValueError, 'too close to plot 2'):
            layout.resize_plot(layout.plot_by_id(1), 16)
        layout.resize_plot(layout.plot_by_id(2), 40, 40)                                             # (nothing next to it on that side)
        for bad in (3, MAX_PLOT + 1, 0, -5, True, 'big'):
            with self.assertRaisesRegex(ValueError, 'blocks wide and deep'):
                layout.resize_plot(layout.plot_by_id(2), bad)

    def test_hand_made_plots_cannot_be_regridded(self):
        layout = Layout.grid(1, 1)
        layout.grid_info = None
        with self.assertRaisesRegex(ValueError, 'not made as a grid'):
            layout.relayout(10)
        with self.assertRaisesRegex(ValueError, 'cannot be added'):
            layout.add_plot()

    def test_the_file_remembers_the_grid_and_plot_mode(self):
        layout = Layout.grid(3, 1, 12, 12, 5)
        layout.auto_claim = True
        again = Layout.from_json(json.loads(json.dumps(layout.to_json())))
        self.assertEqual((again.grid_info, again.auto_claim), (layout.grid_info, True))
        self.assertIsNone(Layout.from_json({'plots': [], 'grid': {'columns': 2}}).grid_info)          # (half a grid is not a grid)


class StartingPlotMode(unittest.TestCase):
    def test_the_command_makes_a_flat_world_with_plots_for_whoever_comes(self):
        args = argparse.Namespace(class_file=None, plot_mode=True, plot_size='12x10', plot_count=3, columns=None, fresh=True, mode=None,
                                  world=None, plot=None, seed=None, name='x')
        world, where = lan.make_world(args)
        layout = world.layout
        self.assertEqual((len(layout.plots), layout.plots[0].size, layout.auto_claim, args.mode), (3, (12, 10), True, 'creative'))
        self.assertEqual(world.flat_spawn, list(layout.spawn))
        bad = argparse.Namespace(**dict(vars(args), plot_size='huge'))
        with self.assertRaises(SystemExit):
            lan.make_world(bad)

    def test_a_class_setup_can_ask_for_plot_mode(self):
        setup = ClassSetup.for_roster('pm', ['Ann'], auto_claim=True)
        again = ClassSetup.from_json(json.loads(json.dumps(setup.to_json())))
        self.assertTrue(again.auto_claim)
        self.assertTrue(again.build_world().layout.auto_claim)


class Base(unittest.TestCase):
    PIN = 'teach1234'

    def setUp(self):
        setup = ClassSetup.for_roster('pm', [], 12, 12, 5, columns=2, extra=2, mode='survival', auto_claim=True)
        self.save = scratch('plotmode') / f'{time.time()}.lanworld.json'
        self.server = LanServer(setup.build_world(), pin=self.PIN, code='maple-tiger-42', host='127.0.0.1', port=0, default_mode='survival',
                                save_path=self.save).start()
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.server.stop()

    def join(self, name, teacher=False, at=(5.0, 4.0, 5.0)):
        client = LanClient('127.0.0.1', self.server.port, 'maple-tiger-42', name)
        client.info = client.connect()
        self.clients.append(client)
        client.send_pos(*at, 0, 0)
        time.sleep(0.12)
        if teacher:
            self.say(client, f'/teacher {self.PIN}')
        return client

    def say(self, client, text, wait=0.3):
        client.chat(text)
        time.sleep(wait)

    def texts(self, client, wait=0.3):
        return [m['m'] for m in messages(client, 'say', wait)]

    @property
    def layout(self):
        return self.server.world.layout


class Joining(Base):
    def test_everyone_who_joins_gets_a_plot_and_the_grid_grows(self):
        names = ['Ann', 'Bo', 'Cy', 'Dee']
        watcher = self.join('Zed', teacher=True)
        for name in names:
            self.join(name)
        self.assertEqual([self.layout.owner_of(n).id for n in names], [1, 2, 3, 4])                  # (the 4 plots made at the start are all taken)
        fifth = self.join('Eli')
        self.assertEqual(self.layout.owner_of('Eli').id, 5)                                            # (a new one appeared for Eli)
        self.assertEqual(len(self.layout.plots), 5)
        self.assertTrue(any('Your plot is number 5' in t for t in self.texts(fifth)))
        drawn = [m for m in messages(watcher, 'blocks') if m['by'] == 0 and any(c[3] == 'stone_bricks' for c in m['c'])]
        self.assertTrue(drawn)                                                                          # (everyone was told to draw its line)
        plots = messages(watcher, 'plots')[-1]['plots']
        self.assertEqual(plots[-1]['owner'], 'Eli')

    def test_a_returning_student_keeps_their_plot(self):
        ann = self.join('Ann')
        ann.close()
        time.sleep(0.3)
        again = self.join('Ann')
        self.assertEqual(self.layout.owner_of('Ann').id, 1)
        self.assertEqual(len([p for p in self.layout.plots if p.owner == 'Ann']), 1)


class Teacher(Base):
    def build(self, client, pos, name='bricks'):
        client.send_blocks([(pos[0], pos[1], pos[2], name, None, None, None)])
        time.sleep(0.2)

    def test_all_plots_the_same_new_size(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        old_ring = (self.layout.plot_by_id(1).x2 + 1, GROUND, 3)
        self.assertEqual(self.server.world.changes[old_ring][0], 'stone_bricks')
        self.say(teacher, '/plotsize 20 16')
        self.assertTrue(any('Every plot is 20 x 16' in t for t in self.texts(teacher)))
        self.assertEqual({p.size for p in self.layout.plots}, {(20, 16)})
        self.assertEqual(self.layout.owner_of('Ann').id, 1)                                           # (still hers)
        self.assertNotIn(old_ring, self.server.world.changes)                                          # (the old line is plain ground again)
        new_ring = (self.layout.plot_by_id(1).x2 + 1, GROUND, 3)
        self.assertEqual(self.server.world.changes[new_ring][0], 'stone_bricks')
        told = [c for m in messages(ann, 'blocks') if m['by'] == 0 for c in m['c']]
        self.assertIn([old_ring[0], GROUND, 3, GROUND_BLOCK, None], told)                              # (and everybody was told so)
        self.assertIn(list(new_ring) + ['stone_bricks', None], told)
        self.assertTrue(messages(ann, 'tp'))                                                           # (students are taken to their plot, which moved)
        ann.send_pos(5.0, 4.0, 5.0, 0, 0)
        time.sleep(0.2)
        self.build(ann, (17, 4, 5))                                                                    # (inside the new, bigger plot 1: it was 12 wide, now 20)
        self.assertIn((17, 4, 5), self.server.world.changes)

    def test_when_something_is_built_it_asks_before_throwing_it_away(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        self.build(ann, (5, 4, 5))
        self.say(teacher, '/plotsize 8')
        self.assertTrue(any('/plotsize 8 8 clear' in t for t in self.texts(teacher)))
        self.assertEqual(self.layout.plot_by_id(1).size, (12, 12))
        self.assertIn((5, 4, 5), self.server.world.changes)
        self.say(teacher, '/plotsize 8 clear')
        self.assertEqual(self.layout.plot_by_id(1).size, (8, 8))
        self.assertNotIn((5, 4, 5), self.server.world.changes)
        removed = [c for m in messages(ann, 'blocks') if m['by'] == 0 for c in m['c']]
        self.assertIn([5, 4, 5, None, None], removed)

    def test_one_plot_in_place_and_what_is_left_outside(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        self.build(ann, (10, 4, 10))
        self.say(teacher, '/resize 1 14 10')
        self.assertEqual(self.layout.plot_by_id(1).size, (14, 10))
        self.assertEqual(self.layout.plot_by_id(2).size, (12, 12))
        self.say(teacher, '/resize 1 16')
        self.assertTrue(any('too close' in t for t in self.texts(teacher)))
        self.say(teacher, '/resize 1 8')                                                               # (the block at 10 is now outside)
        self.assertTrue(any('1 blocks are outside it now and stay' in t for t in self.texts(teacher)))
        self.assertIn((10, 4, 10), self.server.world.changes)
        self.say(teacher, '/resize 1 12 clear')                                                        # (back to 12, the block at 10 is inside again)
        self.say(teacher, '/resize 1 8 clear')
        self.assertNotIn((10, 4, 10), self.server.world.changes)

    def test_add_a_plot(self):
        teacher = self.join('Tea', teacher=True)
        before = len(self.layout.plots)
        self.say(teacher, '/addplot')
        self.assertEqual(len(self.layout.plots), before + 1)
        self.assertIsNone(self.layout.plots[-1].owner)

    def test_only_teachers_and_only_sensible_sizes(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        for command in ('/plotsize 30', '/resize 1 30', '/addplot'):
            self.say(ann, command)
        self.assertEqual({p.size for p in self.layout.plots}, {(12, 12)})
        self.assertTrue(any('Only a teacher' in t for t in self.texts(ann)))
        for command in ('/plotsize', '/plotsize 2', '/plotsize 500', '/plotsize big', '/plotsize 1 2 3', '/resize', '/resize 99 10', '/resize 1', '/resize x 10'):
            self.say(teacher, command, wait=0.15)
        self.assertEqual({p.size for p in self.layout.plots}, {(12, 12)})
        self.assertIn(teacher.id, self.server.players)

    def test_the_new_sizes_are_kept(self):
        teacher = self.join('Tea', teacher=True)
        self.say(teacher, '/plotsize 18')
        self.say(teacher, '/addplot')
        self.server.save()
        saved = WorldState.load(self.save)
        self.assertEqual({p.size for p in saved.layout.plots}, {(18, 18)})
        self.assertEqual(saved.layout.grid_info['width'], 18)
        self.assertTrue(saved.layout.auto_claim)

    def test_building_follows_the_new_borders(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        self.say(teacher, '/plotsize 6')
        ann.send_pos(3.0, 4.0, 3.0, 0, 0)
        time.sleep(0.2)
        self.build(ann, (8, 4, 3))                                                                      # (plot 1 is x 0..5 now: this is outside)
        self.assertNotIn((8, 4, 3), self.server.world.changes)
        self.assertIn('own plot', wait_for(ann, 'reject')['why'])                                         # (told why)
        self.build(ann, (3, 4, 3))
        self.assertIn((3, 4, 3), self.server.world.changes)


if __name__ == '__main__':
    unittest.main()
