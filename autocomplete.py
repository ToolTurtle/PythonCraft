"""autocomplete - smart Tab completion, argument hints and auto-indent for the live-coding prompt.

Works for plain commands (`placeblock 0 0 0 sto<Tab>`), Python (`fill(0,0,0,3,0,3,'sto<Tab>`, `pc.ob<Tab>`) and :commands.
Used by the terminal prompt (readline) and by the in-game console (the / key)."""
import difflib
import inspect
import keyword
import re

BLOCK_PARAMS = {'id', 'block', 'walls', 'roof', 'floor', 'wall', 'top', 'under', 'base', 'old', 'new'}
FACING = ['north', 'south', 'east', 'west']
VALUES = {('settime', 'when'): ['sunrise', 'morning', 'day', 'sunset', 'night'],
          ('weather', 'kind'): ['clear', 'rain', 'snow', 'storm'],
          ('tree', 'kind'): ['oak', 'birch', 'spruce', 'jungle'],
          ('turtle', 'facing'): FACING, ('door', 'facing'): FACING, ('sign', 'facing'): FACING, ('placeblock', 'facing'): FACING}
FACING_PARAMS = {'facing', 'on', 'door'}
DEDENT_WORDS = ('else', 'elif', 'except', 'finally')
END_WORDS = ('return', 'pass', 'break', 'continue', 'raise')
STATEMENTS = ['for', 'while', 'if', 'def', 'import', 'print', 'range', 'len', 'else:', 'elif', 'True', 'False', 'None']


def rank(token, names, limit=40):
    """Names that start with the token, then names that contain it, then close spellings."""
    low = token.lower()
    names = list(dict.fromkeys(names))
    first = sorted((n for n in names if n.lower().startswith(low)), key=lambda n: (len(n), n))
    if not low:
        return first[:limit]
    second = sorted(n for n in names if low in n.lower() and n not in first)
    third = [] if first or second or len(low) < 3 else difflib.get_close_matches(low, names, n=5, cutoff=0.6)
    return (first + second + third)[:limit]


class Completer:
    def __init__(self, session):
        self.session = session

    # ---- the names ------------------------------------------------------------------------------------------------

    def _blocks(self):
        return ['air'] + [n for n in self.session.pycraft.BLOCKS if not re.search(r'(door_[bt]|_on|_head|_lit)$', n)]

    def _mobs(self):
        from mobtypes import TYPES
        return list(TYPES)

    def _items(self):
        from items import ITEMS
        return list(ITEMS)

    def _plot_methods(self):
        plot = self.session.plot
        return [n for n in dir(plot) if not n.startswith('_') and callable(getattr(plot, n))]

    def _function(self, name):
        """The plot method (or the same name in the prompt) that `name` stands for, or None."""
        if name.startswith(('w.', 'plot.')):
            name = name.split('.', 1)[1]
        method = getattr(self.session.plot, name, None)
        return method if callable(method) and not name.startswith('_') else None

    def _params(self, name):
        method = self._function(name)
        if method is None:
            return []
        try:
            return [p for p in inspect.signature(method).parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        except (TypeError, ValueError):
            return []

    def usage(self, line):
        """`placeblock <x> <y> <z> [id] [facing]` for the command being typed (empty if it is not a command)."""
        text = line.lstrip()
        match = re.match(r'(?:w\.|plot\.)?([A-Za-z_]\w*)', text)
        if not match or text.startswith(':'):
            return ''
        name = match.group(1)
        params = self._params(name)
        if not params:
            return ''
        pieces = []
        for p in params:
            pieces.append(f'[{p.name}]' if p.default is not p.empty else f'<{p.name}>')
        return f'{name} ' + ' '.join(pieces)

    def _role(self, function, index):
        """What the argument number `index` of `function` is: ('block'|'mob'|'item'|'values', names) or None."""
        params = self._params(function)
        if not 0 <= index < len(params):
            return None
        name = params[index].name
        base = function.split('.')[-1]
        if (base, name) in VALUES:
            return VALUES[(base, name)]
        if base == 'spawnmob' and name == 'name' or base == 'npc' and name == 'kind':
            return self._mobs()
        if base == 'give' and name == 'id':
            return self._items()
        if name in BLOCK_PARAMS:
            return self._blocks()
        if name in FACING_PARAMS:
            return FACING
        return None

    # ---- what to complete ---------------------------------------------------------------------------------------------

    def completions(self, line, force=False):
        """(start, candidates): the word that begins at line[start:] could be any of the candidates.
        Without force, short or empty words give nothing (used for hints while typing)."""
        stripped = line.lstrip()
        if stripped.startswith(':') and ' ' not in stripped:
            token = stripped
            start = len(line) - len(stripped)
            return start, rank(token, [':' + c for c in self.session.commands])
        if stripped.startswith(':'):
            word, _, rest = stripped[1:].partition(' ')
            if word == 'blocks':
                token = re.search(r'\S*$', line).group()
                return len(line) - len(token), rank(token, self._blocks())
            return len(line), []
        # inside quotes?  fill(0, 0, 0, 3, 0, 3, 'sto
        quotes = [m.start() for m in re.finditer(r'[\'"]', line)]
        if len(quotes) % 2 == 1:
            start = quotes[-1] + 1
            token = line[start:]
            function, index = self._call_context(line[:quotes[-1]])
            names = self._role(function, index) if function else None
            if names is None:
                names = self._blocks() + self._mobs()
            return start, rank(token, names)
        match = re.search(r'[\w.]*$', line)
        token, start = match.group(), match.start()
        before = line[:start]
        # a plain command:  placeblock 0 0 0 sto
        words = before.split()
        if words and not any(c in before for c in '([{=') and self._function(words[0]) is not None and not before.endswith(('.', ',')):
            names = self._role(words[0], len(words) - 1)
            if names is not None:
                if not token and not force and len(names) > 12:
                    return start, names[:0]
                return start, rank(token, names)
            return start, []
        # a call being written:  fill(0, 0, 0, 3, 0, 3, sto
        function, index = self._call_context(before)
        if function:
            names = self._role(function, index)
            if names is not None and token and '.' not in token:
                if token.startswith('pc'):
                    return start, rank(token, self._namespace_names())
                return start, [f"'{n}'" for n in rank(token, names)]
        # a dotted name:  pc.ob   w.fi
        if '.' in token:
            head, _, tail = token.rpartition('.')
            return start, [f'{head}.{n}' for n in rank(tail, self._attributes(head))]
        # the start of a statement or an expression
        if not token and not force:
            return start, []
        names = self._namespace_names()
        if not before.strip():
            names = names + list(self.session.commands) + STATEMENTS
        return start, rank(token, names)

    def _call_context(self, text):
        """The function being called at the end of `text` and the number of the argument being written: ('fill', 6)."""
        depth, commas, position = 0, [], None
        for i in range(len(text) - 1, -1, -1):
            c = text[i]
            if c in ')]}':
                depth += 1
            elif c in '([{':
                if depth == 0:
                    position = i
                    break
                depth -= 1
            elif c == ',' and depth == 0:
                commas.append(i)
        if position is None:
            return None, 0
        match = re.search(r'([A-Za-z_][\w.]*)\s*$', text[:position])
        return (match.group(1), len(commas)) if match else (None, 0)

    def _namespace_names(self):
        return [n for n in self.session.namespace if not n.startswith('_')]

    def _attributes(self, path):
        """The names after the dot, for simple names like pc or w (nothing is run: only attributes are looked up)."""
        if not re.fullmatch(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*', path):
            return []
        parts = path.split('.')
        obj = self.session.namespace.get(parts[0])
        if obj is None:
            return []
        for part in parts[1:]:
            obj = getattr(obj, part, None)
            if obj is None:
                return []
        names = [n for n in dir(obj) if not n.startswith('_')]
        if obj is self.session.pycraft:                       # pc.stone, pc.golem... (not listed by dir)
            names += self._blocks() + self._mobs()
        return names

    # ---- Tab ---------------------------------------------------------------------------------------------------------------

    def _suffix(self, line, start, candidate):
        """What follows a finished argument inside a Python call: the closing quote, then `, ` (more arguments to come) or `)`."""
        quotes = [m.start() for m in re.finditer(r'[\'"]', line[:start + 1] if start < len(line) else line)]
        inside = line[start - 1:start] in ('"', "'") and len([m for m in re.finditer(r'[\'"]', line[:start])]) % 2 == 1
        quote = line[start - 1] if inside else ''
        quoted_form = candidate.startswith("'")
        before = line[:start - 1] if inside else line[:start]
        function, index = self._call_context(before)
        if not function or not (inside or quoted_form or candidate.startswith('pc.')):
            return ''
        params = self._params(function)
        if not params:
            return quote
        more = index + 1 < len(params)
        return quote + (', ' if more else ')')

    def tab(self, line, state=None):
        """The line after pressing Tab, and the state to give back for the next Tab: a single match is completed, several
        matches are completed as far as they agree, and pressing Tab again goes through them one by one."""
        if state and state['shown'] == line:
            index = (state['index'] + 1) % len(state['candidates'])
            new = state['base'] + state['candidates'][index] + state['suffix']
            return new, dict(state, index=index, shown=new)
        start, candidates = self.completions(line, force=True)
        if not candidates:
            return line, None
        token = line[start:]
        base = line[:start]
        suffix = self._suffix(line, start, candidates[0])
        if len(candidates) == 1:
            return base + candidates[0] + suffix, None
        common = _common_prefix(candidates)
        if len(common) > len(token):
            new = base + common
            return new, {'base': base, 'candidates': candidates, 'index': -1, 'shown': new, 'suffix': suffix}
        new = base + candidates[0] + suffix
        return new, {'base': base, 'candidates': candidates, 'index': 0, 'shown': new, 'suffix': suffix}

    def hint(self, line):
        """Two short lines for under the prompt: how the command is written, and what could come next."""
        usage = self.usage(line).replace('<', '').replace('>', '')      # (the game's text treats <...> as markup)
        start, candidates = self.completions(line)
        shown = '   '.join(c.strip("'") if c.startswith("'") else c for c in candidates[:8])
        if len(candidates) > 8:
            shown += f'   (+{len(candidates) - 8})'
        return usage, shown

    # ---- indent --------------------------------------------------------------------------------------------------------------

    def indent_for(self, buffer):
        """The spaces the next line of an unfinished block should start with."""
        if not buffer:
            return ''
        last = buffer[-1]
        base = len(last) - len(last.lstrip())
        stripped = last.strip()
        if stripped.endswith(':') and not stripped.startswith('#'):
            base += 4
        elif stripped.split(' ')[0].rstrip(':') in END_WORDS:
            base = max(0, base - 4)
        return ' ' * base

    def fix_indent(self, buffer, line):
        """Add the block's indent to a line typed without any; step back for else/elif/except/finally."""
        indent = self.indent_for(buffer)
        if not buffer or not line.strip():
            return line
        first = line.strip().split(' ')[0].rstrip(':')
        typed = line[:len(line) - len(line.lstrip())]
        if first in DEDENT_WORDS and typed in ('', indent):
            return ' ' * max(0, len(indent) - 4) + line.strip()
        if not typed:
            return indent + line
        return line


def _common_prefix(names):
    first, last = min(names), max(names)
    i = 0
    while i < len(first) and i < len(last) and first[i] == last[i]:
        i += 1
    return first[:i]
