"""The inventory screens: your pockets, the crafting table, the furnace, and the creative menu.

Clicking works like Minecraft:
  left click    pick up a whole stack / put it down / swap / merge
  right click   pick up half / put down one
  shift + click move a stack to the other part of the inventory (or craft as many as possible)
  click outside throw the stack on the ground
  E or Esc      close"""
import time as pytime

from ursina import Button, Entity, Text, camera, color, held_keys, mouse

import crafting
import cursor
from furnace import FUEL, INPUT, OUTPUT
from inventory import ARMOR_SLOTS, HOTBAR_SIZE, Stack
from items import CREATIVE_ORDER, ITEMS
from textures import item_icon_texture

SLOT = 0.056
STEP = 0.06
SLOT_COLOR = color.rgb32(100, 100, 100)
SLOT_HOVER = color.rgb32(150, 150, 150)
SLOT_DRAG = color.rgb32(120, 150, 210)
PANEL_COLOR = color.rgb32(55, 55, 55)


class SlotView(Entity):
    """One square that shows (and lets you click) a stack."""

    def __init__(self, screen, kind, getter, x, y, models=None, index=None, size=SLOT):
        super().__init__(parent=screen.root, model='quad', position=(x, y, 0), scale=size,
                         color=SLOT_COLOR, collider='box')
        self.kind = kind              # 'normal', 'crafting_output', 'furnace_output' or 'palette'
        self.getter = getter
        self.models = models          # the list of stacks this slot is part of (for 'normal' slots)
        self.index = index
        self.icon = Entity(parent=self, model='quad', scale=0.78, z=-0.01, enabled=False)
        self.bar_back = Entity(parent=self, model='quad', scale=(0.8, 0.08), y=-0.4, z=-0.02,
                               color=color.black, enabled=False)
        self.bar = Entity(parent=self, model='quad', scale=(0.8, 0.08), origin=(-0.5, 0), x=-0.4, y=-0.4,
                          z=-0.03, enabled=False)
        self.count_text = Text(parent=screen.root, origin=(0.5, -0.5), scale=0.75, text='',
                               position=(x + size * 0.47, y - size * 0.47, -0.05))
        self._shown = object()

    def refresh(self):
        stack = self.getter()
        key = None if stack is None else (stack.name, stack.count, stack.damage)
        if key != self._shown:
            self._shown = key
            self.icon.enabled = stack is not None
            if stack is not None:
                self.icon.texture = item_icon_texture(stack.item)
            self.count_text.text = str(stack.count) if stack is not None and stack.count > 1 else ''
            tool = stack.item.tool if stack is not None else None
            worn = tool is not None and stack.damage > 0
            self.bar_back.enabled = self.bar.enabled = worn
            if worn:
                left = 1 - stack.damage / tool.durability
                self.bar.scale_x = 0.8 * left
                self.bar.color = color.rgb32(int(255 * (1 - left)), int(255 * left), 0)


class Screen:
    """A window on the screen: a panel with slots in it. Subclasses fill it in."""

    def __init__(self, ui, title, size, center_y=0.0):
        self.ui = ui
        self.root = Entity(parent=camera.ui, enabled=False, z=-3)
        Entity(parent=self.root, model='quad', scale=(3, 2), color=color.rgba32(0, 0, 0, 120), z=1)
        self.panel = Entity(parent=self.root, model='quad', scale=size, y=center_y, color=PANEL_COLOR, z=0.5,
                            collider='box')
        Text(title, parent=self.root, origin=(-0.5, 0), position=(-size[0] / 2 + 0.03, center_y + size[1] / 2 - 0.04),
             scale=1.1)
        self.views = []

    def slot(self, models, index, x, y):
        view = SlotView(self, 'normal', lambda: models[index], x, y, models, index)
        self.views.append(view)
        return view

    def player_inventory(self, y_main, y_hotbar):
        for row in range(3):
            for col in range(9):
                self.slot(self.ui.inventory.slots, HOTBAR_SIZE + row * 9 + col, (col - 4) * STEP, y_main - row * STEP)
        for col in range(9):
            self.slot(self.ui.inventory.slots, col, (col - 4) * STEP, y_hotbar)

    def refresh(self):
        for view in self.views:
            view.refresh()

    def leftovers(self):
        """Stacks that must go back to the player when the window closes."""
        return []


class CraftingScreen(Screen):
    """The 2x2 crafting grid in your inventory, or the 3x3 one at a crafting table."""

    def __init__(self, ui, size):
        self.size = size
        panel, center = ((0.62, 0.62), 0.10) if size == 2 else ((0.62, 0.64), 0.06)       # (your own inventory is taller: it holds the armor)
        super().__init__(ui, 'Crafting', panel, center)
        self.cells = [None] * (size * size)
        top = 0.25 if size == 2 else 0.26
        for i in range(size * size):
            col, row = i % size, i // size
            self.slot(self.cells, i, -0.12 + (col - (size - 1) / 2) * STEP, top - row * STEP)
        arrow = Text('>', parent=self.root, origin=(0, 0), position=(0.03, top - (size - 1) / 2 * STEP), scale=2)
        out_y = top - (size - 1) / 2 * STEP
        if size == 2:                                     # your own inventory also shows what you are wearing
            for i in range(4):
                self.slot(ui.inventory.armor, i, -0.255, 0.30 - i * STEP)      # (between the title and the inventory rows)
        self.output = SlotView(self, 'crafting_output', self.result, 0.14, out_y, size=SLOT * 1.15)
        self.views.append(self.output)
        y_main = 0.045 if size == 2 else out_y - 0.15
        self.player_inventory(y_main=y_main, y_hotbar=y_main - 3 * STEP - 0.015)

    def result(self):
        recipe = crafting.find([c.name if c else None for c in self.cells], self.size, self.size)
        return Stack(recipe[0], recipe[1]) if recipe else None

    def consume_ingredients(self):
        for i, stack in enumerate(self.cells):
            if stack is not None:
                stack.count -= 1
                if stack.count <= 0:
                    self.cells[i] = None

    def leftovers(self):
        stacks = [s for s in self.cells if s is not None]
        self.cells[:] = [None] * len(self.cells)
        return stacks


class FurnaceScreen(Screen):
    def __init__(self, ui, furnace):
        super().__init__(ui, 'Furnace', (0.62, 0.62), 0.02)
        self.furnace = furnace
        self.slot(furnace.slots, INPUT, -0.1, 0.24)
        self.slot(furnace.slots, FUEL, -0.1, 0.1)
        output = SlotView(self, 'furnace_output', lambda: furnace.slots[OUTPUT], 0.12, 0.17, size=SLOT * 1.2)
        self.views.append(output)
        self.flame = Entity(parent=self.root, model='quad', scale=(0.03, 0.04), origin=(0, -0.5), x=-0.1, y=0.145,
                            color=color.orange)
        self.arrow_back = Entity(parent=self.root, model='quad', scale=(0.1, 0.02), x=0.01, y=0.17,
                                 color=color.rgb32(30, 30, 30))
        self.arrow = Entity(parent=self.root, model='quad', scale=(0.1, 0.02), origin=(-0.5, 0), x=-0.04, y=0.17,
                            z=-0.01, color=color.white)
        self.player_inventory(y_main=-0.03, y_hotbar=-0.03 - 3 * STEP - 0.015)

    def refresh(self):
        super().refresh()
        f = self.furnace
        self.flame.scale_y = 0.04 * (f.burn_left / f.burn_total if f.lit else 0)
        self.arrow.scale_x = 0.1 * min(1.0, f.progress / crafting.COOK_TIME)

    def leftovers(self):
        return []        # the furnace keeps its contents


class ChestScreen(Screen):
    def __init__(self, ui, contents):
        super().__init__(ui, 'Chest', (0.62, 0.76), 0.0)
        for row in range(3):
            for col in range(9):
                self.slot(contents, row * 9 + col, (col - 4) * STEP, 0.2 - row * STEP)
        self.player_inventory(y_main=-0.05, y_hotbar=-0.05 - 3 * STEP - 0.015)

    def leftovers(self):
        return []


class TradeScreen(Screen):
    """Trade with a villager: click an offer to swap your items for theirs."""

    def __init__(self, ui, villager):
        import random as _r
        from mobtypes import PROFESSIONS
        super().__init__(ui, 'Villager', (0.62, 0.62), 0.0)
        if villager.offers is None:
            villager.profession = _r.choice(list(PROFESSIONS))
            villager.offers = [[p] + list(offer) for p in [villager.profession] for offer in PROFESSIONS[p]]
        self.villager = villager
        self.rows = []
        profession = villager.offers[0][0]
        Text(profession, parent=self.root, origin=(0, 0), y=0.24, scale=1.2)
        for i, offer in enumerate(villager.offers):
            _, give, give_n, get, get_n = offer
            row = Button(parent=self.root, text='', y=0.14 - i * 0.085, scale=(0.5, 0.06), color=color.rgb32(80, 80, 80),
                         highlight_color=color.rgb32(120, 120, 120),
                         on_click=lambda o=offer: self.buy(o))
            Entity(parent=self.root, model='quad', texture=item_icon_texture(ITEMS[give]), x=-0.2, y=0.14 - i * 0.085, z=-0.1, scale=0.045)
            Text(f'{give_n}  ->  {get_n}', parent=self.root, origin=(0, 0), x=0.0, y=0.14 - i * 0.085, z=-0.1, scale=1)
            Entity(parent=self.root, model='quad', texture=item_icon_texture(ITEMS[get]), x=0.2, y=0.14 - i * 0.085, z=-0.1, scale=0.045)
            self.rows.append(row)
        self.status = Text('Click an offer to trade', parent=self.root, origin=(0, 0), y=-0.2, scale=1)
        self.player_inventory(y_main=-0.3, y_hotbar=-0.3 - 3 * STEP - 0.015)

    def buy(self, offer):
        _, give, give_n, get, get_n = offer
        inv = self.ui.inventory
        if inv.count(give) < give_n:
            self.status.text = f'You need {give_n} {ITEMS[give].title}'
            return
        need = give_n
        for i, s in enumerate(inv.slots):
            if s is not None and s.name == give and need > 0:
                take = min(s.count, need)
                s.count -= take
                need -= take
                if s.count <= 0:
                    inv.slots[i] = None
        left = inv.add(get, get_n)
        if left:
            self.ui.throw(Stack(get, left))
        inv.changed()
        self.status.text = f'Traded for {get_n} {ITEMS[get].title}!'
        self.ui.sound.play('random/orb', 0.5)


class EnchantScreen(Screen):
    """Put an item and some lapis lazuli in, then pick one of three enchantments."""

    def __init__(self, ui, table):
        super().__init__(ui, 'Enchant', (0.62, 0.74), 0.0)
        import random
        self.table = table
        self.rng = random.Random()
        self.cells = [None, None]                        # the item, and the lapis
        self.shelves = self._count_shelves(ui.world, table)
        self.slot(self.cells, 0, -0.18, 0.2)
        self.slot(self.cells, 1, -0.18, 0.12)
        Text(f'Bookshelves: {self.shelves}', parent=self.root, origin=(-0.5, 0), x=-0.27, y=0.28, scale=0.9)
        base = self.rng.randint(1, 8) + self.shelves // 2 + self.rng.randint(0, self.shelves)
        self.powers = [max(1, base // 3), max(2, base * 2 // 3 + 1), max(3, base)]
        self.buttons = []
        for i in range(3):
            b = Button(parent=self.root, text='', x=0.1, y=0.22 - i * 0.075, scale=(0.32, 0.06),
                       color=color.rgb32(80, 80, 80), highlight_color=color.rgb32(120, 120, 120),
                       on_click=lambda i=i: self.enchant(i))
            self.buttons.append(b)
        self.status = Text('Put in an item and lapis lazuli', parent=self.root, origin=(0, 0), y=-0.02, scale=0.9)
        self.player_inventory(y_main=-0.12, y_hotbar=-0.12 - 3 * STEP - 0.015)

    @staticmethod
    def _count_shelves(world, table):
        n = 0
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                if max(abs(dx), abs(dz)) == 2:
                    for dy in (0, 1):
                        if world.get((table[0] + dx, table[1] + dy, table[2] + dz)) == 'bookshelf':
                            n += 1
        return min(15, n)

    def refresh(self):
        super().refresh()
        from enchantments import category
        item = self.cells[0]
        ok = item is not None and category(item.item) is not None and not item.enchants
        lapis = self.cells[1].count if self.cells[1] is not None and self.cells[1].name == 'lapis_lazuli' else 0
        level = self.ui.player_level()
        for i, button in enumerate(self.buttons):
            button.text = f'Level {self.powers[i]}   (cost {i + 1})' if ok else '---'
            button.enabled = True
            button.color = color.rgb32(80, 110, 80) if ok and lapis >= i + 1 and level >= self.powers[i] else color.rgb32(70, 70, 70)

    def enchant(self, i):
        from enchantments import category, describe, roll
        item = self.cells[0]
        if item is None or category(item.item) is None:
            self.status.text = 'Nothing to enchant here'
            return
        if item.enchants:
            self.status.text = 'Already enchanted'
            return
        lapis = self.cells[1]
        if lapis is None or lapis.name != 'lapis_lazuli' or lapis.count < i + 1:
            self.status.text = f'You need {i + 1} lapis lazuli'
            return
        power = self.powers[i]
        if self.ui.player_level() < power:
            self.status.text = f'You need level {power}'
            return
        item.enchants = roll(item, power, self.rng)
        lapis.count -= i + 1
        if lapis.count <= 0:
            self.cells[1] = None
        self.ui.spend_levels(i + 1)
        self.status.text = ', '.join(describe(item.enchants)) or 'The enchanting failed'
        self.ui.sound.play('random/enchant', 0.6)
        base = self.rng.randint(1, 8) + self.shelves // 2 + self.rng.randint(0, self.shelves)
        self.powers = [max(1, base // 3), max(2, base * 2 // 3 + 1), max(3, base)]
        self.ui.inventory.changed()

    def leftovers(self):
        stacks = [s for s in self.cells if s is not None]
        self.cells[:] = [None, None]
        return stacks


class CreativeScreen(Screen):
    """Every item in the game: click one to take a stack of it."""
    PER_PAGE = 45

    def __init__(self, ui):
        super().__init__(ui, 'Creative Inventory', (0.62, 0.8))
        self.page = 0
        self.names = [n for n in CREATIVE_ORDER if n in ITEMS]
        self.cells = [None] * self.PER_PAGE
        for i in range(self.PER_PAGE):
            col, row = i % 9, i // 9
            view = SlotView(self, 'palette', (lambda i=i: self.cells[i]), (col - 4) * STEP, 0.25 - row * STEP,
                            models=self.cells, index=i)
            self.views.append(view)
        for col in range(9):
            self.slot(self.ui.inventory.slots, col, (col - 4) * STEP, -0.2)
        self.prev = Button(parent=self.root, text='Prev', scale=(0.08, 0.04), x=-0.14, y=-0.3, on_click=lambda: self.turn(-1),
                           color=color.rgb32(80, 80, 80))
        self.next = Button(parent=self.root, text='Next', scale=(0.08, 0.04), x=0.14, y=-0.3, on_click=lambda: self.turn(1),
                           color=color.rgb32(80, 80, 80))
        self.page_text = Text('', parent=self.root, origin=(0, 0), y=-0.3, scale=1)
        self.fill()

    def pages(self):
        return (len(self.names) + self.PER_PAGE - 1) // self.PER_PAGE

    def turn(self, direction):
        self.page = (self.page + direction) % self.pages()
        self.fill()

    def fill(self):
        start = self.page * self.PER_PAGE
        for i in range(self.PER_PAGE):
            name = self.names[start + i] if start + i < len(self.names) else None
            self.cells[i] = Stack(name) if name else None
        self.page_text.text = f'{self.page + 1}/{self.pages()}'


class InventoryUI:
    def __init__(self, inventory, player, world, dropped, sound):
        self.inventory, self.player, self.world, self.dropped, self.sound = inventory, player, world, dropped, sound
        self.screen = None
        self.held = None                  # the stack stuck to the mouse pointer
        self.closed_at = 0
        self.hover_view = None
        self.drag_button = None           # 'left' or 'right' while spreading a stack over several slots
        self.drag_views = []

        self.held_icon = Entity(parent=camera.ui, model='quad', scale=SLOT * 0.85, z=-9, enabled=False)
        self.held_count = Text(parent=camera.ui, origin=(0.5, -0.5), scale=0.75, z=-9.5, enabled=False)
        self.tooltip = Text(parent=camera.ui, origin=(-0.5, -0.5), scale=0.9, z=-9.5, enabled=False,
                            background=True)

    @property
    def active(self):
        return self.screen is not None

    def just_closed(self):
        return pytime.time() - self.closed_at < 0.2

    # ---- opening and closing ---------------------------------------------

    def open_inventory(self):
        self._open(CreativeScreen(self) if self.player.mode == 'creative' else CraftingScreen(self, 2))

    def open_table(self):
        self._open(CraftingScreen(self, 3))

    def open_furnace(self, position):
        if position not in self.world.furnaces:                 # (a furnace nobody has opened yet)
            from furnace import Furnace
            self.world.furnaces[position] = Furnace()
        self._open(FurnaceScreen(self, self.world.furnaces[position]))

    def open_trade(self, villager):
        self._open(TradeScreen(self, villager))

    def open_enchant(self, position):
        self._open(EnchantScreen(self, position))

    def player_level(self):
        from xp import level_for
        return level_for(self.player.xp)[0]

    def spend_levels(self, levels):
        """Enchanting costs levels: you drop that many levels but keep the progress toward the next one."""
        from xp import level_for, points_for_level
        level, progress = level_for(self.player.xp)
        new = max(0, level - levels)
        self.player.xp = points_for_level(new) + progress * (points_for_level(new + 1) - points_for_level(new))

    def open_chest(self, position):
        if position not in self.world.chests:
            self.world.chests[position] = [None] * 27
        self._open(ChestScreen(self, self.world.chests[position]))
        self.sound.play('block/chest_open', 0.6)

    def _open(self, screen):
        self.screen = screen
        screen.root.enabled = True
        self.player.enabled = False
        mouse.locked = False
        cursor.set_hidden(False)
        if not isinstance(screen, ChestScreen):
            self.sound.play('random/click', 0.4)

    def close(self):
        if self.screen is None:
            return
        self.drag_button, self.drag_views = None, []
        # Whatever is still in the crafting grid or on the mouse goes back to the player
        for stack in self.screen.leftovers() + ([self.held] if self.held else []):
            if self.player.mode == 'creative' and stack is self.held:
                continue
            self._give(stack)
        self.held = None
        from ursina import destroy
        if isinstance(self.screen, ChestScreen):
            self.sound.play('block/chest_close', 0.6)
        destroy(self.screen.root)
        self.screen = None
        self.held_icon.enabled = self.held_count.enabled = self.tooltip.enabled = False
        self.player.enabled = True
        mouse.locked = True
        cursor.set_hidden(True)
        self.closed_at = pytime.time()
        self.inventory.changed()

    def _give(self, stack):
        """Put a stack in the inventory; throw whatever does not fit on the ground."""
        left = self.inventory.add_stack(stack)
        if left > 0:
            self.throw(Stack(stack.name, left, stack.damage))

    def throw(self, stack):
        from ursina import Vec3
        forward = self.player.forward
        self.dropped.drop(stack, self.player.position + Vec3(0, 1.4, 0),
                          Vec3(forward[0] * 4, 0, forward[2] * 4))

    # ---- every frame -----------------------------------------------------

    def update(self):
        if self.screen is None:
            return
        self.screen.refresh()

        hovered = mouse.hovered_entity
        self.hover_view = hovered if isinstance(hovered, SlotView) else None
        if self.drag_button is not None:
            self.extend_drag(self.hover_view)
        for view in self.screen.views:
            if view in self.drag_views:
                view.color = SLOT_DRAG
            else:
                view.color = SLOT_HOVER if view is self.hover_view else SLOT_COLOR

        if self.held:
            self.held_icon.enabled = True
            self.held_icon.texture = item_icon_texture(self.held.item)
            self.held_icon.position = (mouse.x, mouse.y)
            self.held_count.enabled = self.held.count > 1
            self.held_count.text = str(self.held.count)
            self.held_count.position = (mouse.x + SLOT * 0.4, mouse.y - SLOT * 0.4)
        else:
            self.held_icon.enabled = self.held_count.enabled = False

        stack = self.hover_view.getter() if self.hover_view and not self.held else None
        self.tooltip.enabled = stack is not None
        if stack is not None:
            from enchantments import describe
            self.tooltip.text = '\n'.join([stack.item.title] + describe(stack.enchants))
            self.tooltip.position = (mouse.x + 0.02, mouse.y + 0.02)

    # ---- clicks ----------------------------------------------------------

    def input(self, key):
        if key in ('e', 'escape', 'tab'):
            self.close()
        elif key in ('left mouse down', 'right mouse down'):
            view = self.hover_view
            button = 'left' if key == 'left mouse down' else 'right'
            if view is not None:
                if self.held is not None and not held_keys['left shift'] and self._can_drag_into(view):
                    self.begin_drag(view, button)       # maybe a drag; we find out when the button is released
                else:
                    self.click(view, button, held_keys['left shift'])
            elif mouse.hovered_entity is not self.screen.panel and self.held:      # clicked outside the window
                if self.player.mode != 'creative':
                    self.throw(self.held)
                self.held = None
        elif key in ('left mouse up', 'right mouse up'):
            if self.drag_button == ('left' if key == 'left mouse up' else 'right'):
                self.finish_drag()
        elif key in ('scroll up', 'scroll down') and isinstance(self.screen, CreativeScreen):
            self.screen.turn(-1 if key == 'scroll up' else 1)

    # ---- spreading a stack over several slots ------------------------------
    #
    # Hold a stack, then press a mouse button on a slot and drag over more slots:
    #   right button  puts ONE item into every slot you drag over
    #   left button   shares the stack out evenly between them
    # If you only touched one slot, it is just a normal click.

    def _can_drag_into(self, view):
        if view.kind != 'normal' or self.held is None or self.held.max_stack == 1:
            return False
        slot = view.models[view.index]
        return slot is None or (slot.same_kind_as(self.held) and slot.count < slot.max_stack)

    def begin_drag(self, view, button):
        self.drag_button = button
        self.drag_views = [view]

    def extend_drag(self, view):
        if view is not None and view not in self.drag_views and self._can_drag_into(view):
            self.drag_views.append(view)

    def finish_drag(self):
        button, views = self.drag_button, self.drag_views
        self.drag_button, self.drag_views = None, []
        if len(views) == 1:
            self.click(views[0], button, False)
            return
        if self.held is None:
            return
        share = 1 if button == 'right' else max(1, self.held.count // len(views))
        for view in views:
            if self.held is None:
                break
            slot = view.models[view.index]
            room = self.held.max_stack - (slot.count if slot else 0)
            give = min(share, self.held.count, room)
            if give <= 0:
                continue
            if slot is None:
                view.models[view.index] = Stack(self.held.name, give, self.held.damage)
            else:
                slot.count += give
            self.held.count -= give
        if self.held is not None and self.held.count <= 0:
            self.held = None
        self.sound.play('random/click', 0.25)
        self.inventory.changed()

    def click(self, view, button, shift):
        self.sound.play('random/click', 0.25)
        if view.kind == 'palette':
            stack = view.getter()
            if stack is not None:
                self.held = Stack(stack.name, stack.max_stack if button == 'left' else 1)
        elif view.kind in ('crafting_output', 'furnace_output'):
            self._click_output(view, shift)
        elif shift:
            self._quick_move(view)
        else:
            self._click_slot(view.models, view.index, button)
        self.inventory.changed()

    def _click_slot(self, models, i, button):
        if models is self.inventory.armor and self.held is not None:
            armor = self.held.item.armor
            if armor is None or armor.slot != ARMOR_SLOTS[i]:
                return                       # only the right piece fits in each armor slot
        slot, held = models[i], self.held
        if button == 'left':
            if held is None:
                self.held, models[i] = slot, None
            elif slot is None:
                models[i], self.held = held, None
            elif slot.same_kind_as(held):
                moved = min(held.count, slot.max_stack - slot.count)
                slot.count += moved
                held.count -= moved
                if held.count == 0:
                    self.held = None
            else:
                models[i], self.held = held, slot
        else:
            if held is None and slot is not None:
                take = (slot.count + 1) // 2
                self.held = slot.copy(take)
                slot.count -= take
                if slot.count == 0:
                    models[i] = None
            elif held is not None and slot is None:
                models[i] = held.copy(1)
                held.count -= 1
            elif held is not None and slot.same_kind_as(held) and slot.count < slot.max_stack:
                slot.count += 1
                held.count -= 1
            elif held is not None:
                models[i], self.held = held, slot
            if self.held is not None and self.held.count <= 0:
                self.held = None

    def _click_output(self, view, shift):
        stack = view.getter()
        if stack is None:
            return
        screen = self.screen
        crafted = view.kind == 'crafting_output'
        while True:
            stack = view.getter()
            if stack is None:
                break
            if shift:
                if self.inventory.add_stack(stack.copy()) > 0:
                    break
            elif self.held is None:
                self.held = stack.copy()
            elif self.held.same_kind_as(stack) and self.held.count + stack.count <= self.held.max_stack:
                self.held.count += stack.count
            else:
                break
            if crafted:
                screen.consume_ingredients()
            else:
                screen.furnace.slots[OUTPUT] = None
            if not shift:
                break

    def _quick_move(self, view):
        stack = view.models[view.index]
        if stack is None:
            return
        if view.models is self.inventory.slots:
            moving_to = range(HOTBAR_SIZE, 36) if view.index < HOTBAR_SIZE else range(0, HOTBAR_SIZE)
            for i in moving_to:                       # first top up matching stacks, then use empty slots
                other = self.inventory.slots[i]
                if other is not None and other.same_kind_as(stack):
                    moved = min(stack.count, other.max_stack - other.count)
                    other.count += moved
                    stack.count -= moved
            for i in moving_to:
                if stack.count > 0 and self.inventory.slots[i] is None:
                    self.inventory.slots[i] = stack.copy()
                    stack.count = 0
        else:
            left = self.inventory.add_stack(stack)
            stack.count = left
        if stack.count <= 0:
            view.models[view.index] = None
