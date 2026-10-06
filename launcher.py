"""launcher - one window to start everything in PythonCraft.

    python3 launcher.py          (or ./pythoncraft.sh on Linux and Mac)

Big tiles: play on your own, join or host a class, tutorial worlds, live coding, the picture painter, the mods folder and a setup check.
Press the number on a tile to start it. The games open in their own windows; what they print shows at the bottom."""
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TEXTURES = HERE / 'assets' / 'textures'

THEME = {'bg': '#15161a', 'panel': '#22252d', 'hover': '#2f333e', 'line': '#343845', 'text': '#f4f4f7', 'muted': '#9ca3b2',
         'log_bg': '#0e0f12', 'good': '#6fd36f', 'warn': '#f0b84a', 'bad': '#ef6b6b'}
FONT_CHOICES = ('Inter', 'Helvetica Neue', 'Ubuntu', 'Cantarell', 'Noto Sans', 'DejaVu Sans', 'Segoe UI', 'Helvetica', 'Arial')
TILE_W, TILE_H = 290, 104


# ---- block icons, drawn from the game's own pictures ---------------------------------------------------------------------------------

def texture(name, fallback, tint=None):
    """A block picture (16 x 16, see-through where it should be) or, if the file is not there, a flat square of the fallback colour."""
    path = TEXTURES / f'{name}.png'
    try:
        image = Image.open(path).convert('RGBA')
    except (OSError, ValueError):
        image = Image.new('RGBA', (16, 16), fallback + (255,))
        draw = ImageDraw.Draw(image)
        for x in range(0, 16, 4):                                   # (a little pattern so the flat colour still looks like a block)
            draw.rectangle((x, 0, x, 15), fill=tuple(min(255, int(c * 1.12)) for c in fallback) + (255,))
    if tint:
        r, g, b = tint
        pixels = image.load()
        for x in range(image.width):
            for y in range(image.height):
                pr, pg, pb, pa = pixels[x, y]
                pixels[x, y] = (pr * r // 255, pg * g // 255, pb * b // 255, pa)
    return image


def shade(image, factor):
    out = image.copy()
    pixels = out.load()
    for x in range(out.width):
        for y in range(out.height):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (int(r * factor), int(g * factor), int(b * factor), a)
    return out


def cube_icon(top, left, right=None, scale=3):
    """An isometric block (seen from above at an angle) made from three 16 x 16 pictures: top, left side, right side."""
    size = 16
    right = right or left
    canvas = Image.new('RGBA', (2 * size, 2 * size), (0, 0, 0, 0))
    faces = (
        (top, (0.5, 1, -size / 2, -0.5, 1, size / 2), 1.0),             # the top: a diamond
        (left, (1, 0, 0, -0.5, 1, -size / 2), 0.82),                    # the left side, a bit darker
        (right, (1, 0, -size, 0.5, 1, -1.5 * size), 0.62),              # the right side, darker still
    )
    for picture, coefficients, brightness in faces:
        face = picture.resize((size, size), Image.NEAREST).transform((2 * size, 2 * size), Image.AFFINE, coefficients, Image.NEAREST)
        mask = face.split()[3].point(lambda a: 255 if a > 100 else 0)
        canvas.paste(shade(face, brightness), (0, 0), mask)
    return canvas.resize((2 * size * scale, 2 * size * scale), Image.NEAREST)


def make_icons():
    """The pictures for the tiles: {name: image}."""
    grass_top = texture('grass_block_top', (96, 160, 64), tint=(112, 184, 72))
    dirt = texture('dirt', (134, 96, 67))
    grass_side = dirt.copy()
    grass_side.paste(grass_top.crop((0, 0, 16, 4)), (0, 0))              # (dirt with a green edge at the top)
    return {
        'play': cube_icon(grass_top, grass_side),
        'host': cube_icon(texture('crafting_table_top', (156, 110, 60)), texture('crafting_table_front', (140, 98, 56)),
                          texture('crafting_table_side', (150, 106, 60))),
        'join': cube_icon(texture('bricks', (150, 80, 70)), texture('bricks', (150, 80, 70))),
        'tutorials': cube_icon(texture('oak_planks', (160, 130, 80)), texture('bookshelf', (130, 100, 60))),
        'live': cube_icon(texture('redstone_lamp_on', (230, 190, 90)), texture('redstone_lamp_on', (230, 190, 90))),
        'paint': cube_icon(texture('white_wool', (235, 235, 235), tint=(238, 96, 112)), texture('white_wool', (235, 235, 235), tint=(238, 96, 112))),
        'mods': cube_icon(texture('tnt_top', (190, 90, 80)), texture('tnt_side', (200, 70, 60))),
        'doctor': cube_icon(texture('diamond_block', (90, 210, 220)), texture('diamond_block', (90, 210, 220))),
    }


# ---- the window -------------------------------------------------------------------------------------------------------------------------

def check_setup(events):
    """(runs on its own thread, and knows only the queue: it must never hold the window) A quick look at the setup: the badge turns green,
    or says how many things need a look."""
    try:
        import doctor
        results = doctor.run_all()
        problems = sum(1 for _title, found in results for status, _t, _h in found if status == doctor.PROBLEM)
        notes = sum(1 for _title, found in results for status, _t, _h in found if status == doctor.NOTE)
    except Exception:                                         # (the badge is a nicety: never let it stop the window)
        return
    if problems:
        text, colour = f'  {problems} thing(s) to fix: click here', THEME['bad']
    elif notes:
        text, colour = f'  setup is fine ({notes} note(s): click to see)', THEME['warn']
    else:
        text, colour = '  everything is set up', THEME['good']
    events.put(('badge', '\u25CF' + text, colour))


def rounded(canvas, x1, y1, x2, y2, radius, **options):
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius, x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2, x1, y2,
              x1, y2 - radius, x1, y1 + radius, x1, y1]
    return canvas.create_polygon(points, smooth=True, **options)


class Tile:
    """One big button: an icon, a name and a line of help. It lights up when the mouse is over it."""

    def __init__(self, parent, label, hint, action, icon, accent, number):
        import tkinter as tk
        self.label, self.hint, self.action, self.accent, self.number, self.icon = label, hint, action, accent, number, icon
        self.canvas = tk.Canvas(parent, width=TILE_W, height=TILE_H, bg=THEME['bg'], highlightthickness=0, cursor='hand2')
        self.hovered = False
        self.canvas.bind('<Enter>', lambda event: self.draw(True))
        self.canvas.bind('<Leave>', lambda event: self.draw(False))
        self.canvas.bind('<ButtonRelease-1>', lambda event: self.invoke() if 0 <= event.x <= TILE_W and 0 <= event.y <= TILE_H else None)
        self.draw(False)

    def draw(self, hover):
        canvas = self.canvas
        self.hovered = hover
        canvas.delete('all')
        rounded(canvas, 2, 2, TILE_W - 2, TILE_H - 2, 14, fill=THEME['hover'] if hover else THEME['panel'], outline=self.accent if hover else THEME['line'], width=2)
        canvas.create_rectangle(2, 22, 7, TILE_H - 22, fill=self.accent, outline=self.accent)           # (the colour stripe)
        if self.icon is not None:
            canvas.create_image(58, TILE_H // 2 + (-3 if hover else 0), image=self.icon)
        canvas.create_text(112, 38, text=self.label, anchor='w', fill=THEME['text'], font=(Launcher.family, 14, 'bold'))
        canvas.create_text(112, 66, text=self.hint, anchor='nw', fill=THEME['muted'], font=(Launcher.family, 10), width=TILE_W - 130)
        canvas.create_text(TILE_W - 14, 16, text=str(self.number), anchor='e', fill=THEME['line'] if not hover else self.accent, font=(Launcher.family, 11, 'bold'))

    def invoke(self):
        self.action()

    def grid(self, **options):
        self.canvas.grid(**options)


class Launcher:
    family = 'Helvetica'

    def __init__(self, root):
        import tkinter as tk
        from tkinter import font as tkfont
        from PIL import ImageTk
        self.tk, self.root = tk, root
        installed = set(tkfont.families(root))
        Launcher.family = next((f for f in FONT_CHOICES if f in installed), 'Helvetica')
        root.title('PythonCraft')
        root.configure(bg=THEME['bg'])
        root.resizable(False, False)
        self.processes = []
        self.events = queue.Queue()                                # (threads leave messages here; only the window's own thread touches the window)
        self.icons = {name: ImageTk.PhotoImage(image) for name, image in make_icons().items()}
        try:
            root.iconphoto(True, ImageTk.PhotoImage(make_icons()['play'].resize((64, 64), Image.NEAREST)))
        except tk.TclError:
            pass

        header = tk.Frame(root, bg=THEME['bg'])
        header.pack(fill='x', padx=26, pady=(20, 4))
        title = tk.Frame(header, bg=THEME['bg'])
        title.pack(side='left')
        tk.Label(title, text='Python', bg=THEME['bg'], fg=THEME['good'], font=(self.family, 34, 'bold')).pack(side='left')
        tk.Label(title, text='Craft', bg=THEME['bg'], fg=THEME['warn'], font=(self.family, 34, 'bold')).pack(side='left')
        self.badge = tk.Label(header, text='  checking your setup...', bg=THEME['bg'], fg=THEME['muted'], font=(self.family, 11), cursor='hand2')
        self.badge.pack(side='right', pady=(14, 0))
        self.badge.bind('<Button-1>', lambda event: self.doctor())
        tk.Label(root, text='Build with blocks, and with code', bg=THEME['bg'], fg=THEME['muted'], font=(self.family, 12), anchor='w').pack(fill='x', padx=30)

        sections = (
            ('PLAY', '#6fd36f', (('Play on my own', 'Walk, mine and build in your own worlds.', self.play, 'play'),
                                 ('Tutorial worlds', 'Walk around worlds that teach you pycraft.', self.tutorials, 'tutorials'),
                                 ('Join a class', "Join your teacher's world on the school network.", self.join, 'join'))),
            ('CREATE', '#f0b84a', (('Live coding', 'Type code, watch it build. Press / in a game.', self.live, 'live'),
                                   ('Paint a picture', 'Make a block picture or a creature skin for a mod.', self.paint, 'paint'),
                                   ('Mods folder', 'Add or remove your mods here.', self.mods_folder, 'mods'))),
            ('TEACH AND SET UP', '#6ab7ff', (('Host a class', 'Plots for everyone: start and run a class.', self.host, 'host'),
                                             ('Check my setup', 'Is everything installed? Can a class connect?', self.doctor, 'doctor'))),
        )
        self.buttons, self.order, number = {}, [], 1
        for heading, accent, entries in sections:
            tk.Label(root, text=heading, bg=THEME['bg'], fg=accent, font=(self.family, 10, 'bold'), anchor='w').pack(fill='x', padx=30, pady=(14, 4))
            row = tk.Frame(root, bg=THEME['bg'])
            row.pack(padx=26)
            for column, (label, hint, action, icon) in enumerate(entries):
                tile = Tile(row, label, hint, action, self.icons[icon], accent, number)
                tile.grid(row=0, column=column, padx=4, pady=3)
                self.buttons[label] = tile
                self.order.append(tile)
                number += 1
        self.log = tk.Text(root, height=7, state='disabled', bg=THEME['log_bg'], fg=THEME['muted'], relief='flat', padx=10, pady=8,
                           font='TkFixedFont', insertbackground=THEME['text'], highlightthickness=1, highlightbackground=THEME['line'])
        self.log.pack(fill='x', padx=30, pady=(18, 4))
        tk.Label(root, text='Press a number to start a tile    Esc to close', bg=THEME['bg'], fg=THEME['line'], font=(self.family, 9)).pack(pady=(0, 12))
        root.bind('<Key>', self.key)
        root.protocol('WM_DELETE_WINDOW', self.close)
        threading.Thread(target=check_setup, args=(self.events,), daemon=True).start()
        self.poll()

    def poll(self):
        """Show what the helper threads left: lines for the log, and the setup badge."""
        try:
            while True:
                kind, *rest = self.events.get_nowait()
                if kind == 'log':
                    self.write(rest[0])
                elif kind == 'badge':
                    self.badge.configure(text=rest[0], fg=rest[1])
        except queue.Empty:
            pass
        try:
            self.root.after(150, self.poll)
        except self.tk.TclError:
            pass                                                   # (the window was closed)

    # ---- the setup badge --------------------------------------------------------------------------------------------------------------


    # ---- the keyboard -----------------------------------------------------------------------------------------------------------------

    def key(self, event):
        if event.keysym == 'Escape':
            self.close()
        elif event.char.isdigit() and 1 <= int(event.char) <= len(self.order):
            self.order[int(event.char) - 1].invoke()

    # ---- running things -----------------------------------------------------------------------------------------------------------------

    def write(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def run(self, words, env=None):
        """Start a program in its own window; what it prints shows at the bottom."""
        process = subprocess.Popen([sys.executable] + [str(w) for w in words], cwd=str(HERE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, env=dict(os.environ, **(env or {})))
        self.processes.append(process)
        self.write(f"started: {' '.join(str(w) for w in words)}\n")

        events, shown = self.events, ' '.join(str(w) for w in words)

        def pump():                                                  # (a thread: it knows only the queue, never the window)
            for line in process.stdout:
                if line.strip() and not line.startswith(('info:', 'set window', 'package_folder', 'asset_folder', 'os:', 'python version',
                                                         'ursina version', 'development mode', 'application successfully', ':', 'Known pipe',
                                                         '(3 aux', '  CocoaGraphics')):
                    events.put(('log', line))
            events.put(('log', f'finished: {shown}\n'))

        threading.Thread(target=pump, daemon=True).start()
        return process

    def play(self):
        self.run(['main.py'])

    def host(self):
        import classtool
        classtool.open_window(parent=self.root)

    def join(self):
        from tkinter import simpledialog
        code = simpledialog.askstring('Join a class', 'The room code (your teacher has it):', parent=self.root)
        if not code:
            return
        name = simpledialog.askstring('Join a class', 'Your name:', parent=self.root, initialvalue=os.environ.get('PYCRAFT_NAME', '')) or 'Player'
        address = simpledialog.askstring('Join a class', "The server's address (leave empty to look for it):", parent=self.root) or ''
        self.run(['lan.py', 'join'] + ([address.strip()] if address.strip() else []) + ['--code', code.strip(), '--name', name.strip()])
        if not address:
            self.write('(looking for a class server on this network... if it finds none, press Join again and type the address)\n')

    def tutorials(self):
        import tutorialworld
        tk = self.tk
        window = tk.Toplevel(self.root, bg=THEME['bg'])
        window.title('Tutorial worlds')
        items = tutorialworld.tutorials()
        if not items:
            tk.Label(window, text='No tutorial worlds here yet (python3 examples/make_tutorials.py makes them).', padx=14, pady=14,
                     bg=THEME['bg'], fg=THEME['text']).pack()
            return
        listbox = tk.Listbox(window, width=72, height=min(15, len(items)), bg=THEME['panel'], fg=THEME['text'], selectbackground='#3a6ea5',
                             relief='flat', highlightthickness=0, font='TkFixedFont')
        for item in items:
            listbox.insert('end', f"  level {item['level']}   {item['name']:22} {item['summary']}")
        listbox.pack(padx=12, pady=10)

        def play():
            picked = listbox.curselection()
            if picked:
                self.run(['tutorialworld.py', 'play', items[picked[0]]['name']])
                window.destroy()

        listbox.bind('<Double-Button-1>', lambda event: play())
        tk.Button(window, text='Walk around it', command=play).pack(pady=(0, 12))

    def live(self):
        self.run(['livecode.py'])
        self.write('(type in the terminal this was started from, or press / in the game window)\n')

    def paint(self):
        from tkinter import simpledialog
        name = simpledialog.askstring('Paint a picture', 'File name (like snad.png):', parent=self.root)
        if not name:
            return
        like = simpledialog.askstring('Paint a picture', 'Start from a copy of this block (like sand), or leave empty:', parent=self.root) or ''
        self.run(['painter.py', name] + (['--like', like.strip()] if like.strip() else []))

    def mods_folder(self):
        folder = HERE / 'mods'
        folder.mkdir(exist_ok=True)
        opener = 'open' if sys.platform == 'darwin' else 'explorer' if sys.platform.startswith('win') else 'xdg-open'
        try:
            subprocess.Popen([opener, str(folder)])
        except OSError:
            self.write(f'The mods folder is {folder}\n')

    def doctor(self):
        import doctor
        tk = self.tk
        window = tk.Toplevel(self.root, bg=THEME['bg'])
        window.title('Check my setup')
        text = tk.Text(window, width=100, height=30, bg=THEME['log_bg'], fg=THEME['text'], relief='flat', padx=12, pady=10, font='TkFixedFont')
        text.pack(padx=10, pady=10)
        text.tag_configure('heading', foreground=THEME['warn'], font=('TkFixedFont', 11, 'bold'))
        for status, colour in ((doctor.OK, THEME['good']), (doctor.NOTE, THEME['warn']), (doctor.PROBLEM, THEME['bad'])):
            text.tag_configure(status, foreground=colour)
        problems = 0
        for title, results in doctor.run_all():
            text.insert('end', f'{title}\n', 'heading')
            for status, line, hint in results:
                text.insert('end', f'  {doctor.LABEL[status]} ', status)
                text.insert('end', f'{line}\n')
                if hint and status != doctor.OK:
                    text.insert('end', f'           -> {hint}\n')
                problems += status == doctor.PROBLEM
            text.insert('end', '\n')
        text.insert('end', 'Everything looks fine.' if not problems else f'{problems} problem(s) to fix (lines marked PROBLEM).', 'ok' if not problems else 'problem')
        text.configure(state='disabled')
        tk.Label(window, text='To test the connection between two computers:  doctor.py listen  here, and  doctor.py reach ADDRESS  on the other.',
                 fg=THEME['muted'], bg=THEME['bg'], wraplength=700).pack(pady=(0, 10))

    def cleanup(self):
        """Let go of the pictures and canvases now, on the window's own thread (Python would otherwise free them whenever it likes, which can
        be on another thread: Tk does not allow that)."""
        for tile in self.order:
            tile.icon = None
            tile.canvas.delete('all')
        self.icons.clear()

    def close(self):
        import gc
        self.cleanup()
        self.root.destroy()
        gc.collect()


def main():
    import tkinter as tk
    root = tk.Tk()
    Launcher(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
