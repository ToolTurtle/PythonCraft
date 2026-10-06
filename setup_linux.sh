#!/usr/bin/env bash
# Set up PythonCraft on Linux Mint (and other Debian/Ubuntu based Linux).
#
#   ./setup_linux.sh               install what is needed, with a question before anything needs your password
#   ./setup_linux.sh --yes         do not ask
#   ./setup_linux.sh --no-apt      skip the system packages (you installed python3-venv, python3-tk, xclip, libopenal1 yourself)
#   ./setup_linux.sh --desktop     also put a PythonCraft icon in your applications menu
#   ./setup_linux.sh --wheels DIR  install the Python packages from a folder of downloaded files (no internet needed; see docs/INSTALL.md)
#   ./setup_linux.sh --dry-run     only say what would be done
#
# It makes a private Python environment in .venv (nothing is installed into your system Python), then checks everything with doctor.py.
set -euo pipefail
cd "$(dirname "$0")"

YES=0; APT=1; DESKTOP=0; DRY=0; WHEELS=""
while [ $# -gt 0 ]; do
  arg="$1"; shift
  case "$arg" in
    --yes|-y) YES=1 ;;
    --no-apt) APT=0 ;;
    --desktop) DESKTOP=1 ;;
    --dry-run) DRY=1 ;;
    --wheels) [ $# -gt 0 ] || { echo "--wheels needs a folder"; exit 2; }; WHEELS="$1"; shift ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "I do not know the option $arg (try --help)"; exit 2 ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then echo "   would run: $*"; else "$@"; fi; }

say "1. Python"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed. Install it with:  sudo apt install python3"; exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "This needs Python 3.10 or newer; you have $(python3 --version 2>&1)."; exit 1
fi
echo "   $(python3 --version)"

PACKAGES="python3-venv python3-pip python3-tk xclip libopenal1 mesa-utils"
if [ "$APT" = 1 ] && command -v apt-get >/dev/null 2>&1; then
  say "2. System packages: $PACKAGES"
  echo "   (python3-venv: private environments, python3-tk: the launcher and painter windows, xclip: copy and paste,"
  echo "    libopenal1: sound, mesa-utils: lets doctor.py check your graphics)"
  if [ "$YES" = 0 ] && [ "$DRY" = 0 ]; then
    read -r -p "   Install them now with sudo apt-get? [Y/n] " answer
    case "${answer:-y}" in [Nn]*) APT=0 ;; esac
  fi
  if [ "$APT" = 1 ]; then
    run sudo apt-get update
    run sudo apt-get install -y $PACKAGES
  else
    echo "   skipped"
  fi
else
  say "2. System packages: skipped"
fi

say "3. A private Python environment (.venv) with the game's packages"
if [ ! -x .venv/bin/python ]; then
  run python3 -m venv .venv
fi
if [ -n "$WHEELS" ]; then
  echo "   (offline: using the files in $WHEELS)"
  run .venv/bin/pip install --no-index --find-links "$WHEELS" -r requirements.txt
else
  run .venv/bin/pip install --upgrade pip
  run .venv/bin/pip install -r requirements.txt
fi

say "4. The pictures and sounds (assets/)"
if [ -d assets/textures ] && [ -n "$(ls -A assets/textures 2>/dev/null)" ]; then
  echo "   found"
else
  echo "   MISSING: the folder assets/ is not part of the shared code (it comes from Minecraft)."
  echo "   Copy the whole assets folder from a computer where PythonCraft works, into $(pwd)/assets"
fi

if [ "$DESKTOP" = 1 ]; then
  say "5. An icon in the applications menu"
  target="$HOME/.local/share/applications/pythoncraft.desktop"
  if [ "$DRY" = 1 ]; then
    echo "   would write $target"
  else
    mkdir -p "$(dirname "$target")"
    cat > "$target" <<DESKTOP_FILE
[Desktop Entry]
Type=Application
Name=PythonCraft
Comment=Build with blocks and with code
Exec=$(pwd)/pythoncraft.sh
Path=$(pwd)
Terminal=false
Categories=Game;Education;
DESKTOP_FILE
    echo "   wrote $target"
  fi
fi

say "Checking everything (doctor.py)"
if [ "$DRY" = 1 ]; then
  echo "   would run: .venv/bin/python doctor.py"
else
  .venv/bin/python doctor.py || true
fi
printf '\nDone. Start with:  ./pythoncraft.sh\n'
