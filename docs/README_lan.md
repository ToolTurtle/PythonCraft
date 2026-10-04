# Playing together on the classroom network (LAN)

Everyone on the same school network can walk around one world, build together, and chat. **It only works on the local network**:
the server refuses any computer that is not on a private address (like 192.168.x.x), so nothing goes out to or comes in from the internet.

## Start a class (one computer runs the server)

```bash
python3 lan.py host                      # a new world
python3 lan.py host --world MyWorld      # a copy of one of your saved worlds (your save is never changed)
python3 lan.py host --plot city.pcplot   # a pycraft plot or a tutorial world
python3 lan.py host --play Ms-Lee        # ...and also play in it on this computer
```

It prints what students need:

```
  Join with:   python3 lan.py join 192.168.1.23 maple-tiger-42 --name YOURNAME
  Room code:   maple-tiger-42
  Teacher PIN: 483920
```

New players start in **adventure** mode (they can walk and open doors, not build): `--mode survival` or `--mode creative` changes that.
The class world is kept in `lanworlds/` and carries on next time.

## Join (every student)

```bash
python3 lan.py join                      # looks for a class server and asks for the room code and a name
python3 lan.py join 192.168.1.23 maple-tiger-42 --name Sam
```

Press **T** (or **/**) to chat. If the mods differ from the host's the game says so: install the same `.pcmod` files (`modtool.py install`).

## Being a teacher: from any computer

The server does not need to be the teacher's computer, and a class can have more than one teacher. In the game, type:

```
/teacher 483920
```

The server checks the PIN (it only keeps a scrambled copy, and slows down guessing: five wrong tries lock that player for a minute).
A teacher starts in creative mode and can use:

| Command | Does |
|---|---|
| `/mode MODE [name\|all]` | `adventure`, `survival`, `creative` or `spectator` for one student (a name, or the start of it) or for everyone |
| `/default MODE` | the mode new players start in |
| `/freeze [name\|all]`, `/unfreeze` | stop students moving (and building) while you talk |
| `/lock`, `/unlock` | nobody but teachers can build |
| `/mute name`, `/unmute name` | stop one student chatting |
| `/kick name [reason]` | remove a student |
| `/tp name` | go to a student |
| `/bring name\|all` | bring students to you |
| `/say text` | a big announcement on everyone's screen |
| `/time day\|night\|noon\|sunrise\|sunset` | change the time for everyone |
| `/list`, `/help`, `/teacher off` | who is here; the commands; stop being a teacher |

Whoever runs the server can type the same commands in its window (without the slash, e.g. `mode creative all`).
Students only get `/list`, `/help` and `/teacher`.

## What is shared, and what is not (yet)

Shared: blocks placed and broken (and doors and levers), where everyone is, chat, mode, time when a teacher sets it.
**Not shared yet:** water and lava flowing, fire, TNT, falling sand, chests and furnaces, and animals (there are no wild animals in a class
world, so everyone sees the same thing), and the day-night clock drifts a little between computers until a teacher sets `/time`.

## How it keeps students safe

- Only local-network addresses may connect; the server never talks to the internet.
- A room code is needed to join; the teacher PIN is kept only as a salted hash and guessing is limited.
- The server decides what is allowed: a student in adventure mode cannot place or break blocks even with a changed game, and nobody can
  change blocks more than a few blocks away from where the server last saw them.
- Every message is checked (size, numbers, block names); too many bad or too many messages gets a player removed.
- Names are cleaned (letters and digits only, first names are enough); nothing a player sends is ever run as code.
- Teachers can mute, kick and turn building off at any time.
