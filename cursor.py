"""Hiding the mouse cursor while playing.

Panda3D's "hide cursor" setting is sometimes ignored on macOS, so as well as
hiding it we swap in a fully transparent cursor image.

We send a small WindowProperties holding ONLY the cursor settings. Re-sending
Ursina's whole `window` object also re-applies the icon, size and position,
which can make the screen flash blank on macOS."""
from pathlib import Path
from panda3d.core import Filename, WindowProperties

BLANK_CURSOR = Path(__file__).parent / 'assets' / 'blank_cursor.png'


def set_hidden(hidden):
    from ursina import application
    if not application.base:
        return
    props = WindowProperties()
    props.set_cursor_hidden(hidden)
    props.set_cursor_filename(Filename.from_os_specific(str(BLANK_CURSOR)) if hidden else Filename())
    application.base.win.requestProperties(props)
