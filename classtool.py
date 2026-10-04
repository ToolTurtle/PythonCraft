"""classtool - the teacher's tool for a class world: design it, start it, look after it.

    python3 classtool.py                          open the window (design the plots, start the class, watch and control it)
    python3 classtool.py window math4.pcclass     open a class you made before

    python3 classtool.py new math4 --roster "Ann, Bo, Cy"       a class setup with a plot for each name  (classes/math4.pcclass)
    python3 classtool.py new math4 --roster names.txt --columns 4 --width 20 --depth 20
    python3 classtool.py show math4.pcclass                      who has which plot
    python3 classtool.py assign math4.pcclass 3 Dee              give plot 3 to Dee   (assign ... 3 -  to make it free)
    python3 classtool.py template math4.pcclass house.pcplot     a starter build that every plot begins with
    python3 classtool.py world math4.pcclass                     build the class world from the setup (a fresh one)
    python3 classtool.py handins math4.pcclass [submissions]     bring each student's newest hand-in into their plot
    python3 classtool.py import math4.pcclass 3 build.pcplot     put a .pcplot into plot 3
    python3 classtool.py export math4.pcclass 3 plot3.pcplot     save what is built in plot 3 (to edit it and import it again)
    python3 classtool.py reset math4.pcclass 3                   empty plot 3 (add --template to put the starter build back)

The commands with a plot number change the class WORLD (lanworlds/NAME.lanworld.json): do them while the server is stopped.
Start the class with  python3 lan.py host --class math4.pcclass  (or the window's Start button)."""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CLASSES = Path(os.environ.get('PYCRAFT_CLASSES') or HERE / 'classes')


def class_path(name_or_path):
    path = Path(name_or_path)
    if path.suffix == '.pcclass' or path.exists():
        return path
    return CLASSES / f'{name_or_path}.pcclass'


def world_file(setup):
    import lan
    return lan.world_path(setup.name)


def open_world(setup, fresh=False):
    """The class world of this setup: the file the server keeps, or a new one built from the setup."""
    from lanserver import WorldState
    path = world_file(setup)
    if path.exists() and not fresh:
        return WorldState.load(path), path
    return setup.build_world(), path


def need_plot(world, number):
    layout = world.layout
    plot = layout.plot_by_id(number) if layout and str(number).isdigit() else None
    if plot is None:
        raise ValueError(f'There is no plot {number}.')
    return plot


# ---- the commands you can type ----------------------------------------------------------------------------------------------------

def run_command(args):
    import classworld
    from classworld import ClassSetup
    from classlayout import clean_roster
    command = args.command
    if command == 'new':
        text = args.roster or ''
        if text and Path(text).is_file():
            text = Path(text).read_text()
        names = clean_roster(text)
        setup = ClassSetup.for_roster(args.name, names, args.width, args.depth, args.gap, args.columns, extra=args.extra, mode=args.mode)
        path = setup.save(CLASSES / f'{args.name}.pcclass')
        print(f'Made {path}: {len(setup.layout.plots)} plots, {len(names)} names.')
        return 0
    setup = ClassSetup.load(class_path(args.file))
    if command == 'show':
        print(f'{setup.name}   (new students start in {setup.mode} mode; students {"may" if setup.self_claim else "may not"} claim a plot)')
        for line in setup.layout.describe():
            print(' ', line)
        print('  starter build:', f'{len(setup.template["blocks"])} blocks' if setup.template else 'none')
        return 0
    if command in ('assign', 'unassign'):
        name = None if command == 'unassign' or args.who in ('-', '') else args.who
        setup.set_owner(int(args.plot), name)
        setup.save(class_path(args.file))
        print(f"Plot {args.plot} is {('for ' + name) if name else 'free'} now (in the setup; use a fresh world to see it: lan.py host --class ... --fresh).")
        return 0
    if command == 'template':
        blocks, facing = classworld.read_pcplot(args.pcplot)
        setup.template = {'blocks': blocks, 'facing': facing}
        setup.save(class_path(args.file))
        print(f'Every plot will start with the {len(blocks)} blocks of {args.pcplot}.')
        return 0
    if command == 'world':
        world = setup.build_world()
        path = world_file(setup)
        world.dirty = True
        world.save(path)
        print(f'Built the class world: {path}')
        return 0
    world, path = open_world(setup)
    if command == 'handins':
        for line in classworld.import_handins(world, args.folder or os.environ.get('PYCRAFT_SUBMISSIONS') or 'submissions', args.challenge):
            print(' ', line)
    elif command == 'import':
        placed, skipped = classworld.import_pcplot(world, need_plot(world, args.plot), args.pcplot)
        print(f'{placed} blocks into plot {args.plot}' + (f' ({skipped} did not fit)' if skipped else '') + '.')
    elif command == 'export':
        print('Wrote', classworld.export_plot(world, need_plot(world, args.plot), args.out))
        return 0
    elif command == 'reset':
        plot = need_plot(world, args.plot)
        classworld.clear(world, plot)
        if args.template and setup.template:
            classworld.paste(world, plot, setup.template['blocks'], setup.template.get('facing'))
        print(f'Plot {args.plot} is empty again' + (' with the starter build.' if args.template and setup.template else '.'))
    world.dirty = True
    world.save(path)
    return 0


# ---- the window -------------------------------------------------------------------------------------------------------------------------

def open_window(path=None, parent=None):
    """The class window: design the plots, start the class, then watch and control it. Returns when the window is closed."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
    import classworld
    import lan
    from classlayout import GROUND, Layout, clean_roster
    from classworld import ClassSetup

    root = tk.Toplevel(parent) if parent else tk.Tk()
    root.title('Class tool')
    state = {'setup': ClassSetup.for_roster('My class', ['Ann', 'Bo', 'Cy', 'Dee']), 'path': None, 'server': None, 'dashboard': None}
    if path:
        state['setup'], state['path'] = ClassSetup.load(path), Path(path)

    left = tk.Frame(root)
    left.pack(side='left', fill='y', padx=8, pady=8)
    right = tk.Frame(root)
    right.pack(side='left', fill='both', expand=True, padx=8, pady=8)

    def row(label, widget_factory):
        frame = tk.Frame(left)
        frame.pack(fill='x', pady=1)
        tk.Label(frame, text=label, width=12, anchor='w').pack(side='left')
        widget = widget_factory(frame)
        widget.pack(side='left', fill='x', expand=True)
        return widget

    name_var = tk.StringVar(value=state['setup'].name)
    row('Class name', lambda f: tk.Entry(f, textvariable=name_var))
    tk.Label(left, text='Names (one per line):', anchor='w').pack(fill='x', pady=(6, 0))
    roster_box = tk.Text(left, width=26, height=10)
    roster_box.pack(fill='x')
    columns_var, width_var, depth_var, gap_var, extra_var = (tk.StringVar(value=v) for v in ('4', '16', '16', '5', '2'))
    for label, var in (('Plots across', columns_var), ('Plot width', width_var), ('Plot depth', depth_var), ('Path width', gap_var),
                       ('Spare plots', extra_var)):
        row(label, lambda f, v=var: tk.Spinbox(f, from_=1, to=128, textvariable=v, width=6))
    mode_var = tk.StringVar(value=state['setup'].mode)
    row('New players', lambda f: ttk.Combobox(f, textvariable=mode_var, values=('adventure', 'survival', 'creative', 'spectator'), state='readonly'))
    claim_var = tk.BooleanVar(value=state['setup'].self_claim)
    tk.Checkbutton(left, text='Students may /claim a free plot', variable=claim_var).pack(anchor='w')
    template_label = tk.Label(left, text='', anchor='w', fg='#555')
    template_label.pack(fill='x')
    status = tk.Label(left, text='', anchor='w', wraplength=240, justify='left', fg='#333')

    canvas = tk.Canvas(right, width=620, height=460, bg='#8bbf6a', highlightthickness=1, highlightbackground='#444')
    canvas.pack(fill='both', expand=True)
    selected = {'plot': None}

    def say(text):
        status.configure(text=text)

    def read_form():
        setup = state['setup']
        setup.name = name_var.get().strip() or 'My class'
        setup.mode, setup.self_claim = mode_var.get(), claim_var.get()
        setup.roster = clean_roster(roster_box.get('1.0', 'end'))
        return setup

    def show_form():
        setup = state['setup']
        name_var.set(setup.name)
        roster_box.delete('1.0', 'end')
        roster_box.insert('1.0', '\n'.join(setup.roster))
        mode_var.set(setup.mode)
        claim_var.set(setup.self_claim)
        template_label.configure(text=f'Starter build: {len(setup.template["blocks"])} blocks' if setup.template else 'Starter build: none')
        draw()

    def draw(*_):
        canvas.delete('all')
        layout = state['setup'].layout
        if not layout.plots:
            return
        x1 = min(p.x1 for p in layout.plots) - 4
        z1 = min(p.z1 for p in layout.plots) - 4
        x2 = max(p.x2 for p in layout.plots) + 4
        z2 = max(p.z2 for p in layout.plots) + 4
        width, height = max(canvas.winfo_width(), 200), max(canvas.winfo_height(), 200)
        scale = min((width - 20) / (x2 - x1 + 1), (height - 20) / (z2 - z1 + 1))
        state['map'] = (x1, z1, scale)
        for plot in layout.plots:
            a, b = 10 + (plot.x1 - x1) * scale, 10 + (plot.z1 - z1) * scale
            c, d = 10 + (plot.x2 + 1 - x1) * scale, 10 + (plot.z2 + 1 - z1) * scale
            fill = '#f5e6a8' if plot.owner else '#cfd8dc'
            canvas.create_rectangle(a, b, c, d, fill=fill, outline='#f9a825' if selected['plot'] == plot.id else '#555', width=3 if selected['plot'] == plot.id else 1)
            canvas.create_text((a + c) / 2, (b + d) / 2, text=f'{plot.id}\n{plot.owner or "(free)"}', font=('Helvetica', 10, 'bold'))
        spawn = state['setup'].layout.spawn
        if spawn:
            sx, sy = 10 + (spawn[0] - x1) * scale, 10 + (spawn[2] - z1) * scale
            canvas.create_text(sx, sy, text='start', fill='#1b5e20')

    def plot_at(event):
        if 'map' not in state:
            return None
        x1, z1, scale = state['map']
        return state['setup'].layout.plot_at(int((event.x - 10) / scale + x1), int((event.y - 10) / scale + z1))

    def click(event):
        plot = plot_at(event)
        selected['plot'] = plot.id if plot else None
        if plot is not None:
            name = simpledialog.askstring('Plot', f'Who gets plot {plot.id}? (leave empty for nobody)', initialvalue=plot.owner or '', parent=root)
            if name is not None:
                state['setup'].set_owner(plot.id, name.strip() or None)
                show_form()
        draw()

    canvas.bind('<Button-1>', click)
    canvas.bind('<Configure>', draw)

    def make_plots():
        setup = read_form()
        try:
            columns, width, depth, gap, extra = (int(v.get()) for v in (columns_var, width_var, depth_var, gap_var, extra_var))
            fresh = ClassSetup.for_roster(setup.name, setup.roster, width, depth, gap, columns, extra=extra, mode=setup.mode)
        except ValueError as error:
            messagebox.showerror('Class tool', str(error), parent=root)
            return
        setup.layout = fresh.layout
        show_form()
        say(f'{len(setup.layout.plots)} plots made, one for each name.')

    def save():
        setup = read_form()
        target = state['path'] or filedialog.asksaveasfilename(parent=root, initialdir=str(CLASSES), initialfile=f'{setup.name}.pcclass',
                                                               defaultextension='.pcclass', filetypes=[('Class setup', '*.pcclass')])
        if not target:
            return None
        state['path'] = setup.save(target)
        say(f"Saved {state['path']}")
        return state['path']

    def open_file():
        chosen = filedialog.askopenfilename(parent=root, initialdir=str(CLASSES), filetypes=[('Class setup', '*.pcclass')])
        if chosen:
            try:
                state['setup'], state['path'] = ClassSetup.load(chosen), Path(chosen)
            except ValueError as error:
                messagebox.showerror('Class tool', str(error), parent=root)
                return
            show_form()

    def choose_template():
        chosen = filedialog.askopenfilename(parent=root, title='A build to start every plot with', filetypes=[('pycraft plot', '*.pcplot')])
        if chosen:
            try:
                blocks, facing = classworld.read_pcplot(chosen)
            except (ValueError, OSError) as error:
                messagebox.showerror('Class tool', str(error), parent=root)
                return
            state['setup'].template = {'blocks': blocks, 'facing': facing}
            show_form()

    def with_world(action, remember=True):
        """Do something to the class world file (not while the class is running)."""
        if state['server'] is not None:
            messagebox.showinfo('Class tool', 'Stop the class first: it is running.', parent=root)
            return
        setup = read_form()
        world, world_path = open_world(setup)
        message = action(world, setup)
        world.dirty = True
        world.save(world_path)
        say(message)

    def chosen_plot(world):
        if selected['plot'] is None:
            raise ValueError('Click a plot first.')
        return need_plot(world, selected['plot'])

    def do_handins():
        folder = filedialog.askdirectory(parent=root, title='The submissions folder', initialdir=str(Path('submissions').resolve()))
        if folder:
            with_world(lambda world, setup: '\n'.join(classworld.import_handins(world, folder)))

    def do_import():
        def action(world, setup):
            plot = chosen_plot(world)
            chosen = filedialog.askopenfilename(parent=root, title=f'A .pcplot for plot {plot.id}', filetypes=[('pycraft plot', '*.pcplot')])
            if not chosen:
                return 'Nothing imported.'
            placed, skipped = classworld.import_pcplot(world, plot, chosen)
            return f'{placed} blocks into plot {plot.id}' + (f' ({skipped} did not fit)' if skipped else '') + '.'
        try_world(action)

    def do_export():
        def action(world, setup):
            plot = chosen_plot(world)
            target = filedialog.asksaveasfilename(parent=root, initialfile=f'plot{plot.id}.pcplot', defaultextension='.pcplot')
            return f'Wrote {classworld.export_plot(world, plot, target)}' if target else 'Nothing exported.'
        try_world(action)

    def do_reset():
        def action(world, setup):
            plot = chosen_plot(world)
            if not messagebox.askyesno('Class tool', f'Empty plot {plot.id}? (what is built there is removed)', parent=root):
                return 'Nothing changed.'
            classworld.clear(world, plot)
            if setup.template:
                classworld.paste(world, plot, setup.template['blocks'], setup.template.get('facing'))
            return f'Plot {plot.id} is empty again.'
        try_world(action)

    def try_world(action):
        try:
            with_world(action)
        except (ValueError, OSError) as error:
            messagebox.showerror('Class tool', str(error), parent=root)

    def start():
        setup = read_form()
        if state['path'] is None and save() is None:
            return
        state['path'] = setup.save(state['path'])
        args = argparse.Namespace(class_file=str(state['path']), world=None, plot=None, seed=None, fresh=False, mode=None, pin=None, code=None,
                                  port=25570, bind='0.0.0.0', max=40, name=setup.name, badwords=None, play=None)
        try:
            server, where = lan.start_server(args)
        except (OSError, ValueError) as error:
            messagebox.showerror('Class tool', f'Could not start the class: {error}', parent=root)
            return
        state['server'] = server
        say(f'The class is running. Room code {server.code}, teacher PIN {server.pin}.')
        state['dashboard'] = Dashboard(root, server, on_stop=lambda: state.update(server=None, dashboard=None))

    buttons = tk.Frame(left)
    buttons.pack(fill='x', pady=6)
    for number, (label, action) in enumerate((('Make plots for the names', make_plots), ('Choose starter build...', choose_template), ('Open...', open_file),
                                             ('Save', save), ('Bring in hand-ins...', do_handins), ('Import .pcplot into plot...', do_import),
                                             ('Export plot...', do_export), ('Empty plot', do_reset))):
        tk.Button(buttons, text=label, command=action).grid(row=number // 2, column=number % 2, sticky='ew', padx=1, pady=1)
    buttons.columnconfigure(0, weight=1)
    buttons.columnconfigure(1, weight=1)
    tk.Button(left, text='Start the class', command=start, bg='#9be89b', height=2).pack(fill='x', pady=(4, 2))
    status.pack(fill='x')
    tk.Label(right, text='Click a plot to give it to someone. A yellow edge marks the plot the buttons on the left work on.', anchor='w',
             fg='#555').pack(fill='x')

    def close():
        if state['server'] is not None and not messagebox.askyesno('Class tool', 'The class is running. Stop it and close?', parent=root):
            return
        if state['server'] is not None:
            state['server'].stop()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', close)
    show_form()
    if parent is None:
        root.mainloop()
    return root


class Dashboard:
    """The running class: room code and PIN, who is here, and the teacher's controls (the same commands as /mode, /freeze and so on)."""

    def __init__(self, parent, server, on_stop=None):
        import tkinter as tk
        from tkinter import ttk
        self.server, self.on_stop, self.tk = server, on_stop, tk
        self.window = tk.Toplevel(parent)
        self.window.title(f'Class running: {server.name}')
        top = tk.Frame(self.window)
        top.pack(fill='x', padx=8, pady=6)
        addresses = ', '.join(__import__('lan').local_ips())
        tk.Label(top, text=f'Room code:  {server.code}', font=('Helvetica', 16, 'bold')).pack(anchor='w')
        tk.Label(top, text=f'Teacher PIN:  {server.pin}', font=('Helvetica', 16, 'bold')).pack(anchor='w')
        tk.Label(top, text=f'Students:  python3 lan.py join {addresses} {server.code} --name NAME   (or just:  python3 lan.py join)',
                 fg='#444').pack(anchor='w')
        columns = ('name', 'mode', 'state', 'plot', 'last')
        self.table = ttk.Treeview(self.window, columns=columns, show='headings', height=14, selectmode='extended')
        for column, width in zip(columns, (140, 90, 140, 50, 280)):
            self.table.heading(column, text=column.title() if column != 'last' else 'Last code typed')
            self.table.column(column, width=width, anchor='w')
        self.table.pack(fill='both', expand=True, padx=8)
        controls = tk.Frame(self.window)
        controls.pack(fill='x', padx=8, pady=4)
        for number, (label, template) in enumerate((('Adventure', 'mode adventure {w}'), ('Survival', 'mode survival {w}'), ('Creative', 'mode creative {w}'),
                                                   ('Spectator', 'mode spectator {w}'), ('Freeze', 'freeze {w}'), ('Unfreeze', 'unfreeze {w}'),
                                                   ('Mute', 'mute {w}'), ('Unmute', 'unmute {w}'), ('Code off', 'code off {w}'), ('Code on', 'code on {w}'),
                                                   ('Undo their last 5 min', 'undo {n} 5m'), ('Kick', 'kick {w}'))):
            tk.Button(controls, text=label, command=lambda t=template: self.run_selected(t)).grid(row=number // 6, column=number % 6, sticky='ew', padx=1, pady=1)
        everyone = tk.Frame(self.window)
        everyone.pack(fill='x', padx=8, pady=2)
        for label, command in (('Everyone: adventure', 'mode adventure all'), ('survival', 'mode survival all'), ('creative', 'mode creative all'),
                               ('Lock building', 'lock'), ('Unlock', 'unlock'), ('Chat off', 'chat off'), ('Chat on', 'chat on'),
                               ('Freeze all', 'freeze all'), ('Unfreeze all', 'unfreeze all')):
            tk.Button(everyone, text=label, command=lambda c=command: self.run(c)).pack(side='left', padx=1)
        say = tk.Frame(self.window)
        say.pack(fill='x', padx=8, pady=4)
        self.say_var = tk.StringVar()
        entry = tk.Entry(say, textvariable=self.say_var)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<Return>', lambda event: self.announce())
        tk.Button(say, text='Announce to everyone', command=self.announce).pack(side='left', padx=4)
        tk.Button(say, text='Open the game as teacher', command=self.open_game).pack(side='left', padx=4)
        tk.Button(say, text='Stop the class', command=self.stop, bg='#f4a3a3').pack(side='left')
        self.log = tk.Text(self.window, height=8, state='disabled', bg='#f5f5f5')
        self.log.pack(fill='x', padx=8, pady=6)
        self.message = tk.Label(self.window, text='', anchor='w', fg='#333')
        self.message.pack(fill='x', padx=8)
        self.window.protocol('WM_DELETE_WINDOW', self.stop)
        self.running = True
        self.refresh()

    def run(self, command):
        try:
            self.message.configure(text=' '.join(self.server.operator(command)) or 'Done.')
        except Exception as error:                                     # (a mistake must not stop the dashboard)
            self.message.configure(text=f'{type(error).__name__}: {error}')

    def run_selected(self, template):
        picked = self.table.selection()
        if not picked:
            self.message.configure(text='Pick one or more students in the list first.')
            return
        for item in picked:
            name = self.table.set(item, 'name').replace(' [teacher]', '')
            self.run(template.format(w=f'#{item}', n=name.split(' ')[0]))

    def open_game(self):
        """Start the game in its own window, joined to this class and already a teacher."""
        import subprocess
        env = dict(os.environ, PYCRAFT_TEACHER_PIN=self.server.pin)
        subprocess.Popen([sys.executable, str(HERE / 'lan.py'), 'join', '127.0.0.1', self.server.code, '--name', 'Teacher', '--port', str(self.server.port)],
                         cwd=str(HERE), env=env)
        self.message.configure(text='Opening the game... you are a teacher in it (press P for the class panel).')

    def announce(self):
        text = self.say_var.get().strip()
        if text:
            self.run(f'say {text}')
            self.say_var.set('')

    def refresh(self):
        if not self.running:
            return
        try:
            snapshot = self.server.snapshot()
        except Exception:
            snapshot = None
        if snapshot:
            known = set(self.table.get_children())
            wanted = set()
            for player in snapshot['roster']:
                ident = str(player['id'])
                wanted.add(ident)
                state = ', '.join(s for s, on in (('frozen', player['frozen']), ('muted', player['muted']), ('no code', not player['code'])) if on)
                values = (player['name'] + (' [teacher]' if player['teacher'] else ''), player['mode'], state, player['plot'] or '', player['last'])
                if ident in known:
                    self.table.item(ident, values=values)
                else:
                    self.table.insert('', 'end', iid=ident, values=values)
            for ident in known - wanted:
                self.table.delete(ident)
            self.window.title(f"Class running: {self.server.name}   ({len(snapshot['roster'])} here, building {'LOCKED' if snapshot['locked'] else 'open'}, "
                              f"chat {'on' if snapshot['chat'] else 'OFF'})")
            self.log.configure(state='normal')
            self.log.delete('1.0', 'end')
            self.log.insert('1.0', '\n'.join(snapshot['log'][-12:]))
            self.log.configure(state='disabled')
        self.window.after(1000, self.refresh)

    def stop(self):
        self.running = False
        try:
            self.server.stop()
        finally:
            self.window.destroy()
            if self.on_stop:
                self.on_stop()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='classtool.py', description="The teacher's tool for a class world.")
    sub = parser.add_subparsers(dest='command')
    window = sub.add_parser('window', help='open the window')
    window.add_argument('file', nargs='?')
    new = sub.add_parser('new', help='a class setup with a plot for each name')
    new.add_argument('name')
    new.add_argument('--roster', default='', help='names (a list like "Ann, Bo" or a file with one name per line)')
    new.add_argument('--columns', type=int)
    new.add_argument('--width', type=int, default=16)
    new.add_argument('--depth', type=int, default=16)
    new.add_argument('--gap', type=int, default=5)
    new.add_argument('--extra', type=int, default=2, help='spare plots (default 2)')
    new.add_argument('--mode', default='adventure', choices=('adventure', 'survival', 'creative', 'spectator'))
    for command in ('show', 'world'):
        sub.add_parser(command).add_argument('file')
    assign = sub.add_parser('assign')
    assign.add_argument('file')
    assign.add_argument('plot')
    assign.add_argument('who')
    unassign = sub.add_parser('unassign')
    unassign.add_argument('file')
    unassign.add_argument('plot')
    template = sub.add_parser('template')
    template.add_argument('file')
    template.add_argument('pcplot')
    handins = sub.add_parser('handins')
    handins.add_argument('file')
    handins.add_argument('folder', nargs='?')
    handins.add_argument('--challenge')
    imp = sub.add_parser('import')
    imp.add_argument('file')
    imp.add_argument('plot')
    imp.add_argument('pcplot')
    exp = sub.add_parser('export')
    exp.add_argument('file')
    exp.add_argument('plot')
    exp.add_argument('out')
    reset = sub.add_parser('reset')
    reset.add_argument('file')
    reset.add_argument('plot')
    reset.add_argument('--template', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command in (None, 'window'):
            open_window(class_path(args.file) if getattr(args, 'file', None) else None)
            return 0
        return run_command(args)
    except (ValueError, OSError) as error:
        print(f'Problem: {error}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
