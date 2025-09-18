import time
import json
import random
from pathlib import Path
import pygame

# --- Baked Layout Constants ---
FRONT_SPRITE_POS = (180, -30)
FRONT_SPRITE_SIZE = (152, 152)
BACK_SPRITE_POS = (-20, 59)
BACK_SPRITE_SIZE = (136, 136)
FRONT_NAME_POS = (24, 7)
FRONT_NAME_SIZE = (96, 18)
BACK_NAME_POS = (202, 111)
BACK_NAME_SIZE = (96, 18)
FRONT_HP_BAR_POS = (65, 27)
FRONT_HP_BAR_SIZE = (100, 12)
BACK_HP_BAR_POS = (191, 137)
BACK_HP_BAR_SIZE = (100, 12)
TIME_POS = (105, 159)
TIME_SIZE = (132, 72)
# -----------------------------

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE, FPS, SWAP_SECONDS,
    ASSETS_DIR, FRONT_DIR, BACK_DIR, BG_IMAGE,
    FONT_PATH, FONT_SIZE, TIME_FONT_SIZE,
    SPRITE_SIZE, PADDING,
    HP_BAR_WIDTH, HP_BAR_HEIGHT, HP_BAR_BORDER
)

# -------------------- Helpers --------------------

def safe_load_image(path, convert_alpha=True):
    p = Path(path)
    if not p.exists():
        return None
    try:
        surf = pygame.image.load(str(p))
        return surf.convert_alpha() if convert_alpha else surf.convert()
    except Exception:
        return None

def safe_load_font(path, size):
    if Path(path).exists():
        try:
            return pygame.font.Font(path, size)
        except Exception:
            pass
    return pygame.font.SysFont(None, size)

def list_pngs(folder):
    p = Path(folder)
    if not p.exists():
        return []
    return sorted([str(x) for x in p.glob("*.png")])

def name_from_path(path):
    return Path(path).stem if path else "?"

def load_pokemon_list():
    jl = Path(ASSETS_DIR) / "pokemonList.json"
    if not jl.exists():
        return {}
    try:
        with open(jl, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = {}
        if isinstance(data, dict):
            for k, v in data.items():
                out[str(k).lower()] = v
        elif isinstance(data, list):
            for item in data:
                n = str(item.get("name", "")).lower()
            #    d = item.get("dex")
                d = item.get("dex")  # keep as is if present
                if n:
                    out[n] = d
        return out
    except Exception:
        return {}

def draw_hp_bar(surface, x, y, value=1.0, width=None, height=None):
    value = max(0.0, min(1.0, float(value)))
    w = width if width is not None else HP_BAR_WIDTH
    h = height if height is not None else HP_BAR_HEIGHT
    outer = pygame.Rect(x, y, w, h)
    inner = pygame.Rect(
        x + HP_BAR_BORDER,
        y + HP_BAR_BORDER,
        int((w - 2 * HP_BAR_BORDER) * value),
        h - 2 * HP_BAR_BORDER,
    )
    pygame.draw.rect(surface, (0, 0, 0), outer, width=HP_BAR_BORDER)  # border (black)
    pygame.draw.rect(surface, (0, 200, 0), inner)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# -------------------- App --------------------

class App:
    def __init__(self):
        # Animation state
        self.animating = False
        self.anim_phase = None  # 'move', 'flash', or None
        self.anim_attacker = None  # 'front' or 'back'
        self.anim_defender = None
        self.anim_start_time = 0
        self.anim_duration = 0
        self.anim_flash_count = 0
        self.anim_flash_on = True
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        # Assets & fonts
        self.bg        = safe_load_image(BG_IMAGE)
        self.font      = safe_load_font(FONT_PATH, FONT_SIZE)
        self.time_font = safe_load_font(FONT_PATH, TIME_FONT_SIZE)

        # Pools and dex mapping
        self.front_paths = list_pngs(FRONT_DIR)
        self.back_paths  = list_pngs(BACK_DIR)
        self.dex_map     = load_pokemon_list()

        # Current selection
        self.curr_front_path = None
        self.curr_back_path  = None
        self.front_img_raw   = None
        self.back_img_raw    = None

        self.battle_interval = 5 * 60  # 5 minutes in seconds
        self.next_battle = time.time() + self.battle_interval
        self.front_hp = 1.0
        self.back_hp = 1.0
        self.pick_new_pair()

    # -------- selection & loading --------

    def pick_new_pair(self, loser=None):
        # loser: 'front', 'back', or None
        if not self.front_paths or not self.back_paths:
            return
        if loser == 'front':
            # Replace front, keep back
            fpath = random.choice([p for p in self.front_paths if name_from_path(p).lower() != name_from_path(self.curr_front_path).lower()])
            self.curr_front_path = fpath
            self.front_img_raw = safe_load_image(fpath)
            self.front_hp = 1.0
            self.back_hp = 1.0  # refill winner
        elif loser == 'back':
            # Replace back, keep front
            bpath = random.choice([p for p in self.back_paths if name_from_path(p).lower() != name_from_path(self.curr_back_path).lower()])
            self.curr_back_path = bpath
            self.back_img_raw = safe_load_image(bpath)
            self.front_hp = 1.0  # refill winner
            self.back_hp = 1.0
        else:
            # Initial pick: both random
            fpath = random.choice(self.front_paths)
            fname = name_from_path(fpath).lower()
            back_choices = [p for p in self.back_paths if name_from_path(p).lower() != fname] or self.back_paths
            bpath = random.choice(back_choices)
            self.curr_front_path = fpath
            self.curr_back_path  = bpath
            self.front_img_raw = safe_load_image(fpath)
            self.back_img_raw  = safe_load_image(bpath)
            self.front_hp = 1.0
            self.back_hp = 1.0

    def get_scaled(self, which):
        if which == "front":
            if not self.front_img_raw: return None
            # Get front sprite size from config_elements[0]
            w, h = self.config_elements[0]["rect"][2:4]
            return pygame.transform.smoothscale(self.front_img_raw, (int(w), int(h)))
        else:
            if not self.back_img_raw: return None
            # Get back sprite size from config_elements[1]
            w, h = self.config_elements[1]["rect"][2:4]
            return pygame.transform.smoothscale(self.back_img_raw, (int(w), int(h)))

    def draw_sprite_card(self, which, rect=None, draw_name=True, draw_hp=True):
        if which == "front":
            if not self.front_img_raw:
                return
            sprite = self.front_img_raw
        else:
            if not self.back_img_raw:
                return
            sprite = self.back_img_raw
        if rect:
            x, y, w, h = rect
            sprite = pygame.transform.smoothscale(sprite, (int(w), int(h)))
            self.screen.blit(sprite, (x, y))
        else:
            # fallback: draw at 0,0 with original size
            self.screen.blit(sprite, (0, 0))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if not self.animating and event.key == pygame.K_m:
                        # Force a battle turn with animation
                        self.start_battle_animation()
            # Immediately break if running is False, before any drawing or logic
            if not running:
                break

            # Battle logic: every 5 minutes, a random Pokémon loses HP (with animation)
            now = time.time()
            if not self.animating and now >= self.next_battle:
                self.start_battle_animation()

            # Animation state machine
            if self.animating:
                self.update_battle_animation()

            # Always draw the current state (animation or not)
            self.draw_bg()
            self.draw_time(rect=(*TIME_POS, *TIME_SIZE))
            front_rect = (*FRONT_SPRITE_POS, *FRONT_SPRITE_SIZE)
            back_rect = (*BACK_SPRITE_POS, *BACK_SPRITE_SIZE)
            if self.animating and self.anim_phase == 'move':
                t = (time.time() - self.anim_start_time) / self.anim_duration
                t = min(max(t, 0), 1)
                if t < 0.5:
                    progress = t / 0.5
                else:
                    progress = 1 - (t - 0.5) / 0.5
                if self.anim_attacker == 'front':
                    x0, y0, w, h = front_rect
                    x1, y1 = WINDOW_WIDTH//2 - w//2, WINDOW_HEIGHT//2 - h//2
                    x = int(x0 + (x1 - x0) * progress)
                    y = int(y0 + (y1 - y0) * progress)
                    self.draw_sprite_card('front', rect=(x, y, w, h), draw_name=False, draw_hp=False)
                    self.draw_sprite_card('back', rect=back_rect, draw_name=False, draw_hp=False)
                else:
                    x0, y0, w, h = back_rect
                    x1, y1 = WINDOW_WIDTH//2 - w//2, WINDOW_HEIGHT//2 - h//2
                    x = int(x0 + (x1 - x0) * progress)
                    y = int(y0 + (y1 - y0) * progress)
                    self.draw_sprite_card('back', rect=(x, y, w, h), draw_name=False, draw_hp=False)
                    self.draw_sprite_card('front', rect=front_rect, draw_name=False, draw_hp=False)
            elif self.animating and self.anim_phase == 'flash':
                if self.anim_defender == 'front':
                    if self.anim_flash_on:
                        self.draw_sprite_card('front', rect=front_rect, draw_name=False, draw_hp=False)
                    self.draw_sprite_card('back', rect=back_rect, draw_name=False, draw_hp=False)
                else:
                    self.draw_sprite_card('front', rect=front_rect, draw_name=False, draw_hp=False)
                    if self.anim_flash_on:
                        self.draw_sprite_card('back', rect=back_rect, draw_name=False, draw_hp=False)
            else:
                self.draw_sprite_card("front", rect=front_rect, draw_name=False, draw_hp=False)
                self.draw_sprite_card("back", rect=back_rect, draw_name=False, draw_hp=False)
            # Draw front name
            name = name_from_path(self.curr_front_path).lower()
            dex = self.dex_map.get(name)
            label = name.capitalize()
            if dex is not None:
                label = f"{label}  No.{dex}"
            text_surf = self.font.render(label, True, (0, 0, 0))
            x, y = FRONT_NAME_POS
            w, h = FRONT_NAME_SIZE
            text_surf = pygame.transform.smoothscale(text_surf, (int(w), int(h)))
            self.screen.blit(text_surf, (x, y))
            # Draw back name
            name = name_from_path(self.curr_back_path).lower()
            dex = self.dex_map.get(name)
            label = name.capitalize()
            if dex is not None:
                label = f"{label}  No.{dex}"
            text_surf = self.font.render(label, True, (0, 0, 0))
            x, y = BACK_NAME_POS
            w, h = BACK_NAME_SIZE
            text_surf = pygame.transform.smoothscale(text_surf, (int(w), int(h)))
            self.screen.blit(text_surf, (x, y))
            # Draw front HP bar
            x, y = FRONT_HP_BAR_POS
            w, h = FRONT_HP_BAR_SIZE
            draw_hp_bar(self.screen, x, y, value=self.front_hp, width=w, height=h)
            # Draw back HP bar
            x, y = BACK_HP_BAR_POS
            w, h = BACK_HP_BAR_SIZE
            draw_hp_bar(self.screen, x, y, value=self.back_hp, width=w, height=h)
            pygame.display.flip()
        return
        return
    def start_battle_animation(self):
        # Randomly pick attacker/defender
        if random.choice([True, False]):
            self.anim_attacker = 'front'
            self.anim_defender = 'back'
        else:
            self.anim_attacker = 'back'
            self.anim_defender = 'front'
        self.anim_phase = 'move'
        self.anim_start_time = time.time()
        self.anim_duration = 0.5  # seconds for move out and back
        self.animating = True
        self.anim_flash_count = 0
        self.anim_flash_on = True

    def update_battle_animation(self):
        now = time.time()
        if self.anim_phase == 'move':
            elapsed = now - self.anim_start_time
            if elapsed >= self.anim_duration:
                # Move done, apply damage and start flash
                dmg = random.uniform(0.1, 0.3)
                if self.anim_defender == 'front':
                    self.front_hp = max(0.0, self.front_hp - dmg)
                    if self.front_hp <= 0.0:
                        self.pick_new_pair(loser='front')
                        self.animating = False
                        self.next_battle = now + self.battle_interval
                        return
                else:
                    self.back_hp = max(0.0, self.back_hp - dmg)
                    if self.back_hp <= 0.0:
                        self.pick_new_pair(loser='back')
                        self.animating = False
                        self.next_battle = now + self.battle_interval
                        return
                self.anim_phase = 'flash'
                self.anim_start_time = now
                self.anim_flash_count = 0
                self.anim_flash_on = False
        elif self.anim_phase == 'flash':
            # Flash defender 3 times (on/off)
            flash_period = 0.15
            elapsed = now - self.anim_start_time
            if elapsed >= flash_period:
                self.anim_flash_on = not self.anim_flash_on
                self.anim_start_time = now
                if not self.anim_flash_on:
                    self.anim_flash_count += 1
            if self.anim_flash_count >= 3:
                self.animating = False
                self.next_battle = now + self.battle_interval

            # Draw everything using baked constants
            self.draw_bg()
            self.draw_time(rect=(*TIME_POS, *TIME_SIZE))
            # Draw sprites with animation if needed
            front_rect = (*FRONT_SPRITE_POS, *FRONT_SPRITE_SIZE)
            back_rect = (*BACK_SPRITE_POS, *BACK_SPRITE_SIZE)
            if self.animating and self.anim_phase == 'move':
                # Animate attacker moving to center and back
                t = (time.time() - self.anim_start_time) / self.anim_duration
                t = min(max(t, 0), 1)
                # Move out (0-0.5), back (0.5-1)
                if t < 0.5:
                    progress = t / 0.5
                else:
                    progress = 1 - (t - 0.5) / 0.5
                # Lerp attacker position
                if self.anim_attacker == 'front':
                    x0, y0, w, h = front_rect
                    x1, y1 = WINDOW_WIDTH//2 - w//2, WINDOW_HEIGHT//2 - h//2
                    x = int(x0 + (x1 - x0) * progress)
                    y = int(y0 + (y1 - y0) * progress)
                    self.draw_sprite_card('front', rect=(x, y, w, h), draw_name=False, draw_hp=False)
                    self.draw_sprite_card('back', rect=back_rect, draw_name=False, draw_hp=False)
                else:
                    x0, y0, w, h = back_rect
                    x1, y1 = WINDOW_WIDTH//2 - w//2, WINDOW_HEIGHT//2 - h//2
                    x = int(x0 + (x1 - x0) * progress)
                    y = int(y0 + (y1 - y0) * progress)
                    self.draw_sprite_card('back', rect=(x, y, w, h), draw_name=False, draw_hp=False)
                    self.draw_sprite_card('front', rect=front_rect, draw_name=False, draw_hp=False)
            elif self.animating and self.anim_phase == 'flash':
                # Draw both, but defender flashes
                if self.anim_defender == 'front':
                    if self.anim_flash_on:
                        self.draw_sprite_card('front', rect=front_rect, draw_name=False, draw_hp=False)
                    self.draw_sprite_card('back', rect=back_rect, draw_name=False, draw_hp=False)
                else:
                    self.draw_sprite_card('front', rect=front_rect, draw_name=False, draw_hp=False)
                    if self.anim_flash_on:
                        self.draw_sprite_card('back', rect=back_rect, draw_name=False, draw_hp=False)
            else:
                self.draw_sprite_card("front", rect=front_rect, draw_name=False, draw_hp=False)
                self.draw_sprite_card("back", rect=back_rect, draw_name=False, draw_hp=False)
            # Draw front name
            name = name_from_path(self.curr_front_path).lower()
            dex = self.dex_map.get(name)
            label = name.capitalize()
            if dex is not None:
                label = f"{label}  No.{dex}"
            text_surf = self.font.render(label, True, (0, 0, 0))
            x, y = FRONT_NAME_POS
            w, h = FRONT_NAME_SIZE
            text_surf = pygame.transform.smoothscale(text_surf, (int(w), int(h)))
            self.screen.blit(text_surf, (x, y))
            # Draw back name
            name = name_from_path(self.curr_back_path).lower()
            dex = self.dex_map.get(name)
            label = name.capitalize()
            if dex is not None:
                label = f"{label}  No.{dex}"
            text_surf = self.font.render(label, True, (0, 0, 0))
            x, y = BACK_NAME_POS
            w, h = BACK_NAME_SIZE
            text_surf = pygame.transform.smoothscale(text_surf, (int(w), int(h)))
            self.screen.blit(text_surf, (x, y))
            # Draw front HP bar
            x, y = FRONT_HP_BAR_POS
            w, h = FRONT_HP_BAR_SIZE
            draw_hp_bar(self.screen, x, y, value=self.front_hp, width=w, height=h)
            # Draw back HP bar
            x, y = BACK_HP_BAR_POS
            w, h = BACK_HP_BAR_SIZE
            draw_hp_bar(self.screen, x, y, value=self.back_hp, width=w, height=h)
            pygame.display.flip()
        pygame.quit()

    def draw_time(self, rect=None):
        now_str = time.strftime("%H:%M")
        surf = self.time_font.render(now_str, True, (0, 0, 0))  # black text
        if rect:
            r = pygame.Rect(*rect)
            surf = pygame.transform.smoothscale(surf, (r.w, r.h))
            self.screen.blit(surf, (r.x, r.y))
        else:
            rect = surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            self.screen.blit(surf, rect)

    def draw_bg(self):
        if self.bg:
            bg_scaled = pygame.transform.smoothscale(self.bg, (WINDOW_WIDTH, WINDOW_HEIGHT))
            self.screen.blit(bg_scaled, (0, 0))
        else:
            self.screen.fill((255, 255, 255))



# -------------------- Entry --------------------

if __name__ == "__main__":
    App().run()
