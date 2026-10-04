#!/usr/bin/env python3
"""
Two Player Snake -- Python / pygame port of two_players_snake.pde

Setup:   pip install pygame
Run:     python two_players_snake.py      (keep lolly.jpg in the same folder)

Snake 1 (arrow keys, right-hand side)
    Arrows ....... steer
    3 / 1 / 6 .... change snake 1's mode:
                     3 = red, slow, and it wins head-on body hits
                     1 = blue, fast
                     6 = purple, normal (default)

Snake 2 (W A S D, left-hand side) and its special moves
    W A S D ...... steer
    C ............ freeze snake 1 for a moment            (6 s cooldown)
    H (hold) ..... turn invisible
    O (hold) ..... disguise the apple as an orange
    L ............ surround the apple with 8 lollies       (10 s cooldown)
    Z ............ reverse snake 2                         (3 s cooldown)
    E (hold) ..... golden ghost mode: no collisions, can escape the window.
                   Uses an energy bar that drains while held and recharges
                   when released. If it runs out inside a wall, you're toast.

P ................ pause / resume (also pauses if the window loses focus)
Shift ............ restart

Turns are buffered: you can press two direction keys quickly within one
step and both will be used, in order.
Aim / Shortest time buttons on the left, as in the original.
"""

import os
import random
import sys

import pygame

# ---------------------------------------------------------------- constants
WIDTH, HEIGHT = 640, 640
SQ = 32                       # size of one grid square
FPS = 60
PANEL_W = WIDTH // 4          # scoreboard panel on the left
NUM_SQ = HEIGHT // SQ
WIN_SCORE = 40                # both snakes must be longer than this to pass
MAX_LEN = 2500

# special-move balancing (frames)
FREEZE_CD = 6 * FPS
LOLLY_CD = 10 * FPS
REVERSE_CD = 3 * FPS
ENERGY_MAX = 6 * FPS          # seconds of ghost mode on a full bar
ENERGY_MIN = FPS              # need at least 1 s of energy to switch it on
ENERGY_REGEN = 0.5            # per frame while not in ghost mode (12 s to refill)
MAX_QUEUED_TURNS = 2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BEST_TIME_FILE = os.path.join(BASE_DIR, "shortest_time.txt")

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIME = (155, 240, 0)          # snake heads / scoreboard text
WALL_COL = (175, 227, 214)
ICE = (165, 242, 243)         # frozen snake
PINK = (255, 153, 153)        # snake 2 body
GOLD = (255, 215, 0)          # snake 2 body when enhanced
PURPLE = (204, 0, 204)        # snake 1 body (mode 6)
RED_MODE = (250, 0, 0)        # snake 1 body (mode 3)
BLUE_MODE = (70, 130, 180)    # snake 1 body (mode 1)

# Processing used angles: 0 = right, 90 = up, 180 = left, 270 = down
DIRS = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}

CHLOE_KEYS = {pygame.K_c, pygame.K_h, pygame.K_l, pygame.K_o, pygame.K_e}
JOHN_KEYS = {pygame.K_j, pygame.K_o, pygame.K_h, pygame.K_n,
             pygame.K_3, pygame.K_1, pygame.K_6}


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Two Player Snake")
        self.clock = pygame.time.Clock()
        self._fonts = {}

        self.lolly = self._load_lolly()
        self.aim_button = pygame.Rect(WIDTH // 16 - 10, HEIGHT * 7 // 8, 100, 30)
        self.best_button = pygame.Rect(WIDTH // 16 - 10, int(HEIGHT * 6.5 / 8), 100, 30)
        self.best_time = self._load_best_time()

        self.popup = None            # (title, message) while a dialog is open
        self.held = set()            # keys currently held down
        self.hide = False
        self.enhance = False
        self.paused = False
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
        seconds = self.time // FPS
        if self.best_time is None or seconds < self.best_time:
            self.best_time = seconds
            try:
                with open(BEST_TIME_FILE, "w") as f:
                    f.write(str(seconds))
            except OSError:
                pass

    # -------------------------------------------------------------- restart
    def restart(self):
        self.stopgame = False
        self.paused = False
        self.passed = 0              # 1 = passed, 2 = escaped, 0 = game over
        self.cd_freeze = self.cd_lolly = self.cd_reverse = 0
        self.energy = ENERGY_MAX
        self.turns1, self.turns2 = [], []   # buffered direction changes
        self.time = 0
        self.cooling = False
        self.cool_start = 0
        self.orange = False
        self.zigzag = False
        self.larger = False
        self.ring = [False] * 8
        self.john_seen = set()

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
    def place_apple(self):
        blocked = set()
        if not self.s1dead:
            blocked.update((self.h1x[i], self.h1y[i]) for i in range(1, self.s1size))
        if not self.s2dead:
            blocked.update((self.h2x[i], self.h2y[i]) for i in range(1, self.s2size))
        free = [(c * SQ, r * SQ)
                for c in range(PANEL_W // SQ + 1, NUM_SQ - 1)
                for r in range(1, NUM_SQ - 1)
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
        if self.enhance:
            self.energy -= 1
            if self.energy <= 0:                 # ghost mode runs dry
                self.energy = 0
                self.enhance = False
                self.colorL = PINK
        else:
            self.energy = min(ENERGY_MAX, self.energy + ENERGY_REGEN)

    def speed_adjust(self):
        if self.colours == 0:
            self.speed, self.speed1, self.speed2 = 12, 8, 3
        elif self.colours == 1:
            self.speed, self.speed1, self.speed2 = 4, 8, 3
        else:
            self.speed, self.speed1, self.speed2 = 12, 4, 3

    def cooling_check(self):
        if self.cooling and self.time >= self.cool_start + self.speed * 8:
            self.cooling = False

    def travel(self):
        if not self.s1dead and not self.cooling and self.time % self.speed1 == 0:
            if self.turns1:
                self.angle1 = self.turns1.pop(0)
            for i in range(self.s1size, 0, -1):
                if i != 1:
                    self.h1x[i] = self.h1x[i - 1]
                    self.h1y[i] = self.h1y[i - 1]
                else:
                    dx, dy = DIRS[self.angle1]
                    self.h1x[1] += dx * SQ
                    self.h1y[1] += dy * SQ

        if not self.s2dead and self.time % self.speed2 == 0:
            if self.turns2:
                self.angle2 = self.turns2.pop(0)
            for i in range(self.s2size, 0, -1):
                if i != 1:
                    self.h2x[i] = self.h2x[i - 1]
                    self.h2y[i] = self.h2y[i - 1]
                else:
                    dx, dy = DIRS[self.angle2]
                    self.h2x[1] += dx * SQ
                    self.h2y[1] += dy * SQ

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
        h1x, h1y, h2x, h2y = self.h1x, self.h1y, self.h2x, self.h2y

        def hits_wall(x, y):
            return x >= WIDTH - SQ or y >= HEIGHT - SQ or x <= PANEL_W or y <= 0

        if not self.s1dead:
            for i in range(2, self.s1size + 1):          # bites itself
                if h1x[1] == h1x[i] and h1y[1] == h1y[i]:
                    self.s1dead = True
                    self.clear1(0)
                    break
            if hits_wall(h1x[1], h1y[1]):
                self.s1dead = True
                self.clear1(0)

        if not self.s2dead and not self.enhance:
            for i in range(2, self.s2size + 1):
                if h2x[1] == h2x[i] and h2y[1] == h2y[i]:
                    self.s2dead = True
                    self.clear2(0)
                    break
            if hits_wall(h2x[1], h2y[1]):
                self.s2dead = True
                self.clear2(0)

        if not self.s1dead and not self.s2dead and not self.enhance:
            for i in range(2, self.s1size + 1):          # snake 2 head hits snake 1 body
                if h2x[1] == h1x[i] and h2y[1] == h1y[i]:
                    if self.colours == 0:
                        self.s2dead = True
                        self.clear2(0)
                    else:
                        self.clear1(i)
                        self.s1size = i
                    break
            for i in range(2, self.s2size + 1):          # snake 1 head hits snake 2 body
                if h1x[1] == h2x[i] and h1y[1] == h2y[i]:
                    self.clear2(i)
                    self.s2size = i
                    break

        if self.s1dead and self.s2dead:
            self.stopgame = True
            self.passed = 0

        if h1x[1] == h2x[1] and h1y[1] == h2y[1] and not self.enhance:   # heads collide
            self.stopgame = True
            self.passed = 0

        if self.s1size > WIN_SCORE and self.s2size > WIN_SCORE:
            self.stopgame = True
            self.passed = 1

        if self.enhance:                                  # escape check
            self.stopgame = True
            self.passed = 2
            for i in range(1, self.s2size + 1):
                if -SQ < h2x[i] < WIDTH and -SQ < h2y[i] < HEIGHT:
                    self.stopgame = False
                    self.passed = 0
                    break

        if self.stopgame and self.passed == 1:
            self._record_time()

    # --------------------------------------------------------------- input
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYUP:
            self.on_keyup(event.key)
            return

        if event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
            if not self.stopgame:
                self.paused = True
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
                self.popup = ("How to pass?", "40 Apples Inside The Hoard Each")
            elif self.best_button.collidepoint(event.pos):
                msg = ("No time recorded yet" if self.best_time is None
                       else f"{self.best_time} seconds")
                self.popup = ("Shortest time", msg)

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
        if key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.held.add(key)
            self.restart()
            return

        self.held.add(key)
        if key in JOHN_KEYS:
            self.john_seen.add(key)

        if key == pygame.K_p and not self.stopgame:
            self.paused = not self.paused
            return
        if self.paused:
            return

        # ---- snake 1
        if not self.s1dead:
            if key == pygame.K_UP:
                self.queue_turn(1, 90)
            if key == pygame.K_DOWN:
                self.queue_turn(1, 270)
            if key == pygame.K_LEFT:
                self.queue_turn(1, 180)
            if key == pygame.K_RIGHT:
                self.queue_turn(1, 0)

            if key == pygame.K_c and not self.s2dead and self.cd_freeze == 0:
                self.cooling = True
                self.cool_start = self.time
                self.cd_freeze = FREEZE_CD
            if key == pygame.K_3:
                self.colorR, self.colours = RED_MODE, 0
            if key == pygame.K_1:
                self.colorR, self.colours = BLUE_MODE, 1
            if key == pygame.K_6:
                self.colorR, self.colours = PURPLE, 2

        # ---- snake 2
        if not self.s2dead:
            if key == pygame.K_w:
                self.queue_turn(2, 90)
            if key == pygame.K_s:
                self.queue_turn(2, 270)
            if key == pygame.K_a:
                self.queue_turn(2, 180)
            if key == pygame.K_d:
                self.queue_turn(2, 0)

            if key == pygame.K_h:
                self.hide = True
            if key == pygame.K_o:
                self.orange = True
            if key == pygame.K_e and self.energy >= ENERGY_MIN:
                self.enhance = True
                self.colorL = GOLD
            if key == pygame.K_l and self.cd_lolly == 0:
                if (not self.larger and self.applex < WIDTH - 2 * SQ
                        and self.appley < HEIGHT - 2 * SQ
                        and self.applex > PANEL_W + SQ and self.appley > SQ):
                    self.larger = True
                    self.ring = [True] * 8
                    self.cd_lolly = LOLLY_CD
            if key == pygame.K_z and not self.zigzag and self.cd_reverse == 0:
                self.reverse_snake2()
                self.cd_reverse = REVERSE_CD

    def reverse_snake2(self):
        """Z: turn snake 2 around so its tail becomes its head."""
        n = self.s2size
        h2x, h2y = self.h2x, self.h2y
        self.zigzag = True
        self.turns2.clear()
        if h2x[n] == h2x[n - 1]:
            self.angle2 = 270 if h2y[n] > h2y[n - 1] else 90
        else:
            self.angle2 = 0 if h2x[n] > h2x[n - 1] else 180
        old_x, old_y = h2x[:], h2y[:]
        for i in range(1, n + 1):
            h2x[i] = old_x[n - i]
            h2y[i] = old_y[n - i]

    def on_keyup(self, key):
        self.held.discard(key)
        if key == pygame.K_h:
            self.hide = False
        if key == pygame.K_o:
            self.orange = False
        if key == pygame.K_e:
            self.enhance = False
            self.colorL = PINK
        if key == pygame.K_z:
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

    def cell(self, x, y, fill, outline=WHITE):
        r = pygame.Rect(x, y, SQ, SQ)
        pygame.draw.rect(self.screen, fill, r)
        pygame.draw.rect(self.screen, outline, r, 1)

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
        r = pygame.Rect(10, y, PANEL_W - 20, 14)
        pygame.draw.rect(self.screen, (225, 225, 225), r, border_radius=4)
        if frac > 0:
            pygame.draw.rect(self.screen, colour, (r.x, r.y, int(r.w * frac), r.h), border_radius=4)
        pygame.draw.rect(self.screen, (141, 141, 141), r, 1, border_radius=4)
        self.text(label, 11, BLACK, r.centerx, r.centery)

    def draw_abilities(self):
        ready, charging = (120, 210, 100), (150, 180, 220)

        def cd_bar(y, name, cd, total):
            secs = -(-cd // FPS)
            self.draw_bar(y, name if cd == 0 else f"{name}  {secs}s",
                          1 - cd / total, ready if cd == 0 else charging)

        cd_bar(442, "C  Freeze", self.cd_freeze, FREEZE_CD)
        cd_bar(460, "L  Lollies", self.cd_lolly, LOLLY_CD)
        cd_bar(478, "Z  Reverse", self.cd_reverse, REVERSE_CD)
        self.draw_bar(496, "E  Ghost", self.energy / ENERGY_MAX, GOLD)

    def draw_paused(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        self.screen.blit(dim, (0, 0))
        self.text("PAUSED", 48, WHITE, WIDTH // 2, HEIGHT // 2 - 20)
        self.text("Press P to resume", 20, WHITE, WIDTH // 2, HEIGHT // 2 + 25)

    def draw_board(self):
        self.screen.fill(WHITE)

        # scoreboard
        self.text(str(self.time // FPS), 15, (0, 255, 0), PANEL_W // 2, 100)
        self.text(f"snake 1\n{self.s1size - 1}", 25, LIME, PANEL_W // 2, HEIGHT // 4)
        self.text(f"snake 2\n{self.s2size - 1}", 25, LIME, PANEL_W // 2, HEIGHT * 5 // 8)
        if self.s1size - 1 == 7 and self.s2size - 1 == 7:
            self.text("Congratulations on\nyour special day!", 12, LIME, PANEL_W // 2, 40)

        if not self.s2dead:
            self.draw_abilities()

        # buttons
        for rect, label in ((self.best_button, "Shortest time"), (self.aim_button, "Aim")):
            pygame.draw.rect(self.screen, (218, 218, 218), rect, border_radius=10)
            pygame.draw.rect(self.screen, (141, 141, 141), rect, 1, border_radius=10)
            self.text(label, 14, BLACK, rect.centerx, rect.centery)

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
            self.draw_snake(self.h2x, self.h2y, self.s2size, self.colorL)

    def draw_pass_screen(self):
        self.screen.fill(WHITE)
        self.text("You passed!\nMarks:", 32, BLACK, WIDTH // 2, HEIGHT * 3 // 8)
        for n, (size, dead) in enumerate(((self.s1size, self.s1dead), (self.s2size, self.s2dead))):
            y = HEIGHT * 3 // 8 + 64 + 32 * n
            self.text(f"Snake{n + 1}: {size - 1}", 32, BLACK, WIDTH // 2, y)
            self.text("(Dead)" if dead else "(Alive)", 32,
                      (255, 0, 0) if dead else (0, 255, 0), WIDTH // 2 + 4 * 32 + 10, y)

    def draw_escape_screen(self):
        self.screen.fill((0, 128, 255))
        self.text("Congratulations,\nyou escaped\nEnjoy the freedom", 50, GOLD,
                  WIDTH // 2, HEIGHT // 2)

    def draw_game_over(self):
        self.text("GAME OVER", 32, BLACK, WIDTH // 2, HEIGHT * 3 // 8)
        self.text(f"Score:  {self.s1size + self.s2size - 2} units long in total", 32, BLACK,
                  WIDTH // 2, HEIGHT * 7 // 16)
        self.text("To restart, press Shift.", 32, BLACK, WIDTH // 2, HEIGHT // 2)

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
        self.text(msg, 20, BLACK, r.centerx, r.centery - 5)
        ok = self.popup_ok_rect()
        pygame.draw.rect(self.screen, (218, 218, 218), ok, border_radius=8)
        pygame.draw.rect(self.screen, (141, 141, 141), ok, 1, border_radius=8)
        self.text("OK", 16, BLACK, ok.centerx, ok.centery)

    def draw(self):
        if self.stopgame and self.passed == 1:
            self.draw_pass_screen()
        elif self.stopgame and self.passed == 2:
            self.draw_escape_screen()
        else:
            self.draw_board()
            if self.stopgame:
                self.draw_game_over()

        # easter eggs from the original
        if CHLOE_KEYS <= self.held:
            self.text(["It Looked Like Peace Ran Away,", "", "Your Forgiveness Objected.", "",
                       "Rise,", "", "Your Omnipotent Unification"],
                      12, LIME, WIDTH // 8, HEIGHT // 2 - 50)
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
            if not self.popup and not self.stopgame and not self.paused:
                self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
