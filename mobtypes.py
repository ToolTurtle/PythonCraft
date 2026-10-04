"""What each creature is: its body (boxes painted from a skin), size, health, speed, behaviour, drops.

A body part is {'role', 'boxes', 'pivot'}:
  boxes   [(skin offset, box corner, box size)]  in Minecraft model units (16 = one block)
  pivot   where the part swings from
  role    what it does when the creature moves: 'head', 'body', 'leg' (swings), 'arm', 'wing', 'still'
  phase   which legs swing together (0 or 1)"""
from dataclasses import dataclass, field


def part(role, boxes, pivot, phase=0, texture='main', rotate_x=0, rotate=(0, 0, 0)):
    return dict(role=role, boxes=boxes, pivot=pivot, phase=phase, texture=texture, rotate_x=rotate_x, rotate=rotate)


def four_legs(offset, box, pivots):
    """Legs for an animal. The front-right and back-left legs swing together."""
    return [part('leg', [(offset, box[0], box[1])], pivot, phase=i in (0, 3)) for i, pivot in enumerate(pivots)]


@dataclass
class MobType:
    name: str
    title: str
    textures: dict                 # 'main' -> file in assets/textures/entity
    parts: list
    width: float
    height: float
    health: int
    speed: float
    behavior: str = 'passive'      # 'passive', 'zombie', 'skeleton', 'creeper', 'spider'
    attack: float = 0
    drops: list = field(default_factory=list)       # (item, least, most) or (item, least, most, chance)
    burns: bool = False            # catches fire in daylight
    monster: bool = False
    sound: str = ''                # folder in assets/sounds/mob
    eyes: bool = False
    fire_immune: bool = False      # unhurt by fire and lava (Nether creatures)
    flying: bool = False           # floats in the air instead of walking
    splits: bool = False           # comes in sizes 1, 2 and 4 and breaks into smaller ones (slimes)
    skin_scale: float = 1.0        # the skin picture is this many times bigger than the usual layout
    scale: float = 1.0             # the body is drawn this many times bigger
    base: str = ''                 # which creature this one is made from (a mod's creature behaves like its base)

    def __post_init__(self):
        if not self.base:
            self.base = self.name


# ---- animals -------------------------------------------------------------------------

PIG = MobType(
    'pig', 'Pig', {'main': 'pig_temperate.png'},
    parts=[
        part('head', [((0, 0), (-4, -4, -8), (8, 8, 8)), ((16, 16), (-2, 0, -9), (4, 3, 1))], (0, 12, -6)),
        part('body', [((28, 8), (-5, -10, -7), (10, 16, 8))], (0, 11, 2), rotate_x=90),
        *four_legs((0, 16), ((-2, 0, -2), (4, 6, 4)), ((-3, 18, 7), (3, 18, 7), (-3, 18, -5), (3, 18, -5))),
    ],
    width=0.9, height=0.9, health=10, speed=1.4,
    drops=[('porkchop', 1, 3)], sound='pig')

COW = MobType(
    'cow', 'Cow', {'main': 'cow_temperate.png'},
    parts=[
        part('head', [((0, 0), (-4, -4, -6), (8, 8, 6)), ((22, 0), (-5, -5, -4), (1, 3, 1)),
                      ((22, 0), (4, -5, -4), (1, 3, 1))], (0, 4, -8)),
        part('body', [((18, 4), (-6, -10, -7), (12, 18, 10)), ((52, 0), (-2, 2, -8), (4, 6, 1))], (0, 5, 2), rotate_x=90),
        *four_legs((0, 16), ((-2, 0, -2), (4, 12, 4)), ((-4, 12, 7), (4, 12, 7), (-4, 12, -5), (4, 12, -5))),
    ],
    width=0.9, height=1.4, health=10, speed=1.5,
    drops=[('leather', 0, 2), ('beef', 1, 3)], sound='cow')

SHEEP = MobType(
    'sheep', 'Sheep', {'main': 'sheep.png', 'wool': 'sheep_wool.png'},
    parts=[
        part('head', [((0, 0), (-3, -4, -6), (6, 6, 8))], (0, 6, -8)),
        part('head', [((0, 0), (-3, -4, -4), (6, 6, 6), 0.6)], (0, 6, -8), texture='wool'),
        part('body', [((28, 8), (-4, -10, -7), (8, 16, 6))], (0, 5, 2), rotate_x=90),
        part('body', [((28, 8), (-4, -10, -7), (8, 16, 6), 1.75)], (0, 5, 2), rotate_x=90, texture='wool'),
        *four_legs((0, 16), ((-2, 0, -2), (4, 12, 4)), ((-3, 12, 7), (3, 12, 7), (-3, 12, -5), (3, 12, -5))),
        *[part('leg', [((0, 16), (-2, 0, -2), (4, 6, 4), 0.5)], p, phase=i in (0, 3), texture='wool')
          for i, p in enumerate(((-3, 12, 7), (3, 12, 7), (-3, 12, -5), (3, 12, -5)))],
    ],
    width=0.9, height=1.3, health=8, speed=1.6,
    drops=[('white_wool', 1, 1)], sound='sheep')

CHICKEN = MobType(
    'chicken', 'Chicken', {'main': 'chicken_temperate.png'},
    parts=[
        part('head', [((0, 0), (-2, -6, -2), (4, 6, 3)), ((14, 0), (-2, -4, -4), (4, 2, 2)),
                      ((14, 4), (-1, -2, -3), (2, 2, 2))], (0, 15, -4)),
        part('body', [((0, 9), (-3, -4, -3), (6, 8, 6))], (0, 16, 0), rotate_x=90),
        part('leg', [((26, 0), (-1, 0, -3), (3, 5, 3))], (-2, 19, 1), phase=0),
        part('leg', [((26, 0), (-1, 0, -3), (3, 5, 3))], (1, 19, 1), phase=1),
        part('wing', [((24, 13), (0, 0, -3), (1, 4, 6))], (-4, 13, 0)),
        part('wing', [((24, 13), (-1, 0, -3), (1, 4, 6))], (4, 13, 0)),
    ],
    width=0.4, height=0.7, health=4, speed=1.4,
    drops=[('feather', 0, 2), ('chicken', 1, 1)], sound='chicken')

# ---- monsters --------------------------------------------------------------------------

def humanoid(arm_box, arm_offsets, leg_box, leg_offsets, leg_pivots, arm_pivots=((-5, 2, 0), (5, 2, 0))):
    return [
        part('head', [((0, 0), (-4, -8, -4), (8, 8, 8))], (0, 0, 0)),
        part('body', [((16, 16), (-4, 0, -2), (8, 12, 4))], (0, 0, 0)),
        part('arm', [(arm_offsets[0], *arm_box)], arm_pivots[0], phase=1),
        part('arm', [(arm_offsets[1], *arm_box)], arm_pivots[1], phase=0),
        part('leg', [(leg_offsets[0], *leg_box)], leg_pivots[0], phase=0),
        part('leg', [(leg_offsets[1], *leg_box)], leg_pivots[1], phase=1),
    ]


ZOMBIE = MobType(
    'zombie', 'Zombie', {'main': 'zombie.png'},
    parts=humanoid(((-3, -2, -2), (4, 12, 4)), ((40, 16), (32, 48)), ((-2, 0, -2), (4, 12, 4)), ((0, 16), (16, 48)),
                   ((-1.9, 12, 0), (1.9, 12, 0))),
    width=0.6, height=1.95, health=20, speed=3.0, behavior='zombie', attack=3, burns=True, monster=True,
    drops=[('rotten_flesh', 0, 2)], sound='zombie')

SKELETON = MobType(
    'skeleton', 'Skeleton', {'main': 'skeleton.png'},
    parts=humanoid(((-1, -2, -1), (2, 12, 2)), ((40, 16), (40, 16)), ((-1, 0, -1), (2, 12, 2)), ((0, 16), (0, 16)),
                   ((-2, 12, 0), (2, 12, 0))),
    width=0.6, height=1.99, health=20, speed=3.0, behavior='skeleton', attack=3, burns=True, monster=True,
    drops=[('bone', 0, 2), ('arrow', 0, 2)], sound='skeleton')

CREEPER = MobType(
    'creeper', 'Creeper', {'main': 'creeper.png'},
    parts=[
        part('head', [((0, 0), (-4, -8, -4), (8, 8, 8))], (0, 6, 0)),
        part('body', [((16, 16), (-4, 0, -2), (8, 12, 4))], (0, 6, 0)),
        *four_legs((0, 16), ((-2, 0, -2), (4, 6, 4)), ((-2, 18, 4), (2, 18, 4), (-2, 18, -4), (2, 18, -4))),
    ],
    width=0.6, height=1.7, health=20, speed=3.0, behavior='creeper', monster=True,
    drops=[('gunpowder', 0, 2)], sound='creeper')

_SPIDER_LEGS = []
for _i, (_pz, _yaw) in enumerate(((2, 40), (1, 15), (0, -15), (-1, -40))):
    _SPIDER_LEGS.append(part('leg', [((18, 0), (-15, -1, -1), (16, 2, 2))], (-4, 15, _pz), phase=_i % 2,
                             rotate=(0, _yaw, -18)))
    _SPIDER_LEGS.append(part('leg', [((18, 0), (-1, -1, -1), (16, 2, 2))], (4, 15, _pz), phase=(_i + 1) % 2,
                             rotate=(0, -_yaw, 18)))

SPIDER = MobType(
    'spider', 'Spider', {'main': 'spider.png'},
    parts=[
        part('head', [((32, 4), (-4, -4, -8), (8, 8, 8))], (0, 15, -3)),
        part('still', [((0, 0), (-3, -3, -3), (6, 6, 6))], (0, 15, 0)),
        part('body', [((0, 12), (-5, -4, -6), (10, 8, 12))], (0, 15, 9)),
        *_SPIDER_LEGS,
    ],
    width=1.4, height=0.9, health=16, speed=4.0, behavior='spider', attack=2, monster=True,
    drops=[('string', 0, 2), ('spider_eye', 0, 1, 0.33)], sound='spider')

# ---- more creatures -----------------------------------------------------------------------

WOLF = MobType(
    'wolf', 'Wolf', {'main': 'wolf.png', 'tame': 'wolf_tame.png', 'angry': 'wolf_angry.png'},
    parts=[
        part('head', [((0, 0), (-3, -3, -2), (6, 6, 4)), ((16, 14), (-3, -5, 0), (2, 2, 1)),
                      ((16, 14), (1, -5, 0), (2, 2, 1)), ((0, 10), (-1.5, 0, -5), (3, 3, 4))], (0, 11.5, -7)),
        part('body', [((18, 14), (-4, -2, -3), (6, 9, 6))], (0, 13, 2), rotate_x=90),
        part('body', [((21, 0), (-3, -3, -3), (8, 6, 7))], (0, 14, -3), rotate_x=90),
        part('leg', [((0, 18), (-1, 0, -1), (2, 8, 2))], (-2.5, 16, 7), phase=1),
        part('leg', [((0, 18), (-1, 0, -1), (2, 8, 2))], (0.5, 16, 7), phase=0),
        part('leg', [((0, 18), (-1, 0, -1), (2, 8, 2))], (-2.5, 16, -4), phase=0),
        part('leg', [((0, 18), (-1, 0, -1), (2, 8, 2))], (0.5, 16, -4), phase=1),
        part('still', [((9, 18), (-1, 0, 0), (2, 8, 2))], (-1, 12, 8), rotate_x=-35),
    ],
    width=0.6, height=0.85, health=8, speed=2.6, behavior='wolf', attack=2, drops=[], sound='wolf')

OCELOT = MobType(
    'ocelot', 'Ocelot', {'main': 'ocelot.png'},
    parts=[
        part('head', [((0, 0), (-2.5, -2, -3), (5, 4, 5)), ((0, 24), (-1.5, 0, -4), (3, 2, 2))], (0, 14, -8)),
        part('body', [((20, 0), (-2, -8, -3), (4, 16, 6))], (0, 13, 0), rotate_x=90),
        part('leg', [((40, 0), (-1, 0, -1), (2, 6, 2))], (-1.1, 18, 6), phase=0),
        part('leg', [((40, 0), (-1, 0, -1), (2, 6, 2))], (1.1, 18, 6), phase=1),
        part('leg', [((8, 13), (-1, 0, -1), (2, 10, 2))], (-1.1, 14, -6), phase=1),
        part('leg', [((8, 13), (-1, 0, -1), (2, 10, 2))], (1.1, 14, -6), phase=0),
        part('still', [((0, 15), (-0.5, 0, 0), (1, 8, 1))], (0, 12, 8), rotate_x=-25),
    ],
    width=0.6, height=0.7, health=10, speed=3.2, behavior='skittish', attack=0, drops=[], sound='ocelot')

SQUID = MobType(
    'squid', 'Squid', {'main': 'squid.png'},
    parts=[
        part('body', [((0, 0), (-6, -8, -6), (12, 16, 12))], (0, 16, 0)),
        *[part('leg', [((48, 0), (-1, 0, -1), (2, 18, 2))], (3.2 * __import__('math').cos(i * 3.1416 / 4) * 2, 20,
                                                        3.2 * __import__('math').sin(i * 3.1416 / 4) * 2), phase=i % 2)
          for i in range(8)],
    ],
    width=0.9, height=0.9, health=10, speed=1.1, behavior='swimmer', drops=[('bone', 0, 0)], sound='squid')

SLIME = MobType(
    'slime', 'Slime', {'main': 'slime.png'},
    parts=[
        part('body', [((0, 16), (-4, -8, -4), (8, 8, 8))], (0, 24, 0)),
        part('body', [((0, 0), (-3.3, -7, -3.3), (6.6, 6.6, 6.6), 0.3)], (0, 24, 0)),
    ],
    width=0.8, height=0.8, health=4, speed=2.4, behavior='slime', attack=2, monster=True,
    drops=[('slime_ball', 0, 2)], sound='slime')

VILLAGER = MobType(
    'villager', 'Villager', {'main': 'villager.png'},
    parts=[
        part('head', [((0, 0), (-4, -10, -4), (8, 10, 8)), ((24, 0), (-1, -3, -6), (2, 4, 2))], (0, 0, 0)),
        part('body', [((16, 20), (-4, 0, -3), (8, 12, 6)), ((0, 38), (-4, 0, -3), (8, 18, 6), 0.5)], (0, 0, 0)),
        part('still', [((44, 22), (-8, -2, -2), (4, 8, 4)), ((44, 22), (4, -2, -2), (4, 8, 4)),
                       ((40, 38), (-4, 2, -2), (8, 4, 4))], (0, 3, -1), rotate_x=-43),      # the folded arms
        part('leg', [((0, 22), (-2, 0, -2), (4, 12, 4))], (-2, 12, 0), phase=0),
        part('leg', [((0, 22), (-2, 0, -2), (4, 12, 4))], (2, 12, 0), phase=1),
    ],
    width=0.6, height=1.95, health=20, speed=1.3, behavior='villager', drops=[], sound='villager')

IRON_GOLEM = MobType(
    'iron_golem', 'Iron Golem', {'main': 'iron_golem.png'},
    parts=[
        part('head', [((0, 0), (-4, -12, -5.5), (8, 10, 8)), ((24, 0), (-1, -5, -7.5), (2, 4, 2))], (0, -7, -2)),
        part('body', [((0, 40), (-9, -2, -6), (18, 12, 11)), ((0, 70), (-4.5, 10, -3), (9, 5, 6), 0.5)], (0, -7, 0)),
        part('arm', [((60, 21), (-13, -2.5, -3), (4, 30, 6))], (0, -7, 0), phase=1),
        part('arm', [((60, 58), (9, -2.5, -3), (4, 30, 6))], (0, -7, 0), phase=0),
        part('leg', [((37, 0), (-3.5, -3, -3), (6, 16, 5))], (-4, 11, 0), phase=0),
        part('leg', [((60, 0), (-3.5, -3, -3), (6, 16, 5))], (5, 11, 0), phase=1),
    ],
    width=1.4, height=2.7, health=100, speed=1.6, behavior='golem', attack=8, drops=[('iron_ingot', 3, 5), ('poppy', 0, 2)],
    sound='irongolem')

# ---- the Nether -------------------------------------------------------------------------

_PIGMAN_PARTS = humanoid(((-3, -2, -2), (4, 12, 4)), ((40, 16), (32, 48)), ((-2, 0, -2), (4, 12, 4)), ((0, 16), (16, 48)),
                         ((-1.9, 12, 0), (1.9, 12, 0)))
_PIGMAN_PARTS[0]['boxes'] = [((0, 0), (-5, -8, -4), (10, 8, 8)), ((31, 1), (-2, -4, -5), (4, 4, 1)),
                             ((51, 6), (4.5, -8, -2), (1, 5, 4)), ((39, 6), (-5.5, -8, -2), (1, 5, 4))]
ZOMBIE_PIGMAN = MobType(
    'zombie_pigman', 'Zombie Pigman', {'main': 'zombified_piglin.png'}, parts=_PIGMAN_PARTS,
    width=0.6, height=1.95, health=20, speed=3.2, behavior='pigman', attack=5, monster=True, fire_immune=True,
    drops=[('rotten_flesh', 0, 1), ('gold_nugget', 0, 1), ('gold_ingot', 1, 1, 0.03)], sound='zombie')

MAGMA_CUBE = MobType(
    'magma_cube', 'Magma Cube', {'main': 'magma_cube.png'},
    parts=[part('body', [((24 if i in (2, 3) else 0, {2: 10, 3: 19}.get(i, i)), (-4, -8 + i, -4), (8, 1, 8)) for i in range(8)],
                (0, 24, 0)),
           part('body', [((24, 40), (-2, -6, -2), (4, 4, 4))], (0, 24, 0))],
    width=0.8, height=0.8, health=4, speed=2.6, behavior='slime', attack=3, monster=True, fire_immune=True, splits=True,
    drops=[('magma_cream', 0, 1, 0.3)], sound='slime')

_TENTACLES = [part('still', [((0, 0), (-1, 0, -1), (2, 7 + (i * 3) % 4, 2))], (-5 + (i % 3) * 5, 24, -5 + (i // 3) * 5)) for i in range(9)]
GHAST = MobType(
    'ghast', 'Ghast', {'main': 'ghast.png', 'shooting': 'ghast_shooting.png'},
    parts=[part('still', [((0, 0), (-8, -16, -8), (16, 16, 16))], (0, 24, 0)), *_TENTACLES],
    width=3.6, height=3.6, health=10, speed=1.8, behavior='ghast', monster=True, fire_immune=True, flying=True,
    skin_scale=2.0, scale=4.0, drops=[('ghast_tear', 0, 1), ('gunpowder', 0, 2)], sound='ghast')

def _rod_ring(ring, radius, y_top):
    """Four blaze rods around the middle, as one part that spins."""
    import math
    boxes = []
    for i in range(4):
        angle = math.radians(i * 90 + ring * 25)
        boxes.append(((0, 16), (math.cos(angle) * radius - 1, y_top, math.sin(angle) * radius - 1), (2, 8, 2)))
    return part('orbit', boxes, (0, 24, 0), phase=ring)


BLAZE = MobType(
    'blaze', 'Blaze', {'main': 'blaze.png'},
    parts=[part('head', [((0, 0), (-4, -26, -4), (8, 8, 8))], (0, 24, 0)),
           _rod_ring(0, 9, -20), _rod_ring(1, 7, -14), _rod_ring(2, 5, -8)],
    width=0.6, height=1.8, health=20, speed=2.2, behavior='blaze', monster=True, fire_immune=True, flying=True,
    drops=[('blaze_rod', 0, 1)], sound='blaze')

TYPES = {t.name: t for t in (BLAZE, ZOMBIE_PIGMAN, MAGMA_CUBE, GHAST, PIG, COW, SHEEP, CHICKEN, ZOMBIE, SKELETON, CREEPER, SPIDER, WOLF, OCELOT, SQUID, SLIME,
                             VILLAGER, IRON_GOLEM)}
NETHER_MONSTERS = [ZOMBIE_PIGMAN, MAGMA_CUBE, GHAST]
ANIMALS = [PIG, COW, SHEEP, CHICKEN]
MONSTERS = [ZOMBIE, SKELETON, CREEPER, SPIDER]


PROFESSIONS = {
    'Farmer': [('wheat', 18, 'emerald', 1), ('emerald', 1, 'bread', 4), ('emerald', 1, 'apple', 4), ('emerald', 3, 'cooked_chicken', 6)],
    'Librarian': [('paper', 24, 'emerald', 1), ('emerald', 9, 'bookshelf', 1), ('book', 4, 'emerald', 1), ('emerald', 1, 'glass', 4)],
    'Blacksmith': [('iron_ingot', 4, 'emerald', 1), ('emerald', 5, 'iron_sword', 1), ('emerald', 6, 'iron_pickaxe', 1), ('coal', 16, 'emerald', 1)],
    'Butcher': [('porkchop', 14, 'emerald', 1), ('beef', 14, 'emerald', 1), ('emerald', 1, 'cooked_porkchop', 5), ('emerald', 1, 'cooked_beef', 5)],
}
