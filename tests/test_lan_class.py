"""Class rules of the LAN server: rollback, plots, code building, moderation, shared simulation, chests, mods on offer."""
import io
import json
import time
import unittest
import zipfile

import tests
import netproto as proto
from classlayout import GROUND, Layout, clean_roster
from lanclient import LanClient, LanError
from lanserver import LanServer, WorldState
from tests import scratch
from tests.test_lan import messages, wait_for


class Base(unittest.TestCase):
    PIN = 'teach1234'
    LAYOUT = None
    OPTIONS = {}

    def setUp(self):
        world = WorldState(seed=3, title='T', layout=self.LAYOUT() if self.LAYOUT else None)
        self.server = LanServer(world, pin=self.PIN, code='maple-tiger-42', host='127.0.0.1', port=0, **self.OPTIONS).start()
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.server.stop()

    def join(self, name='Sam', teacher=False, mode=None, at=(0.0, 70.0, 0.0)):
        client = LanClient('127.0.0.1', self.server.port, 'maple-tiger-42', name)
        client.info = client.connect()
        self.clients.append(client)
        if at:
            client.send_pos(*at, 0, 0)
            time.sleep(0.12)
        if teacher:
            self.say(client, f'/teacher {self.PIN}')
        if mode:
            self.server.operator(f'mode {mode} {client.name}')
            time.sleep(0.1)
        return client

    def say(self, client, text, wait=0.25):
        client.chat(text)
        time.sleep(wait)

    def texts(self, client, wait=0.3):
        return [m['m'] for m in messages(client, 'say', wait)]


def grid():
    return Layout.grid(2, 1, width=16, depth=16, gap=5, names=['Ann'])


class Rollback(Base):
    def test_history_and_undo(self):
        teacher, ann, bo = self.join('Tea', teacher=True), self.join('Ann', mode='survival'), self.join('Bo', mode='survival')
        for number in range(3):
            ann.send_blocks([(number, 70, 1, 'bricks', None, None, None)])
        bo.send_blocks([(5, 70, 1, 'gold_block', None, None, None)])
        time.sleep(0.3)
        self.say(teacher, '/history')
        self.assertTrue(any('Ann: 3 / 3' in t for t in self.texts(teacher)))
        self.say(teacher, '/undo Ann 5m')
        changes = [m for m in messages(bo, 'blocks') if m['by'] == 0]
        self.assertEqual(sorted(c[0] for m in changes for c in m['c']), [0, 1, 2])
        self.assertEqual(self.server.world.changes[(0, 70, 1)], (None, None))              # (put back to what Ann saw: nothing)
        self.assertEqual(self.server.world.changes[(5, 70, 1)], ('gold_block', None))      # (Bo's block stays)
        self.assertTrue(any('Put back 3' in t for t in self.texts(teacher)))

    def test_what_was_built_over_is_left_alone(self):
        teacher, ann, bo = self.join('Tea', teacher=True), self.join('Ann', mode='survival'), self.join('Bo', mode='survival')
        ann.send_blocks([(1, 70, 1, 'bricks', None, None, None)])
        time.sleep(0.2)
        bo.send_blocks([(1, 70, 1, 'gold_block', None, 'bricks', None)])
        time.sleep(0.2)
        self.say(teacher, '/undo Ann all')
        self.assertEqual(self.server.world.changes[(1, 70, 1)], ('gold_block', None))
        self.assertTrue(any('1 could not be' in t for t in self.texts(teacher)))

    def test_undo_by_count_and_bad_words(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann', mode='survival')
        for number in range(5):
            ann.send_blocks([(number, 70, 2, 'bricks', None, None, None)])
        time.sleep(0.3)
        self.say(teacher, '/undo Ann 2')
        self.assertEqual(sum(1 for pos, v in self.server.world.changes.items() if v == ('bricks', None)), 3)
        self.say(teacher, '/undo Ann someday')
        self.assertTrue(any('how far back' in t for t in self.texts(teacher)))
        self.say(teacher, '/undo Zed 5m')
        self.assertTrue(any('nobody called' in t for t in self.texts(teacher)))

    def test_only_teachers_can_undo(self):
        ann = self.join('Ann', mode='survival')
        self.say(ann, '/undo Ann all')
        self.assertTrue(any('Only a teacher' in t for t in self.texts(ann)))


class Plots(Base):
    LAYOUT = staticmethod(grid)

    def test_building_only_in_your_own_plot(self):
        teacher, ann, bo = self.join('Tea', teacher=True), self.join('Ann', mode='survival', at=(5.0, 4.0, 5.0)), self.join('Bo', mode='survival', at=(5.0, 4.0, 5.0))
        ann.send_blocks([(5, 4, 5, 'bricks', None, None, None)])                         # (inside plot 1, Ann's)
        self.assertIsNone(wait_for(ann, 'reject', timeout=0.4))
        bo.send_blocks([(6, 4, 5, 'bricks', None, None, None)])                          # (Bo owns nothing)
        reject = wait_for(bo, 'reject')
        self.assertIn('/claim', reject['why'])
        self.say(bo, '/claim')
        self.assertEqual(self.server.world.layout.owner_of('Bo').id, 2)
        ann.send_pos(25.0, 4.0, 5.0, 0, 0)                                               # (Ann walks into Bo's plot, which starts at x = 21)
        time.sleep(0.2)
        ann.send_blocks([(25, 4, 5, 'bricks', None, None, None)])
        self.assertIn("Bo's plot", wait_for(ann, 'reject')['why'])

    def test_doors_and_levers_work_anywhere(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann', mode='survival', at=(30.0, 4.0, 5.0))
        ann.send_blocks([(30, 4, 5, 'lever_on', None, 'lever', None)])
        self.assertIsNone(wait_for(ann, 'reject', timeout=0.4))

    def test_teachers_build_anywhere(self):
        teacher = self.join('Tea', teacher=True, at=(30.0, 4.0, 5.0))
        teacher.send_blocks([(30, 4, 5, 'bricks', None, None, None)])
        self.assertIsNone(wait_for(teacher, 'reject', timeout=0.4))

    def test_the_border_stops_students_not_teachers(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann', mode='survival')
        ann.send_pos(500.0, 4.0, 500.0, 0, 0)
        moved = wait_for(ann, 'tp')
        self.assertLess(moved['x'], 100)
        teacher.send_pos(500.0, 4.0, 500.0, 0, 0)
        self.assertIsNone(wait_for(teacher, 'tp', timeout=0.4))

    def test_assigning_plots_by_name_even_before_they_join(self):
        teacher = self.join('Tea', teacher=True)
        self.say(teacher, '/assign Cy 2')
        self.assertEqual(self.server.world.layout.plot_by_id(2).owner, 'Cy')
        cy = self.join('Cy', mode='survival')
        self.assertEqual(cy.info['name'], 'Cy')
        self.assertTrue(any('Your plot is number 2' in t for t in self.texts(cy)))
        self.say(teacher, '/unassign Cy')
        self.assertIsNone(self.server.world.layout.plot_by_id(2).owner)
        plots = [m for m in messages(cy, 'plots')]
        self.assertTrue(plots and plots[-1]['plots'][1]['owner'] is None)

    def test_claim_and_home_rules(self):
        ann, bo, cy = self.join('Ann'), self.join('Bo'), self.join('Cy')
        self.say(ann, '/home')
        self.assertIsNotNone(wait_for(ann, 'tp'))
        self.say(bo, '/claim')
        self.say(cy, '/claim')
        self.assertTrue(any('All the plots are taken' in t for t in self.texts(cy)))
        self.say(bo, '/claim')
        self.assertTrue(any('already have plot 2' in t for t in self.texts(bo)))

    def test_layout_markers_and_geometry(self):
        layout = grid()
        self.assertEqual(layout.plot_at(0, 0).id, 1)
        self.assertEqual(layout.plot_at(21, 0).id, 2)
        self.assertIsNone(layout.plot_at(17, 0))
        markers = layout.marker_blocks()
        self.assertEqual(markers[(-1, GROUND, 0)], 'stone_bricks')
        self.assertEqual(markers[(18, GROUND, 8)], 'gravel')
        self.assertNotIn((5, GROUND, 5), markers)
        self.assertEqual(Layout.from_json(json.loads(json.dumps(layout.to_json()))).owner_of('ann').id, 1)
        self.assertEqual(clean_roster('Ann, Bo\nCy <b>;ann'), ['Ann', 'Bo', 'Cy b'])
        with self.assertRaises(ValueError):
            Layout.grid(0, 1)


class CodeBuilding(Base):
    LAYOUT = staticmethod(grid)

    def test_code_builds_in_your_plot_from_any_distance_even_in_adventure(self):
        ann = self.join('Ann', at=(100.0, 4.0, 100.0))                                  # (adventure, far away)
        ann.send_blocks([(2, 4, 2, 'bricks', None, None, None)], code=True)
        self.assertIsNone(wait_for(ann, 'reject', timeout=0.4))
        self.assertEqual(self.server.world.changes[(2, 4, 2)], ('bricks', None))
        ann.send_blocks([(25, 4, 2, 'bricks', None, None, None)], code=True)             # (plot 2 is not hers)
        self.assertIn('own plot', wait_for(ann, 'reject')['why'])

    def test_code_needs_a_plot_and_can_be_turned_off_or_locked(self):
        teacher, bo, ann = self.join('Tea', teacher=True), self.join('Bo'), self.join('Ann')
        bo.send_blocks([(25, 4, 2, 'bricks', None, None, None)], code=True)
        self.assertIn('/claim', wait_for(bo, 'reject')['why'])
        self.say(teacher, '/code off Ann')
        ann.send_blocks([(2, 4, 2, 'bricks', None, None, None)], code=True)
        self.assertIn('turned off', wait_for(ann, 'reject')['why'])
        self.say(teacher, '/code on Ann')
        self.say(teacher, '/lock')
        ann.send_blocks([(2, 4, 2, 'bricks', None, None, None)], code=True)
        self.assertIn('locked', wait_for(ann, 'reject')['why'])

    def test_teachers_see_what_students_typed(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        ann.send_code('fill 0 0 0 3 0 3 stone')
        time.sleep(0.2)
        self.say(teacher, '/code Ann')
        self.assertTrue(any('fill 0 0 0 3 0 3 stone' in t for t in self.texts(teacher)))
        roster = messages(teacher, 'roster', wait=4.5)[-1]['players']
        self.assertEqual([p['last'] for p in roster if p['name'] == 'Ann'], ['fill 0 0 0 3 0 3 stone'])


class Moderation(Base):
    OPTIONS = {'badwords': ['stupid', 'dumb head']}

    def setUp(self):
        self.log = scratch('modlog') / f'{time.time()}.log'
        self.OPTIONS = dict(self.OPTIONS, chat_log=self.log)
        super().setUp()

    def test_filter_stars_out_words_and_tells_teachers(self):
        teacher, ann, bo = self.join('Tea', teacher=True), self.join('Ann'), self.join('Bo')
        ann.chat('you are STUPID and a dumb head')
        message = wait_for(bo, 'chat')
        self.assertEqual(message['m'], 'you are ****** and a *********')
        self.assertTrue(any('[filtered] Ann said' in t for t in self.texts(teacher)))
        teacher.chat('stupid is a word teachers may type')
        self.assertIn('stupid', wait_for(bo, 'chat')['m'])

    def test_chat_off_and_mute_all(self):
        teacher, ann, bo = self.join('Tea', teacher=True), self.join('Ann'), self.join('Bo')
        self.say(teacher, '/chat off')
        ann.chat('hello?')
        self.assertTrue(any('turned off' in t for t in self.texts(ann)))
        teacher.chat('class, listen')
        self.assertIsNotNone(wait_for(bo, 'chat'))
        self.say(teacher, '/chat on')
        self.say(teacher, '/mute all')
        bo.chat('hi')
        self.assertTrue(any('muted' in t for t in self.texts(bo)))

    def test_chat_log_is_written_for_the_teacher(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        ann.chat('hello class')
        self.say(teacher, '/mode survival Ann')
        time.sleep(0.3)
        text = self.log.read_text()
        self.assertIn('Ann: hello class', text)
        self.assertIn('* Ann joined', text)
        self.assertIn('Tea (teacher) used /mode survival Ann', text)
        self.assertNotIn(self.PIN, text)

    def test_wrong_teacher_pin_attempts_are_not_logged_with_the_pin(self):
        ann = self.join('Ann')
        self.say(ann, '/teacher mypin1')
        self.assertNotIn('mypin1', self.log.read_text() if self.log.exists() else '')


class Simulation(Base):
    def test_one_player_runs_the_world_for_everyone(self):
        ann = self.join('Ann')
        self.assertTrue(wait_for(ann, 'authority')['on'])
        bo = self.join('Bo')
        self.assertIsNone(wait_for(bo, 'authority', timeout=0.4))
        ann.send_sim([(3, 70, 3, 'water', None, None, None)])
        self.assertEqual(wait_for(bo, 'blocks')['sim'], True)
        self.assertEqual(self.server.world.changes[(3, 70, 3)], ('water', None))

    def test_others_cannot_pretend_to_run_the_world(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        bo.send_sim([(3, 70, 3, 'lava', None, None, None)])
        time.sleep(0.3)
        self.assertNotIn((3, 70, 3), self.server.world.changes)

    def test_when_they_leave_the_next_player_takes_over(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        ann.close()
        self.assertTrue(wait_for(bo, 'authority', timeout=3)['on'])


class Chests(Base):
    ITEMS = [['stone', 5, 0]] + [None] * 26

    def test_a_chest_is_shared_validated_and_kept(self):
        ann, bo = self.join('Ann', mode='survival'), self.join('Bo', mode='survival')
        ann.send_chest(1, 70, 1, self.ITEMS)
        message = wait_for(bo, 'chest')
        self.assertEqual((message['x'], message['items'][0]), (1, ['stone', 5, 0]))
        late = LanClient('127.0.0.1', self.server.port, 'maple-tiger-42', 'Late')
        late_info = late.connect()
        self.clients.append(late)
        self.assertEqual(late_info['chests'][0][3][0], ['stone', 5, 0])                 # (a late joiner gets the chests as they are)
        ann.send_chest(2, 70, 2, [['not_an_item', 1, 0]] + [None] * 26)
        ann.send_chest(3, 70, 3, [['stone', 99, 0]] + [None] * 26)
        ann.send_chest(4, 70, 4, [None] * 3)
        time.sleep(0.3)
        self.assertEqual(set(self.server.world.chests), {(1, 70, 1)})

    def test_far_away_or_spectating_players_cannot_change_chests(self):
        ann = self.join('Ann', mode='survival', at=(0.0, 70.0, 0.0))
        ann.send_chest(300, 70, 300, self.ITEMS)
        time.sleep(0.3)
        self.assertEqual(self.server.world.chests, {})


class ModsOnOffer(unittest.TestCase):
    def test_a_player_without_the_mod_downloads_it(self):
        import blocks
        folder = scratch('offer')
        png = io.BytesIO()
        from PIL import Image
        Image.new('RGBA', (16, 16), (9, 9, 9, 255)).save(png, 'PNG')
        spec = {'format': 'pcmod', 'version': 1, 'name': 'offered', 'ops': [
            {'op': 'addblock', 'name': 'offered_block', 'faces': {'all': {'file': 'files/a.png'}}, 'like': None, 'props': {}}]}
        with zipfile.ZipFile(folder / 'offered.pcmod', 'w') as archive:
            archive.writestr('mod.json', json.dumps(spec))
            archive.writestr('files/a.png', png.getvalue())
        names = list(blocks.BLOCKS) + ['offered_block']                   # (the server has the block, this computer does not yet)
        server = LanServer(WorldState(), pin='abcd1', code='x-y-11', host='127.0.0.1', known_blocks=names, mods_dir=folder).start()
        try:
            refused = LanClient('127.0.0.1', server.port, 'x-y-11', 'No', auto_mods=False)
            with self.assertRaisesRegex(LanError, 'offered'):
                refused.connect()
            self.assertNotIn('offered_block', blocks.BLOCKS)
            client = LanClient('127.0.0.1', server.port, 'x-y-11', 'Yes')
            client.connect()
            self.assertIn('offered_block', blocks.BLOCKS)                   # (downloaded, checked and loaded)
            client.close()
            asking = LanClient('127.0.0.1', server.port, 'x-y-11', 'X')
            asking.sock = __import__('socket').create_connection(('127.0.0.1', server.port), 3)
            asking.send({'t': 'getmod', 'sha': 'whatever'})
            self.assertIn(b'error', asking.sock.recv(1000))                 # (only what is on offer can be asked for)
            asking.sock.close()
        finally:
            server.stop()

    def test_mods_that_are_not_on_offer_are_just_refused(self):
        server = LanServer(WorldState(), pin='abcd1', code='x-y-11', host='127.0.0.1', known_blocks=['stone', 'zzz']).start()
        try:
            with self.assertRaisesRegex(LanError, 'mods'):
                LanClient('127.0.0.1', server.port, 'x-y-11', 'A').connect()
        finally:
            server.stop()


if __name__ == '__main__':
    unittest.main()


class Animals(Base):
    def entry(self, ident=1, kind='pig', x=5.0):
        return [ident, kind, x, 4.0, 3.0, 90.0, 1, 10]

    def test_only_the_world_runner_can_place_animals_and_others_see_them(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        self.assertTrue(wait_for(ann, 'authority')['on'])
        ann.send_mobs([self.entry(1, 'pig'), self.entry(2, 'cow')])
        message = wait_for(bo, 'mobs')
        self.assertEqual([e[1] for e in message['c']], ['pig', 'cow'])
        bo.send_mobs([self.entry(9, 'zombie')])                                  # (Bo does not run the world)
        self.assertIsNone(wait_for(ann, 'mobs', timeout=0.4))

    def test_bad_animals_are_refused(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        for bad in ([[1, 'not_a_mob', 0, 0, 0, 0, 0, 1]], [[1, 'pig', 'x', 0, 0, 0, 0, 1]], [[1, 'pig', 0, 0, 0]], [self.entry()] * 300):
            ann.send_mobs(bad)
        self.assertIsNone(wait_for(bo, 'mobs', timeout=0.5))

    def test_a_hit_goes_to_the_world_runner_and_loot_comes_back(self):
        ann, bo = self.join('Ann'), self.join('Bo', mode='survival', at=(1.0, 4.0, 1.0))
        bo.send_mobhit(7, 4.5)
        hit = wait_for(ann, 'mobhit')
        self.assertEqual((hit['by'], hit['id'], hit['dmg']), (bo.id, 7, 4.5))
        ann.send_loot(bo.id, 'porkchop', 2)
        self.assertEqual(wait_for(bo, 'loot')['name'], 'porkchop')
        ann.send_loot(bo.id, 'not_an_item', 1)
        ann.send_loot(bo.id, 'diamond', 9999)
        self.assertIsNone(wait_for(bo, 'loot', timeout=0.5))
        bo.send_loot(ann.id, 'diamond', 1)                                       # (only the world runner hands out loot)
        self.assertIsNone(wait_for(ann, 'loot', timeout=0.4))

    def test_frozen_and_spectating_players_cannot_hit(self):
        teacher, ann, bo = self.join('Tea', teacher=True), self.join('Ann'), self.join('Bo')
        self.say(teacher, '/mode spectator Bo')
        time.sleep(0.2)
        bo.send_mobhit(1, 5)
        self.assertIsNone(wait_for(ann, 'mobhit', timeout=0.4))


class NotTheirFault(Base):
    """Things that happen to a player (falling out of the world, a mod only one side has) must never get them removed."""

    def test_animals_that_fell_out_of_the_world_or_are_unknown_are_left_out(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        good = [1, 'pig', 5.0, 4.0, 3.0, 0.0, 0, 10]
        for _ in range(30):
            ann.send_mobs([good, [2, 'sheep', 0.0, -200.0, 0.0, 0.0, 1, 8], [3, 'a_mod_creature', 0.0, 4.0, 0.0, 0.0, 0, 5], [4, 'cow', 1.0, 4.0]])
        time.sleep(0.5)
        self.assertIn(ann.id, self.server.players)
        self.assertEqual([e[1] for e in wait_for(bo, 'mobs')['c']], ['pig'])
        self.assertEqual(self.server.players[ann.id].bad, 0)

    def test_a_player_falling_into_the_void_stays_in_the_game(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        for _ in range(25):
            ann.send_pos(0.0, -500.0, 0.0, 0, 0)
            time.sleep(0.03)
        self.assertIn(ann.id, self.server.players)
        self.assertEqual(self.server.players[ann.id].pos[1], -64.0)

    def test_the_world_sometimes_changes_at_its_very_edge(self):
        ann, bo = self.join('Ann'), self.join('Bo')
        for _ in range(25):
            ann.send_sim([(1, 70, 1, 'water', None, None, None), (1, 500, 1, 'water', None, None, None), (1, 70, 2, 'not_a_block', None, None, None)])
        time.sleep(0.5)
        self.assertIn(ann.id, self.server.players)
        self.assertEqual(self.server.world.changes[(1, 70, 1)], ('water', None))
        self.assertNotIn((1, 500, 1), self.server.world.changes)

    def test_but_a_message_that_makes_no_sense_still_counts(self):
        ann = self.join('Ann')
        for _ in range(12):
            ann.send({'t': 'mobs', 'c': 'not a list'})
        self.assertIsNotNone(wait_for(ann, 'closed', timeout=3))


class CodeInAWorldWithoutPlots(Base):
    """As in live coding: with no plots, code builds around you."""

    def test_code_builds_near_you_but_not_far_away(self):
        ann = self.join('Ann', at=(100.0, 70.0, 100.0))                               # (adventure mode: code is allowed anyway)
        ann.send_blocks([(120, 70, 90, 'bricks', None, None, None)], code=True)
        self.assertIsNone(wait_for(ann, 'reject', timeout=0.4))
        self.assertEqual(self.server.world.changes[(120, 70, 90)], ('bricks', None))
        ann.send_blocks([(400, 70, 100, 'bricks', None, None, None)], code=True)
        self.assertIn('near where you are', wait_for(ann, 'reject')['why'])

    def test_a_teacher_can_still_turn_code_off_or_lock_building(self):
        teacher, ann = self.join('Tea', teacher=True), self.join('Ann')
        self.say(teacher, '/code off Ann')
        ann.send_blocks([(1, 70, 1, 'bricks', None, None, None)], code=True)
        self.assertIn('turned off', wait_for(ann, 'reject')['why'])
        self.say(teacher, '/code on Ann')
        self.say(teacher, '/lock')
        ann.send_blocks([(1, 70, 1, 'bricks', None, None, None)], code=True)
        self.assertIn('locked', wait_for(ann, 'reject')['why'])
        self.say(teacher, '/unlock')
        self.say(teacher, '/freeze Ann')
        ann.send_blocks([(1, 70, 1, 'bricks', None, None, None)], code=True)
        self.assertIn('frozen', wait_for(ann, 'reject')['why'])
