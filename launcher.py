"""launcher - one window to start everything in PythonCraft.

    python3 launcher.py

Buttons: play on your own, host a class (the teacher's tool), join a class, tutorial worlds, live coding, the picture painter,
the mods folder, and a check that everything is set up (doctor). The games open in their own windows; what they print shows at the bottom."""
import os
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


class Launcher:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        root.title('PythonCraft')
        self.processes = []
        tk.Label(root, text='PythonCraft', font=('Helvetica', 22, 'bold')).pack(pady=(10, 0))
        tk.Label(root, text='Build with blocks and with code', fg='#555').pack()
        grid = tk.Frame(root)
        grid.pack(padx=14, pady=10)
        entries = (
            ('Play on my own', 'Walk, mine and build in your own worlds.', self.play),
            ('Host a class', 'Teachers: set up plots for everyone, start the class, watch and control it.', self.host),
            ('Join a class', 'Students: join your teacher\'s world.', self.join),
            ('Tutorial worlds', 'Walk around worlds that teach pycraft.', self.tutorials),
            ('Live coding', 'Type code and watch it build (press / in the game).', self.live),
            ('Paint a picture', 'Make a block picture or a creature skin for a mod.', self.paint),
            ('Mods folder', 'Where your mods live (open it to add or remove some).', self.mods_folder),
            ('Check my setup', 'Is everything installed? Can a class connect?', self.doctor),
        )
        self.buttons = {}
        for number, (label, hint, action) in enumerate(entries):
            frame = tk.Frame(grid)
            frame.grid(row=number // 2, column=number % 2, padx=6, pady=5, sticky='nsew')
            button = tk.Button(frame, text=label, width=24, height=2, command=action, font=('Helvetica', 13, 'bold'))
            button.pack()
            tk.Label(frame, text=hint, wraplength=250, fg='#666', font=('Helvetica', 10)).pack()
            self.buttons[label] = button
        self.log = tk.Text(root, height=9, state='disabled', bg='#f4f4f4')
        self.log.pack(fill='x', padx=14, pady=(0, 10))
        root.protocol('WM_DELETE_WINDOW', self.close)

    # ---- running things --------------------------------------------------------------------------------------------------------

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

        def pump():
            for line in process.stdout:
                if line.strip() and not line.startswith(('info:', 'set window', 'package_folder', 'asset_folder', 'os:', 'python version',
                                                         'ursina version', 'development mode', 'application successfully', ':', 'Known pipe',
                                                         '(3 aux', '  CocoaGraphics')):
                    self.root.after(0, self.write, line)
            self.root.after(0, self.write, f"finished: {' '.join(str(w) for w in words)}\n")

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

    def tutorials(self):
        import tutorialworld
        tk = self.tk
        window = tk.Toplevel(self.root)
        window.title('Tutorial worlds')
        items = tutorialworld.tutorials()
        if not items:
            tk.Label(window, text='No tutorial worlds here yet (python3 examples/make_tutorials.py makes them).', padx=14, pady=14).pack()
            return
        listbox = tk.Listbox(window, width=70, height=min(15, len(items)))
        for item in items:
            listbox.insert('end', f"level {item['level']}   {item['name']:22} {item['summary']}")
        listbox.pack(padx=10, pady=8)

        def play():
            picked = listbox.curselection()
            if picked:
                self.run(['tutorialworld.py', 'play', items[picked[0]]['name']])
                window.destroy()

        listbox.bind('<Double-Button-1>', lambda event: play())
        tk.Button(window, text='Walk around it', command=play).pack(pady=(0, 10))

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
        window = tk.Toplevel(self.root)
        window.title('Check my setup')
        text = tk.Text(window, width=100, height=30)
        text.pack(padx=8, pady=8)
        problems = 0
        for title, results in doctor.run_all():
            text.insert('end', f'{title}\n')
            for status, line, hint in results:
                text.insert('end', f'  {doctor.LABEL[status]} {line}\n')
                if hint and status != doctor.OK:
                    text.insert('end', f'           -> {hint}\n')
                problems += status == doctor.PROBLEM
            text.insert('end', '\n')
        text.insert('end', 'Everything looks fine.' if not problems else f'{problems} problem(s) to fix (lines marked PROBLEM).')
        text.configure(state='disabled')
        tk.Label(window, text='To test the connection between two computers:  python3 doctor.py listen  here, and  python3 doctor.py reach ADDRESS  on the other.',
                 fg='#555', wraplength=700).pack(pady=(0, 8))

    def close(self):
        self.root.destroy()


def main():
    import tkinter as tk
    root = tk.Tk()
    Launcher(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
