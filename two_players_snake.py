#!/usr/bin/env python3
"""
Two Player Snake  --  Python / pygame port of two_players_snake.pde

Setup:   pip install pygame
Run:     python two_players_snake.py      (keep lolly.jpg in the same folder)

A start menu lets you pick the mode (2 players or vs the computer), the AI level,
how many apples win a round, and the match length (single game / best of 3 / 5).

Snake 1  (W A S D, left side of the keyboard)
    W A S D ...... steer
    F ............ Freeze snake 2 for 4 s (long!)         (15 s cooldown)
    L ............ ring of 8 lollies round the apple      (10 s cooldown)
    R ............ Reverse snake 1                       (3 s cooldown)
    H (hold) ..... invisible
    O (hold) ..... apple looks like an orange            (5 s energy bar)
    G (hold) ..... ghost mode: pass through walls and bodies, nothing can hurt you
                   (6 s energy bar; if it runs out inside a wall, you crash)

Snake 2  (arrow keys, right side of the keyboard)
    Arrows ....... steer
    M ............ Magnet: pull the apple up to 3 squares towards you   (8 s cooldown)
    I ............ Ice: freeze snake 1 for about 1.6 s                 (6 s cooldown)
    1 / 2 / 3 .... speed mode:  1 = red, slow but DEADLY (snake 1 dies if it
                         touches you, body or head-on)
                         2 = purple, normal (default)    3 = blue, fast

A frozen snake's head can't be run into: the other snake simply can't enter that square.

P pause (also pauses if the window loses focus)   Shift restart   Esc menu

Rules
    Single game .. original co-op rules: BOTH snakes must reach the apple target.
    Best of 3/5 .. versus: first snake to reach the target wins the round, a crash
                   loses it. Head-on = longer snake wins.
Turns are buffered: two quick direction presses within one step are both used.
"""

import os
import random
import sys

import pygame

# ---------------------------------------------------------------- constants
WIDTH, HEIGHT = 640, 640
SQ = 32                       # size of one grid square
FPS = 60
PANEL_W = 5 * SQ              # scoreboard panel on the left (fixed width)
COLS, ROWS = WIDTH // SQ, HEIGHT // SQ   # grid size; changed by Game.set_board()
MAX_LEN = 2500
FIELD_CX = (PANEL_W + WIDTH) // 2     # horizontal centre of the playfield

# special-move balancing (frames)
FREEZE_DUR = 4 * FPS          # Freeze (F) holds snake 2 for 4 s ...
FREEZE_CD = 15 * FPS          # ... but takes 15 s to recharge (Ice: 1.6 s / 6 s)
LOLLY_CD = 10 * FPS
REVERSE_CD = 3 * FPS
MAGNET_CD = 8 * FPS
MAGNET_CELLS = 3
ICE_DUR = 96                  # frames snake 2 stays frozen by Ice
ICE_CD = 6 * FPS
ENERGY_MAX = 6 * FPS          # ghost mode
ENERGY_MIN = FPS
ENERGY_REGEN = 0.5
ORANGE_MAX = 5 * FPS          # apple disguise
ORANGE_MIN = FPS // 2
ORANGE_REGEN = 0.5
MAX_QUEUED_TURNS = 2

# board sizes (columns x rows of squares, including the scoreboard panel and walls)
BOARDS = [("Classic", 20, 20), ("Large", 28, 22), ("Extra large", 32, 24)]

# menu options
MODES = ["2 players", "vs computer  (you: Snake 1, WASD)", "vs computer  (you: Snake 2, arrows)"]
AI_LEVELS = ["Easy", "Normal", "Hard"]
WIN_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40]
MATCH_OPTIONS = [("Single game", 1), ("Best of 3", 3), ("Best of 5", 5)]
DEFAULT_SEL = [0, 1, 3, 1, 1] # 2 players, Normal, 20 apples, best of 3, Large board

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BEST_TIME_FILE = os.path.join(BASE_DIR, "shortest_time.txt")

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIME = (155, 240, 0)          # snake heads / scoreboard text
WALL_COL = (175, 227, 214)
ICE = (165, 242, 243)         # frozen snake
PINK = (255, 153, 153)        # snake 2 body
GOLD = (255, 215, 0)          # snake 2 body when ghosted
PURPLE = (204, 0, 204)        # snake 1 body (mode 6)
RED_MODE = (250, 0, 0)        # snake 1 body (mode 3)
BLUE_MODE = (70, 130, 180)    # snake 1 body (mode 1)
PANEL_BG = (26, 30, 38)
MENU_BG = (22, 26, 34)
SOFT = (200, 205, 215)

# NOTE: inside the code "snake 1" is still the arrow-key snake (purple) and "snake 2" the
# WASD snake (pink), as in the original sketch. On screen they are shown the other way
# round (Snake 1 = left player on WASD, Snake 2 = right player on the arrows), so every
# player-facing label goes through Game.name() / the swapped panel below.
# Processing used angles: 0 = right, 90 = up, 180 = left, 270 = down
DIRS = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}

JOHN_KEYS = {pygame.K_j, pygame.K_o, pygame.K_h, pygame.K_n,
             pygame.K_3, pygame.K_1, pygame.K_6}
ENTER_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER)
# number-pad digits count the same as the top-row digits
NUMPAD_DIGITS = {getattr(pygame, f"K_KP{n}"): getattr(pygame, f"K_{n}") for n in range(10)}


def sign(v):
    return (v > 0) - (v < 0)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = None
        self.set_board(20, 20)       # the menu always uses the classic 640x640 window
        pygame.display.set_caption("Two Player Snake")
        self.clock = pygame.time.Clock()
        self._fonts = {}

        self.lolly = self._load_lolly()
        self.best_time = self._load_best_time()

        self.popup = None            # (title, message) while a dialog is open
        self.held = set()            # keys currently held down
        self.hide = False
        self.enhance = False
        self.paused = False

        self.in_menu = True
        self.menu_sel = 0
        self.sel = list(DEFAULT_SEL)
        self.ai = {1: False, 2: False}
        self.ai_level = 1
        self.win_score = 20
        self.match_len = 1
        self.wins = [0, 0]
        self.round_no = 1
        self.match_over = False
        self.round_winner = None
        self.round_reason = ""
        self.restart()

    # ------------------------------------------------------------ resources
    def _load_lolly(self):
        try:
            img = pygame.image.load(os.path.join(BASE_DIR, "lolly.jpg")).convert()
            return pygame.transform.smoothscale(img, (SQ, SQ))
        except (pygame.error, FileNotFoundError):
            surf = pygame.Surface((SQ, SQ))
            surf.fill(WHITE)
            pygame.draw.rect(surf, (240, 150, 190), (8, 2, 16, 18), border_radius=6)
            pygame.draw.rect(surf, (220, 190, 120), (14, 20, 4, 10))
            return surf

    def font(self, size):
        if size not in self._fonts:
            self._fonts[size] = pygame.font.SysFont("arial,helvetica,dejavusans", size)
        return self._fonts[size]

    def _load_best_time(self):
        try:
            with open(BEST_TIME_FILE) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def _record_time(self):
        """Save the time if it's the best so far; returns True for a new record."""
        seconds = self.time // FPS
        if self.best_time is None or seconds < self.best_time:
            self.best_time = seconds
            try:
                with open(BEST_TIME_FILE, "w") as f:
                    f.write(str(seconds))
            except OSError:
                pass
            return True
        return False

    @staticmethod
    def name(n):
        """Player-facing name of internal snake n (the two are shown swapped)."""
        return f"Snake {3 - n}"

    # ----------------------------------------------------------- match flow
    def set_board(self, cols, rows):
        """(Re)size the window. All layout code reads these module globals when it draws."""
        global WIDTH, HEIGHT, COLS, ROWS, FIELD_CX
        if self.screen is not None and (cols, rows) == (COLS, ROWS) \
                and (WIDTH, HEIGHT) == (cols * SQ, rows * SQ):
            return
        COLS, ROWS = cols, rows
        WIDTH, HEIGHT = cols * SQ, rows * SQ
        FIELD_CX = (PANEL_W + WIDTH) // 2
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.aim_button = pygame.Rect((PANEL_W - 100) // 2, HEIGHT * 7 // 8, 100, 30)

    def enter_menu(self):
        self.in_menu = True
        self.paused = False
        self.set_board(20, 20)

    def start_match(self):
        mode, lvl, win, match, board = self.sel
        _, cols, rows = BOARDS[board]
        self.set_board(cols, rows)
        self.ai = {1: mode == 1, 2: mode == 2}
        self.ai_level = lvl
        self.win_score = WIN_OPTIONS[win]
        self.match_len = MATCH_OPTIONS[match][1]
        self.wins = [0, 0]
        self.round_no = 1
        self.match_over = False
        self.in_menu = False
        self.restart()

    def restart(self):
        """Reset the board for a new game / new round (match score is kept)."""
        self.stopgame = False
        self.paused = False
        self.passed = 0              # 0 game over, 1 passed, 4 round finished
        self.round_winner = None
        self.round_reason = ""
        self.red_kill = False        # snake 1 died by touching the red snake
        self.new_record = False
        self.time = 0
        self.cooling = False         # snake 1 frozen (by F)
        self.cool_start = 0
        self.cooling2 = False        # snake 2 frozen (by I)
        self.cool2_start = 0
        self.orange = False
        self.zigzag = False
        self.larger = False
        self.ring = [False] * 8
        self.john_seen = set()
        self.cd_freeze = self.cd_lolly = self.cd_reverse = 0
        self.cd_magnet = self.cd_ice = 0
        self.energy = ENERGY_MAX
        self.orange_energy = ORANGE_MAX
        self.turns1, self.turns2 = [], []   # buffered direction changes

        self.colours = 2             # snake 1 mode: 0 = '3', 1 = '1', 2 = '6'
        self.colorR = PURPLE
        self.colorL = GOLD if self.enhance else PINK
        self.speed, self.speed1, self.speed2 = 12, 4, 3

        # Snake 1 (1-indexed arrays like the original; index 1 = head)
        self.h1x = [0] * MAX_LEN
        self.h1y = [0] * MAX_LEN
        self.h1x[1] = WIDTH - 2 * SQ
        self.h1y[1] = HEIGHT - 2 * SQ
        self.s1size = 3
        self.angle1 = 180
        self.s1dead = False

        # Snake 2
        self.h2x = [0] * MAX_LEN
        self.h2y = [0] * MAX_LEN
        self.h2x[1] = PANEL_W + SQ
        self.h2y[1] = SQ
        self.s2size = 3
        self.angle2 = 0
        self.s2dead = False

        self.place_apple()

    # ---------------------------------------------------------------- apple
    def snake_cells(self, snake):
        hx, hy, size = ((self.h1x, self.h1y, self.s1size) if snake == 1
                        else (self.h2x, self.h2y, self.s2size))
        return [(hx[i], hy[i]) for i in range(1, size) if (hx[i], hy[i]) != (0, 0)]

    def place_apple(self):
        blocked = set()
        if not self.s1dead:
            blocked.update((self.h1x[i], self.h1y[i]) for i in range(1, self.s1size))
        if not self.s2dead:
            blocked.update((self.h2x[i], self.h2y[i]) for i in range(1, self.s2size))
        free = [(c * SQ, r * SQ)
                for c in range(PANEL_W // SQ + 1, COLS - 1)
                for r in range(1, ROWS - 1)
                if (c * SQ, r * SQ) not in blocked]
        self.applex, self.appley = random.choice(free) if free else (PANEL_W + 2 * SQ, 2 * SQ)

    def ring_cells(self):
        ax, ay = self.applex, self.appley
        return [(ax - SQ, ay + SQ), (ax, ay + SQ), (ax + SQ, ay + SQ),
                (ax - SQ, ay), (ax + SQ, ay),
                (ax - SQ, ay - SQ), (ax, ay - SQ), (ax + SQ, ay - SQ)]

    @staticmethod
    def in_field(x, y):
        return PANEL_W + SQ <= x <= WIDTH - 2 * SQ and SQ <= y <= HEIGHT - 2 * SQ

    # ---------------------------------------------------------- game logic
    def update(self):
        """One display frame of game logic (the original draw() loop)."""
        self.time += 1
        self.tick_abilities()
        self.ai_abilities()
        self.speed_adjust()
        self.cooling_check()
        if self.time % self.speed == 0:
            self.travel()
            self.larger_step()
            self.eat_apple()
            self.check_dead()

    def tick_abilities(self):
        self.cd_freeze = max(0, self.cd_freeze - 1)
        self.cd_lolly = max(0, self.cd_lolly - 1)
        self.cd_reverse = max(0, self.cd_reverse - 1)
        self.cd_magnet = max(0, self.cd_magnet - 1)
        self.cd_ice = max(0, self.cd_ice - 1)
        if self.enhance:
            self.energy -= 1
            if self.energy <= 0:                 # ghost mode runs dry
                self.energy = 0
                self.enhance = False
                self.colorL = PINK
        else:
            self.energy = min(ENERGY_MAX, self.energy + ENERGY_REGEN)
        if self.orange:
            self.orange_energy -= 1
            if self.orange_energy <= 0:          # disguise runs out
                self.orange_energy = 0
                self.orange = False
        else:
            self.orange_energy = min(ORANGE_MAX, self.orange_energy + ORANGE_REGEN)

    def speed_adjust(self):
        if self.colours == 0:
            self.speed, self.speed1, self.speed2 = 12, 8, 3
        elif self.colours == 1:
            self.speed, self.speed1, self.speed2 = 4, 8, 3
        else:
            self.speed, self.speed1, self.speed2 = 12, 4, 3

    def cooling_check(self):
        if self.cooling and self.time >= self.cool_start + FREEZE_DUR:
            self.cooling = False
        if self.cooling2 and self.time >= self.cool2_start + ICE_DUR:
            self.cooling2 = False

    def travel(self):
        if not self.s1dead and not self.cooling and self.time % self.speed1 == 0:
            if self.ai[1]:
                self.ai_steer(1)
            elif self.turns1:
                self.angle1 = self.turns1.pop(0)
            if not self.blocked_by_frozen_head(1):
                for i in range(self.s1size, 0, -1):
                    if i != 1:
                        self.h1x[i] = self.h1x[i - 1]
                        self.h1y[i] = self.h1y[i - 1]
                    else:
                        dx, dy = DIRS[self.angle1]
                        self.h1x[1] += dx * SQ
                        self.h1y[1] += dy * SQ

        if not self.s2dead and not self.cooling2 and self.time % self.speed2 == 0:
            if self.ai[2]:
                self.ai_steer(2)
            elif self.turns2:
                self.angle2 = self.turns2.pop(0)
            if not self.blocked_by_frozen_head(2):
                for i in range(self.s2size, 0, -1):
                    if i != 1:
                        self.h2x[i] = self.h2x[i - 1]
                        self.h2y[i] = self.h2y[i - 1]
                    else:
                        dx, dy = DIRS[self.angle2]
                        self.h2x[1] += dx * SQ
                        self.h2y[1] += dy * SQ

    def blocked_by_frozen_head(self, snake):
        """A frozen snake's head can't be run into: the mover just stays put this step
        (so freezing someone and ramming their head is not a way to win)."""
        if self.enhance:                              # ghost mode ignores collisions
            return False
        if snake == 1:
            if not self.cooling2 or self.s2dead:
                return False
            dx, dy = DIRS[self.angle1]
            return (self.h1x[1] + dx * SQ, self.h1y[1] + dy * SQ) == (self.h2x[1], self.h2y[1])
        if not self.cooling or self.s1dead:
            return False
        dx, dy = DIRS[self.angle2]
        return (self.h2x[1] + dx * SQ, self.h2y[1] + dy * SQ) == (self.h1x[1], self.h1y[1])

    def head_on(self, snake, x, y):
        if snake == 1:
            return (not self.s1dead) and self.h1x[1] == x and self.h1y[1] == y
        return (not self.s2dead) and self.h2x[1] == x and self.h2y[1] == y

    def larger_step(self):
        """Snake heads eating the ring of lollies around the apple."""
        if not self.larger:
            return
        for i, (cx, cy) in enumerate(self.ring_cells()):
            if not self.ring[i]:
                continue
            if not self.in_field(cx, cy):       # lolly would sit on a wall: drop it
                self.ring[i] = False
                continue
            if self.head_on(1, cx, cy):
                self.s1size += 1
                self.ring[i] = False
            elif self.head_on(2, cx, cy):
                self.s2size += 1
                self.ring[i] = False
        if not any(self.ring):
            self.larger = False

    def eat_apple(self):
        a1 = self.head_on(1, self.applex, self.appley)
        a2 = self.head_on(2, self.applex, self.appley)
        if a1 or a2:
            if a1:
                self.s1size += 1
            else:
                self.s2size += 1
            self.place_apple()

    def clear1(self, newend):
        for i in range(self.s1size, newend, -1):
            self.h1x[i] = 0
            self.h1y[i] = 0

    def clear2(self, newend):
        for i in range(self.s2size, newend, -1):
            self.h2x[i] = 0
            self.h2y[i] = 0

    def check_dead(self):
        # Only squares you can SEE are dangerous: the snake is drawn up to index size-1, so the
        # hidden square its tail just left (index size) must not bite, cut or kill anything.
        h1x, h1y, h2x, h2y = self.h1x, self.h1y, self.h2x, self.h2y

        def hits_wall(x, y):
            return x >= WIDTH - SQ or y >= HEIGHT - SQ or x <= PANEL_W or y <= 0

        if not self.s1dead:
            for i in range(2, self.s1size):          # bites itself
                if h1x[1] == h1x[i] and h1y[1] == h1y[i]:
                    self.s1dead = True
                    self.clear1(0)
                    break
            if hits_wall(h1x[1], h1y[1]):
                self.s1dead = True
                self.clear1(0)

        if not self.s2dead and not self.enhance:
            for i in range(2, self.s2size):
                if h2x[1] == h2x[i] and h2y[1] == h2y[i]:
                    self.s2dead = True
                    self.clear2(0)
                    break
            if hits_wall(h2x[1], h2y[1]):
                self.s2dead = True
                self.clear2(0)

        if (not self.s1dead and not self.s2dead and not self.enhance and self.colours == 0
                and h1x[1] == h2x[1] and h1y[1] == h2y[1]):
            self.s2dead = True                           # head-on with the red snake: it wins
            self.red_kill = True
            self.clear2(0)

        if not self.s1dead and not self.s2dead and not self.enhance:
            for i in range(2, self.s1size):          # snake 2 head hits snake 1 body
                if h2x[1] == h1x[i] and h2y[1] == h1y[i]:
                    if self.colours == 0:                # red mode: snake 2 dies
                        self.s2dead = True
                        self.red_kill = True
                        self.clear2(0)
                    else:
                        self.clear1(i)
                        self.s1size = i
                    break
            for i in range(2, self.s2size):          # snake 1 head hits snake 2 body
                if h1x[1] == h2x[i] and h1y[1] == h2y[i]:
                    self.clear2(i)
                    self.s2size = i
                    break

        if self.match_len > 1:
            self.resolve_round()
        else:
            self.classic_end()

    # ---- original co-op ending ------------------------------------------
    def classic_end(self):
        h1x, h1y, h2x, h2y = self.h1x, self.h1y, self.h2x, self.h2y
        if self.s1dead and self.s2dead:
            self.stopgame = True
            self.passed = 0

        if h1x[1] == h2x[1] and h1y[1] == h2y[1] and not self.enhance:   # heads collide
            self.stopgame = True
            self.passed = 0

        if self.s1size > self.win_score and self.s2size > self.win_score:
            self.stopgame = True
            self.passed = 1

        if self.stopgame and self.passed == 1:
            self.new_record = self._record_time()

    # ---- versus ending (best of 3 / 5) ----------------------------------
    def longer(self):
        if self.s1size > self.s2size:
            return 1
        if self.s2size > self.s1size:
            return 2
        return None

    def resolve_round(self):
        h1x, h1y, h2x, h2y = self.h1x, self.h1y, self.h2x, self.h2y
        ended, winner, reason = False, None, ""

        if self.s1dead and self.s2dead:
            ended, winner, reason = True, self.longer(), "Both snakes crashed"
        elif self.s1dead:
            ended, winner, reason = True, 2, f"{self.name(1)} crashed"
        elif self.s2dead:
            ended, winner = True, 1
            reason = (f"{self.name(2)} touched the red snake" if self.red_kill
                      else f"{self.name(2)} crashed")
        elif h1x[1] == h2x[1] and h1y[1] == h2y[1] and not self.enhance:
            ended, winner, reason = True, self.longer(), "Head-on collision"
        elif self.s1size > self.win_score or self.s2size > self.win_score:
            ended, winner, reason = True, self.longer(), f"Reached {self.win_score} apples"

        if not ended:
            return
        self.stopgame = True
        self.passed = 4
        self.round_winner = winner
        self.round_reason = reason
        if winner is not None:
            self.wins[winner - 1] += 1
            if self.wins[winner - 1] > self.match_len // 2:
                self.match_over = True

    # ----------------------------------------------------- special moves
    def use_freeze(self):
        if self.s1dead or self.s2dead or self.cd_freeze:
            return False
        self.cooling = True
        self.cool_start = self.time
        self.cd_freeze = FREEZE_CD
        return True

    def use_lollies(self):
        if (self.s2dead or self.cd_lolly or self.larger
                or not (self.applex < WIDTH - 2 * SQ and self.appley < HEIGHT - 2 * SQ
                        and self.applex > PANEL_W + SQ and self.appley > SQ)):
            return False
        self.larger = True
        self.ring = [True] * 8
        self.cd_lolly = LOLLY_CD
        return True

    def use_reverse(self):
        if self.s2dead or self.cd_reverse:
            return False
        self.reverse_snake2()
        self.cd_reverse = REVERSE_CD
        return True

    def reverse_snake2(self):
        """Turn snake 2 around so its tail becomes its head."""
        n = self.s2size
        h2x, h2y = self.h2x, self.h2y
        self.turns2.clear()
        if h2x[n] == h2x[n - 1]:
            self.angle2 = 270 if h2y[n] > h2y[n - 1] else 90
        else:
            self.angle2 = 0 if h2x[n] > h2x[n - 1] else 180
        old_x, old_y = h2x[:], h2y[:]
        for i in range(1, n + 1):
            h2x[i] = old_x[n - i]
            h2y[i] = old_y[n - i]

    def use_magnet(self):
        """Pull the apple up to MAGNET_CELLS squares towards snake 1's head."""
        if self.s1dead or self.cd_magnet:
            return False
        blocked = set(self.snake_cells(1)) | (set() if self.s2dead else set(self.snake_cells(2)))
        ax, ay = self.applex, self.appley
        hx, hy = self.h1x[1], self.h1y[1]
        for _ in range(MAGNET_CELLS):
            dx, dy = hx - ax, hy - ay
            if abs(dx) >= abs(dy) and dx != 0:
                nx, ny = ax + sign(dx) * SQ, ay
            elif dy != 0:
                nx, ny = ax, ay + sign(dy) * SQ
            else:
                break
            if (nx, ny) == (hx, hy) or not self.in_field(nx, ny) or (nx, ny) in blocked:
                break
            ax, ay = nx, ny
        if (ax, ay) == (self.applex, self.appley):
            return False
        self.applex, self.appley = ax, ay
        self.cd_magnet = MAGNET_CD
        return True

    def use_ice(self):
        """Snake 1's mirror of Freeze: snake 2 can't move for ICE_DUR frames."""
        if self.s1dead or self.s2dead or self.cd_ice:
            return False
        self.cooling2 = True
        self.cool2_start = self.time
        self.cd_ice = ICE_CD
        return True

    # ------------------------------------------------------------------ AI
    def free_area(self, start, blocked, cap):
        seen = {start}
        stack = [start]
        while stack and len(seen) < cap:
            x, y = stack.pop()
            for dx, dy in DIRS.values():
                n = (x + dx * SQ, y + dy * SQ)
                if n not in seen and n not in blocked and self.in_field(*n):
                    seen.add(n)
                    stack.append(n)
        return len(seen)

    def ai_steer(self, snake):
        hx, hy, size, cur = ((self.h1x, self.h1y, self.s1size, self.angle1) if snake == 1
                             else (self.h2x, self.h2y, self.s2size, self.angle2))
        head = (hx[1], hy[1])
        blocked = set(self.snake_cells(1)) | set(self.snake_cells(2))
        if (self.s1dead and snake == 2) or (self.s2dead and snake == 1):
            blocked = set(self.snake_cells(snake))

        options = []
        for a in (cur, (cur + 90) % 360, (cur + 270) % 360):
            dx, dy = DIRS[a]
            c = (head[0] + dx * SQ, head[1] + dy * SQ)
            if self.in_field(*c) and c not in blocked:
                options.append((a, c))

        if not options:
            if snake == 2 and self.use_reverse():        # trapped: turn round
                return
            return                                       # nothing to do, keep going

        lvl = self.ai_level
        if random.random() < (0.22, 0.05, 0.0)[lvl]:
            self.set_angle(snake, random.choice(options)[0])
            return

        targets = [(self.applex, self.appley)]
        if self.larger:
            targets += [c for i, c in enumerate(self.ring_cells())
                        if self.ring[i] and self.in_field(*c)]
        tx, ty = min(targets, key=lambda t: abs(t[0] - head[0]) + abs(t[1] - head[1]))

        def score(opt):
            a, c = opt
            s = (abs(c[0] - tx) + abs(c[1] - ty)) / SQ - (0.4 if a == cur else 0)
            if lvl == 1:
                exits = sum(1 for dx, dy in DIRS.values()
                            if self.in_field(c[0] + dx * SQ, c[1] + dy * SQ)
                            and (c[0] + dx * SQ, c[1] + dy * SQ) not in blocked)
                if exits == 0:
                    s += 100
            elif lvl == 2:
                area = self.free_area(c, blocked | {c}, size + 15)
                if area < size + 8:
                    s += (size + 8 - area) * 3
            return s

        self.set_angle(snake, min(options, key=score)[0])

    def set_angle(self, snake, angle):
        if snake == 1:
            self.angle1 = angle
            self.turns1.clear()
        else:
            self.angle2 = angle
            self.turns2.clear()

    def ai_abilities(self):
        if self.time % 8 or not (self.ai[1] or self.ai[2]):
            return
        if random.random() > (0.35, 0.7, 1.0)[self.ai_level]:
            return
        ax, ay = self.applex, self.appley
        h1 = (self.h1x[1], self.h1y[1])
        h2 = (self.h2x[1], self.h2y[1])
        d1 = (abs(h1[0] - ax) + abs(h1[1] - ay)) // SQ
        d2 = (abs(h2[0] - ax) + abs(h2[1] - ay)) // SQ

        if self.ai[2] and not self.s2dead:
            if d1 <= 4 and d2 > d1:
                self.use_freeze()
            elif random.random() < 0.3:
                self.use_lollies()
        if self.ai[1] and not self.s1dead:
            if d1 >= 4 and (d2 > d1 or random.random() < 0.3):
                self.use_magnet()
            if d2 <= 4 and d1 > d2:
                self.use_ice()

    # --------------------------------------------------------------- input
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type in (pygame.KEYDOWN, pygame.KEYUP):
            event.key = NUMPAD_DIGITS.get(event.key, event.key)

        if event.type == pygame.KEYUP:
            self.on_keyup(event.key)
            return

        if event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
            if not self.stopgame and not self.in_menu:
                self.paused = True
            return

        if self.in_menu:
            if event.type == pygame.KEYDOWN:
                self.held.add(event.key)
                self.menu_key(event.key)
            return

        if self.popup:                                   # dialog is modal
            if (event.type == pygame.KEYDOWN and
                    event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE)):
                self.popup = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.popup_ok_rect().collidepoint(event.pos):
                    self.popup = None
            return

        if event.type == pygame.KEYDOWN:
            self.on_keydown(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.aim_button.collidepoint(event.pos):
                if self.match_len > 1:
                    msg = f"First to {self.win_score} apples wins the round"
                else:
                    msg = f"{self.win_score} Apples Inside The Hoard Each"
                self.popup = ("How to pass?", msg)

    def menu_key(self, key):
        sizes = [len(MODES), len(AI_LEVELS), len(WIN_OPTIONS), len(MATCH_OPTIONS), len(BOARDS)]
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_sel = (self.menu_sel - 1) % len(sizes)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_sel = (self.menu_sel + 1) % len(sizes)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.sel[self.menu_sel] = (self.sel[self.menu_sel] - 1) % sizes[self.menu_sel]
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.sel[self.menu_sel] = (self.sel[self.menu_sel] + 1) % sizes[self.menu_sel]
        elif key in ENTER_KEYS or key == pygame.K_SPACE:
            self.start_match()

    def queue_turn(self, snake, new):
        """Buffer a direction change (up to MAX_QUEUED_TURNS ahead)."""
        q = self.turns1 if snake == 1 else self.turns2
        cur = q[-1] if q else (self.angle1 if snake == 1 else self.angle2)
        if new == cur or new == (cur + 180) % 360:
            return
        if not q:                                   # don't turn into our own neck
            hx, hy, nx, ny = ((self.h1x[1], self.h1y[1], self.h1x[2], self.h1y[2]) if snake == 1
                              else (self.h2x[1], self.h2y[1], self.h2x[2], self.h2y[2]))
            dx, dy = DIRS[new]
            if (dx and hx + dx * SQ == nx) or (dy and hy + dy * SQ == ny):
                return
        if len(q) < MAX_QUEUED_TURNS:
            q.append(new)

    def on_keydown(self, key):
        self.held.add(key)
        if key in JOHN_KEYS:
            self.john_seen.add(key)

        # round / match finished: Enter continues
        if self.stopgame and self.passed == 4 and key in ENTER_KEYS:
            if self.match_over:
                self.start_match()                   # rematch, same settings
            else:
                if self.round_winner is not None:    # a draw replays the same round number
                    self.round_no += 1
                self.restart()                       # next round
            return
        if key == pygame.K_ESCAPE:
            self.enter_menu()
            return
        if key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            if not (self.stopgame and self.passed == 4):
                self.restart()
            return
        if key == pygame.K_p and not self.stopgame:
            self.paused = not self.paused
            return
        if self.paused:
            return

        # ---- snake 1 (arrows)
        if not self.s1dead and not self.ai[1]:
            if key == pygame.K_UP:
                self.queue_turn(1, 90)
            if key == pygame.K_DOWN:
                self.queue_turn(1, 270)
            if key == pygame.K_LEFT:
                self.queue_turn(1, 180)
            if key == pygame.K_RIGHT:
                self.queue_turn(1, 0)

            if key == pygame.K_m:
                self.use_magnet()
            if key == pygame.K_i:
                self.use_ice()
            if key == pygame.K_1:
                self.colorR, self.colours = RED_MODE, 0
            if key == pygame.K_2:
                self.colorR, self.colours = PURPLE, 2
            if key == pygame.K_3:
                self.colorR, self.colours = BLUE_MODE, 1

        # ---- snake 2 (WASD)
        if not self.s2dead and not self.ai[2]:
            if key == pygame.K_w:
                self.queue_turn(2, 90)
            if key == pygame.K_s:
                self.queue_turn(2, 270)
            if key == pygame.K_a:
                self.queue_turn(2, 180)
            if key == pygame.K_d:
                self.queue_turn(2, 0)

            if key == pygame.K_f:
                self.use_freeze()
            if key == pygame.K_l:
                self.use_lollies()
            if key == pygame.K_r and not self.zigzag:
                if self.use_reverse():
                    self.zigzag = True               # ignore key-repeat until released
            if key == pygame.K_h:
                self.hide = True
            if key == pygame.K_o and self.orange_energy >= ORANGE_MIN:
                self.orange = True
            if key == pygame.K_g and self.energy >= ENERGY_MIN:
                self.enhance = True
                self.colorL = GOLD

    def on_keyup(self, key):
        self.held.discard(key)
        if key == pygame.K_h:
            self.hide = False
        if key == pygame.K_o:
            self.orange = False
        if key == pygame.K_g:
            self.enhance = False
            self.colorL = PINK
        if key == pygame.K_r:
            self.zigzag = False

    # ------------------------------------------------------------- drawing
    def text(self, lines, size, colour, cx, cy):
        """Draw (multi-line) text centred on (cx, cy)."""
        if isinstance(lines, str):
            lines = lines.split("\n")
        font = self.font(size)
        lh = int(size * 1.25)
        top = cy - lh * len(lines) / 2
        for k, line in enumerate(lines):
            if line.strip():
                surf = font.render(line, True, colour)
                self.screen.blit(surf, surf.get_rect(center=(cx, top + lh * k + lh / 2)))

    def text_left(self, line, size, colour, x, cy):
        surf = self.font(size).render(line, True, colour)
        self.screen.blit(surf, surf.get_rect(midleft=(x, cy)))

    def cell(self, x, y, fill, outline=WHITE, width=1):
        r = pygame.Rect(x, y, SQ, SQ)
        pygame.draw.rect(self.screen, fill, r)
        pygame.draw.rect(self.screen, outline, r, width)

    def draw_snake(self, hx, hy, size, body_colour, frozen=False):
        # indices 1..size-1 are visible; index `size` is the vacated tail cell.
        # (0, 0) is the "no segment yet" marker used by the original.
        for i in range(size - 1, 0, -1):
            x, y = hx[i], hy[i]
            if (x, y) == (0, 0):
                continue
            colour = ICE if frozen else (LIME if i == 1 else body_colour)
            self.cell(x, y, colour)

    def draw_bar(self, y, label, frac, colour):
        r = pygame.Rect(10, y, PANEL_W - 20, 13)
        pygame.draw.rect(self.screen, (225, 225, 225), r, border_radius=4)
        if frac > 0:
            pygame.draw.rect(self.screen, colour, (r.x, r.y, int(r.w * frac), r.h), border_radius=4)
        pygame.draw.rect(self.screen, (141, 141, 141), r, 1, border_radius=4)
        self.text(label, 11, BLACK, r.centerx, r.centery)

    def cd_bar(self, y, name, cd, total):
        ready, charging = (120, 210, 100), (150, 180, 220)
        secs = -(-cd // FPS)
        self.draw_bar(y, name if cd == 0 else f"{name}  {secs}s",
                      1 - cd / total, ready if cd == 0 else charging)

    def draw_modes(self, y):
        """Speed-mode switches for the arrow snake: keys 1 / 2 / 3, current one lit."""
        modes = [("1 Slow", 0, RED_MODE), ("2 Normal", 2, PURPLE), ("3 Fast", 1, BLUE_MODE)]
        for n, (label, mode_id, colour) in enumerate(modes):
            r = pygame.Rect(10 + n * 48, y, 44, 16)
            active = self.colours == mode_id
            pygame.draw.rect(self.screen, colour if active else (52, 58, 70), r, border_radius=4)
            pygame.draw.rect(self.screen, WHITE if active else (90, 96, 110), r, 1, border_radius=4)
            self.text(label, 10, WHITE if active else (170, 175, 185), r.centerx, r.centery)

    def draw_abilities(self):
        top_y, bot_y = HEIGHT // 4, HEIGHT * 5 // 8      # centres of the two score labels
        if not self.s2dead:                              # Snake 1 (WASD), top block
            y = top_y + 40
            self.cd_bar(y, "F  Freeze", self.cd_freeze, FREEZE_CD)
            self.cd_bar(y + 15, "L  Lollies", self.cd_lolly, LOLLY_CD)
            self.cd_bar(y + 30, "R  Reverse", self.cd_reverse, REVERSE_CD)
            self.draw_bar(y + 45, "G  Ghost", self.energy / ENERGY_MAX, GOLD)
            self.draw_bar(y + 60, "O  Orange", self.orange_energy / ORANGE_MAX, (255, 165, 0))
        if not self.s1dead:                              # Snake 2 (arrows), bottom block
            y = bot_y + 35
            self.cd_bar(y, "M  Magnet", self.cd_magnet, MAGNET_CD)
            self.cd_bar(y + 15, "I  Ice", self.cd_ice, ICE_CD)
            self.draw_modes(y + 33)

    def draw_panel(self):
        pygame.draw.rect(self.screen, PANEL_BG, (0, 0, PANEL_W, HEIGHT))
        mid = PANEL_W // 2
        if self.match_len > 1:
            need = self.match_len // 2 + 1
            self.text(f"BEST OF {self.match_len}  -  ROUND {self.round_no}", 11, SOFT, mid, 12)
            snake2_col = (225, 130, 240)
            self.text(str(self.wins[1]), 26, PINK, 36, 36)         # Snake 1 (WASD) rounds won
            self.text(":", 24, WHITE, mid, 35)
            self.text(str(self.wins[0]), 26, snake2_col, 124, 36)  # Snake 2 (arrows) rounds won
            self.text("SNAKE 1", 9, PINK, 36, 56)
            self.text("SNAKE 2", 9, snake2_col, 124, 56)
            self.text(f"first to {need}", 10, SOFT, mid, 72)
        self.text(str(self.time // FPS), 15, (0, 255, 0), mid, 100)
        top_y, bot_y = HEIGHT // 4, HEIGHT * 5 // 8
        if self.ai[2]:
            self.text("computer", 11, SOFT, mid, top_y - 38)
        if self.ai[1]:
            self.text("computer", 11, SOFT, mid, bot_y - 38)
        self.text(f"snake 1\n{self.s2size - 1}", 25, LIME, mid, top_y)
        self.text(f"snake 2\n{self.s1size - 1}", 25, LIME, mid, bot_y)
        if self.s1size - 1 == 7 and self.s2size - 1 == 7:
            self.text("Congratulations on\nyour special day!", 12, LIME, mid, top_y - 24)
        self.draw_abilities()

        rect = self.aim_button
        pygame.draw.rect(self.screen, (218, 218, 218), rect, border_radius=10)
        pygame.draw.rect(self.screen, (141, 141, 141), rect, 1, border_radius=10)
        self.text("Aim", 14, BLACK, rect.centerx, rect.centery)

    def draw_board(self):
        self.screen.fill(WHITE)
        self.draw_panel()

        # apple
        if not self.orange:
            self.cell(self.applex, self.appley, (255, 0, 0), BLACK)
        else:
            pygame.draw.circle(self.screen, (255, 165, 0),
                               (self.applex + SQ // 2, self.appley + SQ // 2), SQ // 2)

        # walls
        for r in ((PANEL_W, 0, WIDTH - PANEL_W, SQ),
                  (PANEL_W, HEIGHT - SQ, WIDTH - PANEL_W, SQ),
                  (PANEL_W, 0, SQ, HEIGHT),
                  (WIDTH - SQ, 0, SQ, HEIGHT)):
            pygame.draw.rect(self.screen, WALL_COL, r)
            pygame.draw.rect(self.screen, BLACK, r, 1)

        # lollies
        if self.larger:
            for i, (cx, cy) in enumerate(self.ring_cells()):
                if self.ring[i] and self.in_field(cx, cy):
                    self.screen.blit(self.lolly, (cx, cy))

        # snakes
        if not self.s1dead:
            self.draw_snake(self.h1x, self.h1y, self.s1size, self.colorR, frozen=self.cooling)
        if not self.s2dead and not self.hide:
            self.draw_snake(self.h2x, self.h2y, self.s2size, self.colorL, frozen=self.cooling2)

    def draw_banner(self, lines):
        """Translucent box over the playfield. lines = [(text, size, colour), ...]"""
        total = sum(int(sz * 1.5) for _, sz, _ in lines) + 30
        box = pygame.Surface((440, total), pygame.SRCALPHA)
        box.fill((255, 255, 255, 235))
        rect = box.get_rect(center=(FIELD_CX, HEIGHT // 2))
        self.screen.blit(box, rect)
        pygame.draw.rect(self.screen, (90, 90, 90), rect, 2, border_radius=4)
        y = rect.top + 15
        for txt, sz, col in lines:
            h = int(sz * 1.5)
            self.text(txt, sz, col, FIELD_CX, y + h / 2)
            y += h

    def draw_pass_screen(self):
        self.screen.fill(WHITE)
        self.text("You passed!\nMarks:", 32, BLACK, WIDTH // 2, HEIGHT * 3 // 8)
        for n, (size, dead) in enumerate(((self.s2size, self.s2dead), (self.s1size, self.s1dead))):
            y = HEIGHT * 3 // 8 + 64 + 32 * n
            self.text(f"Snake{n + 1}: {size - 1}", 32, BLACK, WIDTH // 2, y)
            self.text("(Dead)" if dead else "(Alive)", 32,
                      (255, 0, 0) if dead else (0, 160, 0), WIDTH // 2 + 4 * 32 + 10, y)
        secs = self.time // FPS
        line = f"Your time: {secs} s" + ("   -   NEW RECORD!" if self.new_record
                                         else f"      Best: {self.best_time} s")
        self.text(line, 22, (0, 130, 0) if self.new_record else (60, 60, 60),
                  WIDTH // 2, HEIGHT * 3 // 8 + 190)
        self.text("Shift: play again      Esc: menu", 18, (90, 90, 90), WIDTH // 2, HEIGHT - 50)

    def draw_game_over(self):
        self.draw_banner([("GAME OVER", 34, BLACK),
                          (f"Score:  {self.s1size + self.s2size - 2} units long in total", 24, BLACK),
                          ("Shift: restart      Esc: menu", 20, (90, 90, 90))])

    def draw_round_over(self):
        w = self.round_winner
        if self.match_over:
            head, hint = f"SNAKE {3 - w} WINS THE MATCH!", "Enter: rematch      Esc: menu"
        elif w is None:
            head, hint = "DRAW", "Enter: replay the round"
        else:
            head, hint = f"SNAKE {3 - w} WINS THE ROUND", "Enter: next round"
        if w is None:
            reason = self.round_reason + " - no point"
        else:
            reason = self.round_reason
        self.draw_banner([(head, 30, BLACK),
                          (reason, 20, (60, 60, 60)),
                          (f"Match score    {self.wins[1]}  -  {self.wins[0]}", 24, BLACK),
                          (hint, 20, (90, 90, 90))])

    def popup_rect(self):
        return pygame.Rect(0, 0, 360, 150).move(WIDTH // 2 - 180, HEIGHT // 2 - 75)

    def popup_ok_rect(self):
        r = self.popup_rect()
        return pygame.Rect(r.centerx - 40, r.bottom - 45, 80, 30)

    def draw_popup(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 90))
        self.screen.blit(dim, (0, 0))
        r = self.popup_rect()
        pygame.draw.rect(self.screen, (245, 245, 245), r, border_radius=8)
        pygame.draw.rect(self.screen, (120, 120, 120), r, 2, border_radius=8)
        title, msg = self.popup
        self.text(title, 18, (60, 60, 60), r.centerx, r.top + 24)
        self.text(msg, 18, BLACK, r.centerx, r.centery - 5)
        ok = self.popup_ok_rect()
        pygame.draw.rect(self.screen, (218, 218, 218), ok, border_radius=8)
        pygame.draw.rect(self.screen, (141, 141, 141), ok, 1, border_radius=8)
        self.text("OK", 16, BLACK, ok.centerx, ok.centery)

    def draw_paused(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        self.screen.blit(dim, (0, 0))
        self.text("PAUSED", 48, WHITE, WIDTH // 2, HEIGHT // 2 - 20)
        self.text("Press P to resume", 20, WHITE, WIDTH // 2, HEIGHT // 2 + 25)

    def draw_menu(self):
        self.screen.fill(MENU_BG)
        self.text("TWO PLAYER SNAKE", 44, LIME, WIDTH // 2, 52)
        if self.best_time is not None:
            self.text(f"Best single-game time: {self.best_time} s", 13, SOFT, WIDTH // 2, 90)

        mode, lvl, win, match, board = self.sel
        bname, bcols, brows = BOARDS[board]
        rows = [("Mode", MODES[mode]),
                ("Computer level", AI_LEVELS[lvl]),
                ("Apples to win", str(WIN_OPTIONS[win])),
                ("Match", MATCH_OPTIONS[match][0]),
                ("Board", f"{bname}  ({bcols - 7} x {brows - 2} squares)")]
        for i, (label, val) in enumerate(rows):
            y = 116 + i * 37
            selected = i == self.menu_sel
            greyed = i == 1 and mode == 0
            if selected:
                pygame.draw.rect(self.screen, (52, 62, 84), (36, y - 17, 568, 34), border_radius=8)
            self.text_left(label, 22, (120, 125, 135) if greyed else WHITE, 56, y)
            vcol = (120, 125, 135) if greyed else (LIME if selected else SOFT)
            self.text_left(f"<  {val}  >" if selected else f"    {val}", 20, vcol, 240, y)

        if MATCH_OPTIONS[match][1] > 1:
            hint = [f"Versus: first snake to {WIN_OPTIONS[win]} apples wins the round.",
                    "A crash loses the round."]
        else:
            hint = [f"Co-op: BOTH snakes must reach {WIN_OPTIONS[win]} apples to pass.",
                    "Both snakes crash = game over."]
        self.text(hint, 14, SOFT, WIDTH // 2, 314)

        cols = [
            (30, "SNAKE 1  -  W A S D" + ("  (computer)" if mode == 2 else ""), PINK,
             [("W A S D", "steer"),
              ("F", "Freeze snake 2 for 4 s (15 s CD)"),
              ("L", "Lollies around the apple"),
              ("R", "Reverse your snake"),
              ("H", "(hold) invisible"),
              ("O", "(hold) apple looks like an orange"),
              ("G", "(hold) ghost: nothing can hurt you")]),
            (335, "SNAKE 2  -  arrow keys" + ("  (computer)" if mode == 1 else ""), (225, 130, 240),
             [("Arrows", "steer"),
              ("M", "Magnet: pull the apple closer"),
              ("I", "Ice: freeze snake 1 for a moment"),
              ("1", "red: slow but deadly"),
              ("2", "purple: normal speed"),
              ("3", "blue: fast")]),
        ]
        for x, head, col, items in cols:
            self.text_left(head, 16, col, x, 360)
            for k, (key, desc) in enumerate(items):
                y = 390 + k * 21
                self.text_left(key, 14, LIME, x, y)
                self.text_left(desc, 13, SOFT, x + 72, y)

        self.text("Up / Down: choose      Left / Right: change      Enter: start", 16, WHITE,
                  WIDTH // 2, 566)
        self.text("In game:   P pause      Shift restart      Esc menu", 14, (150, 155, 165),
                  WIDTH // 2, 596)

    def draw(self):
        if self.in_menu:
            self.draw_menu()
            return

        if self.stopgame and self.passed == 1:
            self.draw_pass_screen()
        else:
            self.draw_board()
            if self.stopgame and self.passed == 4:
                self.draw_round_over()
            elif self.stopgame:
                self.draw_game_over()

        # easter eggs from the original
        if JOHN_KEYS <= self.john_seen:
            self.text(["John 3:16",
                       "For God so loved the world that he gave his one and only Son,",
                       "that whoever believes in him shall not perish but have eternal life."],
                      18, (153, 76, 0), WIDTH // 2, HEIGHT // 2)

        if self.popup:
            self.draw_popup()
        elif self.paused:
            self.draw_paused()

    # ------------------------------------------------------------ main loop
    def run(self):
        while True:
            for event in pygame.event.get():
                self.handle_event(event)
            if (not self.in_menu and not self.popup and not self.stopgame
                    and not self.paused):
                self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
