"""The classroom network game: a real server and real clients on this computer (no game window)."""
import json
import socket
import time
import unittest

import tests
import netproto as proto
from lanclient import LanClient, LanError
from lanserver import LanServer, WorldState


def wait_for(client, kind, timeout=3, match=None):
    """The next message of this kind (other messages are kept in `client.seen`)."""
    end = time.monotonic() + timeout
    client.__dict__.setdefault('seen', [])
    while time.monotonic() < end:
        for message in client.poll():
            client.seen.append(message)
            if message['t'] == kind and (match is None or match(message)):
                return message
        time.sleep(0.02)
    return None


def messages(client, kind, wait=0.4):
    time.sleep(wait)
    client.__dict__.setdefault('seen', [])
    client.seen.extend(client.poll())
    return [m for m in client.seen if m['t'] == kind]


class Base(unittest.TestCase):
    PIN = 'teach1234'

    def setUp(self):
        self.server = LanServer(WorldState(seed=3, title='T', changes={(1, 70, 1): ('stone', None)}), pin=self.PIN, code='maple-tiger-42',
                                host='127.0.0.1', port=0).start()
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.server.stop()

    def join(self, name='Sam', code='maple-tiger-42'):
        client = LanClient('127.0.0.1', self.server.port, code, name)
        info = client.connect()
        self.clients.append(client)
        client.info = info
        return client

    def at(self, client, x=0, y=70, z=0):
        client.send_pos(x, y, z, 0, 0)
        time.sleep(0.15)

    def say(self, client, text, wait=0.3):
        client.chat(text)
        time.sleep(wait)


class Joining(Base):
    def test_joining_receives_the_world(self):
        client = self.join()
        self.assertEqual((client.info['seed'], client.info['mode']), (3, 'adventure'))
        self.assertIn([1, 70, 1, 'stone', None], client.info['changes'])

    def test_wrong_code_and_wrong_version_and_other_mods_are_refused(self):
        with self.assertRaisesRegex(LanError, 'room code'):
            self.join(code='wrong')
        client = LanClient('127.0.0.1', self.server.port, 'maple-tiger-42', 'X', blocks_hash='different')
        with self.assertRaisesRegex(LanError, 'mods'):
            client.connect()

    def test_a_server_that_is_not_there(self):
        with self.assertRaisesRegex(LanError, 'Could not reach'):
            LanClient('127.0.0.1', 1, 'x', 'X').connect(timeout=1)

    def test_names_are_made_safe_and_unique(self):
        a, b = self.join('Sam<script>'), self.join('Sam<script>')
        self.assertEqual(a.info['name'], 'Samscript')
        self.assertEqual(b.info['name'], 'Samscript2')
        self.assertEqual(proto.clean_name('   '), 'Player')

    def test_others_see_you_come_and_go(self):
        a = self.join('Ann')
        b = self.join('Bo')
        self.assertEqual(wait_for(a, 'join')['p']['name'], 'Bo')
        b.close()
        self.assertEqual(wait_for(a, 'leave')['id'], b.id)

    def test_positions_reach_the_others(self):
        a, b = self.join('Ann'), self.join('Bo')
        a.send_pos(5, 70, 6, 90, 0, moving=True)
        message = wait_for(b, 'pos')
        self.assertEqual((message['id'], message['x'], message['z'], message['v']), (a.id, 5.0, 6.0, True))


class Building(Base):
    def test_students_start_in_adventure_and_cannot_build(self):
        a, b = self.join('Ann'), self.join('Bo')
        self.at(a)
        a.send_blocks([(1, 70, 1, 'bricks', None)])
        self.assertTrue(wait_for(a, 'reject'))
        self.assertIsNone(wait_for(b, 'blocks', timeout=0.4))

    def test_doors_and_levers_still_work_in_adventure(self):
        a, b = self.join('Ann'), self.join('Bo')
        self.at(a)
        a.send_blocks([(1, 70, 1, 'lever_on', None)])
        self.assertTrue(wait_for(b, 'blocks'))

    def test_a_teacher_can_change_the_mode_and_then_blocks_are_shared(self):
        teacher, a, b = self.join('Tea'), self.join('Ann'), self.join('Bo')
        self.say(teacher, f'/teacher {self.PIN}')
        self.say(teacher, '/mode survival all')
        self.assertEqual(wait_for(a, 'mode', match=lambda m: m['mode'] == 'survival')['locked'], False)
        self.at(a)
        a.send_blocks([(1, 71, 1, 'bricks', 'north')])
        message = wait_for(b, 'blocks')
        self.assertEqual((message['by'], message['c']), (a.id, [[1, 71, 1, 'bricks', 'north']]))
        late = self.join('Late')
        late.send_pos(0, 70, 0, 0, 0)
        self.assertEqual(late.info['mode'], 'adventure')                    # (new players still start as the default says)
        self.assertIn([1, 71, 1, 'bricks', 'north'], late.info['changes'])  # (but they get the world as it is now)

    def test_nobody_reaches_far_away_blocks(self):
        teacher, a = self.join('Tea'), self.join('Ann')
        self.say(teacher, f'/teacher {self.PIN}')
        self.say(teacher, '/mode survival all')
        self.at(a, 0, 70, 0)
        a.send_blocks([(500, 70, 500, 'stone', None)])
        self.assertTrue(wait_for(a, 'reject'))

    def test_lock_and_unlock(self):
        teacher, a = self.join('Tea'), self.join('Ann')
        self.say(teacher, f'/teacher {self.PIN}')
        self.say(teacher, '/mode survival all')
        self.say(teacher, '/lock')
        self.assertTrue(wait_for(a, 'mode', match=lambda m: m['locked'] is True))
        self.at(a)
        a.send_blocks([(1, 71, 1, 'bricks', None)])
        self.assertTrue(wait_for(a, 'reject'))
        self.say(teacher, '/unlock')
        self.assertTrue(wait_for(a, 'mode', match=lambda m: m['locked'] is False))

    def test_unknown_blocks_and_bad_numbers_are_not_allowed(self):
        teacher = self.join('Tea')
        self.say(teacher, f'/teacher {self.PIN}')
        self.at(teacher)
        for bad in ([1, 70, 1, 'not_a_block', None], [1, 999, 1, 'stone', None], [1, 70, 'x', 'stone', None], [1, 70, 1, 'stone']):
            teacher.send_blocks([bad])
        self.assertIsNone(self.server.world.changes.get((1, 999, 1)))
        self.assertNotIn('not_a_block', [v[0] for v in self.server.world.changes.values()])


class Teachers(Base):
    def test_the_right_pin_makes_a_teacher_wherever_they_sit(self):
        teacher = self.join('Tea')
        self.say(teacher, f'/teacher {self.PIN}')
        self.assertTrue(wait_for(teacher, 'role')['teacher'])
        self.assertTrue(self.server.players[teacher.id].teacher)

    def test_a_wrong_pin_is_not_enough_and_guessing_is_slowed_down(self):
        a = self.join('Ann')
        for guess in ('0000', '1234', 'teach', 'abcd', 'nope'):
            self.say(a, f'/teacher {guess}', wait=0.05)
        time.sleep(1.2)                                                    # (chat is rate limited too: wait for one more try)
        self.say(a, f'/teacher {self.PIN}')
        self.assertFalse(self.server.players[a.id].teacher)                 # (locked out, so even the right PIN failed)
        texts = [m['m'] for m in messages(a, 'say')]
        self.assertTrue(any('not the PIN' in t for t in texts))
        self.assertTrue(any('Too many wrong tries' in t for t in texts))

    def test_students_cannot_use_teacher_commands(self):
        a, b = self.join('Ann'), self.join('Bo')
        self.say(a, '/mode creative all')
        self.say(a, '/kick Bo')
        self.assertEqual(self.server.players[b.id].mode, 'adventure')
        self.assertIn(b.id, self.server.players)
        self.assertTrue(any('Only a teacher' in m['m'] for m in messages(a, 'say')))

    def test_mode_for_one_student_by_name_or_the_start_of_it(self):
        teacher, a, b = self.join('Tea'), self.join('Ann'), self.join('Bob')
        self.say(teacher, f'/teacher {self.PIN}')
        self.say(teacher, '/mode creative An')
        self.assertEqual((self.server.players[a.id].mode, self.server.players[b.id].mode), ('creative', 'adventure'))
        self.say(teacher, '/mode spectator Zed')
        self.assertTrue(any('nobody called' in m['m'] for m in messages(teacher, 'say')))

    def test_freeze_mute_kick(self):
        teacher, a, b = self.join('Tea'), self.join('Ann'), self.join('Bob')
        self.say(teacher, f'/teacher {self.PIN}')
        self.say(teacher, '/freeze Ann')
        self.assertTrue(wait_for(a, 'freeze')['on'])
        a.send_pos(9, 70, 9, 0, 0)
        self.assertIsNone(wait_for(b, 'pos', timeout=0.4))                  # (a frozen player does not move for others either)
        self.say(teacher, '/unfreeze Ann')
        self.say(teacher, '/mute Bob')
        b.chat('hello')
        self.assertIsNone(wait_for(a, 'chat', timeout=0.4))
        self.say(teacher, '/kick Bob out you go')
        closed = wait_for(b, 'closed')
        self.assertIn('out you go', closed['m'])
        self.assertNotIn(b.id, self.server.players)

    def test_bring_tp_say_time(self):
        teacher, a = self.join('Tea'), self.join('Ann')
        self.say(teacher, f'/teacher {self.PIN}')
        self.at(teacher, 10, 70, 10)
        self.say(teacher, '/bring all')
        moved = wait_for(a, 'tp')
        self.assertGreater(moved['x'], 10)
        a.send_pos(50, 70, 50, 0, 0)
        time.sleep(0.15)
        self.say(teacher, '/tp Ann')
        self.assertEqual(wait_for(teacher, 'tp')['x'], 50.0)
        self.say(teacher, '/say Eyes up here')
        self.assertEqual(wait_for(a, 'announce')['m'], 'Eyes up here')
        self.say(teacher, '/time night')
        self.assertEqual(wait_for(a, 'time')['ticks'], 14000)

    def test_a_teacher_can_stop_being_one(self):
        teacher = self.join('Tea')
        self.say(teacher, f'/teacher {self.PIN}')
        self.say(teacher, '/teacher off')
        self.assertFalse(self.server.players[teacher.id].teacher)

    def test_the_person_running_the_server_has_teacher_powers_too(self):
        a = self.join('Ann')
        self.assertTrue(any('1 player' in line for line in self.server.operator('mode creative all')))
        self.assertEqual(self.server.players[a.id].mode, 'creative')


class Safety(Base):
    def raw(self):
        sock = socket.create_connection(('127.0.0.1', self.server.port), 3)
        sock.settimeout(3)
        return sock

    def read_all(self, sock):
        data = b''
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except (socket.timeout, OSError):
            pass
        return data

    def test_only_local_addresses(self):
        for good in ('192.168.1.5', '10.0.0.2', '172.16.4.4', '127.0.0.1', '::1', '169.254.1.1'):
            self.assertTrue(proto.is_local_address(good), good)
        for bad in ('8.8.8.8', '1.1.1.1', '93.184.216.34', 'nonsense', '2001:4860:4860::8888'):
            self.assertFalse(proto.is_local_address(bad), bad)

    def test_garbage_before_hello_is_refused(self):
        sock = self.raw()
        sock.sendall(b'GET / HTTP/1.1\r\n\r\n')
        self.assertIn(b'error', self.read_all(sock))
        sock.close()

    def test_a_huge_message_is_refused(self):
        client = self.join('Ann')
        client.sock.sendall(b'{"t":"chat","m":"' + b'a' * 200000 + b'"}\n')
        closed = wait_for(client, 'closed', timeout=3)
        self.assertIsNotNone(closed)

    def test_repeated_bad_messages_get_you_removed(self):
        client = self.join('Ann')
        for _ in range(15):
            client.sock.sendall(b'not json at all\n')
        self.assertIsNotNone(wait_for(client, 'closed', timeout=3))

    def test_a_flood_of_chat_is_slowed_down(self):
        client = self.join('Ann')
        for number in range(40):
            client.chat(f'spam {number}')
        time.sleep(0.5)
        self.assertLess(len([m for m in messages(client, 'chat')]), 15)

    def test_the_pin_is_never_kept_or_shown(self):
        self.assertNotIn(self.PIN.encode(), self.server.pin_hash)
        self.assertNotIn(self.PIN, json.dumps(self.server.world.to_json()))
        self.assertNotIn(self.PIN, ' '.join(self.server.log_lines))
        client = self.join('Ann')
        self.say(client, f'/teacher {self.PIN}x')
        self.assertNotIn(self.PIN, ' '.join(self.server.log_lines))

    def test_message_checks(self):
        self.assertEqual(proto.clean_chat('hi\x00\x07 there'), 'hi there')
        self.assertEqual(len(proto.clean_chat('a' * 1000)), proto.MAX_CHAT)
        for bad in (True, 'x', float('nan'), float('inf'), 10 ** 12):
            with self.assertRaises(proto.ProtocolError):
                proto.number(bad)
        with self.assertRaises(proto.ProtocolError):
            proto.number(1.5, integer=True)
        self.assertEqual(proto.decode(b'{"t":"ping"}')['t'], 'ping')
        for line in (b'[1]', b'{"t":5}', b'{"x":1}', b'\xff\xfe'):
            with self.assertRaises(proto.ProtocolError):
                proto.decode(line)

    def test_a_full_class_says_so(self):
        server = LanServer(WorldState(), pin='abcd1', code='x-y-11', host='127.0.0.1', max_players=1).start()
        try:
            first = LanClient('127.0.0.1', server.port, 'x-y-11', 'A')
            first.connect()
            with self.assertRaisesRegex(LanError, 'full'):
                LanClient('127.0.0.1', server.port, 'x-y-11', 'B').connect()
            first.close()
        finally:
            server.stop()


class Saving(unittest.TestCase):
    def test_the_world_is_saved_and_loaded(self):
        path = tests.scratch('lan') / 'w.lanworld.json'
        server = LanServer(WorldState(seed=9), pin='abcd1', code='a-b-11', host='127.0.0.1', save_path=path).start()
        client = LanClient('127.0.0.1', server.port, 'a-b-11', 'T')
        client.connect()
        client.chat('/teacher abcd1')
        time.sleep(0.2)
        client.send_pos(0, 70, 0, 0, 0)
        client.chat('/mode creative me')
        time.sleep(0.2)
        client.send_blocks([(1, 70, 1, 'gold_block', None)])
        time.sleep(0.3)
        client.close()
        server.stop()
        loaded = WorldState.load(path)
        self.assertEqual((loaded.seed, loaded.changes[(1, 70, 1)]), (9, ('gold_block', None)))


if __name__ == '__main__':
    unittest.main()
