# Level 3: Coder

**You will learn:** functions, builds that react to the player, characters and signs, watching your code build live,
the turtle, chance, and sharing. About three lessons. (You should have done Level 2.)

Start every program with:

```python
import pycraft as pc
w = pc.plot(40, 20, 40)
```

and finish with `pc.runplot(w, pc.adventure)` (or `pc.live(w, build)`, see section 3).

## 1. Functions: build once, use many times

```python
def tower(x, z, height):
    w.fill(x, 0, z, x + 2, height - 1, z + 2, 'stone_bricks')
    w.torch(x + 1, height, z + 1)

tower(2, 2, 8)
tower(10, 2, 12)
```

## 2. Make things happen

```python
def hello():
    w.say('Welcome!')

w.onenter(5, 1, 5, hello)              # when the player walks here
w.onclick(3, 1, 3, hello)              # when the player right-clicks the block here (put a block there first)
w.onkey('f', hello)                    # when F is pressed
w.every(10, hello)                     # every 10 seconds
w.goal(26, 1, 26, 'You win!')          # a finish line
```

Inside these functions you can change the world: `w.placeblock(...)`, `w.settime('night')`, `w.weather('storm')`,
`w.give('bread', 3)`, `w.teleport(x, y, z)`, `w.playsound('levelup')`.

## 3. Watch your code run

```python
def build():
    for y in range(10):
        w.placeblock(5, y, 5, 'gold_block')
        pc.wait(0.3)                   # pause so you can watch

pc.live(w, build)                      # the game is open while build() runs (instead of pc.runplot)
```

## 4. Characters, signs and creatures

```python
w.sign(4, 1, 2, ['Welcome to my village!', 'Page two...'])       # click it to read
farmer = w.npc('Farmer', 8, 1, 6, ['Hello!', 'Nice day.'])      # click to talk
pig = w.spawnmob('pig', 3, 1, 3)
pig.walk_to(9, 9)                       # give orders: walk_to, follow, stay, say, onclick
cow = w.spawnmob('cow', 12, 1, 12)
cow.follow()
```

## 5. The turtle

A builder you steer. With the pen down, it builds a block at every step:

```python
t = w.turtle(5, 0, 10, block='bricks')
for side in range(4):
    t.forward(5)
    t.right()                           # turn 90 degrees
```

## 6. Chance and surprises

```python
for x in range(0, 30, 3):
    if w.chance(0.4):                   # 4 times in 10
        w.tree(x, 0, 5, w.choose('oak', 'birch', 'spruce'))
```

## 7. Share and keep your work

```python
w.save('village')                       # village.pcplot: blocks, signs, what characters say, the sky
code = w.share()                        # a block of text a friend can paste into w.loadcode(code)
```

To take a picture of your build for the class gallery: `pc.runplot(w, pc.adventure, gallery='pictures', name='Sam')`,
then press **F2** in the game.

## 8. Challenges

Hand your best build in for your teacher to review: see [Challenges](README_challenges.md). Challenge mode
**levels 9 to 12** are: words, a lever that lights a lamp, making something happen, and a castle.

## Cheat sheet

| | |
|---|---|
| `def name(args):` | make a function |
| `w.onenter / onclick / onkey / every` | react (give the function without brackets) |
| `w.say`, `w.give`, `w.teleport`, `w.playsound` | do things in the game |
| `pc.live(w, build)` and `pc.wait(0.3)` | watch your code build |
| `w.sign`, `w.npc`, `w.spawnmob` + `.walk_to/.follow/.say` | characters |
| `w.turtle(...)`: `.forward .back .up .down .right .left .penup .pendown` | the turtle |
| `w.chance(p)`, `w.choose(...)`, `w.randint(a, b)`, `w.seed(n)` | chance |
| `w.save('x')`, `w.share()` | keep and share |

[Back to the start](../README.md)
