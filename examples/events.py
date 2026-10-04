import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pycraft as pc

# Make your build react: onenter() runs a function when the player walks somewhere,
# onclick() when they right-click a block, onkey() on a key press, every() again and again.
w = pc.plot(24, 12, 24)
w.fill(0, 0, 0, 23, 0, 23, 'grass')
w.house(8, 1, 8, 9, 7, 5)
w.spawnpoint(12, 1, 0)

# 1. a magic block: click it to make a diamond tower
w.placeblock(3, 1, 3, 'gold_block')
height = [1]


def grow():
    height[0] += 1
    w.placeblock(3, height[0], 3, 'diamond_block')
    w.playsound('pop')
    w.say(f'The tower is {height[0]} blocks tall')


w.onclick(3, 1, 3, grow)

# 2. a surprise: walk onto the redstone block
w.placeblock(20, 0, 3, 'redstone_block')


def surprise():
    w.say('Surprise!', 3)
    w.spawnmob('pig', 20, 1, 5)
    w.playsound('levelup')


w.onenter(20, 1, 3, surprise)

# 3. a key: press F to turn the weather around
state = ['clear']


def switch_weather():
    state[0] = 'rain' if state[0] == 'clear' else 'clear'
    w.weather(state[0])


w.onkey('f', switch_weather)

# 4. a timer: the day slowly flickers
w.every(10, lambda: w.say('Ten more seconds have passed...', 2))

pc.runplot(w, pc.adventure, peaceful=True)
