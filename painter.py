"""painter - a small picture painter for your mod's blocks, items and creature skins.

    python3 painter.py snad.png                    open snad.png (or start a new 16 x 16 picture)
    python3 painter.py snad.png --like sand        start from a copy of the sand block's picture
    python3 painter.py golem.png --skin golem      start from a creature's skin (paint it, then use it with .texture())
    python3 painter.py snad.png --size 32          a bigger new picture

At the live-coding prompt:  paint snad.png --like sand   (the painter opens in its own window).

Mouse: left button paints, right button picks a colour from the picture.
Keys:  P pencil   E eraser   F fill   L lighter   D darker   M mirror on/off   T tiles on/off
       Ctrl+Z undo   Ctrl+Shift+Z redo   Ctrl+S save   (or the buttons)"""
import argparse
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
MAX_SIZE = 256

PALETTE = ['#000000', '#3b3b3b', '#7a7a7a', '#b5b5b5', '#ffffff', '#5b3a1a', '#8b5a2b', '#c68e57',
           '#d9c27a', '#e8dca0', '#7b1f1f', '#c02b2b', '#e8592a', '#f2a03d', '#f5d63d', '#a8d63d',
           '#4c9b2b', '#2b6b2b', '#1f4a3a', '#2bb5a8', '#3d9be8', '#2b4fc0', '#1f2b7b', '#7b3dc0',
           '#b56be8', '#e86bc0', '#f5a0c0', '#8b8b5a', '#5a6b8b', '#8b5a6b', '#4a4a2b', '#2b1f1f']


def hex_to_rgba(text, alpha=255):
    text = text.lstrip('#')
    if len(text) != 6:
        raise ValueError(f'{text!r} is not a colour like #aa3355.')
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def rgba_to_hex(color):
    return '#%02x%02x%02x' % tuple(color[:3])


class Picture:
    """The picture being painted, with undo. (All the painting rules live here; the window only draws it.)"""

    def __init__(self, image):
        if image.width > MAX_SIZE or image.height > MAX_SIZE or image.width < 1 or image.height < 1:
            raise ValueError(f'A picture can be 1 to {MAX_SIZE} pixels wide and tall.')
        self.image = image.convert('RGBA')
        self.undo_stack, self.redo_stack = [], []
        self.mirror = False
        self.saved_copy = self.image.copy()

    @property
    def size(self):
        return self.image.size

    @classmethod
    def blank(cls, width=16, height=None):
        return cls(Image.new('RGBA', (width, height or width), (0, 0, 0, 0)))

    @classmethod
    def open(cls, path):
        return cls(Image.open(path))

    def changed(self):
        return self.image.tobytes() != self.saved_copy.tobytes()

    def save(self, path):
        self.image.save(path)
        self.saved_copy = self.image.copy()
        return str(path)

    # ---- undo ----------------------------------------------------------------------------------------------------------

    def checkpoint(self):
        """Call before a stroke: the stroke can then be undone as one step."""
        self.undo_stack.append(self.image.copy())
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.image.copy())
        self.image = self.undo_stack.pop()
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.image.copy())
        self.image = self.redo_stack.pop()
        return True

    # ---- painting ----------------------------------------------------------------------------------------------------------

    def inside(self, x, y):
        return 0 <= x < self.size[0] and 0 <= y < self.size[1]

    def _spots(self, x, y):
        spots = [(x, y)]
        if self.mirror:
            spots.append((self.size[0] - 1 - x, y))
        return [(a, b) for a, b in spots if self.inside(a, b)]

    def paint(self, x, y, color):
        for a, b in self._spots(x, y):
            self.image.putpixel((a, b), tuple(color))

    def erase(self, x, y):
        self.paint(x, y, (0, 0, 0, 0))

    def shade(self, x, y, amount):
        """Make a pixel lighter (amount > 0) or darker (amount < 0)."""
        for a, b in self._spots(x, y):
            r, g, b_, alpha = self.image.getpixel((a, b))
            if alpha == 0:
                continue
            self.image.putpixel((a, b), tuple(max(0, min(255, c + amount)) for c in (r, g, b_)) + (alpha,))

    def line(self, x0, y0, x1, y1, action):
        """Do `action(x, y)` on every pixel from one point to another (so a fast mouse leaves no gaps)."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            action(x0, y0)
            if (x0, y0) == (x1, y1):
                return
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    def fill(self, x, y, color):
        """Paint the whole area of one colour that touches (x, y)."""
        if not self.inside(x, y):
            return 0
        target, color = self.image.getpixel((x, y)), tuple(color)
        if target == color:
            return 0
        pixels, count, todo = self.image.load(), 0, [(x, y)]
        while todo:
            a, b = todo.pop()
            if not self.inside(a, b) or pixels[a, b] != target:
                continue
            pixels[a, b] = color
            count += 1
            todo += [(a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)]
        return count

    def pick(self, x, y):
        return self.image.getpixel((x, y)) if self.inside(x, y) else None

    def flip(self, vertical=False):
        self.checkpoint()
        self.image = self.image.transpose(Image.FLIP_TOP_BOTTOM if vertical else Image.FLIP_LEFT_RIGHT)

    def clear(self):
        self.checkpoint()
        self.image = Image.new('RGBA', self.size, (0, 0, 0, 0))

    def common_colors(self, count=12):
        """The colours used most in the picture (to paint more of the same)."""
        load = self.image.load()
        pixels = Counter(load[x, y] for x in range(self.size[0]) for y in range(self.size[1]) if load[x, y][3] > 0)
        return [p for p, _ in pixels.most_common(count)]


# ---- starting pictures ------------------------------------------------------------------------------------------------

def starting_picture(path, like=None, skin=None, size=16):
    """Open the file if it exists; otherwise a copy of a block's picture (like=), a creature's skin (skin=) or a blank one."""
    path = Path(path)
    if path.is_file():
        return Picture.open(path)
    sys.path.insert(0, str(HERE))
    if like:
        import mods
        mods.export_texture(like, str(path))
        return Picture.open(path)
    if skin:
        import mods
        mods.export_skin(skin, str(path))
        return Picture.open(path)
    return Picture.blank(size)


# ---- the window -----------------------------------------------------------------------------------------------------------

def bind_shortcuts(root, save, undo, redo):
    """Ctrl+S, Ctrl+Z and Ctrl+Shift+Z (and Command on a Mac, a name that Linux and Windows do not know)."""
    import tkinter as tk
    for prefix in ('Control', 'Command'):
        try:
            root.bind(f'<{prefix}-s>', save)
            root.bind(f'<{prefix}-z>', undo)
            root.bind(f'<{prefix}-Z>', redo)
        except tk.TclError:
            pass


def run(path, like=None, skin=None, size=16, close_after=None):
    import tkinter as tk
    from tkinter import colorchooser, messagebox
    from PIL import ImageTk

    path = Path(path)
    if path.suffix.lower() != '.png':
        path = path.with_suffix('.png')
    picture = starting_picture(path, like, skin, size)
    width, height = picture.size
    zoom = max(4, min(32, 512 // max(width, height)))

    root = tk.Tk()
    root.title(f'painter - {path.name}')
    state = {'tool': 'pencil', 'color': (60, 60, 60, 255), 'last': None, 'tiles': True, 'photo': None, 'tile_photo': None}

    left = tk.Frame(root)
    left.pack(side='left', padx=8, pady=8)
    canvas = tk.Canvas(left, width=width * zoom, height=height * zoom, highlightthickness=1, highlightbackground='#444', cursor='crosshair')
    canvas.pack()
    status = tk.Label(left, text='', anchor='w', font='TkFixedFont')
    status.pack(fill='x')
    right = tk.Frame(root)
    right.pack(side='left', padx=8, pady=8, anchor='n')

    def checker(w, h, cell):
        image = Image.new('RGBA', (w, h), (200, 200, 200, 255))
        for cy in range(0, h, cell):
            for cx in range(0, w, cell):
                if (cx // cell + cy // cell) % 2:
                    image.paste((160, 160, 160, 255), (cx, cy, cx + cell, cy + cell))
        return image

    background = checker(width * zoom, height * zoom, max(4, zoom // 2))
    tile_label = tk.Label(right)

    def redraw():
        big = picture.image.resize((width * zoom, height * zoom), Image.NEAREST)
        shown = Image.alpha_composite(background, big)
        state['photo'] = ImageTk.PhotoImage(shown)
        canvas.delete('all')
        canvas.create_image(0, 0, image=state['photo'], anchor='nw')
        if zoom >= 8:
            for i in range(1, width):
                canvas.create_line(i * zoom, 0, i * zoom, height * zoom, fill='#777777', stipple='gray25')
            for j in range(1, height):
                canvas.create_line(0, j * zoom, width * zoom, j * zoom, fill='#777777', stipple='gray25')
        if state['tiles']:
            tiles = Image.new('RGBA', (width * 3, height * 3))
            for i in range(3):
                for j in range(3):
                    tiles.paste(picture.image, (i * width, j * height))
            scale = max(1, 96 // max(width, height))
            tiles = tiles.resize((width * 3 * scale, height * 3 * scale), Image.NEAREST)
            state['tile_photo'] = ImageTk.PhotoImage(Image.alpha_composite(checker(tiles.width, tiles.height, 8), tiles))
            tile_label.configure(image=state['tile_photo'])
            tile_label.pack(pady=4)
        else:
            tile_label.pack_forget()
        title = f'painter - {path.name}' + (' *' if picture.changed() else '')
        root.title(title)
        swatch.configure(bg=rgba_to_hex(state['color']))
        tool_label.configure(text=f"tool: {state['tool']}" + ('   mirror' if picture.mirror else ''))

    def cell(event):
        return event.x // zoom, event.y // zoom

    def apply(x, y):
        tool = state['tool']
        if tool == 'pencil':
            picture.paint(x, y, state['color'])
        elif tool == 'eraser':
            picture.erase(x, y)
        elif tool == 'lighter':
            picture.shade(x, y, 12)
        elif tool == 'darker':
            picture.shade(x, y, -12)

    def press(event):
        x, y = cell(event)
        if not picture.inside(x, y):
            return
        picture.checkpoint()
        if state['tool'] == 'fill':
            picture.fill(x, y, state['color'])
            if picture.mirror:
                picture.fill(width - 1 - x, y, state['color'])
        else:
            apply(x, y)
            state['last'] = (x, y)
        redraw()

    def drag(event):
        x, y = cell(event)
        if state['tool'] == 'fill' or state['last'] is None:
            return
        x, y = max(0, min(width - 1, x)), max(0, min(height - 1, y))
        picture.line(*state['last'], x, y, apply)
        state['last'] = (x, y)
        redraw()

    def release(event):
        state['last'] = None

    def pick(event):
        found = picture.pick(*cell(event))
        if found and found[3] > 0:
            state['color'] = found
            state['tool'] = 'pencil' if state['tool'] in ('eraser', 'fill') else state['tool']
            redraw()

    def motion(event):
        x, y = cell(event)
        found = picture.pick(x, y)
        status.configure(text=f'x {x}  y {y}   ' + (rgba_to_hex(found) + ('' if found[3] else ' (see-through)') if found else ''))

    canvas.bind('<Button-1>', press)
    canvas.bind('<B1-Motion>', drag)
    canvas.bind('<ButtonRelease-1>', release)
    canvas.bind('<Button-2>', pick)
    canvas.bind('<Button-3>', pick)
    canvas.bind('<Motion>', motion)

    def set_tool(name):
        state['tool'] = name
        redraw()

    def set_color(color):
        state['color'] = tuple(color)
        if state['tool'] in ('eraser', 'lighter', 'darker'):
            state['tool'] = 'pencil'
        redraw()

    def choose():
        chosen = colorchooser.askcolor(color=rgba_to_hex(state['color']), parent=root)[1]
        if chosen:
            set_color(hex_to_rgba(chosen))

    def toggle_mirror():
        picture.mirror = not picture.mirror
        redraw()

    def toggle_tiles():
        state['tiles'] = not state['tiles']
        redraw()

    def save(event=None):
        picture.save(path)
        status.configure(text=f'Saved {path}')
        redraw()

    def undo(event=None):
        picture.undo()
        redraw()

    def redo(event=None):
        picture.redo()
        redraw()

    def flip(vertical):
        picture.flip(vertical)
        redraw()

    def clear():
        picture.clear()
        redraw()

    def close_asking():
        if not picture.changed():
            root.destroy()
            return
        answer = messagebox.askyesnocancel('painter', 'Save your picture before closing?', parent=root)
        if answer is None:
            return
        if answer:
            save()
        root.destroy()

    tool_label = tk.Label(right, text='', font='TkFixedFont', anchor='w')
    tool_label.pack(fill='x')
    swatch = tk.Label(right, width=12, height=2, relief='sunken')
    swatch.pack(pady=2)
    palette = tk.Frame(right)
    palette.pack()
    for index, colour in enumerate(PALETTE):
        tk.Button(palette, bg=colour, width=2, height=1, relief='flat', borderwidth=0, highlightthickness=0,
                  command=lambda c=colour: set_color(hex_to_rgba(c))).grid(row=index // 8, column=index % 8, padx=1, pady=1)
    used = tk.Frame(right)
    used.pack(pady=(6, 0))
    tk.Label(used, text='in this picture:', font='TkFixedFont').pack(anchor='w')
    used_row = tk.Frame(used)
    used_row.pack()
    for index, colour in enumerate(picture.common_colors(12)):
        tk.Button(used_row, bg=rgba_to_hex(colour), width=2, relief='flat', borderwidth=0, highlightthickness=0,
                  command=lambda c=colour: set_color(c)).grid(row=0, column=index, padx=1)
    tk.Button(right, text='More colours...', command=choose).pack(fill='x', pady=(6, 2))
    tools = tk.Frame(right)
    tools.pack(fill='x')
    for number, (label, name) in enumerate((('Pencil (P)', 'pencil'), ('Eraser (E)', 'eraser'), ('Fill (F)', 'fill'),
                                           ('Lighter (L)', 'lighter'), ('Darker (D)', 'darker'))):
        tk.Button(tools, text=label, command=lambda n=name: set_tool(n)).grid(row=number // 2, column=number % 2, sticky='ew')
    tk.Button(tools, text='Mirror (M)', command=toggle_mirror).grid(row=2, column=1, sticky='ew')
    more = tk.Frame(right)
    more.pack(fill='x', pady=(6, 0))
    for number, (label, action) in enumerate((('Flip left-right', lambda: flip(False)), ('Flip up-down', lambda: flip(True)),
                                             ('Tiles (T)', toggle_tiles), ('Clear', clear), ('Undo', undo), ('Redo', redo))):
        tk.Button(more, text=label, command=action).grid(row=number // 2, column=number % 2, sticky='ew')
    tk.Button(right, text='Save (Ctrl+S)', command=save, bg='#9be89b').pack(fill='x', pady=(8, 0))

    for key, name in (('p', 'pencil'), ('e', 'eraser'), ('f', 'fill'), ('l', 'lighter'), ('d', 'darker')):
        root.bind(key, lambda event, n=name: set_tool(n))
    root.bind('m', lambda event: toggle_mirror())
    root.bind('t', lambda event: toggle_tiles())
    bind_shortcuts(root, save, undo, redo)
    root.protocol('WM_DELETE_WINDOW', close_asking)
    redraw()
    if close_after:                                             # (used for testing)
        root.after(int(close_after * 1000), root.destroy)
    root.mainloop()
    return str(path)


def open_window(path, like=None, skin=None, size=16, wait=False):
    """Open the painter in its own window (from pc.paint and the prompt). It does not hold up your program unless wait=True."""
    import subprocess
    command = [sys.executable, str(Path(__file__).resolve()), str(path)]
    if like:
        command += ['--like', like]
    if skin:
        command += ['--skin', skin]
    if size != 16:
        command += ['--size', str(size)]
    process = subprocess.Popen(command)
    if wait:
        process.wait()
    return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='painter.py', description='Paint a picture for a mod: a block, an item or a creature skin.')
    parser.add_argument('file', help='the .png to paint (made if it does not exist)')
    parser.add_argument('--like', help='start from a copy of this block\'s picture (like sand)')
    parser.add_argument('--skin', help='start from this creature\'s skin (like golem)')
    parser.add_argument('--size', type=int, default=16, help='the size of a new picture (default 16)')
    parser.add_argument('--close-after', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        run(args.file, args.like, args.skin, args.size, args.close_after)
    except (ValueError, OSError) as error:
        print(f'Could not start the painter: {error}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
