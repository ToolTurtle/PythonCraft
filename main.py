"""PythonCraft - run with:  python3 main.py"""
import atexit
from pathlib import Path

import ursina
from ursina import Ursina, color, window

import savegame
from mac_fix import clear_leftover_shaders, fix_shaders, fix_ui_scale
from title import TitleScreen

fix_shaders()  # only does anything on macOS

# Ursina's own icon file, so it is found no matter where the game is run from.
ICON = Path(ursina.__file__).parent / 'textures' / 'ursina.ico'
app = Ursina(title='PythonCraft', icon=str(ICON))
clear_leftover_shaders()
window.color = color.rgb32(135, 206, 235)
window.fps_counter.enabled = False
window.entity_counter.enabled = False
window.collider_counter.enabled = False
window.exit_button.enabled = False
window.cog_button.enabled = False

import mods                        # your own blocks and creatures: every file in the mods/ folder (see docs/README_mods.md)
loaded_mods = mods.load_folder()
if loaded_mods:
    print('Mods loaded:', ', '.join(loaded_mods))
from game import Game

game = None            # the running game (None while we are on the title screen)
pending = []           # things to do next frame (so the "Loading..." message can appear first)


def open_world(folder):
    title.show_loading()

    def start():
        global game
        level, modified, facing, flowing = savegame.load(folder)
        dims = savegame.load_dims(folder)
        title.hide()
        game = Game(folder, level['name'], seed=level['seed'], level=level, modified=modified, facing=facing, flowing=flowing, dims=dims)
        game.mods = mods.ModRuntime(game)

    pending.append(start)


def create_world(name, seed, mode):
    title.show_loading()

    def start():
        global game
        folder = savegame.new_folder(name)
        title.hide()
        game = Game(folder, name, seed=seed, mode=mode)
        game.mods = mods.ModRuntime(game)
        game.save()

    pending.append(start)


title = TitleScreen(on_open=open_world, on_create=create_world)


def save_on_exit():
    """Safety net: if the window is closed, still keep the game."""
    try:
        if game is not None:
            game.save()
    except Exception as error:      # (the window may already be gone)
        print('could not save on exit:', error)


atexit.register(save_on_exit)


def input(key):
    if game is not None:
        game.input(key)
    else:
        title.input(key)


def update():
    fix_ui_scale()
    if pending:
        pending.pop(0)()
        return
    if game is not None:
        game.update()
        game.mods.update(ursina.time.dt)


app.run()
