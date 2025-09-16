import time
import json
import random
from pathlib import Path
import pygame

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

def draw_hp_bar(surface, x, y, value=1.0):
    value = max(0.0, min(1.0, float(value)))
    outer = pygame.Rect(x, y, HP_BAR_WIDTH, HP_BAR_HEIGHT)
    inner = pygame.Rect(
        x + HP_BAR_BORDER,
        y + HP_BAR_BORDER,
        int((HP_BAR_WIDTH - 2 * HP_BAR_BORDER) * value),
        HP_BAR_HEIGHT - 2 * HP_BAR_BORDER,
    )
    pygame.draw.rect(surface, (0, 0, 0), outer, width=HP_BAR_BORDER)  # border (black)
    pygame.draw.rect(surface, (0, 200, 0), inner)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# -------------------- App --------------------

class App:
    def __init__(self):
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

        # Editable placement state
        self.selected = "front"  # 'front' or 'back'
        self.front_w = SPRITE_SIZE
        self.front_h = SPRITE_SIZE
        self.back_w  = SPRITE_SIZE
        self.back_h  = SPRITE_SIZE

        # Default positions (top-right for front, bottom-left for back)
        self.front_x = WINDOW_WIDTH - PADDING - self.front_w
        self.front_y = PADDING
        self.back_x  = PADDING
        # room for name + HP bar under sprite
        text_and_bar = (self.font.get_height() + 2) + (HP_BAR_HEIGHT + 2 * PADDING)
        self.back_y  = WINDOW_HEIGHT - PADDING - self.back_h - text_and_bar

        self.next_swap = time.time() + SWAP_SECONDS
        self.pick_new_pair()

    # -------- selection & loading --------

    def pick_new_pair(self):
        if not self.front_paths or not self.back_paths:
            return
        fpath = random.choice(self.front_paths)
        fname = name_from_path(fpath).lower()
        back_choices = [p for p in self.back_paths if name_from_path(p).lower() != fname] or self.back_paths
        bpath = random.choice(back_choices)

        self.curr_front_path = fpath
        self.curr_back_path  = bpath
        self.front_img_raw = safe_load_image(fpath)
        self.back_img_raw  = safe_load_image(bpath)

    def get_scaled(self, which):
        if which == "front":
            if not self.front_img_raw: return None
            return pygame.transform.smoothscale(self.front_img_raw, (int(self.front_w), int(self.front_h)))
        else:
            if not self.back_img_raw: return None
            return pygame.transform.smoothscale(self.back_img_raw, (int(self.back_w), int(self.back_h)))

    # -------- drawing --------

    def draw_bg(self):
        if self.bg:
            bg_scaled = pygame.transform.smoothscale(self.bg, (WINDOW_WIDTH, WINDOW_HEIGHT))
            self.screen.blit(bg_scaled, (0, 0))
        else:
            self.screen.fill((255, 255, 255))

    def draw_time(self):
        now_str = time.strftime("%H:%M")
        surf = self.time_font.render(now_str, True, (0, 0, 0))  # black text
        rect = surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(surf, rect)

    def draw_sprite_card(self, which):
        if which == "front":
            sprite = self.get_scaled("front")
            if not sprite: return
            x, y = int(self.front_x), int(self.front_y)
            name = name_from_path(self.curr_front_path).lower()
        else:
            sprite = self.get_scaled("back")
            if not sprite: return
            x, y = int(self.back_x), int(self.back_y)
            name = name_from_path(self.curr_back_path).lower()

        dex = self.dex_map.get(name)
        label = name.capitalize()
        if dex is not None:
            label = f"{label}  No.{dex}"

        # Sprite
        self.screen.blit(sprite, (x, y))

        # Label
        text_surf = self.font.render(label, True, (0, 0, 0))  # black
        self.screen.blit(text_surf, (x, y + sprite.get_height() + 2))

        # HP bar
        draw_hp_bar(self.screen, x, y + sprite.get_height() + 2 + text_surf.get_height() + 2, value=1.0)

    def draw_overlay(self):
        """Small translucent HUD with current edit info."""
        info = []
        if self.selected == "front":
            info.append(f"Editing: FRONT  ({name_from_path(self.curr_front_path)})")
            info.append(f"Pos: ({int(self.front_x)}, {int(self.front_y)})  Size: {int(self.front_w)}x{int(self.front_h)}")
        else:
            info.append(f"Editing: BACK   ({name_from_path(self.curr_back_path)})")
            info.append(f"Pos: ({int(self.back_x)}, {int(self.back_y)})  Size: {int(self.back_w)}x{int(self.back_h)}")
        info.append("Arrows=move  Shift=fast  +/-=scale  Space=switch  N=new pair  R=reset  C=print code")

        # Render
        lines = [self.font.render(s, True, (0, 0, 0)) for s in info]
        w = max(l.get_width() for l in lines) + 12
        h = sum(l.get_height() for l in lines) + 12

        hud = pygame.Surface((w, h), pygame.SRCALPHA)
        hud.fill((255, 255, 255, 180))  # translucent white
        y = 6
        for l in lines:
            hud.blit(l, (6, y))
            y += l.get_height()

        self.screen.blit(hud, (PADDING, PADDING))

    # -------- input & utils --------

    def reset_layout(self):
        self.front_w = SPRITE_SIZE
        self.front_h = SPRITE_SIZE
        self.back_w  = SPRITE_SIZE
        self.back_h  = SPRITE_SIZE
        self.front_x = WINDOW_WIDTH - PADDING - self.front_w
        self.front_y = PADDING
        text_and_bar = (self.font.get_height() + 2) + (HP_BAR_HEIGHT + 2 * PADDING)
        self.back_x  = PADDING
        self.back_y  = WINDOW_HEIGHT - PADDING - self.back_h - text_and_bar

    def print_code_snippet(self):
        """Prints copy-pasteable Python lines for your current layout."""
        print("\n# --- Layout capture ---")
        print(f"FRONT_POS = ({int(self.front_x)}, {int(self.front_y)})")
        print(f"FRONT_SIZE = ({int(self.front_w)}, {int(self.front_h)})")
        print(f"BACK_POS = ({int(self.back_x)}, {int(self.back_y)})")
        print(f"BACK_SIZE = ({int(self.back_w)}, {int(self.back_h)})")
        print("# ----------------------\n")

    # -------- main loop --------

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.selected = "back" if self.selected == "front" else "front"
                    elif event.key == pygame.K_n:
                        self.pick_new_pair()
                    elif event.key == pygame.K_r:
                        self.reset_layout()
                    elif event.key == pygame.K_c:
                        self.print_code_snippet()
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):  # '+' is usually shift+'='
                        self.scale_selected(+4)
                    elif event.key == pygame.K_MINUS:
                        self.scale_selected(-4)

            self.handle_arrows()

            if time.time() >= self.next_swap:
                self.pick_new_pair()
                self.next_swap = time.time() + SWAP_SECONDS

            # Draw
            self.draw_bg()
            self.draw_time()
            self.draw_sprite_card("front")
            self.draw_sprite_card("back")
            self.draw_overlay()
            pygame.display.flip()

        pygame.quit()

    def handle_arrows(self):
        keys = pygame.key.get_pressed()
        speed = 1
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            speed = 5

        if self.selected == "front":
            if keys[pygame.K_LEFT]:  self.front_x -= speed
            if keys[pygame.K_RIGHT]: self.front_x += speed
            if keys[pygame.K_UP]:    self.front_y -= speed
            if keys[pygame.K_DOWN]:  self.front_y += speed

            # Clamp to screen
            self.front_x = clamp(self.front_x, 0, WINDOW_WIDTH - self.front_w)
            self.front_y = clamp(self.front_y, 0, WINDOW_HEIGHT - self.front_h)
        else:
            if keys[pygame.K_LEFT]:  self.back_x -= speed
            if keys[pygame.K_RIGHT]: self.back_x += speed
            if keys[pygame.K_UP]:    self.back_y -= speed
            if keys[pygame.K_DOWN]:  self.back_y += speed

            self.back_x = clamp(self.back_x, 0, WINDOW_WIDTH - self.back_w)
            self.back_y = clamp(self.back_y, 0, WINDOW_HEIGHT - self.back_h)

    def scale_selected(self, delta):
        if self.selected == "front":
            self.front_w = clamp(self.front_w + delta, 16, WINDOW_WIDTH)
            self.front_h = clamp(self.front_h + delta, 16, WINDOW_HEIGHT)
            # keep inside bounds if necessary
            self.front_x = clamp(self.front_x, 0, WINDOW_WIDTH - self.front_w)
            self.front_y = clamp(self.front_y, 0, WINDOW_HEIGHT - self.front_h)
        else:
            self.back_w = clamp(self.back_w + delta, 16, WINDOW_WIDTH)
            self.back_h = clamp(self.back_h + delta, 16, WINDOW_HEIGHT)
            self.back_x = clamp(self.back_x, 0, WINDOW_WIDTH - self.back_w)
            self.back_y = clamp(self.back_y, 0, WINDOW_HEIGHT - self.back_h)

# -------------------- Entry --------------------

if __name__ == "__main__":
    App().run()
