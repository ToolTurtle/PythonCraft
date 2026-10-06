#!/usr/bin/env bash
# Start PythonCraft things on Linux (and Mac) without remembering the python command.
#   ./pythoncraft.sh              the launcher window (everything in one place)
#   ./pythoncraft.sh play         the game on your own           ./pythoncraft.sh live    live coding
#   ./pythoncraft.sh host [...]   start a class server           ./pythoncraft.sh join [...]   join a class
#   ./pythoncraft.sh class        the teacher's class tool       ./pythoncraft.sh paint FILE.png
#   ./pythoncraft.sh doctor       check the setup and the network     ./pythoncraft.sh test   run the tests
#   ./pythoncraft.sh SCRIPT.py [...]   any other script in this folder
cd "$(dirname "$0")" || exit 1
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
what="${1:-launcher}"
[ $# -gt 0 ] && shift
case "$what" in
  launcher) exec "$PY" launcher.py "$@" ;;
  play)     exec "$PY" main.py "$@" ;;
  live)     exec "$PY" livecode.py "$@" ;;
  host)     exec "$PY" lan.py host "$@" ;;
  join)     exec "$PY" lan.py join "$@" ;;
  class)    exec "$PY" classtool.py "$@" ;;
  paint)    exec "$PY" painter.py "$@" ;;
  doctor)   exec "$PY" doctor.py "$@" ;;
  test)     exec "$PY" run_tests.py "$@" ;;
  *.py)     exec "$PY" "$what" "$@" ;;
  *)        sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
