"""The six faces of a cube, used to build chunk meshes."""

H = 0.5

# Each face lists its corners as seen from outside: bottom-left, bottom-right,
# top-right, top-left; which texture it uses ('top', 'bottom' or 'side');
# and the direction it faces. The block next to a face is at that direction.
FACES = [
    ([(-H, H, -H), (H, H, -H), (H, H, H), (-H, H, H)], 'top', (0, 1, 0)),
    ([(H, -H, -H), (-H, -H, -H), (-H, -H, H), (H, -H, H)], 'bottom', (0, -1, 0)),
    ([(-H, -H, -H), (H, -H, -H), (H, H, -H), (-H, H, -H)], 'side', (0, 0, -1)),
    ([(H, -H, H), (-H, -H, H), (-H, H, H), (H, H, H)], 'side', (0, 0, 1)),
    ([(H, -H, -H), (H, -H, H), (H, H, H), (H, H, -H)], 'side', (1, 0, 0)),
    ([(-H, -H, H), (-H, -H, -H), (-H, H, -H), (-H, H, H)], 'side', (-1, 0, 0)),
]
