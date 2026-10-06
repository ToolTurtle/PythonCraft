# Installing PythonCraft

PythonCraft is Python code plus a folder of pictures and sounds. It runs on a Mac and on Linux (Linux Mint and other Debian/Ubuntu based
systems). **Windows is untested.** You need Python 3.10 or newer, the packages in `requirements.txt`, and the `assets/` folder.

> **The `assets/` folder is not in the shared code.** The block pictures and sounds come from Minecraft and belong to Mojang/Microsoft
> (see NOTICE). Copy the whole `assets/` folder from a computer where PythonCraft already works into the PythonCraft folder on every new computer.

## Linux Mint

```bash
cd PythonCraft
./setup_linux.sh --desktop          # asks before using sudo; --yes does not ask, --no-apt skips the system packages
./pythoncraft.sh                    # the launcher window
```

The script installs `python3-venv python3-pip python3-tk xclip libopenal1 mesa-utils` with apt (venv: a private Python environment; tk: the
launcher, painter and class tool windows; xclip: copy and paste; libopenal1: sound; mesa-utils: lets the check test your graphics), makes a private
environment in `.venv`, installs the game's Python packages into it (nothing goes into your system Python), and runs the check (`doctor.py`).
`--desktop` adds a PythonCraft icon to the applications menu.

`./pythoncraft.sh` is a short way to start things: `./pythoncraft.sh play`, `live`, `host`, `join`, `class`, `paint FILE.png`, `doctor`, `test`
(or any script name). It uses the private environment automatically.

Linux Mint 21 has Python 3.10 and Mint 22 has 3.12; both work. If the game window opens but the mouse does not turn the camera, you are probably on a
Wayland session: log out and choose an X11 session (Mint Cinnamon uses X11 by default). Graphics older than OpenGL 3.1 will not work; on a virtual
machine the game runs but slowly.

### No internet at school? Install from a folder

On any computer with internet (the same kind of system and Python version as the school's):

```bash
mkdir wheels && python3 -m pip download -r requirements.txt -d wheels
```

Copy the `wheels` folder next to `setup_linux.sh` (a USB stick will do), then on each school computer:

```bash
./setup_linux.sh --wheels wheels
```

### Setting up a whole class of computers

1. Set up one computer, check it with `./pythoncraft.sh doctor`, and run `./pythoncraft.sh test` once.
2. Copy the PythonCraft folder (with `assets/`) to the others, **without** the `.venv` folder (it only works on the computer that made it), and run
   `./setup_linux.sh` on each.
3. The teacher's computer, if it hosts the class, must allow connections in: `sudo ufw allow 25570/tcp && sudo ufw allow 25571/udp`
   (only needed if the firewall is on: `sudo ufw status`). Then see [README_lan.md](README_lan.md).
4. On a student computer that cannot join: `./pythoncraft.sh doctor reach ADDRESS`, and on the teacher's: `./pythoncraft.sh doctor listen`.

## Mac

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python launcher.py          # or ./pythoncraft.sh
```

(Or install the packages with `pip3 install` into your own Python.) For the launcher, painter and class tool windows you need Tk: it comes with the
python.org installer; with Homebrew Python run `brew install python-tk`. The first time a class is hosted, the Mac asks whether Python may accept
connections: choose Allow.

## Checking it works

```bash
./pythoncraft.sh doctor      # Python, packages, pictures and sounds, mods, saves, network (and, on Linux, screen, graphics, sound, firewall)
./pythoncraft.sh test        # the test suite (a few of the tests open game windows for a few seconds; PYCRAFT_NO_WINDOW=1 skips those)
```

## What has been checked, and what has not

Checked from a Mac: all the code runs on a case-sensitive file system (like Linux's), every file is valid Python 3.10, the shell scripts are valid
and their dry runs do what they say, and the Linux-only checks in `doctor.py` are tested with pretend Linux systems. **Not yet checked on a real Linux
computer:** installing the packages with apt and pip there, the game's graphics and mouse on Linux, sound, and the class games between a Linux and a
Mac computer. If something does not work, `doctor.py` is the first thing to run, and the output of `./pythoncraft.sh doctor` is what to send back.
