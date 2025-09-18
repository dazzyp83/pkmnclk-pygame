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
    # ...existing code...

    def __init__(self):
        # ...existing code...
        # debug
        self.debug_last_key = None
        self.debug_last_m_tick = -1
    def start_battle_animation(self):
        """Shim to stop AttributeError when pressing M."""
        # Prefer an existing method if present
        if hasattr(self, "start_battle") and callable(self.start_battle):
            return self.start_battle()

        # Fallback: initialise minimal battle state
        self.in_battle = True
        self.available_moves = getattr(self, "available_moves", ["Tackle"])
        self.current_front = getattr(self, "current_front", self.front_sprite if hasattr(self, "front_sprite") else None)
        self.current_back = getattr(self, "current_back", self.back_sprite if hasattr(self, "back_sprite") else None)

        if not hasattr(self, "battle_state") or self.battle_state is None:
            class _MinimalBattle:
                def take_turn(self_inner):
                    pass  # no-op
            self.battle_state = _MinimalBattle()
    def draw_label_safe(self, label, pos, size):
        # Guard: skip drawing if font module is not initialized
        if not pygame.font.get_init() or not pygame.display.get_init() or self.screen is None:
            return
        try:
            text_surf = self.font.render(label, True, (0, 0, 0))
            w, h = size
            text_surf = pygame.transform.smoothscale(text_surf, (int(w), int(h)))
            self.screen.blit(text_surf, pos)
        except Exception:
            pass
    def force_battle_turn_safe(self):
        # Add guards for assets/state as needed
        if self.front_img_raw is None or self.back_img_raw is None:
            print("Sprites not ready (front/back).")
            return
        self.apply_forced_turn()

    def apply_forced_turn(self):
        """
        When user presses M, apply a simple attack to the enemy and start a hit animation.
        Replace with your real battle logic later.
        """
        import random
        dmg = random.randint(6, 14)
        self.enemy_hp = max(0, self.enemy_hp - dmg)
        self.hit_anim_ms = 220   # duration in ms
        self.hit_anim_dir = 1
        self.damage_popup = f"-{dmg}"
        self.damage_popup_ms = 600
        try:
            pygame.mixer.get_init() or pygame.mixer.init()
            # self.sfx_hit.play()  # if you have it
        except Exception:
            pass

    def draw_enemy(self):
        if self.front_img_raw is None:
            return
        # base position (match your layout: FRONT_SPRITE_POS)
        x, y = FRONT_SPRITE_POS
        # during hit animation, shake horizontally and optional flash
        if self.hit_anim_ms > 0:
            x += 4 * self.hit_anim_dir
            flashing = (pygame.time.get_ticks() // 60) % 2 == 0
        else:
            flashing = False
        if not flashing:
            sprite = pygame.transform.smoothscale(self.front_img_raw, FRONT_SPRITE_SIZE)
            self.screen.blit(sprite, (x, y))
        # damage popup above the sprite
        if self.damage_popup_ms > 0 and self.damage_popup:
            if pygame.font.get_init():
                t = 1.0 - (self.damage_popup_ms / 600.0)
                dy = int(18 * t)
                surf = self.font.render(self.damage_popup, True, (0, 0, 0))
                self.screen.blit(surf, (x + 20, y - 10 - dy))

    def draw_bars(self):
        # Enemy (front, top-left in your layout)
        self.draw_hp_bar_custom(65, 27, 100, 12, self.enemy_hp, self.enemy_hp_max)
        # Player (back, bottom-right in your layout)
        self.draw_hp_bar_custom(191, 137, 100, 12, self.player_hp, self.player_hp_max)

    def draw_hp_bar_custom(self, x, y, w, h, current, maximum, border=(0,0,0), fill=(50,200,50), back=(220,220,220)):
        pygame.draw.rect(self.screen, back, (x, y, w, h))
        pct = 0 if maximum <= 0 else max(0.0, min(1.0, current / maximum))
        fw = int(w * pct)
        pygame.draw.rect(self.screen, fill, (x, y, fw, h))
        pygame.draw.rect(self.screen, border, (x, y, w, h), 2)
    def __init__(self):
        # --- battle/hp state ---
        self.player_hp = 100
        self.enemy_hp = 100
        self.player_hp_max = 100
        self.enemy_hp_max = 100

        # --- hit animation state ---
        self.hit_anim_ms = 0       # >0 while animating enemy getting hit
        self.hit_anim_dir = 1      # shake direction
        self.damage_popup = None   # e.g. "-12"
        self.damage_popup_ms = 0   # time remaining for popup
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
        if not pygame.display.get_init() or self.screen is None:
            return
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
        clock = pygame.time.Clock()
        self.running = True
        while self.running:
            # 1) Handle events FIRST
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_m:
                        try:
                            self.force_battle_turn_safe()
                        except Exception:
                            import traceback
                            traceback.print_exc()
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            # 2) If the window was closed during events, bail out ASAP
            if not self.running or not pygame.display.get_init():
                break

            # 3) Draw only with a live display surface
            try:
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
            except Exception as e:
                import traceback
                traceback.print_exc()
                break
            clock.tick(60)
        pygame.quit()
        return
        clock = pygame.time.Clock()
        self.running = True
        while self.running:
            # 1) Handle events FIRST
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break

                # --- DEBUG: show every keydown so we know if events arrive ---
                if event.type == pygame.KEYDOWN:
                    try:
                        self.debug_last_key = pygame.key.name(event.key)
                    except Exception:
                        self.debug_last_key = str(event.key)
                    # universal M check (works regardless of shift/caps)
                    if event.key == pygame.K_m:
                        print("DEBUG: KEYDOWN M at", pygame.time.get_ticks(), "ms")
                        self.debug_last_m_tick = pygame.time.get_ticks()
                        try:
                            self.apply_forced_turn()
                        except Exception as e:
                            import traceback
                            print("\n[FORCE TURN] crashed — traceback:")
                            traceback.print_exc()

                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            # OPTIONAL: polling approach for M (debounced)
            keys = pygame.key.get_pressed()
            if keys[pygame.K_m]:
                now = pygame.time.get_ticks()
                if now - getattr(self, "_m_cooldown_last", -9999) > 250:
                    print("DEBUG: POLL M at", now, "ms")
                    self._m_cooldown_last = now
                    try:
                        self.apply_forced_turn()
                    except Exception as e:
                        import traceback
                        print("\n[FORCE TURN] crashed — traceback:")
                        traceback.print_exc()

            # 2) If the window was closed during events, bail out ASAP
            if not self.running or not pygame.display.get_init():
                break

            # 3) Draw only with a live display surface
            try:
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
                # Draw enemy with hit animation and popup
                self.draw_enemy()
                # Draw bars (HP)
                self.draw_bars()
                # Draw names as before
                name = name_from_path(self.curr_front_path).lower()
                dex = self.dex_map.get(name)
                label = name.capitalize()
                if dex is not None:
                    label = f"{label}  No.{dex}"
                self.draw_label_safe(label, FRONT_NAME_POS, FRONT_NAME_SIZE)
                name = name_from_path(self.curr_back_path).lower()
                dex = self.dex_map.get(name)
                label = name.capitalize()
                if dex is not None:
                    label = f"{label}  No.{dex}"
                self.draw_label_safe(label, BACK_NAME_POS, BACK_NAME_SIZE)
                # Draw back sprite (player) as before
                self.draw_sprite_card("back", rect=(*BACK_SPRITE_POS, *BACK_SPRITE_SIZE), draw_name=False, draw_hp=False)
                # Draw debug overlay
                self.draw_debug_overlay()
                pygame.display.flip()
            except Exception as e:
                import traceback
                traceback.print_exc()
                break
            dt = clock.get_time()  # ms since last frame
            # tick animation timers
            if self.hit_anim_ms > 0:
                self.hit_anim_ms = max(0, self.hit_anim_ms - dt)
                if (pygame.time.get_ticks() // 30) % 2 == 0:
                    self.hit_anim_dir *= -1
            if self.damage_popup_ms > 0:
                self.damage_popup_ms = max(0, self.damage_popup_ms - dt)
            clock.tick(60)
        # Only quit pygame after loop exits
        pygame.quit()
        return
    def draw_debug_overlay(self):
        if not pygame.font.get_init():
            return
        info = []
        if self.debug_last_key:
            info.append(f"Last key: {self.debug_last_key}")
        if self.debug_last_m_tick >= 0:
            info.append(f"M pressed @ {self.debug_last_m_tick}ms")
        if not info:
            return
        y = 6
        for line in info:
            surf = self.font.render(line, True, (0, 0, 0))
            self.screen.blit(surf, (8, y))
            y += surf.get_height() + 2

    def draw_time(self, rect=None):
        if not pygame.display.get_init() or self.screen is None:
            return
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
        if not pygame.display.get_init() or self.screen is None:
            return
        if self.bg:
            bg_scaled = pygame.transform.smoothscale(self.bg, (WINDOW_WIDTH, WINDOW_HEIGHT))
            self.screen.blit(bg_scaled, (0, 0))
        else:
            self.screen.fill((255, 255, 255))



# -------------------- Entry --------------------

if __name__ == "__main__":
    App().run()
