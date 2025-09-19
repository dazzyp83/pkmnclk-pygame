import numpy as np
# --- helpers ---
def invert_surface(surface):
    arr = pygame.surfarray.pixels3d(surface).copy()
    arr = 255 - arr
    # Always create a surface with SRCALPHA
    inverted = pygame.Surface(surface.get_size(), pygame.SRCALPHA, 32)
    pygame.surfarray.blit_array(inverted, arr)
    # Copy alpha if present
    if surface.get_flags() & pygame.SRCALPHA:
        alpha = pygame.surfarray.pixels_alpha(surface)
        pygame.surfarray.pixels_alpha(inverted)[:, :] = alpha
    return inverted
# main.py — Battle clock with enter/exit, lunges toward, and wider time display

import time, json, random
from enum import Enum, auto
from pathlib import Path
import pygame
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    FPS, ASSETS_DIR, FRONT_DIR, BACK_DIR, BG_IMAGE,
    FONT_PATH, FONT_SIZE, TIME_FONT_SIZE,
    HP_BAR_WIDTH, HP_BAR_HEIGHT, HP_BAR_BORDER
)

# --- Layout constants ---
FRONT_SPRITE_POS = (180, -30)
FRONT_SPRITE_SIZE = (150, 150)
BACK_SPRITE_POS  = (-20, 60)
BACK_SPRITE_SIZE = (136, 136)

FRONT_NAME_POS  = (25, 7)
FRONT_NAME_SIZE = (96, 18)
BACK_NAME_POS   = (202, 111)
BACK_NAME_SIZE  = (96, 18)

FRONT_HP_BAR_POS  = (65, 27)
FRONT_HP_BAR_SIZE = (100, 12)
BACK_HP_BAR_POS   = (191, 137)
BACK_HP_BAR_SIZE  = (100, 12)

# Wider, flatter time box
TIME_POS  = (70, 170)        # shift left a bit
TIME_SIZE = (200, 50)        # stretched out horizontally

# --- helpers ---
def safe_load_image(path):
    if not Path(path).exists(): return None
    return pygame.image.load(str(path)).convert_alpha()

def safe_load_font(path, size):
    return pygame.font.Font(path, size) if Path(path).exists() else pygame.font.SysFont(None, size)

def list_pngs(folder): return sorted([str(p) for p in Path(folder).glob("*.png")])
def stem_upper(p): return Path(p).stem.upper() if p else "?"

def clamp(v, lo, hi): return max(lo, min(hi, v))

def draw_hp_bar(surf,x,y,value=1.0,w=HP_BAR_WIDTH,h=HP_BAR_HEIGHT):
    v=clamp(value,0,1)
    outer=pygame.Rect(x,y,w,h)
    inner=pygame.Rect(x+HP_BAR_BORDER,y+HP_BAR_BORDER,int((w-2*HP_BAR_BORDER)*v),h-2*HP_BAR_BORDER)
    pygame.draw.rect(surf,(0,0,0),outer,HP_BAR_BORDER)
    pygame.draw.rect(surf,(0,200,0),inner)

# --- Entrance/Exit Animator ---
class MonAnim:
    def __init__(self, base_x, base_y, w, h, axis='y', direction=+1, duration=0.4):
        self.base_x,self.base_y,self.w,self.h = base_x,base_y,w,h
        self.axis,self.dir,self.duration = axis,direction,duration
        self.state = "idle"; self.t = 0.0
    def enter(self): self.state="enter"; self.t=0.0
    def exit(self):  self.state="exit";  self.t=0.0
    def update(self, dt):
        if self.state=="idle": return
        self.t+=dt
        if self.t>=self.duration: self.t=self.duration; self.state="idle"
    def pos(self):
        if self.state=="idle": return self.base_x,self.base_y
        u=clamp(self.t/self.duration,0,1)
        if self.axis=='y':
            off=-self.h if self.dir<0 else WINDOW_HEIGHT
            if self.state=="enter": y=off+(self.base_y-off)*u
            else: y=self.base_y+(off-self.base_y)*u
            return self.base_x,y
        else:
            off=-self.w if self.dir<0 else WINDOW_WIDTH
            if self.state=="enter": x=off+(self.base_x-off)*u
            else: x=self.base_x+(off-self.base_x)*u
            return x,self.base_y

# --- Battle Turn ---
class BState(Enum):
    IDLE=auto(); ATTACK_OUT=auto(); ATTACK_BACK=auto(); HIT_FLASH=auto(); COOLDOWN=auto()

class BattleTurn:
    def __init__(self, attacker, defender):
        self.attacker,self.defender=attacker,defender
        self.state=BState.IDLE; self.t=0; self.offset_x=0; self.flash_on=False
        self.damage=random.randint(6,18)
    def start(self):
        if self.state!=BState.IDLE: return
        self.state=BState.ATTACK_OUT; self.t=0
    def update(self,dt):
        if self.state==BState.IDLE: return
        self.t+=dt
        if self.state==BState.ATTACK_OUT:
            u=clamp(self.t/0.14,0,1); self.offset_x=int(28*(u*u))
            if u>=1:self.state=BState.ATTACK_BACK; self.t=0
        elif self.state==BState.ATTACK_BACK:
            u=clamp(self.t/0.12,0,1); self.offset_x=int(28*((1-u)**2))
            if u>=1:self.state=BState.HIT_FLASH; self.t=0
        elif self.state==BState.HIT_FLASH:
            self.flash_on=int(self.t//(0.35/6))%2==0
            if self.t>=0.35:self.flash_on=False; self.state=BState.COOLDOWN; self.t=0
        elif self.state==BState.COOLDOWN and self.t>=0.18:
            self.state=BState.IDLE
    @property
    def done(self): return self.state==BState.IDLE

# --- App ---
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.sc = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clk = pygame.time.Clock()
        raw_bg = safe_load_image(BG_IMAGE)
        self.bg = pygame.transform.scale(raw_bg, (WINDOW_WIDTH, WINDOW_HEIGHT)) if raw_bg else None
        self.font = safe_load_font(FONT_PATH, FONT_SIZE)
        self.tfont = safe_load_font(FONT_PATH, TIME_FONT_SIZE)
        self.front_list = list_pngs(FRONT_DIR)
        self.back_list = list_pngs(BACK_DIR)
        self.front_img = self.back_img = None
        self.front_name = self.back_name = ""
        self.front_name_surf = None
        self.back_name_surf = None
        self.time_str = ""
        self.time_surf = None
        self.front_hp = self.back_hp = 1.0
        self.front_anim = MonAnim(*FRONT_SPRITE_POS, *FRONT_SPRITE_SIZE, axis='y', direction=-1)
        self.back_anim = MonAnim(*BACK_SPRITE_POS, *BACK_SPRITE_SIZE, axis='x', direction=-1)
        self.turn_is_front = True
        self.anim = None
        self.pending_replacement = None
        self.pick_new_pair()
        self.front_anim.enter()
        self.back_anim.enter()
        # Message queue for sequential battle messages
        self.message_queue = []  # List of (message, duration) tuples
        self.current_message = None  # (message, time_left)
        self.last_winner = None  # Track last winner for wild message

    def pick_new_pair(self,loser=None):
        if loser is None:
            f = random.choice(self.front_list) if self.front_list else None
            b = random.choice(self.back_list) if self.back_list else None
            # Always load a fresh image for each, even if f == b
            front_img = safe_load_image(f) if f else None
            back_img = safe_load_image(b) if b else None
            self.front_img = pygame.transform.scale(front_img, FRONT_SPRITE_SIZE) if front_img else None
            self.back_img = pygame.transform.scale(back_img, BACK_SPRITE_SIZE) if back_img else None
            self.front_name, self.back_name = stem_upper(f), stem_upper(b)
            self.front_hp = self.back_hp = 1.0
        elif loser == "front":
            f = random.choice(self.front_list) if self.front_list else None
            front_img = safe_load_image(f)
            self.front_img = pygame.transform.scale(front_img, FRONT_SPRITE_SIZE) if front_img else None
            self.front_name = stem_upper(f)
            self.front_hp = 1.0
            self.front_anim.enter()
            # Enqueue only wild message for new front
            if self.front_name and self.last_winner:
                self.message_queue.append((f"A wild {self.front_name} appeared!", 1.5))
        elif loser == "back":
            b = random.choice(self.back_list) if self.back_list else None
            back_img = safe_load_image(b)
            self.back_img = pygame.transform.scale(back_img, BACK_SPRITE_SIZE) if back_img else None
            self.back_name = stem_upper(b)
            self.back_hp = 1.0
            self.back_anim.enter()
            # Enqueue only wild message for new back
            if self.back_name and self.last_winner:
                self.message_queue.append((f"A wild {self.back_name} appeared!", 1.5))

    def start_turn(self):
        if not(self.anim and not self.anim.done) and self.pending_replacement is None:
            atk="front" if self.turn_is_front else "back"
            dfn="back" if atk=="front" else "front"
            self.anim=BattleTurn(atk,dfn); self.anim.start()

    def update_turn(self,dt):
        if not self.anim: return
        prev=self.anim.state; self.anim.update(dt)
        if prev==BState.ATTACK_BACK and self.anim.state==BState.HIT_FLASH:
            dmg=self.anim.damage/100.0
            if self.anim.defender=="front": self.front_hp=clamp(self.front_hp-dmg,0,1)
            else: self.back_hp=clamp(self.back_hp-dmg,0,1)
        if prev!=BState.IDLE and self.anim.state==BState.IDLE:
            if self.front_hp<=0 or self.back_hp<=0:
                winner="back" if self.front_hp<=0 else "front"
                loser ="front" if winner=="back" else "back"
                winner_name = self.back_name if winner=="back" else self.front_name
                loser_name = self.front_name if loser=="front" else self.back_name
                # Enqueue fainted and winner messages
                self.message_queue.append((f"{loser_name} fainted!", 1.5))
                self.message_queue.append((f"{winner_name} Wins!", 1.5))
                self.last_winner = winner_name
                if winner=="front": self.front_hp=1.0
                else: self.back_hp=1.0
                if loser=="front": self.front_anim.exit()
                else: self.back_anim.exit()
                self.pending_replacement=loser; self.anim=None
                self.turn_is_front=(winner=="front")
            else:
                self.turn_is_front=not self.turn_is_front

    def draw_names(self):
        # Front name: anchor from left (first letter), vertically centered
        if self.front_name:
            txt = self.font.render(self.front_name, True, (0,0,0))
            surf_w, surf_h = txt.get_size()
            box_x, box_y = FRONT_NAME_POS
            box_w, box_h = FRONT_NAME_SIZE
            draw_x = box_x  # left edge of box
            draw_y = box_y + (box_h - surf_h)//2
            self.sc.blit(txt, (draw_x, draw_y))
        if self.back_name:
            txt = self.font.render(self.back_name, True, (0,0,0))
            surf_w, surf_h = txt.get_size()
            box_x, box_y = BACK_NAME_POS
            box_w, box_h = BACK_NAME_SIZE
            draw_x = box_x + box_w - surf_w  # right edge of box
            draw_y = box_y + (box_h - surf_h)//2
            self.sc.blit(txt, (draw_x, draw_y))

    def draw_time(self, dt=0):
        # Message queue logic: show queued messages, else show clock
        if self.current_message is None and self.message_queue:
            # Pop next message from queue
            msg, duration = self.message_queue.pop(0)
            self.current_message = [msg, duration]
        if self.current_message:
            msg, time_left = self.current_message
            self.current_message[1] -= dt
            # Draw a white box over the clock area
            tx, ty = TIME_POS
            tw, th = TIME_SIZE
            pygame.draw.rect(self.sc, (255,255,255), (tx, ty, tw, th))
            # Word wrap message to two lines if needed
            def wrap_text(text, font, max_width, max_lines=3):
                words = text.split()
                lines = []
                current = ""
                for word in words:
                    test = current + (" " if current else "") + word
                    if font.size(test)[0] <= max_width:
                        current = test
                    else:
                        if current:
                            lines.append(current)
                        current = word
                if current:
                    lines.append(current)
                if len(lines) > max_lines:
                    # Force only max_lines, join overflow into last line
                    lines = lines[:max_lines-1] + [" ".join(lines[max_lines-1:])]
                return lines
            lines = wrap_text(msg, self.font, tw - 12, max_lines=3)
            total_height = sum(self.font.size(line)[1] for line in lines)
            # Move text up by reducing the offset (from +10 to +3)
            y = ty + (th - total_height)//2 + 3
            # Determine if this is the last announcement in the queue (after popping)
            is_last_announcement = not self.message_queue and self.current_message[1] > 0
            for line in lines:
                color = (255,0,0) if is_last_announcement else (0,0,0)
                txt = self.font.render(line, True, color)
                surf_w, surf_h = txt.get_size()
                draw_x = tx + (tw - surf_w)//2
                self.sc.blit(txt, (draw_x, y))
                y += surf_h
            # Advance to next message if timer runs out
            if self.current_message[1] <= 0:
                self.current_message = None
            return
        # Normal clock
        h, m = time.strftime("%H"), time.strftime("%M")
        if int(time.time()) % 2 == 0:
            clock_str = f"{h}:{m}"
        else:
            clock_str = f"{h} {m}"
        if clock_str != self.time_str:
            self.time_str = clock_str
            txt = self.tfont.render(clock_str, True, (0,0,0))
            pad = 8
            surf_w = txt.get_width() + pad * 2
            surf_h = txt.get_height() + pad * 2
            surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
            surf.fill((255,255,255,0))
            surf.blit(txt, txt.get_rect(center=(surf_w//2, surf_h//2)))
            self.time_surf = surf
        if self.time_surf:
            tx, ty = TIME_POS
            tw, th = TIME_SIZE
            surf_w, surf_h = self.time_surf.get_size()
            draw_x = tx + (tw - surf_w)//2
            draw_y = ty + (th - surf_h)//2
            self.sc.blit(self.time_surf, (draw_x, draw_y))


    def draw(self):
        if self.bg:
            self.sc.blit(self.bg, (0,0))
        else:
            self.sc.fill((255,255,255))
        self.front_anim.update(self.dt)
        self.back_anim.update(self.dt)
        if self.pending_replacement=="front" and self.front_anim.state=="idle":
            self.pick_new_pair(loser="front"); self.pending_replacement=None
        elif self.pending_replacement=="back" and self.back_anim.state=="idle":
            self.pick_new_pair(loser="back"); self.pending_replacement=None
        fx,fy=self.front_anim.pos(); bx,by=self.back_anim.pos()
        a_offset=0; d_flash=False
        if self.anim and not self.anim.done:
            if self.anim.state in (BState.ATTACK_OUT,BState.ATTACK_BACK): a_offset=self.anim.offset_x
            elif self.anim.state==BState.HIT_FLASH: d_flash=self.anim.flash_on
        # draw sprites
        if self.anim and self.anim.attacker=="front":
            if self.front_img:
                self.sc.blit(self.front_img, (fx - a_offset, fy))  # front lunges left
            if self.back_img:
                if d_flash:
                    inv = invert_surface(self.back_img)
                    self.sc.blit(inv, (bx, by))
                else:
                    self.sc.blit(self.back_img, (bx, by))
        elif self.anim and self.anim.attacker=="back":
            if self.front_img:
                if d_flash:
                    inv = invert_surface(self.front_img)
                    self.sc.blit(inv, (fx, fy))
                else:
                    self.sc.blit(self.front_img, (fx, fy))
            if self.back_img:
                self.sc.blit(self.back_img, (bx + a_offset, by))  # back lunges right
        else:
            if self.front_img: self.sc.blit(self.front_img, (fx, fy))
            if self.back_img:  self.sc.blit(self.back_img, (bx, by))
        # HUD
        draw_hp_bar(self.sc,*FRONT_HP_BAR_POS,value=self.front_hp,w=FRONT_HP_BAR_SIZE[0],h=FRONT_HP_BAR_SIZE[1])
        draw_hp_bar(self.sc,*BACK_HP_BAR_POS,value=self.back_hp,w=BACK_HP_BAR_SIZE[0],h=BACK_HP_BAR_SIZE[1])
        self.draw_names()
        self.draw_time(self.dt)

    def run(self):
        run=True
        while run:
            self.dt=self.clk.tick(FPS)/1000.0
            for e in pygame.event.get():
                if e.type==pygame.QUIT: run=False
                if e.type==pygame.KEYDOWN:
                    if e.key in (pygame.K_ESCAPE,pygame.K_q): run=False
                    if e.key==pygame.K_m: self.start_turn()
            self.update_turn(self.dt); self.draw(); pygame.display.flip()
        pygame.quit()

if __name__=="__main__": App().run()
