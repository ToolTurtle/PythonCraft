"""Sound effects and music.

Sound files live in assets/sounds. A "group" is all the files whose names start
with the same word, e.g. 'step/grass' means step/grass1.ogg, step/grass2.ogg ...
Playing a group picks one of them at random, so footsteps don't sound identical."""
import random
from pathlib import Path

from panda3d.core import AudioSound, Filename
from ursina import application, time

SOUND_DIR = Path(__file__).parent / 'assets' / 'sounds'

# What a block sounds like when you walk on it, break it or place it
MATERIAL = {'soul_sand': 'sand', 'netherrack': 'stone', 
    'grass': 'grass', 'grass_snow': 'snow', 'oak_leaves': 'grass',
    'dirt': 'gravel', 'gravel': 'gravel',
    'sand': 'sand',
    'snow': 'snow',
    'oak_log': 'wood', 'oak_planks': 'wood',
    'cactus': 'cloth',
    'glass': 'glass',
}   # everything else (stone, ores, bricks, ...) sounds like stone

MUSIC_PAUSE = (45, 120)   # seconds of quiet between songs


def _load(path):
    """Load a sound file (.ogg or .wav) with Panda3D's own loader."""
    return application.base.loader.loadSfx(Filename.from_os_specific(str(path)))


def material_of(block_name):
    return MATERIAL.get(block_name, 'stone')


class Sound:
    def __init__(self):
        self.volume = 0.7            # sound effects, 0 to 1
        self.music_volume = 0.25
        self._variants = {}          # group -> list of file paths
        self._clips = {}             # path -> sound clip (loaded once, played many times)
        self._music = None
        self._music_wait = random.uniform(5, 15)    # the first song starts soon after the game does

    # ---- sound effects ---------------------------------------------------

    def _files(self, group):
        if group not in self._variants:
            folder, _, prefix = group.rpartition('/')
            self._variants[group] = sorted((SOUND_DIR / folder).glob(f'{prefix}*.ogg'))
        return self._variants[group]

    def has(self, group):
        """Do we have any sound files for this group?"""
        return bool(self._files(group))

    def play(self, group, volume=1.0, pitch_variation=0.08):
        """Play a random sound from the group. `volume` is 0 to 1 (before the volume setting)."""
        files = self._files(group)
        if not files or volume <= 0.01:
            return
        path = random.choice(files)
        if path not in self._clips:
            self._clips[path] = _load(path)
        clip = self._clips[path]
        clip.setVolume(min(1.0, volume * self.volume))
        clip.setPlayRate(1 + random.uniform(-pitch_variation, pitch_variation))
        clip.play()

    # ---- music -----------------------------------------------------------

    def update(self):
        """Call every frame: starts a song now and then, with quiet gaps between."""
        if self._music is not None and self._music.status() == AudioSound.PLAYING:
            return
        self._music = None
        self._music_wait -= time.dt
        if self._music_wait <= 0:
            songs = sorted((SOUND_DIR / 'music').glob('*.ogg'))
            if songs:
                self._music = _load(random.choice(songs))
                self._music.setVolume(self.music_volume)
                self._music.play()
            self._music_wait = random.uniform(*MUSIC_PAUSE)

    def set_music_volume(self, value):
        self.music_volume = value
        if self._music is not None:
            self._music.setVolume(value)


def distance_volume(distance, reach=20):
    """Quieter the farther away: 1 right next to you, 0 at `reach` blocks."""
    return max(0.0, 1 - distance / reach) ** 1.5
