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
FRONT_SPRITE_SIZE = (152, 152)
BACK_SPRITE_POS  = (-20, 59)
BACK_SPRITE_SIZE = (136, 136)

FRONT_NAME_POS  = (24, 7)
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
        pygame.init(); pygame.display.set_caption(WINDOW_TITLE)
        self.sc=pygame.display.set_mode((WINDOW_WIDTH,WINDOW_HEIGHT)); self.clk=pygame.time.Clock()
        self.bg=safe_load_image(BG_IMAGE)
        self.font=safe_load_font(FONT_PATH,FONT_SIZE)
        self.tfont=safe_load_font(FONT_PATH,TIME_FONT_SIZE)
        self.front_list=list_pngs(FRONT_DIR); self.back_list=list_pngs(BACK_DIR)
        self.front_img=self.back_img=None
        self.front_name=self.back_name=""
        self.front_hp=self.back_hp=1.0
        self.front_anim=MonAnim(*FRONT_SPRITE_POS,*FRONT_SPRITE_SIZE,axis='y',direction=-1)
        self.back_anim =MonAnim(*BACK_SPRITE_POS,*BACK_SPRITE_SIZE,axis='x',direction=-1)
        self.turn_is_front=True; self.anim=None; self.pending_replacement=None
        self.pick_new_pair(); self.front_anim.enter(); self.back_anim.enter()

    def pick_new_pair(self,loser=None):
        if loser is None:
            f=random.choice(self.front_list) if self.front_list else None
            b=random.choice(self.back_list) if self.back_list else None
            self.front_img=safe_load_image(f); self.back_img=safe_load_image(b)
            self.front_name,self.back_name=stem_upper(f),stem_upper(b)
            self.front_hp=self.back_hp=1.0
        elif loser=="front":
            f=random.choice(self.front_list) if self.front_list else None
            self.front_img=safe_load_image(f); self.front_name=stem_upper(f)
            self.front_hp=1.0; self.front_anim.enter()
        elif loser=="back":
            b=random.choice(self.back_list) if self.back_list else None
            self.back_img=safe_load_image(b); self.back_name=stem_upper(b)
            self.back_hp=1.0; self.back_anim.enter()

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
                if winner=="front": self.front_hp=1.0
                else: self.back_hp=1.0
                if loser=="front": self.front_anim.exit()
                else: self.back_anim.exit()
                self.pending_replacement=loser; self.anim=None
                self.turn_is_front=(winner=="front")
            else: self.turn_is_front=not self.turn_is_front

    def draw_names(self):
        if self.front_name:
            txt=self.font.render(self.front_name,True,(0,0,0))
            surf=pygame.transform.smoothscale(txt,FRONT_NAME_SIZE)
            self.sc.blit(surf,FRONT_NAME_POS)
        if self.back_name:
            txt=self.font.render(self.back_name,True,(0,0,0))
            surf=pygame.transform.smoothscale(txt,BACK_NAME_SIZE)
            self.sc.blit(surf,BACK_NAME_POS)

    def draw_time(self):
        # current time
        h, m = time.strftime("%H"), time.strftime("%M")
        # blink colon every other second
        if int(time.time()) % 2 == 0:
            clock_str = f"{h}:{m}"
        else:
            clock_str = f"{h} {m}"  # replace colon with space

        txt = self.tfont.render(clock_str, True, (0,0,0))
        tx, ty = TIME_POS
        tw, th = TIME_SIZE
        rect = txt.get_rect(center=(tx+tw//2, ty+th//2))
        self.sc.blit(txt, rect)


    def draw(self):
        if self.bg:
            self.sc.blit(pygame.transform.smoothscale(self.bg,(WINDOW_WIDTH,WINDOW_HEIGHT)),(0,0))
        else: self.sc.fill((255,255,255))
        self.front_anim.update(self.dt); self.back_anim.update(self.dt)
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
                spr=pygame.transform.smoothscale(self.front_img,FRONT_SPRITE_SIZE)
                self.sc.blit(spr,(fx - a_offset,fy))  # front lunges left
            if self.back_img:
                spr=pygame.transform.smoothscale(self.back_img,BACK_SPRITE_SIZE)
                self.sc.blit(spr,(bx,by))
                if d_flash:
                    o=pygame.Surface(BACK_SPRITE_SIZE,pygame.SRCALPHA); o.fill((255,255,255,150))
                    self.sc.blit(o,(bx,by))
        elif self.anim and self.anim.attacker=="back":
            if self.front_img:
                spr=pygame.transform.smoothscale(self.front_img,FRONT_SPRITE_SIZE)
                self.sc.blit(spr,(fx,fy))
                if d_flash:
                    o=pygame.Surface(FRONT_SPRITE_SIZE,pygame.SRCALPHA); o.fill((255,255,255,150))
                    self.sc.blit(o,(fx,fy))
            if self.back_img:
                spr=pygame.transform.smoothscale(self.back_img,BACK_SPRITE_SIZE)
                self.sc.blit(spr,(bx + a_offset,by))  # back lunges right
        else:
            if self.front_img: self.sc.blit(pygame.transform.smoothscale(self.front_img,FRONT_SPRITE_SIZE),(fx,fy))
            if self.back_img:  self.sc.blit(pygame.transform.smoothscale(self.back_img,BACK_SPRITE_SIZE),(bx,by))
        # HUD
        draw_hp_bar(self.sc,*FRONT_HP_BAR_POS,value=self.front_hp,w=FRONT_HP_BAR_SIZE[0],h=FRONT_HP_BAR_SIZE[1])
        draw_hp_bar(self.sc,*BACK_HP_BAR_POS,value=self.back_hp,w=BACK_HP_BAR_SIZE[0],h=BACK_HP_BAR_SIZE[1])
        self.draw_names()
        self.draw_time()

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
