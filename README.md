# Two Player Snake

A two-player snake game for the keyboard, written in Python with [pygame](https://www.pygame.org/).
Two snakes share one board and fight for the apples, with special moves, a computer opponent
and best-of-3 / best-of-5 matches.

![Start menu](screenshots/menu.png)

![Gameplay](screenshots/gameplay.png)

![Round over](screenshots/round_over.png)

## Features

- **Two players on one keyboard**, or play **against the computer** (Easy / Normal / Hard)
- **Best of 3 / best of 5 matches**, or a single co-op game
- **Special moves** for both snakes: freeze, ice, magnet, lollies, reverse, ghost mode,
  invisibility, speed modes and more
- **Biting:** run into the other snake's body and you cut it in two. The cut-off part turns into
  **red apples** that either snake can eat
- **Three board sizes** (Classic, Large, Extra large)
- Pause, restart, buffered turns (two quick key presses in one step both count), number-pad support

## Install and run

You need Python 3.8+ and pygame 2.0+ (developed and tested with Python 3.12 and pygame 2.6).

```bash
pip install -r requirements.txt
python main.py
```

Keep `lolly.jpg` in the same folder as `main.py`. (The game still runs without it, and draws
a simple lolly instead.)

## How to play

Pick your options in the start menu (Up/Down to choose, Left/Right to change, Enter to start).

| Setting | Options |
|---|---|
| Mode | 2 players, or vs computer (you play Snake 1 on WASD, or Snake 2 on the arrows) |
| Computer level | Easy, Normal, Hard |
| Apples to win | 5 to 40 |
| Match | Single game, Best of 3, Best of 5 |
| Board | Classic (13 x 18 squares), Large (21 x 20), Extra large (25 x 22) |

The scoreboard shows each snake's length (a new snake starts at 2).

### Rules

- **Versus (best of 3 / 5):** the first snake to reach the target score wins the round. A snake
  that hits a wall or bites itself loses the round. If the two heads collide head-on, the longer
  snake wins (equal length is a draw and the round is replayed). First to win the majority of
  rounds wins the match.
- **Single game (co-op):** *both* snakes must reach the target score to pass. If both crash it's
  game over. The fastest winning time is saved.
- **Biting:** if a snake's head runs into the other snake's visible body, the other snake is cut
  at that point. The part that was cut off turns into red apples (+1 length each for whoever eats
  them; the biter gets the one under its head straight away).
- **Walls and your own body** are deadly. Only squares you can actually see are dangerous.
- A **frozen snake's head can't be run into**: the other snake simply can't enter that square.

### Controls

**Snake 1: W A S D** (pink)

| Key | Move | Details |
|---|---|---|
| `W A S D` | Steer | |
| `F` | Freeze | Freezes Snake 2 for 4 s (15 s cooldown) |
| `L` | Lollies | Ring of 8 lollies around the apple, each worth +1 length (10 s cooldown) |
| `R` | Reverse | Turns your snake round, tail becomes head (12 s cooldown) |
| `H` (hold) | Hide | Your snake turns invisible |
| `O` (hold) | Orange | The apple looks like an orange (5 s energy bar) |
| `G` (hold) | Ghost | Pass through walls and bodies, nothing can hurt you (6 s energy bar). If the energy runs out inside a wall, you crash |

**Snake 2: arrow keys** (purple)

| Key | Move | Details |
|---|---|---|
| Arrow keys | Steer | |
| `M` | Magnet | Pulls the apple up to 3 squares towards you (8 s cooldown) |
| `I` | Ice | Freezes Snake 1 for about 1.6 s (6 s cooldown) |
| `1` | Red mode | 3/4 speed, but **deadly**: if Snake 1 touches you, it dies |
| `2` | Purple mode | Normal speed (default) |
| `3` | Blue mode | Fast, on a 3 s boost bar that refills in about 15 s |

The number-pad digits work as well as the top row.

**Anytime:** `P` pause (the game also pauses if the window loses focus), `Shift` restart,
`Esc` back to the menu, `Enter` for the next round or a rematch, and the on-screen **Aim**
button tells you the target.

### The computer opponent

All three levels head for the apple, the lollies and any red apples lying around.

- **Easy** makes the odd random move, uses its special moves only occasionally, and never bites.
- **Normal** also looks ahead to avoid dead ends, uses its special moves, and bites (and goes
  hunting for a bite nearby) when it can cut off a decent chunk.
- **Hard** plans around free space so it rarely traps itself, uses its special moves all the time,
  and hunts for bites from further away.

The computer never bites a red snake (that would kill it) or a ghosting snake (nothing happens).

## Balance

The numbers (cooldowns, durations, energy bars, speeds) were tuned with thousands of simulated
computer-vs-computer rounds so neither snake has a big built-in advantage. They are plain
constants near the top of `main.py` if you want to tweak them (`FREEZE_DUR`, `REVERSE_CD`,
`BOOST_MAX`, `AI_BITE_NEED`, ...).

## Project layout

```
main.py            the whole game
lolly.jpg          the lolly picture
requirements.txt   Python dependency (pygame)
screenshots/       images used in this README
```

The best single-game time is written to `shortest_time.txt` next to `main.py` (ignored by git).

## Credits

This game started as a Processing sketch (`two_players_snake.pde`) that I created when I was an
undergraduate at Warwick. As a kid and a teenager I watched a lot of the Ultraman series, which is
where I got some of the special moves from, as well as the idea of switching between different
colours.

It was then rewritten in Python with pygame and extended with the menu, matches, computer
opponent, special moves and bigger boards.

## License

See [LICENSE](LICENSE).
