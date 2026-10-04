"""Building Minecraft-style mob models: boxes painted from a skin texture.

Minecraft models use their own units and axes: 16 units = 1 block, y points
DOWN, and the front of the mob is -z. `convert` turns that into our blocks
(y up, front = +z). Each box takes its picture from the skin using the usual
Minecraft layout:   [top][bottom]
                [right][front][left][back]"""
from ursina import Mesh, Texture
from PIL import Image


def load_skin(path):
    image = Image.open(path).convert('RGBA')
    return Texture(image), image.size


def convert(point):
    """Model units (y down, front -z) -> blocks (y up, front +z)."""
    return (-point[0] / 16, -point[1] / 16, -point[2] / 16)


def _rotate(point, rotation):
    """Turn a point around the x, then y, then z axis (degrees). Used for the body of a four-legged
    animal (which lies on its side) and the splayed legs of a spider."""
    import math
    rx, ry, rz = rotation
    x, y, z = point
    if rx:
        c, s = math.cos(math.radians(rx)), math.sin(math.radians(rx))
        y, z = y * c - z * s, y * s + z * c
    if ry:
        c, s = math.cos(math.radians(ry)), math.sin(math.radians(ry))
        x, z = x * c + z * s, -x * s + z * c
    if rz:
        c, s = math.cos(math.radians(rz)), math.sin(math.radians(rz))
        x, y = x * c - y * s, x * s + y * c
    return (x, y, z)


def _faces(box_origin, size, offset, grow=0):
    """The six faces of a box as (corners, skin region). Corners go top-left,
    top-right, bottom-right, bottom-left as seen from outside. `grow` makes the box bigger
    on every side without changing which part of the skin it uses (for overlay layers)."""
    x0, y0, z0 = box_origin
    w, h, d = size
    x1, y1, z1 = x0 + w + grow, y0 + h + grow, z0 + d + grow
    x0, y0, z0 = x0 - grow, y0 - grow, z0 - grow
    u, v = offset
    return [
        ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (u + d, v + d, w, h)),          # front
        ([(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)], (u + 2 * d + w, v + d, w, h)),  # back
        ([(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)], (u, v + d, d, h)),              # right
        ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (u + d + w, v + d, d, h)),      # left
        ([(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)], (u + d, v, w, d)),              # top
        ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (u + d + w, v, w, d)),          # bottom
    ]


def build_part(boxes, skin_size, rotate_x=0, rotate=(0, 0, 0)):
    """One body part made of boxes. Each box is (offset_in_skin, origin, size) or
    (offset_in_skin, origin, size, grow)."""
    rotation = (rotate_x + rotate[0], rotate[1], rotate[2])
    tw, th = skin_size
    vertices, uvs, normals, quads = [], [], [], []

    for box in boxes:
        offset, origin, size = box[0], box[1], box[2]
        grow = box[3] if len(box) > 3 else 0
        center = tuple(origin[i] + size[i] / 2 for i in range(3))
        center = convert(_rotate(center, rotation))
        for corners, (rx, ry, rw, rh) in _faces(origin, size, offset, grow):
            world = [convert(_rotate(c, rotation)) for c in corners]

            # The direction this face points: away from the middle of the box.
            a, b, c = world[0], world[1], world[3]
            edge1 = [b[i] - a[i] for i in range(3)]
            edge2 = [c[i] - a[i] for i in range(3)]
            normal = (edge1[1] * edge2[2] - edge1[2] * edge2[1],
                      edge1[2] * edge2[0] - edge1[0] * edge2[2],
                      edge1[0] * edge2[1] - edge1[1] * edge2[0])
            if sum(normal[i] * (a[i] - center[i]) for i in range(3)) < 0:
                normal = tuple(-n for n in normal)
            length = sum(n * n for n in normal) ** .5
            normal = tuple(n / length for n in normal)

            first = len(vertices)
            vertices += world
            corner_uvs = [(rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)]
            uvs += [(px / tw, 1 - py / th) for px, py in corner_uvs]   # the picture's top row is v = 1
            normals += [normal] * 4
            quads.append((first, first + 1, first + 2, first + 3))

    return Mesh(vertices=vertices, triangles=quads, uvs=uvs, normals=normals)
