"""Stacks of items and the player's 36-slot inventory (slots 0-8 are the hotbar)."""
import random

from items import ITEMS


class Stack:
    """`count` of one kind of item. Tools also track how worn they are (`damage`)."""
    __slots__ = ('name', 'count', 'damage', 'enchants')

    def __init__(self, name, count=1, damage=0, enchants=None):
        self.name = name
        self.count = count
        self.damage = damage
        self.enchants = dict(enchants) if enchants else {}

    @property
    def item(self):
        return ITEMS[self.name]

    @property
    def max_stack(self):
        return self.item.max_stack

    def copy(self, count=None):
        return Stack(self.name, self.count if count is None else count, self.damage, self.enchants)

    def same_kind_as(self, other):
        return other is not None and other.name == self.name and self.max_stack > 1 and not self.enchants and not other.enchants

    def __repr__(self):
        return f'Stack({self.name!r}, {self.count}, damage={self.damage}' + (f', enchants={self.enchants})' if self.enchants else ')')


HOTBAR_SIZE = 9
SIZE = 36
ARMOR_SLOTS = ('helmet', 'chestplate', 'leggings', 'boots')


class Inventory:
    def __init__(self):
        self.slots = [None] * SIZE
        self.armor = [None] * 4        # worn: helmet, chestplate, leggings, boots
        self.selected = 0
        self.version = 0            # goes up every change, so the screen knows when to redraw

    def changed(self):
        self.version += 1

    @property
    def held(self):
        """The stack in the selected hotbar slot (or None)."""
        return self.slots[self.selected]

    def add(self, name, count=1, damage=0):
        """Put items in the first places that fit. Returns how many did NOT fit."""
        max_stack = ITEMS[name].max_stack
        if max_stack > 1:                                   # top up stacks we already have
            for stack in self.slots:
                if stack is not None and stack.name == name and stack.count < max_stack:
                    moved = min(count, max_stack - stack.count)
                    stack.count += moved
                    count -= moved
                    if count == 0:
                        self.changed()
                        return 0
        for i, stack in enumerate(self.slots):              # then use empty slots
            if stack is None:
                moved = min(count, max_stack)
                self.slots[i] = Stack(name, moved, damage)
                count -= moved
                if count == 0:
                    break
        self.changed()
        return count

    def add_stack(self, stack):
        """Like add(), but for a whole Stack. Returns the leftover count."""
        if stack.enchants:                       # enchanted things never merge: they go in an empty slot
            for i, s in enumerate(self.slots):
                if s is None:
                    self.slots[i] = stack.copy()
                    self.changed()
                    return 0
            return stack.count
        return self.add(stack.name, stack.count, stack.damage)

    def count(self, name):
        return sum(s.count for s in self.slots if s is not None and s.name == name)

    def use_one_held(self):
        """Take one item from the selected slot (placing a block, eating...)."""
        stack = self.held
        if stack is None:
            return
        stack.count -= 1
        if stack.count <= 0:
            self.slots[self.selected] = None
        self.changed()

    def wear_held_tool(self, amount=1):
        """Use up some of the held tool. Returns True if it broke."""
        stack = self.held
        if stack is None or stack.item.tool is None:
            return False
        from enchantments import level_of
        unbreaking = level_of(stack, 'unbreaking')
        if unbreaking and random.random() < unbreaking / (unbreaking + 1):
            return False                         # Unbreaking: the tool often takes no damage
        stack.damage += amount
        broke = stack.damage >= stack.item.tool.durability
        if broke:
            self.slots[self.selected] = None
        self.changed()
        return broke

    def select(self, index):
        self.selected = index % HOTBAR_SIZE
        self.changed()

    def armor_points(self):
        from enchantments import level_of
        return sum(s.item.armor.points + level_of(s, 'protection') for s in self.armor if s is not None)

    def wear_armor(self):
        """Every piece of armor takes a little damage when you are hit."""
        for i, s in enumerate(self.armor):
            if s is not None:
                s.damage += 1
                if s.damage >= s.item.armor.durability:
                    self.armor[i] = None
        self.changed()

    def equip(self, index):
        """Wear the armor in inventory slot `index` (swapping with what is already worn)."""
        stack = self.slots[index]
        if stack is None or stack.item.armor is None:
            return False
        slot = ARMOR_SLOTS.index(stack.item.armor.slot)
        self.slots[index], self.armor[slot] = self.armor[slot], stack
        self.changed()
        return True
