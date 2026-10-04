"""The hotbar: nine slots showing pictures of blocks."""
import math
from pathlib import Path

from PIL import Image
from ursina import Button, Entity, Text, Texture, camera, color

from textures import item_icon_texture

SLOTS = 9
SLOT_SPACING = 0.075


def pretty(name):
    return name.replace('_', ' ').title()


class Hotbar:
    """The nine slots at the bottom of the screen: the first nine slots of the inventory."""

    def __init__(self, inventory):
        self.inventory = inventory
        self.root = Entity(parent=camera.ui, z=-1)
        self.frames, self.icons, self.counts, self.bar_backs, self.bars = [], [], [], [], []
        for i in range(SLOTS):
            x = (i - SLOTS // 2) * SLOT_SPACING
            self.frames.append(Entity(parent=self.root, model='quad', x=x, y=-0.44, scale=0.068,
                                      color=color.rgb32(40, 40, 40)))
            self.icons.append(Entity(parent=self.root, model='quad', x=x, y=-0.44, z=-0.01, scale=0.05,
                                     enabled=False))
            self.counts.append(Text(parent=self.root, origin=(0.5, -0.5), scale=0.75, text='',
                                    position=(x + 0.03, -0.465, -0.05)))
            self.bar_backs.append(Entity(parent=self.root, model='quad', x=x, y=-0.466, z=-0.02, scale=(0.05, 0.005),
                                         color=color.black, enabled=False))
            self.bars.append(Entity(parent=self.root, model='quad', origin=(-0.5, 0), x=x - 0.025, y=-0.466,
                                    z=-0.03, scale=(0.05, 0.005), enabled=False))
        self.label = Text(parent=self.root, origin=(0, 0), y=-0.325, scale=1)
        self._seen = (-1, -1)

    def select_number(self, number):
        """Keys 1-9 pick a slot."""
        self.inventory.select(number - 1)

    def scroll(self, direction):
        self.inventory.select(self.inventory.selected + direction)

    def update(self):
        """Redraw when the inventory changed (cheap check every frame)."""
        state = (self.inventory.version, self.inventory.selected)
        if state != self._seen:
            self._seen = state
            self.refresh()

    def refresh(self):
        selected = self.inventory.selected
        for i in range(SLOTS):
            stack = self.inventory.slots[i]
            self.icons[i].enabled = stack is not None
            self.counts[i].text = str(stack.count) if stack is not None and stack.count > 1 else ''
            if stack is not None:
                self.icons[i].texture = item_icon_texture(stack.item)
            tool = stack.item.tool if stack is not None else None
            worn = tool is not None and stack.damage > 0
            self.bar_backs[i].enabled = self.bars[i].enabled = worn
            if worn:
                left = 1 - stack.damage / tool.durability
                self.bars[i].scale_x = 0.05 * left
                self.bars[i].color = color.rgb32(int(255 * (1 - left)), int(255 * left), 0)
            chosen = i == selected
            self.frames[i].color = color.white if chosen else color.rgb32(40, 40, 40)
            self.frames[i].scale = 0.074 if chosen else 0.068
        held = self.inventory.held
        self.label.text = held.item.title if held is not None else ''


class StatusBars:
    """Hearts (survival only), air bubbles (when you are running out of breath),
    and a red flash when you get hurt."""

    ICONS = 10
    SPACING = 0.031
    SIZE = 0.028

    def __init__(self):
        self.root = Entity(parent=camera.ui, z=-1)
        left = -(SLOTS * SLOT_SPACING) / 2 + 0.012
        y = -0.352
        textures = {name: Texture(_gui(name)) for name in ('heart_container', 'heart_full', 'heart_half', 'air', 'food_empty', 'food_full', 'food_half', 'armor_empty', 'armor_full', 'armor_half')}
        self.textures = textures
        self.containers, self.fills, self.bubbles = [], [], []
        self.food_backs, self.food_fills = [], []
        self.armor_icons = []
        for i in range(self.ICONS):
            x = left + i * self.SPACING
            self.containers.append(Entity(parent=self.root, model='quad', x=x, y=y, scale=self.SIZE,
                                          texture=textures['heart_container']))
            self.fills.append(Entity(parent=self.root, model='quad', x=x, y=y, z=-0.01, scale=self.SIZE,
                                     texture=textures['heart_full']))
            fx = -left - i * self.SPACING               # food is drawn from the right edge toward the middle
            self.food_backs.append(Entity(parent=self.root, model='quad', x=fx, y=y, scale=self.SIZE,
                                          texture=textures['food_empty']))
            self.food_fills.append(Entity(parent=self.root, model='quad', x=fx, y=y, z=-0.01, scale=self.SIZE,
                                          texture=textures['food_full']))
            self.armor_icons.append(Entity(parent=self.root, model='quad', x=x, y=y + 0.032, scale=self.SIZE,
                                           texture=textures['armor_empty'], enabled=False))
            self.bubbles.append(Entity(parent=self.root, model='quad', x=-left - i * self.SPACING, y=y + 0.032,
                                       scale=self.SIZE, texture=textures['air'], enabled=False))
        self.flash_overlay = Entity(parent=camera.ui, model='quad', scale=(3, 2), z=3,
                                    color=color.rgba32(200, 0, 0, 0))
        self.flash_time = 0

    def flash(self):
        self.flash_time = 0.35

    def update(self, player, dt):
        health, air_max = player.health, player_air_max()
        for i in range(self.ICONS):
            value = health - i * 2                 # 2 or more = full heart, 1 = half, 0 or less = none
            self.fills[i].enabled = value >= 1
            self.fills[i].texture = self.textures['heart_full' if value >= 2 else 'heart_half']
        for i in range(self.ICONS):
            value = player.food - i * 2
            self.food_fills[i].enabled = value >= 1
            self.food_fills[i].texture = self.textures['food_full' if value >= 2 else 'food_half']
        for i, icon in enumerate(self.armor_icons):
            value = player.armor_points - i * 2
            icon.enabled = player.armor_points > 0
            icon.texture = self.textures['armor_full' if value >= 2 else 'armor_half' if value == 1 else 'armor_empty']
        popped = 0 if player.air >= air_max else math.ceil(player.air / air_max * self.ICONS)
        for i, bubble in enumerate(self.bubbles):
            bubble.enabled = player.air < air_max and i < popped
        self.flash_time = max(0, self.flash_time - dt)
        self.flash_overlay.color = color.rgba32(200, 0, 0, int(110 * self.flash_time / 0.35))


class DeathScreen:
    def __init__(self, on_respawn, on_quit):
        self.root = Entity(parent=camera.ui, enabled=False, z=-2)
        Entity(parent=self.root, model='quad', scale=(3, 2), color=color.rgba32(90, 0, 0, 170), z=1)
        Text('You died!', parent=self.root, origin=(0, 0), y=0.15, scale=3)
        for y, label, action in ((-0.02, 'Respawn', on_respawn), (-0.1, 'Quit game', on_quit)):
            Button(parent=self.root, text=label, y=y, scale=(.4, .06), on_click=action,
                   color=color.rgb32(80, 80, 80), highlight_color=color.rgb32(120, 120, 120))

    def show(self):
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False

    @property
    def visible(self):
        return self.root.enabled


def _gui(name):
    return Image.open(Path(__file__).parent / 'assets' / 'textures' / 'gui' / f'{name}.png').convert('RGBA')


def player_air_max():
    from player import MAX_AIR
    return MAX_AIR


class XPBar:
    """The green experience bar above the hotbar, with your level on top."""

    def __init__(self):
        from PIL import Image
        self.root = Entity(parent=camera.ui, z=-1)
        self.back = Entity(parent=self.root, model='quad', y=-0.4, scale=(0.56, 0.0125), color=color.rgb32(30, 50, 20))
        self.fill = Entity(parent=self.root, model='quad', origin=(-0.5, 0), x=-0.28, y=-0.4, z=-0.01,
                           scale=(0.0001, 0.0125), color=color.rgb32(120, 255, 40))
        self.text = Text(parent=self.root, origin=(0, 0), y=-0.384, scale=1, color=color.rgb32(130, 255, 60))
        self._shown = None

    def update(self, xp):
        if xp == self._shown:
            return
        self._shown = xp
        from xp import level_for
        level, progress = level_for(xp)
        self.fill.scale_x = max(0.0001, 0.56 * progress)
        self.text.text = str(level) if level > 0 else ''
