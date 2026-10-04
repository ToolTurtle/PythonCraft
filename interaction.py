"""Breaking, placing and using: everything the mouse does in the world.

  Left mouse   hold to mine a block (tools make it faster); click an animal to hit it
  Right mouse  place the block you are holding (hold to keep placing), eat food,
               or open a crafting table / furnace
  Middle mouse (creative) pick the block you are looking at"""
import random
from pathlib import Path

from PIL import Image
from ursina import Entity, Texture, Vec3, color, held_keys

from blocks import BLOCKS
from drops import drops_for, held_tool, mining_time
from facing import placement_orient, support_of, SUPPORT_OFFSET
from furnace import Furnace
from inventory import Stack
from sound import material_of

REACH = 5.0
PLACE_DELAY = 0.25        # seconds between blocks while holding the right button
CREATIVE_BREAK_DELAY = 0.25
EAT_SECONDS = 1.6
BITE_SECONDS = 0.25
HIT_SOUND_DELAY = 0.22

CRACK_DIR = Path(__file__).parent / 'assets' / 'textures' / 'crack'
INTERACTIVE = ('crafting_table', 'furnace', 'chest', 'enchanting_table')
ADVENTURE_USABLE = INTERACTIVE + ('oak_door_b', 'oak_door_t', 'bed', 'lever', 'lever_on', 'stone_button')     # what you may right-click in adventure mode     # right-clicking these opens a window


def _crack_textures():
    return [Texture(Image.open(CRACK_DIR / f'destroy_stage_{i}.png').convert('RGBA')) for i in range(10)]


class BlockInteraction:
    def __init__(self, world, player, inventory, mobs, sound, particles, dropped, ui, tnt=None):
        self.tnt = tnt
        self.on_sleep = None          # set by game.py
        self.on_message = None
        self.redstone = None
        self.fire = None
        self.portals = None
        self.click_hooks = {}         # block position -> function to call when it is right-clicked (pycraftWorld uses this)
        self.vehicles = None
        self.suppress_use = False      # set while a right-click was already used on a creature
        self.fluids = None
        self.world, self.player, self.inventory = world, player, inventory
        self.mobs, self.sound, self.particles = mobs, sound, particles
        self.dropped, self.ui = dropped, ui
        self.xp_orbs = None
        self.plants = None

        self.outline = Entity(model='wireframe_cube', color=color.black, scale=1.002, enabled=False)
        self.crack = Entity(model='cube', scale=1.004, enabled=False, color=color.rgba32(0, 0, 0, 230))
        self.crack_textures = _crack_textures()

        self.mining = None            # the block we are cracking right now
        self.progress = 0.0           # 0 to 1
        self._attacked = False        # this left-button press hit an animal, so don't also mine
        self._place_timer = 0
        self._creative_timer = 0
        self._hit_timer = 0
        self.eat_progress = 0.0         # seconds spent chewing the food in your hand
        self._bite_timer = 0

    # ---- events from the mouse -------------------------------------------

    def press_left(self):
        """The left button just went down: hit an animal if we are pointing at one."""
        origin, direction = self.player.look_ray()
        hit = self.world.raycast(origin, direction, REACH)
        block_distance = hit[2] if hit else float('inf')
        target = self.mobs.hit_test(origin, direction, reach=3.5)
        cart = self.vehicles.hit_test(origin, direction, 3.5)
        if cart and cart[1] < block_distance and not (target and target[1] < cart[1]):
            self.vehicles.destroy_vehicle(cart[0], drop=self.player.mode == 'survival')
            self._attacked = True
            return
        self._attacked = bool(target and target[1] < block_distance)
        if self._attacked:
            tool = held_tool(self.inventory.held)
            from enchantments import level_of
            held = self.inventory.held
            damage = 100 if self.player.mode == 'creative' else ((tool.attack if tool else 1) + 1.25 * level_of(held, 'sharpness'))
            target[0].hurt(self.player.position, damage=damage)
            if level_of(held, 'knockback'):
                target[0].knockback = target[0].knockback * (1 + level_of(held, 'knockback'))
            self.player.add_exhaustion(0.3)
            if tool is not None and self.player.mode == 'survival':
                self._wear_tool()

    def _boat_target(self):
        hit = self.world.raycast(*self.player.look_ray(), REACH, fluids=True)
        if hit and self.fluids.kind_at(hit[0]) == 'water':
            return hit[0]
        return None

    def press_right(self):
        """The right button just went down: feed, tame or trade with a creature if we are pointing at one.
        Returns True if it did something (so we do not also place a block)."""
        origin, direction = self.player.look_ray()
        hit = self.world.raycast(origin, direction, REACH)
        block_distance = hit[2] if hit else float('inf')
        held = self.inventory.held
        if self.player.riding is None:
            vehicle = self.vehicles.hit_test(origin, direction, 3.5)
            if vehicle and vehicle[1] < block_distance:
                self.vehicles.mount(vehicle[0])
                return True
            if held is not None and held.name == 'oak_boat':
                water = self._boat_target()
                if water is not None:
                    self.vehicles.spawn('boat', (water[0], water[1] + 0.5, water[2]))
                    if self.player.mode != 'creative':
                        self.inventory.use_one_held()
                    return True
        target = self.mobs.hit_test(origin, direction, reach=3.5)
        if not target or target[1] >= block_distance:
            return False
        mob = target[0]
        held = self.inventory.held

        def give():
            if self.player.mode != 'creative':
                self.inventory.use_one_held()
        result = self.mobs.use_on(mob, held, give)
        if result == 'scripted':
            mob.script_click()
        elif result == 'trade':
            self.ui.open_trade(mob)
        elif result == 'tamed' and self.on_message:
            self.on_message('The wolf is yours now!')
        return result is not None

    def release_left(self):
        self._attacked = False

    def pick_block(self):
        """Middle click (creative): put the block you are looking at in your hand."""
        if self.player.mode != 'creative':
            return
        hit = self.world.raycast(*self.player.look_ray(), REACH)
        if hit:
            name = BLOCKS[self.world.get(hit[0])].get('drops', self.world.get(hit[0])) or self.world.get(hit[0])
            for i, stack in enumerate(self.inventory.slots[:9]):       # already in the hotbar? select it
                if stack is not None and stack.name == name:
                    self.inventory.select(i)
                    return
            from items import ITEMS
            if name in ITEMS:
                self.inventory.slots[self.inventory.selected] = Stack(name, ITEMS[name].max_stack)
                self.inventory.changed()

    # ---- every frame -----------------------------------------------------

    def update(self, dt, active):
        """`active` is False while a menu is open, you are dead, or in spectator mode."""
        if not active:
            self._stop_mining()
            self.outline.enabled = False
            return

        hit = self.world.raycast(*self.player.look_ray(), REACH)
        if hit and self.player.build_locked and self.world.get(hit[0]) not in ADVENTURE_USABLE \
                and hit[0] not in self.click_hooks:
            hit = None                         # (nothing to do here in adventure mode, so no outline)
        self.outline.enabled = hit is not None
        if hit:
            self.outline.position = hit[0]

        stack = self.inventory.held
        food = stack.item if stack is not None and stack.item.food else None
        looking_at_machine = hit is not None and self.world.get(hit[0]) in INTERACTIVE
        if not held_keys['right mouse']:
            self.suppress_use = False
        if self.suppress_use:
            pass
        elif held_keys['right mouse'] and food is not None and not looking_at_machine:
            self._eat(dt, food)                # hold the button to eat
        else:
            self.eat_progress = 0
            if held_keys['right mouse']:
                self._place_timer -= dt
                if self._place_timer <= 0 and hit:
                    self._place_timer = PLACE_DELAY if self._use(hit) else 0
            else:
                self._place_timer = 0

        if held_keys['left mouse'] and not self._attacked and not self.player.build_locked:
            self._mine(dt, hit)
        else:
            self._stop_mining()

    # ---- right button: use / place ---------------------------------------

    def _use(self, hit):
        """Do whatever the right button does here. Returns True if something happened."""
        block, face, _ = hit
        target_kind = self.world.get(block)
        if block in self.click_hooks:
            self._place_timer = 0.4
            self.click_hooks[block]()
            return True
        if self.player.build_locked and target_kind not in ADVENTURE_USABLE:
            return False                       # adventure mode: nothing else can be used on the world

        if target_kind == 'crafting_table':
            self._place_timer = 0.5
            self.ui.open_table()
            return True
        if target_kind == 'furnace':
            self._place_timer = 0.5
            self.ui.open_furnace(block)
            return True
        if target_kind in ('lever', 'lever_on'):
            self._place_timer = 0.3
            self.redstone.toggle_lever(block)
            return True
        if target_kind == 'stone_button':
            self._place_timer = 0.3
            self.redstone.press_button(block)
            return True
        if target_kind == 'chest':
            self._place_timer = 0.5
            self.ui.open_chest(block)
            return True
        if target_kind == 'enchanting_table':
            self._place_timer = 0.5
            self.ui.open_enchant(block)
            return True
        if target_kind in ('oak_door_b', 'oak_door_t'):
            self._place_timer = 0.3
            self._toggle_door(block, target_kind)
            return True
        if target_kind == 'bed' and self.world.nether:           # beds explode where there is no night to skip
            self.world.remove(block)
            self.mobs.explode(block, 4.0)
            return True
        if target_kind == 'bed':
            self._place_timer = 1.0
            if self.on_sleep:
                self.on_sleep(block)
            return True
        held = self.inventory.held
        if held is not None and held.name == 'minecart' and target_kind is not None and target_kind.endswith(('rail', 'rail_on')):
            self.vehicles.spawn('minecart', (block[0], block[1] - 0.5 + 0.0625, block[2]))
            if self.player.mode != 'creative':
                self.inventory.use_one_held()
            return True
        if held is not None and held.name == 'bucket' and False:
            pass
        if held is not None and held.name in ('bucket', 'water_bucket', 'lava_bucket') and self._use_bucket(held):
            return True
        if (held is not None and held.item.tool is not None and held.item.tool.kind == 'hoe'
                and target_kind in ('grass', 'dirt', 'grass_snow') and face == (0, 1, 0)
                and self.world.get((block[0], block[1] + 1, block[2])) is None):
            self.world.replace(block, 'farmland')
            self.sound.play('dig/gravel', 0.7)
            if self.player.mode == 'survival':
                self._wear_tool()
            return True
        if held is not None and held.name == 'flint_and_steel' and target_kind != 'tnt':
            spot = (block[0] + face[0], block[1] + face[1], block[2] + face[2])
            if self.portals is not None and self.portals.try_light(spot):
                if self.player.mode == 'survival':
                    self._wear_tool()
                return True
            if self.fire.start(spot):
                if self.player.mode == 'survival':
                    self._wear_tool()
                return True
        if target_kind == 'tnt' and held is not None and held.name == 'flint_and_steel':
            self.world.remove(block)
            self.tnt.prime(block, 4.0)
            self.sound.play('random/fuse', 0.8)
            if self.player.mode == 'survival':
                self._wear_tool()
            return True
        if held is not None and held.item.tool is not None and held.item.tool.kind == 'bow':
            return False                     # (a bow is used by holding and releasing the button)

        stack = self.inventory.held
        if stack is None:
            return False
        item = stack.item
        if item.armor is not None:
            self.inventory.equip(self.inventory.selected)
            self.sound.play('random/click', 0.5)
            return True
        if item.places:
            return self._place(block, face, item.places)
        return False

    def _use_bucket(self, held):
        """Fill a bucket from a fluid, or pour one out."""
        hit = self.world.raycast(*self.player.look_ray(), REACH, fluids=True)
        if hit is None:
            return False
        block, face, _ = hit
        if held.name == 'bucket':
            kind = self.fluids.take(block)
            if kind is None:
                return False
            self._swap_held(f'{kind}_bucket')
            self.sound.play('liquid/splash', 0.4)
            return True
        kind = 'water' if held.name == 'water_bucket' else 'lava'
        if kind == 'water' and self.world.nether:               # water boils away in the Nether
            self._swap_held('bucket')
            self.sound.play('liquid/lavapop', 0.6)
            return True
        spot = block if self.world.get(block) is None else (block[0] + face[0], block[1] + face[1], block[2] + face[2])
        cell = self.world.get(spot)
        if (cell is not None and not (self.fluids.kind_at(spot) and spot in self.world.flowing)) or self.player.overlaps_block(spot):
            return False
        self.fluids.start(spot, kind)
        self._swap_held('bucket')
        self.sound.play('liquid/splash', 0.5)
        return True

    def _swap_held(self, name):
        if self.player.mode == 'creative' and name == 'bucket':
            return                                # creative buckets never run out
        self.inventory.slots[self.inventory.selected] = Stack(name, 1)
        self.inventory.changed()

    def _place_door(self, spot):
        above = (spot[0], spot[1] + 1, spot[2])
        if self.world.get(above) not in (None, 'water') or self.world.get((spot[0], spot[1] - 1, spot[2])) is None:
            return False
        facing = placement_orient('oak_door_b', (0, 1, 0), self.player.position, spot)
        self.world.place(spot, 'oak_door_b', facing)
        self.world.place(above, 'oak_door_t', facing)
        if self.player.mode != 'creative':
            self.inventory.use_one_held()
        self.sound.play('dig/wood', 0.8)
        return True

    def _toggle_door(self, block, kind):
        bottom = block if kind == 'oak_door_b' else (block[0], block[1] - 1, block[2])
        for pos in (bottom, (bottom[0], bottom[1] + 1, bottom[2])):
            state = self.world.facing.get(pos) or 'south'
            self.world.facing[pos] = state[:-1] if state.endswith('+') else state + '+'
        self.world._rebuild_around(bottom)
        opened = self.world.facing[bottom].endswith('+')
        self.sound.play('random/door_open' if opened else 'random/door_close', 0.7)

    def _eat(self, dt, item):
        """Chew for a moment, then the food is eaten. (Only hungry survival players can eat.)"""
        if self.player.mode != 'survival' or self.player.food >= 20:
            self.eat_progress = 0
            return
        self.eat_progress += dt
        self._bite_timer -= dt
        if self._bite_timer <= 0:
            self._bite_timer = BITE_SECONDS
            self.sound.play('random/eat', 0.5)
        if self.eat_progress >= EAT_SECONDS:
            self.eat_progress = 0
            self.player.eat(item.food, item.saturation)
            self.inventory.use_one_held()

    def _place(self, block, face, kind):
        spot = (block[0] + face[0], block[1] + face[1], block[2] + face[2])
        if self.world.get(spot) not in (None, 'water'):
            return False
        if self.player.overlaps_block(spot) or self.mobs.overlaps_block(spot):
            return False                       # something is standing there
        support = (spot[0], spot[1] - 1, spot[2])
        need = BLOCKS[kind].get('plant_on')
        if need == 'solid':
            if not self.world.is_solid(support):
                return False
        elif need and self.world.get(support) not in need:
            return False                       # seeds need farmland, sugar cane needs sand or dirt
        if kind == 'ladder' and face[1] != 0:
            return False                       # ladders hang on walls
        if kind == 'oak_door_b':
            return self._place_door(spot)
        d = self.player.look_ray()[1]
        axis = max(range(3), key=lambda i: abs(d[i]))
        if axis == 0:
            look6 = 'west' if d[0] > 0 else 'east'             # a piston's front points back at you
        elif axis == 1:
            look6 = 'down' if d[1] > 0 else 'up'
        else:
            look6 = 'north' if d[2] > 0 else 'south'
        orient = placement_orient(kind, face, self.player.position, spot, look6)
        if BLOCKS[kind].get('orient') == 'attach' and orient is None:
            return False                       # a torch cannot hang from a ceiling
        self.world.place(spot, kind, orient)
        if kind == 'furnace':
            self.world.furnaces[spot] = Furnace()
        if kind == 'chest':
            self.world.chests[spot] = [None] * 27
        if kind == 'sponge' and self.fluids is not None:
            self.fluids.absorb(spot)
        if self.player.mode != 'creative':
            self.inventory.use_one_held()
        self.sound.play(f'dig/{material_of(kind)}', 0.8)
        self.particles.emit(kind, spot, count=4, speed=1.0)
        return True

    # ---- left button: mining ---------------------------------------------

    def _mine(self, dt, hit):
        if hit is None:
            self._stop_mining()
            return
        block, face, _ = hit
        kind = self.world.get(block)
        if block != self.mining:               # started on a different block: crack from zero
            self._stop_mining()
            self.mining = block
            self._creative_timer = 0
            self._hit_timer = 0

        if self.player.mode == 'creative':     # no waiting in creative mode
            self._creative_timer -= dt
            if self._creative_timer <= 0:
                self._break(block, kind)
                self._creative_timer = CREATIVE_BREAK_DELAY
            return

        seconds = mining_time(kind, self.inventory.held)
        if seconds is None:                    # bedrock
            return
        self.progress += dt / max(seconds, 0.05)

        self._hit_timer -= dt
        if self._hit_timer <= 0:               # a little thud and some crumbs while we dig
            self._hit_timer = HIT_SOUND_DELAY
            self.sound.play(f'dig/{material_of(kind)}', 0.45)
            self.particles.emit(kind, block, count=2, speed=1.2, face=face)

        if self.progress >= 1:
            self._break(block, kind)
        else:
            self.crack.position = block
            self.crack.texture = self.crack_textures[int(self.progress * 10)]
            self.crack.enabled = True

    def _break(self, block, kind):
        survival = self.player.mode == 'survival'
        centre = Vec3(block[0], block[1], block[2])
        if kind in ('oak_door_b', 'oak_door_t'):
            other = (block[0], block[1] + (1 if kind == 'oak_door_b' else -1), block[2])
            if self.world.get(other) in ('oak_door_b', 'oak_door_t'):
                self.world.remove(other, notify=False)
        if survival and self.xp_orbs is not None:
            gain = {'coal_ore': (0, 2), 'diamond_ore': (3, 7), 'gold_ore': (0, 0)}.get(kind)
            if gain and gain[1]:
                self.xp_orbs.spawn(centre + Vec3(0, 0.2, 0), random.randint(*gain))
        if survival and kind != 'oak_door_t':
            for name, count in drops_for(kind, self.inventory.held):
                self._throw_item(Stack(name, count), centre)
            if held_tool(self.inventory.held) is not None:
                self._wear_tool()
        if kind == 'chest' and block in self.world.chests:
            for stack in self.world.chests.pop(block):
                if stack is not None and survival:
                    self._throw_item(stack, centre)
        if kind == 'furnace' and block in self.world.furnaces:
            for stack in self.world.furnaces.pop(block).contents():
                if survival:
                    self._throw_item(stack, centre)
        self.player.add_exhaustion(0.025)
        self.sound.play(f'dig/{material_of(kind)}')
        self.particles.emit(kind, block, count=18, speed=2.2)
        self.world.remove(block)
        self._drop_hanging_things(block, survival)
        if kind.endswith('_log') and self.plants is not None:
            self.plants.schedule_decay(block)
        self._stop_mining()

    def _drop_hanging_things(self, block, survival):
        """Torches hanging on a block that has just gone fall off as items."""
        for offset in SUPPORT_OFFSET.values():
            spot = (block[0] - offset[0], block[1] - offset[1], block[2] - offset[2])
            kind = self.world.get(spot)
            if kind and BLOCKS[kind].get('orient') == 'attach' and support_of(spot, self.world.facing.get(spot)) == block:
                self.world.remove(spot)
                if survival:
                    self._throw_item(Stack(kind, 1), Vec3(*spot))

    def _throw_item(self, stack, centre):
        velocity = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
        self.dropped.drop(stack, centre + Vec3(0, 0.1, 0), velocity)

    def _wear_tool(self):
        if self.inventory.wear_held_tool(1):
            self.sound.play('random/break', 0.8)

    def _stop_mining(self):
        self.mining = None
        self.progress = 0
        self.crack.enabled = False
