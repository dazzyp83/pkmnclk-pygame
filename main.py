import os
import sys
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
    # "assets/front/abra.png" -> "abra"
    return Path(path).stem

def load_pokemon_list():
    # Optional: assets/pokemonList.json with entries like:
    # [{"name": "abra", "dex": 63}, ...]
    jl = Path(ASSETS_DIR) / "pokemonList.json"
    if not jl.exists():
        return {}
    try:
        with open(jl, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = {}
        # Support either { "abra": 63 } or [{name:"abra", dex:63}]
        if isinstance(data, dict):
            for k, v in data.items():
                out[str(k).lower()] = v
        elif isinstance(data, list):
            for item in data:
                n = str(item.get("name", "")).lower()
                d = item.get("dex")
                if n:
                    out[n] = d
        return out
    except Exception:
        return {}

def draw_hp_bar(surface, x, y, value=1.0):
    """value: 0.0..1.0"""
    value = max(0.0, min(1.0, float(value)))
    outer = pygame.Rect(x, y, HP_BAR_WIDTH, HP_BAR_HEIGHT)
    inner = pygame.Rect(
        x + HP_BAR_BORDER,
        y + HP_BAR_BORDER,
        int((HP_BAR_WIDTH - 2 * HP_BAR_BORDER) * value),
        HP_BAR_HEIGHT - 2 * HP_BAR_BORDER,
    )
    pygame.draw.rect(surface, (0, 0, 0), outer, width=HP_BAR_BORDER)  # border
    pygame.draw.rect(surface, (0, 200, 0), inner)  # fill (green)

# -------------------- App --------------------

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        # Assets
        self.bg = safe_load_image(BG_IMAGE)
        self.font = safe_load_font(FONT_PATH, FONT_SIZE)
        self.time_font = safe_load_font(FONT_PATH, TIME_FONT_SIZE)

        # Sprite pools & name->dex mapping
        self.front_paths = list_pngs(FRONT_DIR)
        self.back_paths  = list_pngs(BACK_DIR)
        self.dex_map = load_pokemon_list()

        # Current selection
        self.curr_front_path = None
        self.curr_back_path = None
        self.curr_front = None
        self.curr_back = None

        self.pick_new_pair()
        self.next_swap = time.time() + SWAP_SECONDS

    # -------- selection & loading --------

    def pick_new_pair(self):
        """Choose a front/back pair with different names where possible."""
        if not self.front_paths or not self.back_paths:
            return

        front_path = random.choice(self.front_paths)
        front_name = name_from_path(front_path).lower()

        # Filter back choices to avoid same name if possible
        back_choices = [p for p in self.back_paths if name_from_path(p).lower() != front_name] or self.back_paths
        back_path = random.choice(back_choices)

        # Load and scale
        self.curr_front_path = front_path
        self.curr_back_path = back_path
        self.curr_front = self.load_scaled(front_path)
        self.curr_back = self.load_scaled(back_path)

    def load_scaled(self, path):
        img = safe_load_image(path)
        if not img:
            return None
        return pygame.transform.smoothscale(img, (SPRITE_SIZE, SPRITE_SIZE))

    # -------- drawing --------

    def draw_bg(self):
        if self.bg:
            bg_scaled = pygame.transform.smoothscale(self.bg, (WINDOW_WIDTH, WINDOW_HEIGHT))
            self.screen.blit(bg_scaled, (0, 0))
        else:
            self.screen.fill((0, 0, 0))

    def draw_time(self):
        now_str = time.strftime("%H:%M")
        surf = self.time_font.render(now_str, True, (0, 0, 0))
        rect = surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(surf, rect)

    def draw_sprite_card(self, sprite, name, dex, topright=False):
        """
        Draw a sprite + name/dex + HP bar block.
        - Back sprite goes bottom-left (topright=False)
        - Front sprite goes top-right (topright=True)
        """
        if not sprite:
            return

        if topright:
            x = WINDOW_WIDTH - PADDING - SPRITE_SIZE
            y = PADDING
            text_align = "right"
            text_x = WINDOW_WIDTH - PADDING
        else:
            x = PADDING
            y = WINDOW_HEIGHT - PADDING - SPRITE_SIZE - (HP_BAR_HEIGHT + 2 * PADDING) - (self.font.get_height() + 2)
            text_align = "left"
            text_x = PADDING

        # Sprite
        self.screen.blit(sprite, (x, y))

        # Name + Dex (one line, capped width under/above sprite)
        label = name.capitalize()
        if dex is not None:
            label = f"{label}  No.{dex}"

        text_surf = self.font.render(label, True, (0, 0, 0))
        text_rect = text_surf.get_rect()
        if text_align == "right":
            text_rect.topright = (text_x, y + SPRITE_SIZE + 2)
        else:
            text_rect.topleft = (text_x, y + SPRITE_SIZE + 2)
        self.screen.blit(text_surf, text_rect)

        # HP bar under the text
        bar_y = text_rect.bottom + 2
        bar_x = text_rect.right - HP_BAR_WIDTH if text_align == "right" else text_x
        draw_hp_bar(self.screen, bar_x, bar_y, value=1.0)

    # -------- main loop --------

    def run(self):
        running = True
        while running:
            _dt = self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_n:   # force new pair
                        self.pick_new_pair()

            if time.time() >= self.next_swap:
                self.pick_new_pair()
                self.next_swap = time.time() + SWAP_SECONDS

            # Draw frame
            self.draw_bg()
            self.draw_time()

            # Names / Dex numbers
            front_name = name_from_path(self.curr_front_path).lower() if self.curr_front_path else "?"
            back_name  = name_from_path(self.curr_back_path).lower() if self.curr_back_path else "?"
            front_dex = self.dex_map.get(front_name)
            back_dex  = self.dex_map.get(back_name)

            # Place sprites
            self.draw_sprite_card(self.curr_front, front_name, front_dex, topright=True)
            self.draw_sprite_card(self.curr_back,  back_name,  back_dex,  topright=False)

            pygame.display.flip()

        pygame.quit()

# -------------------- Entry --------------------

if __name__ == "__main__":
    App().run()
