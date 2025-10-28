import random, math, pygame
from array import array
from collections import deque
import os

# -------------------- CONFIG --------------------
TILE = 56
COLS, ROWS = 16, 12
GRID_W, GRID_H = COLS * TILE, ROWS * TILE
SIDEBAR_W = 360
WIDTH, HEIGHT = GRID_W + SIDEBAR_W, GRID_H
FPS = 60

# Colors
BG = (18, 18, 24)
GRID = (44, 44, 54)
EMPTY = (225, 226, 236)
WALL  = (70, 74, 96)
SUPER = (160, 150, 210)
EXIT  = (110, 200, 120)
PLAYER= (245, 220, 120)
TEXT  = (235, 235, 245)
ACCENT  = (120, 180, 255)
ACCENT2 = (255, 170, 120)
DECO_TILE = (140, 150, 180)
TELEPORT = (120, 210, 255)
ABSORB   = (230, 100, 130)

# Flash colors (RGBA)
FLASH_OPEN      = (50, 210, 120, 160)
FLASH_WALL      = (220, 60, 60, 160)
FLASH_PAIR_SAME = (120, 180, 255, 150)
FLASH_PAIR_OPP  = (255, 170, 120, 150)
FLASH_QRING     = (200, 200, 60, 140)

# Quantum params
P_WALL_ON_COLLAPSE = 0.40
P_TUNNEL = 0.10
OBSERVE_RADIUS_PASSIVE = 1

# Reroute
REROUTE_RADIUS = 2
REROUTE_P_WALL = 0.20
REROUTE_CHARGES = 3
REROUTE_COOLDOWN_MOVES = 5

# Resources
ENERGY_MAX_BASE = 20
COST_REROUTE = 3
COST_TUNNEL  = 2
COST_TELEPORT = 1
MIN_ENERGY_TO_WIN = 0

# Decoherence
DECO_TTL_BASE = 10
DECO_SHOW_FADE = True

# Tiles
EMPTY_T, WALL_T, SUPER_T, EXIT_T = 0, 1, 2, 3
TELEPORT_T, ABSORB_T = 4, 5
SAME, OPPOSITE = 0, 1

# -------------------- LEVELS --------------------
LEVELS = [
    {"p_wall":0.35, "tunnel":0.08, "teleports":0, "absorbs":0, "energy":ENERGY_MAX_BASE+5, "deco_ttl":DECO_TTL_BASE+5, "pairs":6},
    {"p_wall":0.40, "tunnel":0.10, "teleports":2, "absorbs":2, "energy":ENERGY_MAX_BASE+4, "deco_ttl":DECO_TTL_BASE+4, "pairs":8},
    {"p_wall":0.43, "tunnel":0.11, "teleports":3, "absorbs":2, "energy":ENERGY_MAX_BASE+2, "deco_ttl":DECO_TTL_BASE+3, "pairs":9},
    {"p_wall":0.45, "tunnel":0.12, "teleports":4, "absorbs":3, "energy":ENERGY_MAX_BASE,   "deco_ttl":DECO_TTL_BASE+2, "pairs":10},
    {"p_wall":0.48, "tunnel":0.12, "teleports":5, "absorbs":4, "energy":ENERGY_MAX_BASE-2, "deco_ttl":DECO_TTL_BASE+1, "pairs":11},
    {"p_wall":0.50, "tunnel":0.13, "teleports":6, "absorbs":4, "energy":ENERGY_MAX_BASE-3, "deco_ttl":DECO_TTL_BASE,   "pairs":12},
]

# Difficulty presets (not shown in UI; Standard used)
DIFFS = [
    {"name":"Relaxed",  "wall_mult":1.00, "passive_p_wall":0.00, "frontier_steps":10, "frontier_p_wall":0.05,
     "deco_ttl_bonus":+5, "deco_protect_r":2, "reroute_bonus":+1, "reroute_cd_delta":-2, "tunnel_mult":1.2},
    {"name":"Standard", "wall_mult":1.00, "passive_p_wall":0.20, "frontier_steps":5,  "frontier_p_wall":0.15,
     "deco_ttl_bonus":+2, "deco_protect_r":1, "reroute_bonus":0,  "reroute_cd_delta":0,  "tunnel_mult":1.3},
    {"name":"Hard",     "wall_mult":1.15, "passive_p_wall":0.30, "frontier_steps":3,  "frontier_p_wall":0.20,
     "deco_ttl_bonus":0,  "deco_protect_r":1, "reroute_bonus":-1, "reroute_cd_delta":+1, "tunnel_mult":0.9},
]

# -------------------- SOUND --------------------
class Sfx:
    enabled = False
    snd_open = snd_wall = snd_pair = snd_q = snd_tp = snd_absorb = None

def init_sound():
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
        Sfx.enabled = True
    except Exception:
        Sfx.enabled = False
        return
    def tone(freq=440, ms=120, vol=0.35):
        sr = pygame.mixer.get_init()[0]
        n = int(sr * ms / 1000)
        from math import sin, pi
        buf = array('h'); amp = int(vol * 32767)
        for i in range(n):
            t = i / sr
            s = sin(2*pi*freq*t)
            a = min(1.0, i/(0.002*sr), (n-1-i)/(0.002*sr))
            buf.append(int(amp * s * max(0.0, min(1.0, a))))
        return pygame.mixer.Sound(buffer=buf.tobytes())
    try:
        Sfx.snd_open    = tone(880, 80, 0.35)
        Sfx.snd_wall    = tone(220, 120, 0.35)
        Sfx.snd_pair    = tone(660, 100, 0.30)
        Sfx.snd_q       = tone(520, 160, 0.30)
        Sfx.snd_tp      = tone(990, 70, 0.30)
        Sfx.snd_absorb  = tone(180, 300, 0.35)
    except Exception:
        Sfx.enabled = False

def play(snd):
    if Sfx.enabled and snd:
        try: snd.play()
        except Exception: pass

# -------------------- HELPERS --------------------
def draw_text(surf, txt, x, y, font, color=TEXT):
    surf.blit(font.render(txt, True, color), (x, y))

def rounded_panel(w, h, alpha=180):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, alpha), s.get_rect(), border_radius=12)
    return s

def neighbors_within_radius(px, py, r):
    out = []
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if abs(dx) + abs(dy) <= r:
                out.append((px+dx, py+dy))
    return out

def in_bounds(x, y): return 0 <= x < COLS and 0 <= y < ROWS

# ---- Arrow-safe font + baseline renderer ----
def _font_has_all(font_obj, text):
    try:
        mets = font_obj.metrics(text)
        return mets is not None and all(m is not None for m in mets)
    except Exception:
        return False

def get_arrow_font(size, fallback_font):
    here = os.path.dirname(os.path.abspath(__file__))
    local_paths = [
        os.path.join(here, "DejaVuSans.ttf"),
        os.path.join(here, "NotoSansSymbols2.ttf"),
        os.path.join(here, "NotoSansSymbols-Regular.ttf"),
        os.path.join(here, "assets", "DejaVuSans.ttf"),
        os.path.join(here, "assets", "NotoSansSymbols2.ttf"),
        os.path.join(here, "assets", "NotoSansSymbols-Regular.ttf"),
    ]
    for p in local_paths:
        if os.path.isfile(p):
            try:
                f = pygame.font.Font(p, size)
                if _font_has_all(f, "←↑→↓"):
                    return f
            except:
                pass
    for name in ["DejaVu Sans", "Noto Sans Symbols 2", "Noto Sans Symbols", "Segoe UI Symbol", "Arial Unicode MS", "Symbola"]:
        try:
            f = pygame.font.SysFont(name, size)
            if _font_has_all(f, "←↑→↓"):
                return f
        except:
            pass
    return fallback_font

def draw_mixed_baseline(surf, x, y, chunks, color=TEXT):
    if not chunks: return 0
    baseline_ascent = max(f.get_ascent() for _, f in chunks)
    cx = x
    for text, f in chunks:
        dy = baseline_ascent - f.get_ascent()
        surf.blit(f.render(text, True, color), (cx, y + dy))
        cx += f.size(text)[0]
    return cx - x

# ---- NEW: simple text wrap helper ----
def draw_wrapped_text(surf, text, x, y, font, color, max_width, line_gap=2):
    """Render text wrapped to max_width starting at (x,y). Returns final y (after last line)."""
    words = text.split(" ")
    line = ""
    yy = y
    for w in words:
        test = (line + (" " if line else "") + w)
        if font.size(test)[0] <= max_width:
            line = test
        else:
            if line: surf.blit(font.render(line, True, color), (x, yy))
            else:    surf.blit(font.render(w,   True, color), (x, yy)); w = ""
            yy += font.get_linesize() + line_gap
            line = w
    if line:
        surf.blit(font.render(line, True, color), (x, yy))
        yy += font.get_linesize() + line_gap
    return yy

# -------------------- WORLD GEN (unchanged) --------------------
def carve_hidden_path(start, goal):
    (sx, sy), (gx, gy) = start, goal
    x, y = sx, sy
    path = [(x, y)]
    visited = {(x, y)}
    attempts = 0
    while (x, y) != (gx, gy) and attempts < 5000:
        dx = 0 if random.random() < 0.4 else (1 if gx > x else (-1) if gx < x else 0)
        dy = 0 if random.random() < 0.4 else (1 if gy > y else (-1) if gy < y else 0)
        if random.random() < 0.35 or (dx == 0 and dy == 0):
            if random.random() < 0.5: dx, dy = random.choice([-1, 1]), 0
            else: dy, dx = random.choice([-1, 1]), 0
        nx, ny = x + dx, y + dy
        if 1 <= nx < COLS-1 and 1 <= ny < ROWS-1 and (nx, ny) not in visited:
            path.append((nx, ny)); visited.add((nx, ny)); x, y = nx, ny
        attempts += 1
    if path[-1] != (gx, gy): path.append((gx, gy))
    return path

def make_grid_and_pairs(cfg_pairs):
    grid = [[SUPER_T for _ in range(COLS)] for _ in range(ROWS)]
    for x in range(COLS):
        grid[0][x] = grid[ROWS-1][x] = WALL_T
    for y in range(ROWS):
        grid[y][0] = WALL_T; grid[y][COLS-1] = WALL_T

    start = (1, 1)
    exit_pos = (COLS-2, ROWS-2)
    grid[start[1]][start[0]] = EMPTY_T
    grid[exit_pos[1]][exit_pos[0]] = EXIT_T

    for _ in range(48):
        x = random.randint(2, COLS-3)
        y = random.randint(2, ROWS-3)
        grid[y][x] = random.choice([WALL_T, SUPER_T])

    safe_path = carve_hidden_path(start, exit_pos)
    safe_set = set(safe_path)
    for (x, y) in safe_path:
        if (x, y) not in (start, exit_pos):
            grid[y][x] = SUPER_T
        if grid[y][x] == WALL_T:
            grid[y][x] = SUPER_T

    candidates = [(x, y) for y in range(1, ROWS-1) for x in range(1, COLS-1)
                  if grid[y][x] == SUPER_T and (x, y) not in {start, exit_pos}]
    random.shuffle(candidates)
    entangled_pairs, used = [], set()
    target_pairs = min(cfg_pairs, len(candidates)//4)
    i = 0
    while len(entangled_pairs) < target_pairs and i+1 < len(candidates):
        a, b = candidates[i], candidates[i+1]; i += 2
        if a in used or b in used: continue
        if abs(a[0]-b[0]) + abs(a[1]-b[1]) < 2: continue
        used.add(a); used.add(b)
        mode = random.choice([SAME, OPPOSITE])
        entangled_pairs.append((a, b, mode))
    entangled_map = {}
    for a, b, mode in entangled_pairs:
        entangled_map[a] = (b, mode)
        entangled_map[b] = (a, mode)

    return grid, start, exit_pos, entangled_pairs, entangled_map, safe_set

# -------------------- COLLAPSE / PATH CHECK / SPECIALS (unchanged) --------------------
def add_flash(flashes, x, y, rgba, ttl=14):
    flashes.append([pygame.Rect(x*TILE, y*TILE, TILE, TILE), list(rgba), ttl])

def collapse_with_value(grid, x, y, value, flashes=None):
    if in_bounds(x, y) and grid[y][x] == SUPER_T:
        grid[y][x] = value
        if flashes is not None:
            add_flash(flashes, x, y, FLASH_OPEN if value == EMPTY_T else FLASH_WALL)
        return True
    return False

def collapse_at(grid, x, y, entangled_map, flashes, safe_set, p_wall_override=None):
    if not in_bounds(x, y) or grid[y][x] != SUPER_T: return 0
    if (x, y) in safe_set:
        value = EMPTY_T
    else:
        p = P_WALL_ON_COLLAPSE if p_wall_override is None else p_wall_override
        value = WALL_T if random.random() < p else EMPTY_T
    grid[y][x] = value
    add_flash(flashes, x, y, FLASH_OPEN if value == EMPTY_T else FLASH_WALL)
    play(Sfx.snd_open if value == EMPTY_T else Sfx.snd_wall)
    collapsed = 1
    key = (x, y)
    if key in entangled_map:
        (px, py), mode = entangled_map[key]
        if in_bounds(px, py) and grid[py][px] == SUPER_T:
            if mode == SAME:
                collapse_with_value(grid, px, py, value, flashes)
                add_flash(flashes, px, py, FLASH_PAIR_SAME)
            else:
                opposite = EMPTY_T if value == WALL_T else WALL_T
                collapse_with_value(grid, px, py, opposite, flashes)
                add_flash(flashes, px, py, FLASH_PAIR_OPP)
            collapsed += 1
            play(Sfx.snd_pair)
    return collapsed

def collapse_area(grid, center, entangled_map, r, flashes, safe_set, p_wall_override=None):
    px, py = center
    total = 0
    cells = neighbors_within_radius(px, py, r)
    cells.sort(key=lambda c: abs(c[0]-px)+abs(c[1]-py))
    for (x, y) in cells:
        if in_bounds(x, y) and grid[y][x] == SUPER_T:
            total += collapse_at(grid, x, y, entangled_map, flashes, safe_set, p_wall_override)
    return total

def has_empty_path(grid, start, goal):
    sx, sy = start; gx, gy = goal
    q = deque([(sx, sy)]); seen = {(sx, sy)}
    while q:
        x, y = q.popleft()
        if (x, y) == (gx, gy): return True
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if in_bounds(nx, ny) and (nx, ny) not in seen:
                v = grid[ny][nx]
                if v in (EMPTY_T, EXIT_T, TELEPORT_T):
                    seen.add((nx, ny)); q.append((nx, ny))
    return False

def place_specials(grid, count, forbidden, tile_id):
    placed = []
    tries = 0
    while len(placed) < count and tries < 5000:
        x = random.randint(2, COLS-3)
        y = random.randint(2, ROWS-3)
        if (x, y) in forbidden: tries += 1; continue
        if grid[y][x] in (SUPER_T, EMPTY_T):
            grid[y][x] = tile_id
            placed.append((x, y))
            forbidden.add((x, y))
        tries += 1
    return placed

def pair_up(coords):
    random.shuffle(coords)
    pairs = []
    for i in range(0, len(coords)-1, 2):
        pairs.append((coords[i], coords[i+1]))
    return pairs

# -------------------- INTRO / HELP (unchanged logic) --------------------
def show_intro(screen, title_font, body_font, tiny_font, arrow_font_body):
    clock = pygame.time.Clock()
    panel_w, panel_h = int(WIDTH*0.78), int(HEIGHT*0.78)
    panel_x = (WIDTH - panel_w)//2
    panel_y = (HEIGHT - panel_h)//2
    btn_w, btn_h = 200, 54
    start_btn = pygame.Rect(0, 0, btn_w, btn_h)
    start_btn.center = (WIDTH//2, panel_y + panel_h - 70)

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); raise SystemExit
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); raise SystemExit
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    return
            if e.type == pygame.MOUSEBUTTONDOWN and start_btn.collidepoint(e.pos):
                return

        screen.fill(BG)
        title = "Quantum Maze Explorer"
        sub   = "Quantum-inspired puzzle: superposition, entanglement, tunneling, decoherence."
        tw = title_font.render(title, True, TEXT)
        sw = body_font.render(sub, True, TEXT)
        screen.blit(tw, (WIDTH//2 - tw.get_width()//2, panel_y - 24 - tw.get_height()))
        screen.blit(sw, (WIDTH//2 - sw.get_width()//2, panel_y - 24))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0,0,0,205), panel.get_rect(), border_radius=18)
        screen.blit(panel, (panel_x, panel_y))

        x0, y0 = panel_x + 24, panel_y + 24
        draw_mixed_baseline(
            screen, x0, y0 + 0*28,
            [("Goal: reach the EXIT (green). Move with ", body_font),
             ("←↑→↓", arrow_font_body),
             (" / WASD.", body_font)]
        )
        lines = [
            "Observation: nearby '?' collapse as you move (r=1).",
            "Entanglement: SOME '?' are paired — SAME/OPPOSITE collapse.",
            "Q — Quantum Reroute: re-superpose nearby walls, friendlier recollapse.",
            "T — Tunneling (persists): try stepping through a wall (costs energy).",
            "Teleport tiles: jump between paired nodes (small energy cost).",
            "Absorption nodes: collapse you — instant level restart.",
            "E — Toggle entanglement overlay (persists).",
            "G — Toggle arrow to EXIT (persists).",
            "SPACE — used only to go NEXT LEVEL after you win.",
            "Tip: Press H anytime in-game to re-open this tutorial.",
        ]
        for i, line in enumerate(lines, start=1):
            draw_text(screen, line, x0, y0 + i*28, body_font)

        pygame.draw.rect(screen, (35, 35, 45), start_btn, border_radius=12)
        pygame.draw.rect(screen, (90, 90, 110), start_btn, 2, border_radius=12)
        lbl = body_font.render("Start (Enter)", True, TEXT)
        screen.blit(lbl, lbl.get_rect(center=start_btn.center))

        draw_text(screen, "ESC to quit", panel_x + 16, panel_y + panel_h - 28, tiny_font)
        pygame.display.flip()
        clock.tick(60)

def show_help_overlay(screen, title_font, body_font, tiny_font, arrow_font_body):
    clock = pygame.time.Clock()
    panel_w, panel_h = int(WIDTH*0.78), int(HEIGHT*0.78)
    panel_x = (WIDTH - panel_w)//2
    panel_y = (HEIGHT - panel_h)//2
    btn_w, btn_h = 200, 54
    resume_btn = pygame.Rect(0, 0, btn_w, btn_h)
    resume_btn.center = (WIDTH//2, panel_y + panel_h - 70)

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); raise SystemExit
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_h, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                    return
            if e.type == pygame.MOUSEBUTTONDOWN and resume_btn.collidepoint(e.pos):
                return

        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        screen.blit(dim, (0, 0))

        title = "Tutorial / Controls"
        tw = title_font.render(title, True, TEXT)
        screen.blit(tw, (WIDTH//2 - tw.get_width()//2, panel_y - 24 - tw.get_height()))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0,0,0,205), panel.get_rect(), border_radius=18)
        screen.blit(panel, (panel_x, panel_y))

        x0, y0 = panel_x + 24, panel_y + 24
        draw_mixed_baseline(
            screen, x0, y0 + 0*28,
            [("Move: ", body_font), ("←↑→↓", arrow_font_body), (" / WASD", body_font)]
        )
        lines = [
            "Q — Quantum Reroute (costs energy, friendlier recollapse).",
            "T — Toggle Tunneling (persists across levels/restarts).",
            "E — Toggle entanglement overlay (persists).",
            "G — Toggle arrow to EXIT (persists).",
            "Teleport tiles — move between paired nodes (small energy cost).",
            "Absorption nodes — instant level restart.",
            "Superposition '?' collapses when you approach (r=1).",
            "SPACE — go to NEXT LEVEL after you win.",
            "Tip: Never-stuck guard ensures at least one open neighbor when boxed in.",
        ]
        for i, line in enumerate(lines, start=1):
            draw_text(screen, line, x0, y0 + i*28, body_font)

        pygame.draw.rect(screen, (35, 35, 45), resume_btn, border_radius=12)
        pygame.draw.rect(screen, (90, 90, 110), resume_btn, 2, border_radius=12)
        lbl = body_font.render("Resume (H/Enter)", True, TEXT)
        screen.blit(lbl, lbl.get_rect(center=resume_btn.center))

        draw_text(screen, "ESC also resumes to game", panel_x + 16, panel_y + panel_h - 28, tiny_font)
        pygame.display.flip()
        clock.tick(60)

# -------------------- MAIN --------------------
def main():
    pygame.init()
    init_sound()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Quantum Maze Explorer — v0.90.2")
    clock = pygame.time.Clock()

    # Base UI fonts
    font = pygame.font.SysFont(None, 24)
    big  = pygame.font.SysFont(None, 30)
    tiny = pygame.font.SysFont(None, 20)

    # Arrow-capable fonts
    arrow_font_tiny = get_arrow_font(tiny.get_height(), tiny)
    arrow_font_body = get_arrow_font(font.get_height(), font)

    # Intro once
    show_intro(screen, pygame.font.SysFont(None, 48), font, tiny, arrow_font_body)

    # PERSISTENT prefs
    prefs = {"tunnel": False, "show_entanglement": True, "show_arrow": True}

    level_idx = 0
    diff_idx = 1  # Standard
    next_btn_rect = None

    def start_level(idx, d_idx):
        global P_WALL_ON_COLLAPSE, P_TUNNEL
        cfg = LEVELS[min(idx, len(LEVELS)-1)]
        dcf = DIFFS[d_idx]

        P_WALL_ON_COLLAPSE = cfg["p_wall"] * dcf["wall_mult"]
        P_TUNNEL = cfg["tunnel"] * dcf["tunnel_mult"]

        grid, player, exit_pos, entangled_pairs, entangled_map, safe_set = make_grid_and_pairs(cfg["pairs"])
        deco = {}

        forbidden = {player, exit_pos}
        tp_coords = place_specials(grid, cfg["teleports"], forbidden, TELEPORT_T)
        place_specials(grid, cfg["absorbs"], forbidden, ABSORB_T)
        tp_pairs = pair_up(tp_coords)
        tp_map = {a:b for a,b in tp_pairs} | {b:a for a,b in tp_pairs}

        state = {
            "grid": grid, "player": player, "exit": exit_pos,
            "pairs": entangled_pairs, "emap": entangled_map, "safe": safe_set,
            "deco": deco, "tp_map": tp_map,
            "steps": 0, "won": False,
            "tunnel": prefs["tunnel"],
            "show_entanglement": prefs["show_entanglement"],
            "show_arrow": prefs["show_arrow"],
            "show_controls": True, "show_status": True,
            "flashes": [], "toasts": [], "rpulse": 0,
            "energy": max(0, cfg["energy"]),
            "reroute_charges": max(0, REROUTE_CHARGES + dcf["reroute_bonus"]),
            "reroute_cd": max(1, REROUTE_COOLDOWN_MOVES + dcf["reroute_cd_delta"]),
            "diff_idx": d_idx, "diff_name": dcf["name"],
            "passive_p_wall": dcf["passive_p_wall"],
            "frontier_steps": dcf["frontier_steps"],
            "frontier_p_wall": dcf["frontier_p_wall"],
            "deco_ttl": cfg["deco_ttl"] + dcf["deco_ttl_bonus"],
            "deco_protect_r": dcf["deco_protect_r"],
        }

        # never-stuck guard
        def ensure_one_exit_open_local(px, py):
            g = state["grid"]
            neigh = [(px+1,py),(px-1,py),(px,py+1),(px,py-1)]
            any_open = False
            options = []
            for (x,y) in neigh:
                if not in_bounds(x,y): continue
                v = g[y][x]
                if v in (EMPTY_T, EXIT_T, TELEPORT_T):
                    any_open = True
                elif v == SUPER_T:
                    options.append((x,y))
            if not any_open and options:
                ex, ey = state["exit"]
                options.sort(key=lambda t: abs(t[0]-ex)+abs(t[1]-ey))
                x,y = options[0]
                collapse_at(g, x, y, state["emap"], state["flashes"], state["safe"], p_wall_override=0.0)

        collapse_area(state["grid"], state["player"], state["emap"], OBSERVE_RADIUS_PASSIVE, state["flashes"], state["safe"], p_wall_override=state["passive_p_wall"])
        ensure_one_exit_open_local(state["player"][0], state["player"][1])

        def add_toast(text, x, y):
            surf = big.render(text, True, (255,255,255))
            state["toasts"].append([surf, [x, y], -0.6, 45])

        def tick_decoherence():
            g = state["grid"]; d = state["deco"]; p = state["player"]
            for y in range(ROWS):
                for x in range(COLS):
                    if g[y][x] == EMPTY_T:
                        d.setdefault((x, y), state["deco_ttl"])
                    elif g[y][x] in (WALL_T, SUPER_T, EXIT_T, TELEPORT_T, ABSORB_T):
                        d.pop((x, y), None)
            protect = set(neighbors_within_radius(p[0], p[1], state["deco_protect_r"]))
            to_super = []
            for (x, y), ttl in list(d.items()):
                if (x, y) in protect:
                    d[(x, y)] = state["deco_ttl"]
                else:
                    d[(x, y)] = ttl - 1
                    if d[(x, y)] <= 0:
                        to_super.append((x, y)); d.pop((x, y), None)
            for (x, y) in to_super:
                if g[y][x] == EMPTY_T:
                    g[y][x] = SUPER_T
                    add_flash(state["flashes"], x, y, FLASH_WALL)

        def ensure_frontier_grace(nx, ny):
            return state["frontier_p_wall"] if state["steps"] < state["frontier_steps"] else None

        def try_move(dx, dy):
            if state["won"]: return
            g = state["grid"]; em = state["emap"]; sa = state["safe"]
            p = state["player"]; nx, ny = p[0]+dx, p[1]+dy
            if in_bounds(nx, ny):
                target = g[ny][nx]
                if target == SUPER_T:
                    pw = ensure_frontier_grace(nx, ny)
                    collapse_at(g, nx, ny, em, state["flashes"], sa, p_wall_override=pw)
                    target = g[ny][nx]
                if target in (EMPTY_T, EXIT_T, TELEPORT_T, ABSORB_T):
                    if target == ABSORB_T:
                        play(Sfx.snd_absorb)
                        return "absorb"
                    state["player"] = (nx, ny)
                    state["steps"] += 1
                    collapse_area(g, state["player"], em, OBSERVE_RADIUS_PASSIVE, state["flashes"], sa, p_wall_override=state["passive_p_wall"])
                    if state["reroute_cd"] > 0: state["reroute_cd"] -= 1
                    if target == TELEPORT_T:
                        if state["energy"] >= COST_TELEPORT:
                            state["energy"] -= COST_TELEPORT
                            tp = state["tp_map"].get((nx, ny))
                            if tp:
                                state["player"] = tp
                                play(Sfx.snd_tp)
                                collapse_area(g, state["player"], em, OBSERVE_RADIUS_PASSIVE, state["flashes"], sa, p_wall_override=state["passive_p_wall"])
                        else:
                            add_toast("Not enough energy to teleport", nx*TILE+8, ny*TILE-10)
                    # guard
                    neigh = [(state["player"][0]+1,state["player"][1]),(state["player"][0]-1,state["player"][1]),
                             (state["player"][0],state["player"][1]+1),(state["player"][0],state["player"][1]-1)]
                    any_open=False; opts=[]
                    for (x,y) in neigh:
                        if not in_bounds(x,y): continue
                        v=g[y][x]
                        if v in (EMPTY_T,EXIT_T,TELEPORT_T): any_open=True
                        elif v==SUPER_T: opts.append((x,y))
                    if not any_open and opts:
                        ex,ey=state["exit"]; opts.sort(key=lambda t: abs(t[0]-ex)+abs(t[1]-ey))
                        x,y=opts[0]; collapse_at(g,x,y,em,state["flashes"],sa,p_wall_override=0.0)

                elif target == WALL_T and state["tunnel"]:
                    if state["energy"] < COST_TUNNEL:
                        add_toast("Not enough energy to tunnel", p[0]*TILE+8, p[1]*TILE-10)
                    else:
                        if random.random() < P_TUNNEL:
                            state["energy"] -= COST_TUNNEL
                            state["player"] = (nx, ny)
                            state["steps"] += 1
                            collapse_area(g, state["player"], em, OBSERVE_RADIUS_PASSIVE, state["flashes"], sa, p_wall_override=state["passive_p_wall"])
                            if state["reroute_cd"] > 0: state["reroute_cd"] -= 1
                        else:
                            add_toast("Tunnel failed", p[0]*TILE+8, p[1]*TILE-10)

            if state["player"] == state["exit"] and state["energy"] >= MIN_ENERGY_TO_WIN:
                state["won"] = True
            return None

        def quantum_reroute():
            if state["won"]: return
            if state["reroute_charges"] <= 0:
                add_toast("No reroute charges", state["player"][0]*TILE+8, state["player"][1]*TILE-10); return
            if state["reroute_cd"] > 0:
                add_toast(f"Reroute cooldown: {state['reroute_cd']}", state["player"][0]*TILE+8, state["player"][1]*TILE-10); return
            if state["energy"] < COST_REROUTE:
                add_toast("Not enough energy", state["player"][0]*TILE+8, state["player"][1]*TILE-10); return

            state["energy"] -= COST_REROUTE
            g = state["grid"]; p = state["player"]
            for (x, y) in neighbors_within_radius(p[0], p[1], REROUTE_RADIUS):
                if in_bounds(x, y) and g[y][x] == WALL_T and (x, y) != state["exit"] and x not in (0, COLS-1) and y not in (0, ROWS-1):
                    g[y][x] = SUPER_T
            collapsed = collapse_area(g, p, state["emap"], REROUTE_RADIUS, state["flashes"], state["safe"], p_wall_override=REROUTE_P_WALL)
            state["reroute_charges"] -= 1
            state["reroute_cd"] = max(1, state["reroute_cd"])
            state["rpulse"] = 16
            play(Sfx.snd_q)
            cx = p[0]*TILE + TILE//2; cy = p[1]*TILE + TILE//2
            add_toast(f"Reroute: {collapsed} collapsed", cx-90, cy-12)

        state["add_toast"] = add_toast
        state["tick_deco"] = tick_decoherence
        state["try_move"] = try_move
        state["quantum_reroute"] = quantum_reroute

        return state

    state = start_level(level_idx, diff_idx)

    # -------------------- LOOP --------------------
    running = True
    next_btn_rect = None
    while running:
        dt = clock.tick(FPS)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False; continue

            if e.type == pygame.KEYDOWN:
                k = e.key

                if k == pygame.K_ESCAPE:
                    running = False; continue
                if k == pygame.K_r:
                    state = start_level(level_idx, diff_idx); continue

                if state["won"]:
                    last_level = (level_idx == len(LEVELS)-1)
                    if k == pygame.K_SPACE:
                        level_idx = 0 if last_level else min(level_idx+1, len(LEVELS)-1)
                        state = start_level(level_idx, diff_idx)
                    continue

                if k == pygame.K_h:
                    show_help_overlay(screen, pygame.font.SysFont(None, 48), font, tiny, arrow_font_body)
                    continue

                if k == pygame.K_e:
                    state["show_entanglement"] = not state["show_entanglement"]
                    prefs["show_entanglement"] = state["show_entanglement"]
                    px, py = state["player"]
                    state["toasts"].append([big.render("Links: ON" if state["show_entanglement"] else "Links: OFF", True, (255,255,255)), [px*TILE+8, py*TILE-10], -0.6, 35])

                moved_res = None
                if k in (pygame.K_UP, pygame.K_w):    moved_res = state["try_move"](0, -1)
                elif k in (pygame.K_DOWN, pygame.K_s):  moved_res = state["try_move"](0, 1)
                elif k in (pygame.K_LEFT, pygame.K_a):  moved_res = state["try_move"](-1, 0)
                elif k in (pygame.K_RIGHT, pygame.K_d): moved_res = state["try_move"](1, 0)
                elif k == pygame.K_q:
                    state["quantum_reroute"]()
                elif k == pygame.K_t:
                    state["tunnel"] = not state["tunnel"]
                    prefs["tunnel"] = state["tunnel"]
                    px, py = state["player"]
                    state["toasts"].append([big.render("Tunnel: ON" if state["tunnel"] else "Tunnel: OFF", True, (255,255,255)), [px*TILE+8, py*TILE-10], -0.6, 35])
                elif k == pygame.K_g:
                    state["show_arrow"] = not state["show_arrow"]
                    prefs["show_arrow"] = state["show_arrow"]
                    px, py = state["player"]
                    state["toasts"].append([big.render("Arrow: ON" if state["show_arrow"] else "Arrow: OFF", True, (255,255,255)), [px*TILE+8, py*TILE-10], -0.6, 35])
                elif k == pygame.K_l:
                    state["show_controls"] = not state["show_controls"]; state["show_status"] = not state["show_status"]

                if moved_res == "absorb":
                    play(Sfx.snd_absorb)
                    state = start_level(level_idx, diff_idx)
                    continue

            if e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = e.pos
                if state["won"] and next_btn_rect and next_btn_rect.collidepoint(mx, my):
                    last_level = (level_idx == len(LEVELS)-1)
                    level_idx = 0 if last_level else min(level_idx+1, len(LEVELS)-1)
                    state = start_level(level_idx, diff_idx)

        # Logic
        state["tick_deco"]()

        # Draw
        screen.fill(BG)
        g = state["grid"]; px, py = state["player"]

        # Grid
        for y in range(ROWS):
            for x in range(COLS):
                rect = pygame.Rect(x*TILE, y*TILE, TILE, TILE)
                v = g[y][x]
                if v == EMPTY_T:
                    if DECO_SHOW_FADE and (x, y) in state["deco"]:
                        ttl = state["deco"][(x, y)]
                        max_ttl = state["deco_ttl"]
                        f = max(0.0, min(1.0, ttl / max_ttl))
                        col = (
                            int(DECO_TILE[0] + (EMPTY[0]-DECO_TILE[0])*f),
                            int(DECO_TILE[1] + (EMPTY[1]-DECO_TILE[1])*f),
                            int(DECO_TILE[2] + (EMPTY[2]-DECO_TILE[2])*f),
                        )
                        pygame.draw.rect(screen, col, rect)
                    else:
                        pygame.draw.rect(screen, EMPTY, rect)
                elif v == WALL_T:
                    pygame.draw.rect(screen, WALL, rect)
                elif v == SUPER_T:
                    pygame.draw.rect(screen, SUPER, rect)
                    qsurf = big.render("?", True, (40, 20, 70))
                    screen.blit(qsurf, qsurf.get_rect(center=rect.center))
                elif v == EXIT_T:
                    pygame.draw.rect(screen, EXIT, rect)
                elif v == TELEPORT_T:
                    pygame.draw.rect(screen, TELEPORT, rect, border_radius=10)
                    pygame.draw.rect(screen, (20,40,60), rect, 2, border_radius=10)
                elif v == ABSORB_T:
                    pygame.draw.rect(screen, ABSORB, rect)
                    pygame.draw.rect(screen, (60,20,30), rect, 2)
                pygame.draw.rect(screen, GRID, rect, 1)

        # Entanglement overlay
        if state["show_entanglement"]:
            for (a, b, mode) in state["pairs"]:
                (ax, ay), (bx, by) = a, b
                if any(g[p[1]][p[0]] == SUPER_T for p in [a, b]):
                    axc = ax*TILE + TILE//2; ayc = ay*TILE + TILE//2
                    bxc = bx*TILE + TILE//2; byc = by*TILE + TILE//2
                    color = ACCENT if mode == SAME else ACCENT2
                    pygame.draw.line(screen, color, (axc, ayc), (bxc, byc), 2)
                    mx, my = (axc+bxc)//2, (ayc+byc)//2
                    pygame.draw.rect(screen, color, pygame.Rect(mx-1, my-1, 2, 2))

        # Passive ring
        for (x, y) in neighbors_within_radius(px, py, OBSERVE_RADIUS_PASSIVE):
            if in_bounds(x, y):
                pygame.draw.rect(screen, ACCENT, pygame.Rect(x*TILE, y*TILE, TILE, TILE), 2)

        # Player
        player_rect = pygame.Rect(px*TILE+8, py*TILE+8, TILE-16, TILE-16)
        pygame.draw.rect(screen, (0,0,0), player_rect.inflate(4,4), border_radius=14)
        pygame.draw.rect(screen, PLAYER, player_rect, border_radius=12)

        # Reroute ring (brief)
        if state["rpulse"] > 0:
            alpha = int(180 * (state["rpulse"] / 16))
            for (x, y) in neighbors_within_radius(px, py, REROUTE_RADIUS):
                if in_bounds(x, y):
                    pygame.draw.rect(screen, (FLASH_QRING[0], FLASH_QRING[1], FLASH_QRING[2], alpha),
                                     pygame.Rect(x*TILE, y*TILE, TILE, TILE), 3)
            state["rpulse"] -= 1

        # Flashes fade
        if state["flashes"]:
            overlay = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
            for f in state["flashes"][:]:
                rect, rgba, ttl = f
                pygame.draw.rect(overlay, tuple(rgba), rect, border_radius=6)
                f[2] -= 1
                rgba[3] = max(0, rgba[3] - 10)
                if f[2] <= 0 or rgba[3] <= 0:
                    state["flashes"].remove(f)
            screen.blit(overlay, (0, 0))

        # Toasts float
        for t in state["toasts"][:]:
            surf, pos, vy, ttl = t
            pos[1] += vy; t[3] = ttl - 1
            screen.blit(surf, (pos[0]+1, pos[1]+1)); screen.blit(surf, pos)
            if t[3] <= 0: state["toasts"].remove(t)

        # Tunnel badge when ON
        if state["tunnel"] and not state["won"]:
            badge = big.render("T", True, (0,0,0))
            badge_bg = pygame.Surface((22, 22), pygame.SRCALPHA)
            pygame.draw.circle(badge_bg, (255, 255, 255, 200), (11, 11), 11)
            screen.blit(badge_bg, (player_rect.right - 18, player_rect.top - 6))
            screen.blit(badge, (player_rect.right - 18 + 5, player_rect.top - 6 + 2))

        # Exit arrow
        if state["show_arrow"] and not state["won"]:
            cx = px*TILE + TILE//2; cy = py*TILE + TILE//2
            ex = state["exit"][0]*TILE + TILE//2; ey = state["exit"][1]*TILE + TILE//2
            dx, dy = ex-cx, ey-cy; d = math.hypot(dx, dy)
            if d > 1:
                ux, uy = dx/d, dy/d
                pygame.draw.line(screen, ACCENT, (cx+int(ux*10), cy+int(uy*10)),
                                 (cx+int(ux*28), cy+int(uy*28)), 3)

        # --- Sidebar ---
        sidebar_x = GRID_W + 8
        inner_w = SIDEBAR_W - 16
        text_max_w = inner_w - 24 

        # Controls
        panel = rounded_panel(inner_w, 260, 190) 
        screen.blit(panel, (sidebar_x, 8))
        x0, y0 = sidebar_x + 12, 16
        draw_text(screen, "Controls", x0, y0, big)
        y = y0 + 30

        # First line with arrows baseline-aligned
        draw_mixed_baseline(screen, x0, y, [("←↑→↓", arrow_font_tiny), (" / WASD Move", tiny)])
        y += tiny.get_linesize() + 6

        # Wrap long control lines
        control_lines = [
            "Q Reroute",
            "T Tunnel (persists)",
            "E Links overlay (persists)",
            "G Exit arrow (persists)",
            "L Toggle panels",
            "H Tutorial",
            "R Restart",
            "ESC Quit",
            "SPACE -> Next level (only when you win)",
        ]
        for line in control_lines:
            y = draw_wrapped_text(screen, line, x0, y, tiny, TEXT, text_max_w, line_gap=0)
            y += 4  # small gap between controls

        # Status
        panel2 = rounded_panel(inner_w, 260, 190)
        screen.blit(panel2, (sidebar_x, 8 + 260 + 10))
        x0, y0 = sidebar_x + 12, 8 + 260 + 18
        draw_text(screen, "Status", x0, y0, big)
        y = y0 + 30

        dist_m = abs(state["exit"][0]-px) + abs(state["exit"][1]-py)
        draw_text(screen, f"Level: {level_idx+1}/{len(LEVELS)}", x0, y, font); y += font.get_linesize() + 6

        draw_text(screen, f"Links: {'ON' if state['show_entanglement'] else 'OFF'}", x0, y, tiny); y += tiny.get_linesize()
        draw_text(screen, f"Arrow: {'ON' if state['show_arrow'] else 'OFF'}", x0, y, tiny); y += tiny.get_linesize()
        draw_text(screen, f"Tunneling: {'ON' if state['tunnel'] else 'OFF'}", x0, y, tiny); y += tiny.get_linesize() + 6

        draw_text(screen, f"Steps: {state['steps']}   Energy: {state['energy']}", x0, y, font); y += font.get_linesize() + 4
        draw_text(screen, f"P(wall): {P_WALL_ON_COLLAPSE:.2f}   P(tunnel): {P_TUNNEL:.2f}", x0, y, tiny); y += tiny.get_linesize()
        draw_text(screen, f"Reroute: {state['reroute_charges']}   Cooldown: {state['reroute_cd']}", x0, y, tiny); y += tiny.get_linesize()
        draw_text(screen, f"Exit distance: {dist_m}", x0, y, tiny); y += tiny.get_linesize()

        if not has_empty_path(state["grid"], state["player"], state["exit"]) and not state["won"]:
            y += 6
            y = draw_wrapped_text(screen, "Tip: Q for friendlier recollapse.", x0, y, tiny, (255,210,120), text_max_w, line_gap=0)

        # Win banner
        next_btn_rect = None
        if state["won"]:
            last_level = (level_idx == len(LEVELS)-1)
            panel_w = rounded_panel(GRID_W - 120, 220 if last_level else 200, 210)
            pan_x, pan_y = 60, HEIGHT//2 - (110 if last_level else 100)
            screen.blit(panel_w, (pan_x, pan_y))

            if last_level:
                draw_text(screen, "All levels cleared!", pan_x + 20, pan_y + 16, big)
                draw_text(screen, f"Total Steps (L{level_idx+1}): {state['steps']}   Energy: {state['energy']}",
                          pan_x + 20, pan_y + 50, font)
                draw_text(screen, "SPACE -> play again  •  R -> restart last level  •  ESC -> quit",
                          pan_x + 20, pan_y + 80, tiny)
                btn_label = "Play again"
            else:
                draw_text(screen, "You escaped!", pan_x + 20, pan_y + 16, big)
                draw_text(screen, f"Steps: {state['steps']}   Energy: {state['energy']}",
                          pan_x + 20, pan_y + 50, font)
                draw_text(screen, "SPACE -> next level   •   R -> restart",
                          pan_x + 20, pan_y + 80, tiny)
                btn_label = "Next level"

            btn_w, btn_h = 200, 48
            next_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
            next_btn_rect.center = (pan_x + (GRID_W - 120)//2, pan_y + (160 if last_level else 140))
            pygame.draw.rect(screen, (35, 35, 45), next_btn_rect, border_radius=12)
            pygame.draw.rect(screen, (90, 90, 110), next_btn_rect, 2, border_radius=12)
            lbl = font.render(btn_label, True, TEXT)
            screen.blit(lbl, lbl.get_rect(center=next_btn_rect.center))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
