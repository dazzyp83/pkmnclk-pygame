from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    FPS, ASSETS_DIR, FRONT_DIR, BACK_DIR, BG_IMAGE,
    FONT_PATH, FONT_SIZE
)

print("Config loaded successfully:")
print(f"Window: {WINDOW_WIDTH}x{WINDOW_HEIGHT} ({WINDOW_TITLE})")
print(f"FPS: {FPS}")
print(f"Assets folder: {ASSETS_DIR}")
print(f"Front sprites: {FRONT_DIR}")
print(f"Back sprites: {BACK_DIR}")
print(f"Background: {BG_IMAGE}")
print(f"Font: {FONT_PATH} ({FONT_SIZE}pt)")
