"""A furnace's contents and cooking progress. Each furnace block has one of these."""
from crafting import COOK_TIME, SMELTING, fuel_value
from inventory import Stack

INPUT, FUEL, OUTPUT = 0, 1, 2


class Furnace:
    def __init__(self):
        self.slots = [None, None, None]     # input, fuel, output
        self.burn_left = 0.0                # seconds of fire left from the current fuel
        self.burn_total = 1.0
        self.progress = 0.0                 # seconds spent cooking the current item

    def _result(self):
        """What the input would turn into, if there is room for it."""
        source = self.slots[INPUT]
        if source is None or source.name not in SMELTING:
            return None
        result = SMELTING[source.name]
        out = self.slots[OUTPUT]
        if out is not None and (out.name != result or out.count >= out.max_stack):
            return None
        return result

    @property
    def lit(self):
        return self.burn_left > 0

    def update(self, dt):
        result = self._result()
        if result is not None and self.burn_left <= 0:
            fuel = self.slots[FUEL]
            if fuel is not None and fuel_value(fuel.name) > 0:        # light a new piece of fuel
                self.burn_left = self.burn_total = fuel_value(fuel.name)
                fuel.count -= 1
                if fuel.count <= 0:
                    self.slots[FUEL] = None

        if self.burn_left > 0:
            self.burn_left = max(0.0, self.burn_left - dt)
            if result is not None:
                self.progress += dt
                if self.progress >= COOK_TIME:
                    self.progress = 0.0
                    self.slots[INPUT].count -= 1
                    if self.slots[INPUT].count <= 0:
                        self.slots[INPUT] = None
                    if self.slots[OUTPUT] is None:
                        self.slots[OUTPUT] = Stack(result)
                    else:
                        self.slots[OUTPUT].count += 1
                return
        self.progress = max(0.0, self.progress - dt * 2)               # cools down if nothing is cooking

    def contents(self):
        return [s for s in self.slots if s is not None]
