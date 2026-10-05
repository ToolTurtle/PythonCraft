"""One running game: the world, the player, and everything around them.

A Game is either brand new, or rebuilt from a save (see savegame.py)."""
import time as pytime

from ursina import destroy, Text, Entity, application, camera, time, mouse, color, window, Vec2, Vec3, Vec4

import cursor
import savegame
import textures
from biomes import PLAINS
from dropped_items import DroppedItems
from hud import DeathScreen, Hotbar, StatusBars, XPBar
from xp import ExperienceOrbs
from blockentities import FallingBlocks, PrimedTNT
from plants import Plants
from portals import Portals
from redstone import Redstone
from fire import Fire
from vehicles import Vehicles
from fluids import Fluids
from interaction import BlockInteraction
from inventory import Inventory, Stack
from inventory_ui import InventoryUI
from sky import Sky, PHASES
from menu import PauseMenu
from mobs import Mobs
from particles import Particles
from player import Player
from projectiles import Projectiles
from sound import Sound, material_of
from world import World

AUTOSAVE_SECONDS = 120


class Game:
    def __init__(self, folder, name, seed=None, mode='survival', level=None, modified=None, facing=None, flowing=None,
                 flat_spawn=None, adventure=False, dims=None, dimension='overworld'):
        self.folder, self.name = folder, name
        level = level or {}
        saved_player = level.get('player')

        self.world = world = World(PLAINS, seed=seed, modified=modified, tints=level.get('tints'), facing=facing, flat_spawn=flat_spawn,
                                   dimension=dimension)
        world.flowing.update(flowing or {})
        for dim_name, (dim_modified, dim_facing, dim_flowing) in (dims or {}).items():
            world.load_dimension(dim_name, dim_modified, dim_facing, dim_flowing)
        if level.get('dimension', 'overworld') != 'overworld':
            world.switch_dimension(level['dimension'])
            world.preload(level['player']['position'][0], level['player']['position'][2])      # ground to stand on
        self.fluids = Fluids(world, None)
        position = tuple(saved_player['position']) if saved_player else world.spawn_point()
        self.player = player = Player(world, position)
        self.sky = Sky(level.get('time', 1000), level.get('days', 0))
        self.sky.set_dimension(world.dimension)
        self._stashed = {}            # what lives in the dimensions we are not in: {name: {'mobs', 'dropped', 'vehicles'}}
        player.spawn = world.spawn_point()
        self.sound = sound = Sound()
        self.menu = menu = PauseMenu(player, world, sound)
        self.mobs = mobs = Mobs(world, sound, player)
        mobs.sky = self.sky

        self.status = StatusBars()
        self.xp_bar = XPBar()
        self.death_screen = DeathScreen(on_respawn=self.respawn, on_quit=self.save_and_quit)
        self.inventory = inventory = Inventory()
        self.hotbar = Hotbar(inventory)
        self.particles = particles = Particles(world)
        self.dropped = dropped = DroppedItems(world, sound)
        mobs.dropped = dropped
        mobs.particles = particles
        mobs.projectiles = self.projectiles = Projectiles(world, player, mobs)
        self.projectiles.sound = sound
        self.projectiles.on_player_hit = self.arrow_hit_player
        self.ui = ui = InventoryUI(inventory, player, world, dropped, sound)
        self.falling = FallingBlocks(world)
        self.tnt = PrimedTNT(world, mobs)
        mobs.tnt = self.tnt
        self.interaction = BlockInteraction(world, player, inventory, mobs, sound, particles, dropped, ui, self.tnt)
        self.bow_charge = None
        self.plants = Plants(world, dropped)
        self.interaction.on_sleep = self.sleep
        self.redstone = Redstone(world, player, mobs, dropped, self.tnt, sound)
        self.interaction.redstone = self.redstone
        self.fire = Fire(world, player, mobs, self.tnt, sound)
        self.interaction.fire = self.fire
        self.portals = Portals(world, player, self.change_dimension, sound)
        self.interaction.portals = self.portals
        self.portals.must_leave = True              # (a game saved inside a portal does not whisk you away on loading)
        self.vehicles = Vehicles(world, player, dropped, sound)
        self.interaction.vehicles = self.vehicles
        self.interaction.on_message = self.message
        if adventure:
            player.build_locked = True
            menu.locked_mode = 'Adventure'
        self.fluids.sound = sound
        self.xp_orbs = ExperienceOrbs(world, player, sound)
        self.interaction.xp_orbs = self.xp_orbs
        self.interaction.plants = self.plants
        mobs.xp_orbs = self.xp_orbs
        player.on_armor_hit = inventory.wear_armor
        player.on_xp_gain = lambda leveled: sound.play('random/levelup' if leveled else 'random/orb', 0.5 if leveled else 0.2)
        self.interaction.fluids = self.fluids
        menu.on_save = self.save
        menu.on_respawn = self.respawn_player
        menu.on_unstuck = self.unstuck
        menu.sky = self.sky
        menu.on_quit = self.save_and_quit

        player.on_step = lambda block: sound.play(f'step/{material_of(block)}', 0.5)
        player.on_splash = lambda: (sound.play('liquid/splash'),
                                    particles.emit('water', player.position + Vec3(0, 0.4, 0), 14, speed=2.5))
        player.on_swim = lambda: sound.play('liquid/swim', 0.6)
        player.on_hurt = self.player_hurt
        player.on_death = self.player_died
        world.on_retint.append(self.retinted)

        self.biome_label = Text(text='', position=window.bottom_left + Vec2(0.02, 0.04), scale=.8)
        self.saved_label = Text(text='Game saved', origin=(0.5, 0.5), position=window.top_right + Vec2(-0.03, -0.04),
                                scale=1, enabled=False)
        self.saved_label_time = 0
        self.message_bg = Entity(parent=camera.ui, model='quad', color=color.rgba32(0, 0, 0, 170), enabled=False, z=0.5)
        self.message_label = Text(text='', origin=(0, 0), position=(0, 0.2), scale=1.4, enabled=False)
        self.message_time = 0
        self.water_overlay = Entity(parent=camera.ui, model='quad', scale=(3, 2), z=2, enabled=False,
                                    color=color.rgba32(30, 70, 200, 110))

        self.sky.update(0, camera.world_position)       # the shaders need these before the first frame is drawn
        self._set_fog()
        self.play_seconds = level.get('play_seconds', 0)
        self.autosave_timer = AUTOSAVE_SECONDS
        self.frames = 0
        self.console = None             # the in-game code prompt (/), set by livecode

        if level:
            self._restore(level)
        else:
            mobs.spawn_initial(10, around=world.spawn_point())
            player.set_mode(mode)
        self._ensure_storage()

    # ---- saving and loading ----------------------------------------------

    def snapshot(self):
        """Everything needed to rebuild this game, as plain numbers and text."""
        player, inventory = self.player, self.inventory

        def stack(s):
            return None if s is None else [s.name, s.count, s.damage, s.enchants]

        return {
            'name': self.name,
            'seed': self.world.seed,
            'last_played': pytime.time(),
            'play_seconds': self.play_seconds,
            'time': self.sky.time,
            'days': self.sky.days,
            'tints': {n: list(textures.get_tint(n)) for n in ('grass', 'foliage', 'water')},
            'settings': {
                'sensitivity': player.mouse_sensitivity[0], 'fov': player.base_fov,
                'render_distance': self.world.render_distance,
                'sound_volume': self.sound.volume, 'music_volume': self.sound.music_volume,
            },
            'player': {
                'position': list(player.position), 'rotation_y': player.rotation_y,
                'pitch': player.camera_pivot.rotation_x, 'mode': player.mode,
                'health': player.health, 'air': player.air, 'food': player.food,
                'saturation': player.saturation, 'exhaustion': player.exhaustion, 'selected': inventory.selected,
            },
            'inventory': [stack(s) for s in inventory.slots],
            'armor': [stack(s) for s in inventory.armor],
            'xp': player.xp,
            'dimension': self.world.dimension,
            'furnaces': [{'position': list(pos), 'slots': [stack(s) for s in f.slots], 'burn_left': f.burn_left,
                          'burn_total': f.burn_total, 'progress': f.progress, 'dim': dim}
                         for dim, state in self.world.dimension_data().items() for pos, f in state['furnaces'].items()],
            'mobs': self.mobs.snapshot(),
            'other_mobs': {dim: self.mobs.snapshot(stash['mobs']) for dim, stash in self._stashed.items()},
            'villages_done': [list(k) for k in self.world.villages_done],
            'vehicles': [{'kind': v.name, 'position': list(v.position), 'heading': getattr(v, 'heading', None)} for v in self.vehicles.list],
            'chests': [{'position': list(pos), 'slots': [stack(s) for s in slots], 'dim': dim}
                       for dim, state in self.world.dimension_data().items() for pos, slots in state['chests'].items()],
            'dropped': [{'position': list(d.position), 'stack': stack(d.stack)} for d in self.dropped.items],
        }

    def _restore(self, level):
        from furnace import Furnace

        def stack(data):
            from items import ITEMS
            return None if data is None or data[0] not in ITEMS else Stack(*data)       # (an item from a mod that is not loaded is dropped)

        settings = level.get('settings', {})
        player, inventory, world = self.player, self.inventory, self.world
        if 'sensitivity' in settings:
            player.mouse_sensitivity = Vec2(settings['sensitivity'], settings['sensitivity'])
            player.base_fov = settings['fov']
            camera.fov = settings['fov']
            world.set_render_distance(settings['render_distance'])
            self.sound.volume = settings['sound_volume']
            self.sound.music_volume = settings['music_volume']
            self.menu.refresh_sliders()

        saved = level['player']
        player.set_mode(saved['mode'])
        player.rotation_y = saved['rotation_y']
        player.camera_pivot.rotation_x = saved['pitch']
        player.health, player.air = saved['health'], saved['air']
        player.food = saved.get('food', 20)
        player.saturation = saved.get('saturation', 5.0)
        player.exhaustion = saved.get('exhaustion', 0.0)
        for i, data in enumerate(level['inventory']):
            inventory.slots[i] = stack(data)
        inventory.selected = saved['selected']
        for i, data in enumerate(level.get('armor', [None] * 4)):
            inventory.armor[i] = stack(data)
        player.xp = level.get('xp', 0)
        inventory.changed()

        def storage(dim, key):
            if dim == world.dimension:
                return getattr(world, key)
            return world._other_dimensions.setdefault(dim, world._blank_state())[key]

        for data in level.get('furnaces', []):
            furnace = Furnace()
            furnace.slots = [stack(s) for s in data['slots']]
            furnace.burn_left, furnace.burn_total, furnace.progress = data['burn_left'], data['burn_total'], data['progress']
            storage(data.get('dim', 'overworld'), 'furnaces')[tuple(data['position'])] = furnace
        for data in level.get('pigs', []):                       # (older saves only had pigs)
            self.mobs.add('pig', tuple(data['position']), data['rotation_y'], data['health'])
        self.mobs.restore(level.get('mobs', []))
        world.villages_done = {tuple(k) for k in level.get('villages_done', [])}
        for data in level.get('vehicles', []):
            vehicle = self.vehicles.spawn(data['kind'], tuple(data['position']))
            if data.get('heading') is not None:
                vehicle.heading = data['heading']
        world.village_queue = [q for q in world.village_queue if q[0] not in world.villages_done]
        for data in level.get('chests', []):
            storage(data.get('dim', 'overworld'), 'chests')[tuple(data['position'])] = [stack(s) for s in data['slots']]
        for dim, entries in level.get('other_mobs', {}).items():          # creatures waiting in the other dimension
            before = len(self.mobs.mobs)
            self.mobs.restore(entries)
            waiting = self.mobs.mobs[before:]
            del self.mobs.mobs[before:]
            for mob in waiting:
                mob.enabled = False
            self._stashed[dim] = {'mobs': waiting, 'dropped': [], 'vehicles': []}
        for data in level.get('dropped', []):
            self.dropped.drop(stack(data['stack']), tuple(data['position']), Vec3(0, 0, 0))

    def _ensure_storage(self):
        """Every chest and furnace block needs somewhere to keep things, even when it was put in the
        world by a program (the pycraftWorld library) instead of by a player placing it."""
        from furnace import Furnace
        for pos, kind in self.world.modified.items():
            if kind == 'chest' and pos not in self.world.chests:
                self.world.chests[pos] = [None] * 27
            elif kind == 'furnace' and pos not in self.world.furnaces:
                self.world.furnaces[pos] = Furnace()

    def message(self, text, seconds=3.0):
        label = self.message_label
        label.text = text
        multi = '\n' in text                         # several lines (code on a sign): left-aligned, on a dark panel
        label.scale = 1.1 if multi else 1.4
        label.origin = (-.5, .5) if multi else (0, 0)
        label.position = (-0.42, 0.34) if multi else (0, 0.2)
        label.enabled = True
        if multi:
            width, height = label.width * 1.12 + 0.05, label.height * 1.06 + 0.04
            self.message_bg.position = (-0.42 - 0.02 + width / 2, 0.34 + 0.015 - height / 2)
            self.message_bg.scale = (width, height)
        self.message_bg.enabled = multi
        self.message_time = seconds

    def sleep(self, bed):
        """Sleeping in a bed skips the night and sets where you come back after dying."""
        if self.sky.daylight > 0.5:
            self.message('You can only sleep at night')
            return
        self.sky.set_time(0)
        self.player.spawn = (bed[0] + 0.5, bed[1] + 1, bed[2] + 0.5)
        self.message('Good morning! Your spawn point has been set')

    def save(self):
        data = self.world.dimension_data()
        main = data.pop('overworld')
        savegame.save(self.folder, self.snapshot(), main['modified'], main['facing'], main['flowing'], dims=data)
        self.saved_label.enabled = True
        self.saved_label_time = 2.0
        self.autosave_timer = AUTOSAVE_SECONDS

    def save_and_quit(self):
        self.save()
        application.quit()

    # ---- events ------------------------------------------------------------

    def arrow_hit_player(self, damage, direction):
        self.player.damage(damage, 'arrow')
        self.player.velocity_xz += Vec3(direction.x, 0, direction.z) * 3

    def player_hurt(self, kind, amount):
        self.sound.play('damage/fallbig' if (kind == 'fall' and amount >= 5) else
                        'damage/fallsmall' if kind == 'fall' else 'damage/hit', 1.0)
        self.status.flash()

    def player_died(self):
        mouse.locked = False
        cursor.set_hidden(False)
        self.death_screen.show()

    def unstuck(self):
        """Move the player to the nearest free spot (two free cells above a floor), keeping health, items and the world as they are.
        If nothing is near, to the top of the ground here; failing that, the spawn point."""
        import math as _math
        from chunk import HEIGHT
        player, world = self.player, self.world
        cx, cz = round(player.x), round(player.z)
        fy = _math.floor(player.y + 0.5)

        def free(x, y, z):
            return world.solid_top((x, y, z)) == 0 and world.get((x, y, z)) not in ('lava',)

        def standable(x, y, z):
            return 0 <= y < HEIGHT and free(x, y, z) and free(x, y + 1, z) and world.solid_top((x, y - 1, z)) > 0

        best = None
        for radius in range(0, 9):
            found = []
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if max(abs(dx), abs(dz)) != radius:
                        continue
                    for y in range(fy - 8, fy + 9):
                        if standable(cx + dx, y, cz + dz):
                            found.append((dx * dx + dz * dz + (y - fy) ** 2, (cx + dx, y, cz + dz)))
            if found:
                best = min(found)[1]
                break
        if best is None:
            for y in range(HEIGHT - 3, 0, -1):
                if standable(cx, y, cz):
                    best = (cx, y, cz)
                    break
        if best is None:
            self.respawn_player()
            self.message('Nowhere free near you, so back to the start.', 4)
            return False
        player.position = (best[0], best[1] - 0.5 + 0.01, best[2])
        player.velocity_y = 0
        player._peak_y = player.y                          # (no falling damage for this)
        self.message('Moved you to a free spot.', 3)
        return True

    def respawn_player(self):
        """Back to the overworld spawn point, wherever you died."""
        if self.world.dimension != 'overworld':
            self.change_dimension('overworld')
        self.player.respawn(self.world.spawn_point())

    def respawn(self):
        self.respawn_player()
        self.death_screen.hide()
        mouse.locked = True
        cursor.set_hidden(True)

    def change_dimension(self, name):
        """Move everything to another dimension: the land, the creatures, the sky."""
        world = self.world
        old = world.dimension
        if name == old:
            return
        lists = {'mobs': self.mobs.mobs, 'dropped': self.dropped.items, 'vehicles': self.vehicles.list}
        self._stashed[old] = {key: list(items) for key, items in lists.items()}
        for items in self._stashed[old].values():
            for entity in items:
                entity.enabled = False
        arrived = self._stashed.pop(name, None) or {'mobs': [], 'dropped': [], 'vehicles': []}
        for key, items in lists.items():
            items[:] = arrived[key]
            for entity in items:
                entity.enabled = key != 'mobs'          # (creatures show themselves when their land is shown)
        # things in flight do not come along
        self.projectiles.clear()
        for key in ('falling', 'lit'):
            for holder in (self.falling, self.tnt):
                entities = getattr(holder, key, None)
                if entities:
                    for entity in list(entities):
                        destroy(entity)
                    entities.clear()
        for orb in list(self.xp_orbs.orbs):
            destroy(orb)
        self.xp_orbs.orbs.clear()
        for fluid in self.fluids.active.values():
            fluid.clear()
        self.redstone.button_timers.clear()
        self.redstone.door_power.clear()
        self.redstone.dirty = True
        self.fire.fires.clear()
        self.plants.decaying.clear()
        self.interaction.mining = None
        world.switch_dimension(name)
        self.sky.set_dimension(name)
        self.message('The Nether' if name == 'nether' else 'The Overworld', 2.5)

    def _set_fog(self):
        """Far-away land fades into the sky color instead of popping into view."""
        far = max(24, (self.world.render_distance - 0.6) * 16)
        render = application.base.render
        if self.world.nether:
            far = min(far, 80)                  # a thick red haze
            render.set_shader_input('fog_range', Vec2(far * 0.25, far))
        else:
            render.set_shader_input('fog_range', Vec2(far * 0.7, far))

    def retinted(self):
        textures.refresh_item_icons()          # block pictures must pick up the new grass and leaf colors
        self.inventory.changed()

    # ---- keyboard and mouse ------------------------------------------------

    def input(self, key):
        player, ui, menu, inventory = self.player, self.ui, self.menu, self.inventory
        if player.dead:
            return                      # (the death screen has its own buttons)
        if self.console is not None and self.console.is_open:
            self.console.input(key)
            return
        if ui.active:
            ui.input(key)               # the inventory, crafting table or furnace is open
            return
        if key == 'escape':
            menu.toggle()
            return
        if key == '/' and self.console is not None and not menu.is_open and not menu.just_closed() and not ui.just_closed():
            self.console.open()                 # the code prompt (live coding)
            return
        if menu.is_open or menu.just_closed() or ui.just_closed() or player.mode == 'spectator':
            return

        if key == 'e':
            ui.open_inventory()
        elif key == 'q' and inventory.held is not None:      # throw one item
            stack = inventory.held
            ui.throw(Stack(stack.name, 1, stack.damage))
            inventory.use_one_held()
        elif key.isdigit() and key != '0':
            self.hotbar.select_number(int(key))
        elif key in ('scroll up', 'scroll down'):
            self.hotbar.scroll(1 if key == 'scroll down' else -1)
        elif key == 'left mouse down':
            self.interaction.press_left()
        elif key == 'left mouse up':
            self.interaction.release_left()
        elif key == 'middle mouse down':
            self.interaction.pick_block()
        elif key == 'right mouse down':
            held = inventory.held
            if self.interaction.press_right():
                self.interaction.suppress_use = True          # we used it on a creature: do not also use it on the world
            elif held is not None and held.name == 'bow':
                self.bow_charge = 0.0                      # start drawing the bow
        elif key == 'right mouse up':
            if self.bow_charge is not None:
                self._release_bow()

    def _release_bow(self):
        charge, self.bow_charge = self.bow_charge, None
        inventory = self.inventory
        has_arrows = self.player.mode == 'creative' or inventory.count('arrow') > 0
        if charge < 0.15 or not has_arrows or inventory.held is None or inventory.held.name != 'bow':
            return
        power = min(1.0, charge / 1.0)
        origin, direction = self.player.look_ray()
        from enchantments import level_of
        self.projectiles.shoot(origin, direction, 14 + 26 * power, 'player', round(2 + 4 * power + 1.25 * level_of(inventory.held, 'power')))
        if self.player.mode == 'survival':
            self._use_arrow()
            inventory.wear_held_tool(1)

    def _use_arrow(self):
        for i, s in enumerate(self.inventory.slots):
            if s is not None and s.name == 'arrow':
                s.count -= 1
                if s.count <= 0:
                    self.inventory.slots[i] = None
                self.inventory.changed()
                return

    # ---- every frame -------------------------------------------------------

    def update(self):
        player, world, ui, menu = self.player, self.world, self.ui, self.menu
        dt = time.dt

        # Hide the cursor once the window is up (it may not be ready on the very first frame).
        self.frames += 1
        if self.frames in (1, 30):
            cursor.set_hidden(not menu.is_open)

        self.sky.update(dt, camera.world_position)
        world.update_view(player.x, player.z)   # show the chunks near the player
        self._set_fog()
        world.build_step()
        self.sound.update()
        self.mobs.update_visibility()
        self.mobs.update_lighting()
        self.mobs.update_spawning(dt)
        self.mobs.update_villages(dt)
        self.mobs.update_spawners(dt)
        self.projectiles.update(dt)
        self.falling.update(dt)
        self.fluids.update(dt)
        self.redstone.update(dt)
        self.fire.update(dt)
        self.vehicles.update(dt)
        self.plants.update(dt)
        self.plants.update_trees(dt)
        self.xp_orbs.update(dt)
        player.armor_points = self.inventory.armor_points()
        if self.message_time > 0:
            self.message_time -= dt
            self.message_label.enabled = self.message_time > 0
            self.message_bg.enabled = self.message_bg.enabled and self.message_time > 0
        self.tnt.update(dt)
        self.portals.update(dt, not self.player.dead and self.player.mode != 'spectator')
        if self.bow_charge is not None:
            self.bow_charge += dt
            if self.menu.is_open or self.ui.active or self.player.dead:
                self.bow_charge = None
        self.biome_label.text = f'Biome: {world.biome_at(player.x, player.z).name}'
        self.water_overlay.enabled = player.eyes_in_water() and not menu.is_open

        # Which parts of the screen to show right now
        playing = not menu.is_open and not player.dead and not ui.active
        self.hotbar.root.enabled = (not menu.is_open and not player.dead and player.mode != 'spectator'
                                    and not ui.active)
        self.hotbar.update()
        self.status.root.enabled = playing and player.mode == 'survival'
        self.biome_label.enabled = playing
        player.crosshair.enabled = playing
        player.crosshair.scale = 1                          # (the cross is always the same small size: nothing may stretch it)
        self.status.update(player, dt)
        self.xp_bar.update(player.xp)
        self.xp_bar.root.enabled = playing and player.mode == 'survival'

        # Mining, placing, the outline around the targeted block, and flying crumbs
        self.interaction.update(dt, playing and player.mode != 'spectator')
        self.particles.update(dt)
        for furnace in world.furnaces.values():
            furnace.update(dt)
        self.dropped.update(player, self.inventory, dt)
        ui.update()

        # Saving
        self.play_seconds += dt
        self.autosave_timer -= dt
        if self.autosave_timer <= 0:
            self.save()
        if self.saved_label_time > 0:
            self.saved_label_time -= dt
            self.saved_label.enabled = self.saved_label_time > 0
