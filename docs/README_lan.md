# Classroom worlds (LAN): everyone in one world

Everyone on the same school network can walk around one world, build together (by hand and with code), and chat. **It only works on the
local network**: the server refuses any computer that is not on a private address (like 192.168.x.x), so nothing goes out to or comes
in from the internet.

## The quick way: the launcher

```bash
python3 launcher.py
```

A window with buttons: **Host a class** (teachers), **Join a class** (students), play on your own, tutorial worlds, live coding, the picture
painter, the mods folder, and **Check my setup**. If something does not work, start there: it checks Python, the packages, the pictures and
sounds, the mods and the network, and says what to fix. (`python3 doctor.py` does the same by typing; see "If it will not connect".)

## Teachers: set up and start a class

**Host a class** opens the class tool. Type or paste the students' names (one per line) and press *Make plots for the names*: you get a grid of
plots, one for each name plus a few spare ones, with stone-brick lines and gravel paths. Click a plot to give it to someone else. Then:

| Button | Does |
|---|---|
| Choose starter build... | every plot starts with this build (any `.pcplot`) |
| Bring in hand-ins... | each student's newest hand-in (from the `submissions` folder) goes into *their* plot, to look at together |
| Import .pcplot into plot... / Export plot... | put a build into the selected plot, or save what is in it to edit with the usual pycraft tools |
| Empty plot | clear the selected plot (the starter build comes back if there is one) |
| Save / Open | the setup is a `.pcclass` file in `classes/` |
| **Start the class** | starts the server and opens the dashboard |

The **dashboard** shows the room code and teacher PIN, who is here (with their game mode, plot and the last code they typed) and buttons for
everything a teacher does: modes, freeze, mute, code on/off, lock building, chat on/off, kick, announcements, and *Undo their last 5 minutes*.
*Open the game as teacher* starts the game in its own window, already a teacher.

Without the window, the same by typing: `python3 classtool.py` shows the commands (`new`, `assign`, `template`, `handins`, `import`, `export`, `reset`)
and `python3 lan.py host --class math4.pcclass` starts the class. Other ways to start: `lan.py host` (a new world), `--world NAME` (a copy of one of
your saved worlds: your save is never changed), `--plot city.pcplot`. `--play NAME` also opens a game for you on the same computer.

New students start in **adventure** mode (they can walk and open doors but not build by hand): change it in the class tool or with `--mode`.
The class world is kept in `lanworlds/` and carries on next time (`--fresh` starts again from the setup).

## Plot mode: the quick way to give everyone a plot

```bash
python3 lan.py host --plot-mode                      # a flat world; everyone who joins gets a plot of their own
python3 lan.py host --plot-mode --plot-size 24 --plot-count 12
python3 lan.py host --plot-mode --plot-size 30x20 --mode survival
```

The world is flat grass with a stone-brick line round every plot and gravel paths between them. Whoever joins gets the next free plot at once, and
**the grid grows by itself** when the plots run out, so there is always one for everybody. (A teacher does not use up a plot: when someone
becomes a teacher their empty plot goes back to the students.) New players start in creative mode here, so they can build freely inside their plot
(`--mode survival` or `adventure` change that). In the class tool the same is the tick box *Plot mode: everyone who joins gets a plot*.

**The teacher can change the sizes while the class is running**, from the dashboard (*Plot size*), from the teacher panel (**P**: *Plots smaller*,
*Plots bigger*, *Add a plot*) or by typing:

| Command | Does |
|---|---|
| `/plotsize 24` or `/plotsize 24 16` | every plot becomes that size (width x depth) and they are laid out again, keeping who owns which. Only works while nothing is built in the plots: if something is, it says how many blocks and asks you to add `clear` (`/plotsize 24 clear`) to remove them and go ahead |
| `/resize 3 30 20` | just plot 3, keeping its corner. It must keep 3 blocks of path from the next plot. If it shrinks past things that were built, they stay where they are (add `clear` to remove them) |
| `/addplot` | one more plot at the end of the grid |

A plot is from 4 to 128 blocks wide and deep. The stone-brick lines and paths are redrawn for everybody at once, and students are taken to their plot
again if the plots moved.

## Students: join

```bash
python3 lan.py join                      # looks for a class server and asks for the room code and a name
python3 lan.py join 192.168.1.23 maple-tiger-42 --name Sam
```

or press *Join a class* in the launcher. In the game:

| Key | Does |
|---|---|
| **T** | chat (**/** starts a chat command) |
| **C** | the code prompt: type commands or Python, and they build **inside your plot** (see [COMMANDS.md](COMMANDS.md)) |
| **P** | the teacher panel (teachers) |
| **X** | stop following a student (teachers) |

Type `/claim` to get a plot (if you do not have one yet), `/home` to go to it, `/plots` to see who has which. A name tag floats over each plot.
You can build by hand only inside your own plot (in survival or creative mode; a teacher chooses). If you are missing a mod the teacher uses,
the game downloads it from the server first (only `.pcmod` files, which hold data and are checked: see [README_mods.md](README_mods.md)).

## Being a teacher: from any computer

The server does not need to be the teacher's computer, and a class can have more than one teacher. In the game, type `/teacher 483920` (the PIN
the server printed). The server checks it (it only keeps a scrambled copy, and slows down guessing: five wrong tries lock that player for a minute).
A teacher starts in creative mode, can build anywhere, and presses **P** for the class panel: a list of students with buttons for mode, freeze, mute,
go to, bring, **follow** (watch a student from behind), code on/off and kick, plus class-wide buttons and an announcement box. The commands:

| Command | Does |
|---|---|
| `/mode MODE [name\|all]` | `adventure`, `survival`, `creative` or `spectator` for one student or everyone; `/default MODE` for new players |
| `/freeze [name\|all]`, `/unfreeze` | stop students moving and building while you talk |
| `/lock`, `/unlock` | nobody but teachers can build (by hand or by code) |
| `/code on\|off [name\|all]`, `/code name` | allow or stop building with code; see what a student typed |
| `/mute name\|all`, `/unmute`, `/chat on\|off` | one student, everyone, or all chat |
| `/history [name]` | who changed how much; a student's latest changes |
| `/undo name 5m` | **put back what that student changed** (`30s`, `2h`, a number of changes like `20`, or `all`): anything built over by someone else since is left alone |
| `/assign name N`, `/unassign name\|N` | give a plot to a name (who need not be here yet) or take it back |
| `/plotsize W [D]`, `/resize N W [D]`, `/addplot` | change plot sizes, or add a plot (see *Plot mode*) |
| `/goto N`, `/tp name`, `/bring name\|all` | go to a plot or a student; bring students to you |
| `/say text`, `/time day\|night\|noon\|sunrise\|sunset` | announce to everyone; set the time |
| `/teacher off` | stop being a teacher |

Whoever runs the server can type the same commands there (without the slash, e.g. `mode creative all`).
Students only get `/list`, `/help`, `/teacher`, `/claim`, `/home` and `/plots`.

## What is shared, and what is not

**Shared:** blocks (placed by hand or by code), where everyone is, chat, chests (when someone closes one), and **the world's own changes**: one
player's computer (the first to join) works out water, falling sand, fire, redstone, crops and TNT for everybody, and the others watch. **Animals** are
run the same way: they appear near every player, everyone sees them, and anyone can hit them (what they drop goes straight to the player who killed it).

**Not shared yet:** feeding, breeding and trading with animals, items lying on the ground, furnaces, and experience orbs. Animals only appear where the
world-running computer has the land loaded (the class world is small, so that is everywhere in practice). If that player leaves, another computer takes
over: water that was flowing stops and the animals appear afresh. The day-night clock drifts a little between computers until a teacher sets `/time`.

## How it keeps a class safe

- Only local-network addresses may connect; the server never talks to the internet.
- A room code is needed to join; the teacher PIN is kept only as a salted hash, guessing is limited, and the PIN is never written to the chat log.
- The server decides what is allowed: a student cannot place or break blocks outside their plot, in adventure mode, while frozen or while building is
  locked, even with a changed game. Code builds only inside the student's own plot. Nobody changes blocks far from where the server last saw them.
- Every message is checked (size, numbers, block and creature names); too many bad or too many messages gets a player removed.
- **Chat:** a word filter stars out words from `badwords.txt` (edit it for your class; teachers are not filtered, and teachers are told when something
  is filtered). `/chat off` and `/mute all` stop chat. What is said is written to `lanworlds/NAME.chat.log` on the **server's computer only**, for the teacher.
- Names are cleaned (letters and digits only; first names are enough); nothing a player sends is ever run as code. Code students type in the game
  runs only on their own computer, and the server only ever sees the blocks it builds.
- Teachers can mute, kick, turn building off and roll back changes at any time.

## If it will not connect

```bash
python3 doctor.py                     # checks this computer and the network
python3 doctor.py listen              # on the server's computer: waits for other computers and says who connected
python3 doctor.py reach 192.168.1.23  # on a student's computer: can I get to the server? is a class server there?
```

The usual reasons: different networks; a school network that stops computers talking to each other ("client isolation": ask your IT person);
the server computer's firewall blocked Python (on a Mac it asks the first time: choose Allow); the address or room code is wrong; or the students'
computers do not have the same mods (the game downloads `.pcmod` mods itself, but a mod written as a `.py` program has to be installed by hand).
Ports used: TCP 25570 for the game, UDP 25571 for finding servers automatically (if that does not work, give the address instead).
