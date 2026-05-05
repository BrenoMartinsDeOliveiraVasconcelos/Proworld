"""
2D Top-Down Procedural Survival Game
Controls:
  WASD          - move player
  Left mouse    - attack (break trees, kill creatures, destroy blocks)
  Right mouse   - place colred block (on empty ground)
  1-8           - select color 1-8
  Shift+1-8     - select color 9-16
  ESC           - quit

Requirements: pygame (pip install pygame)
"""

import pygame
import random
import math
import sys
from typing import List, Tuple, Optional
import datetime

# ----------------------------------------------------------------------
# Constants & settings
# ----------------------------------------------------------------------
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
TILE_SIZE = 32
WORLD_WIDTH = 512   # in tiles
WORLD_HEIGHT = 512

# Colours
COLOR_DIRT = (139, 90, 43)
COLOR_PLAYER = (255, 255, 255)
COLOR_HP_BAR = (255, 0, 0)
COLOR_HP_BG = (50, 50, 50)

# 16 building block colours
BLOCK_COLORS = [
    (255, 0, 0),     # 1 red
    (0, 255, 0),     # 2 green
    (0, 0, 255),     # 3 blue
    (255, 255, 0),   # 4 yellow
    (0, 255, 255),   # 5 cyan
    (255, 0, 255),   # 6 magenta
    (255, 165, 0),   # 7 orange
    (128, 0, 128),   # 8 purple
    (255, 255, 255), # 9 white
    (0, 0, 0),       # 10 black
    (128, 128, 128), # 11 grey
    (139, 69, 19),   # 12 brown
    (255, 192, 203), # 13 pink
    (50, 205, 50),   # 14 lime
    (0, 128, 128),   # 15 teal
    (128, 0, 0),     # 16 maroon
]

# Element colours (used for creatures and their attacks)
ELEMENT_COLORS = {
    "Fire":        (255, 69, 0),
    "Water":       (30, 144, 255),
    "Ground":      (139, 69, 19),
    "Rock":        (169, 169, 169),
    "Dark":        (75, 0, 130),
    "Electricity": (255, 255, 0),
    "Light":       (255, 255, 224),
}

# Base vallues
BASE_P_SPEED = 220.0
BASE_CREATURE_SPEED = 90.0
PLAYER_RECOVER_TIME = 1 # in seconds
PLAYER_RECOVER_RATE = 0.01
VEGETATION_BOOST = 32


# Creature settings
CREATURE_MAX_COUNT = int((WORLD_WIDTH*WORLD_HEIGHT)/300)
CREATURE_HP = 100
CREATURE_SPEED = BASE_CREATURE_SPEED
CREATURE_ATTACK_RANGE = 120.0
CREATURE_SIGHT_RANGE = 200.0
CREATURE_ATTACK_COOLDOWN = 2.0   # seconds
CREATURE_ATTACK_DAMAGE = 15

# Player settings
PLAYER_SPEED = BASE_P_SPEED
PLAYER_MAX_HP = 100
PLAYER_ATTACK_COOLDOWN = 0.35
PLAYER_ATTACK_DAMAGE = 35
PLAYER_ATTACK_RANGE = 55.0     # distance in front

# Attack projectile settings
PROJECTILE_SPEED = 300.0
PROJECTILE_LIFETIME = 1.2      # seconds to live
PROJECTILE_DAMAGE = 15

# ----------------------------------------------------------------------
# Simple Perlin noise implementation (2D)
# ----------------------------------------------------------------------
class PerlinNoise:
    def __init__(self, seed=0):
        self.perm = list(range(256))
        random.seed(seed)
        random.shuffle(self.perm)
        self.perm *= 2  # double for overflow

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, a, b, t):
        return a + t * (b - a)

    def grad(self, hash_val, x, y):
        h = hash_val & 3
        u = x if h < 2 else y
        v = y if h < 2 else x
        return (u if h & 1 == 0 else -u) + (v if h & 2 == 0 else -v)

    def noise(self, x, y):
        # integer part
        xi = int(math.floor(x)) & 255
        yi = int(math.floor(y)) & 255
        # fractional part
        xf = x - math.floor(x)
        yf = y - math.floor(y)
        # fade curves
        u = self.fade(xf)
        v = self.fade(yf)
        # hash coordinates
        aa = self.perm[self.perm[xi] + yi]
        ab = self.perm[self.perm[xi] + yi + 1]
        ba = self.perm[self.perm[xi + 1] + yi]
        bb = self.perm[self.perm[xi + 1] + yi + 1]
        # blend
        x1 = self.lerp(self.grad(aa, xf, yf), self.grad(ba, xf - 1, yf), u)
        x2 = self.lerp(self.grad(ab, xf, yf - 1), self.grad(bb, xf - 1, yf - 1), u)
        return self.lerp(x1, x2, v)   # range approx -1..1

# ----------------------------------------------------------------------
# Tile object
# ----------------------------------------------------------------------
class Tile:
    def __init__(self, tile_type: str, color: tuple, speed_impact: int):
        self.type = tile_type          # "water", "sand", "grass", "rock"
        self.vegetation = None         # "tree" or "bush" or None
        self.block_color = None        # index into BLOCK_COLORS or None
        self.terrain_color = color
        self.speed_impact = speed_impact
        self.allow_spawn = False

# ----------------------------------------------------------------------
# Creature class
# ----------------------------------------------------------------------
class Creature:
    def __init__(self, x, y, element: str, behavior: str):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.speed = CREATURE_SPEED
        self.element = element
        self.behavior = behavior      # "aggressive" or "passive"
        self.hp = CREATURE_HP
        self.max_hp = CREATURE_HP
        self.attack_cooldown = random.uniform(0, CREATURE_ATTACK_COOLDOWN)
        # visual shape
        self.shape = random.choice(["circle", "square", "triangle", "diamond"])
        self.size = random.randint(14, 22)
        # random wander
        self.wander_timer = random.uniform(0, 2)
        self.wander_angle = random.uniform(0, 2*math.pi)

    def update(self, dt, player_x, player_y, attacks: list, player_hp: list):
        # decrease attack cooldown
        self.attack_cooldown = max(0, self.attack_cooldown - dt)

        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)

        if self.behavior == "aggressive":
            if dist < CREATURE_SIGHT_RANGE:
                # chase player
                if dist > 1:
                    self.vx = (dx / dist) * self.speed
                    self.vy = (dy / dist) * self.speed
                # attack if close enough and cooldown ready
                if dist < CREATURE_ATTACK_RANGE and self.attack_cooldown == 0:
                    self.attack(attacks, player_x, player_y)
                return
        elif self.behavior == "passive":
            if dist < CREATURE_SIGHT_RANGE:
                # flee
                if dist > 0.1:
                    self.vx = -(dx / dist) * self.speed
                    self.vy = -(dy / dist) * self.speed
                return

        # random wandering
        self.wander_timer -= dt
        if self.wander_timer <= 0:
            self.wander_angle = random.uniform(0, 2*math.pi)
            self.wander_timer = random.uniform(1.5, 3.0)
        self.vx = math.cos(self.wander_angle) * self.speed * 0.5
        self.vy = math.sin(self.wander_angle) * self.speed * 0.5

    def attack(self, attacks: list, target_x, target_y):
        self.attack_cooldown = CREATURE_ATTACK_COOLDOWN
        angle = math.atan2(target_y - self.y, target_x - self.x)
        attacks.append(AttackProjectile(
            self.x, self.y, angle, self.element, damage=CREATURE_ATTACK_DAMAGE
        ))

    def take_damage(self, amount):
        self.hp -= amount
        return self.hp <= 0

    def get_color(self):
        base = ELEMENT_COLORS.get(self.element, (200, 200, 200))
        if self.hp < self.max_hp * 0.5:
            base = tuple(max(0, c-60) for c in base)
        return base

# ----------------------------------------------------------------------
# Attack projectile
# ----------------------------------------------------------------------
class AttackProjectile:
    def __init__(self, x, y, angle, element, damage):
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * PROJECTILE_SPEED
        self.vy = math.sin(angle) * PROJECTILE_SPEED
        self.element = element
        self.damage = damage
        self.life = PROJECTILE_LIFETIME
        self.color = ELEMENT_COLORS.get(element, (255, 255, 255))
        self.trail_particles = []

    def update(self, dt, particles: list):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        # spawn trail particles
        if random.random() < 0.6:
            particles.append({
                'x': self.x, 'y': self.y,
                'vx': random.uniform(-30, 30),
                'vy': random.uniform(-30, 30),
                'life': 0.4,
                'max_life': 0.4,
                'color': self.color,
                'size': random.randint(2, 5)
            })
        return self.life <= 0

# ----------------------------------------------------------------------
# Main game
# ----------------------------------------------------------------------
class Game:
    def __init__(self):
        # Terrain type, max height (0-1), color, speed impact, possible vegetations (list of tuples containing type and chance) and allow spawn
        self.types = [
            # (Type, Max Height, Color (R,G,B), Speed Impact, [Vegetation], Allow Spawn)
            ("deep_water",   0.35, (119, 158, 203), 0.30, [], False), 
            ("water",        0.45, (174, 198, 207), 0.50, [], False),
            ("sand",         0.52, (238, 217, 196), 1.25, [("bush", 0.02)], True),
            ("dirt",         0.60, (188, 152, 126), 1.10, [("bush", 0.05), ("tree", 0.05)], True),
            ("light_grass",  0.70, (161, 202, 165), 1.00, [("grass", 0.4), ("tree", 0.15)], True),
            ("forest_grass", 0.80, (119, 160, 119), 0.85, [("tree", 0.5), ("bush", 0.3)], True),
            ("gravel",       0.90, (180, 176, 170), 0.70, [("bush", 0.05)], True),
            ("snow",         1.00, (235, 238, 240), 0.60, [], True)
        ]
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Procedural World")
        self.clock = pygame.time.Clock()
        self.running = True

        # world map
        self.tiles = [[Tile("grass", (0, 0, 0), 0) for _ in range(WORLD_HEIGHT)] for _ in range(WORLD_WIDTH)]
        self.perlin = PerlinNoise(seed=random.randint(0, 9999))

        # player
        self.player_x = WORLD_WIDTH * TILE_SIZE / 2
        self.player_y = WORLD_HEIGHT * TILE_SIZE / 2
        self.player_hp = PLAYER_MAX_HP
        self.player_max_hp = PLAYER_MAX_HP
        self.attack_cooldown = 0.0
        self.selected_color = 0  # 0-15
        self.player_xp = 0

        # entities
        self.creatures: List[Creature] = []
        self.attacks: List[AttackProjectile] = []
        self.particles = []

        # generate terrain
        self._generate_world()

        # camera offset
        self.camera_x = 0
        self.camera_y = 0

    def _sample_noise(self, x, y, scale=0.08):
        # returns value roughly -1..1
        return self.perlin.noise(x * scale, y * scale)

    def _generate_world(self):
                     
        # ground type based on height noise
        for tx in range(WORLD_WIDTH):
            for ty in range(WORLD_HEIGHT):
                h = self._sample_noise(tx, ty, 0.06)
                # convert to 0..1 approx
                val = (h + 1) * 0.5

                tile_type = ""
                terrain_color = (0, 0, 0)
                speed_impact = 0
                allow_spawn = False

                for t in self.types:
                    if val > t[1]:
                        continue
                    else:
                        tile_type = t[0]
                        terrain_color = t[2]
                        speed_impact = t[3]
                        allow_spawn = t[5]
                        break
                        
                tile = Tile(tile_type, terrain_color, speed_impact)
                tile.allow_spawn = allow_spawn
                self.tiles[tx][ty] = tile

        # vegetation: trees and bushes on grass/dirt
        for tx in range(WORLD_WIDTH):
            for ty in range(WORLD_HEIGHT):
                tile = self.tiles[tx][ty]
                tile_type = tile.type
                tile_vegetation = []

                for tp in self.types:
                    if tp[0] == tile_type:
                        tuple_size = len(tp)

                        if tuple_size >= 1:
                            tile_vegetation = tp[4]
                        else:
                            tile.vegetation = None
                        
                        break

                
                vegetation_list_size = len(tile_vegetation)

                if vegetation_list_size == 1:
                    if random.random() < tile_vegetation[0][1]:
                        tile.vegetation = tile_vegetation[0][0]
                elif vegetation_list_size > 1:
                    vnoise = self._sample_noise(tx + 1000, ty + 1000, 0.15)

                    sorted_vegetations = sorted(tile_vegetation, key=lambda x: x[1], reverse=True)

                    for veg in sorted_vegetations:
                        if vnoise > veg[1]:
                            tile.vegetation = veg[0]

        # spawn creatures
        elements = list(ELEMENT_COLORS.keys())
        for _ in range(CREATURE_MAX_COUNT):
            for _ in range(50):  # try to find valid position
                cx = random.randint(0, WORLD_WIDTH-1) * TILE_SIZE + TILE_SIZE//2
                cy = random.randint(0, WORLD_HEIGHT-1) * TILE_SIZE + TILE_SIZE//2
                tile = self.tiles[int(cx//TILE_SIZE)][int(cy//TILE_SIZE)]
                if tile.allow_spawn:
                    element = random.choice(elements)
                    behavior = random.choice(["aggressive", "passive"])
                    self.creatures.append(Creature(cx, cy, element, behavior))
                    break

    def _get_tile_at(self, world_x, world_y) -> Optional[Tile]:
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        if 0 <= tx < WORLD_WIDTH and 0 <= ty < WORLD_HEIGHT:
            return self.tiles[tx][ty]
        return None

    def _player_attack(self):
        # melee attack in mouse direction
        mx, my = pygame.mouse.get_pos()
        world_mx = mx + self.camera_x
        world_my = my + self.camera_y
        angle = math.atan2(world_my - self.player_y, world_mx - self.player_x)
        # attack rectangle
        attack_dist = PLAYER_ATTACK_RANGE
        ax = self.player_x + math.cos(angle) * attack_dist/2
        ay = self.player_y + math.sin(angle) * attack_dist/2
        # define rectangle width 30, length attack_dist
        w = 25
        h = attack_dist
        # simple: check distance from segment or circle. We'll check all creatures/trees in area.
        # use a circle check with radius attack_dist/2 + some, and angle constraint.
        # For simplicity: dot product to check if in front.
        for creature in self.creatures[:]:
            dx = creature.x - self.player_x
            dy = creature.y - self.player_y
            if abs(dx) < attack_dist and abs(dy) < attack_dist:
                dist = math.hypot(dx, dy)
                if dist < attack_dist + creature.size:
                    # check angle: angle between direction and to creature < 50 degrees
                    creature_angle = math.atan2(dy, dx)
                    diff = abs(creature_angle - angle)
                    if diff > math.pi: diff = 2*math.pi - diff
                    if diff < math.radians(55):
                        if creature.take_damage(PLAYER_ATTACK_DAMAGE):
                            self._increase_xp(1)
                            self.creatures.remove(creature)
                            self._spawn_death_particles(creature.x, creature.y, creature.element)
                        break  # attack hits only one creature

        # break trees
        tx = int(self.player_x // TILE_SIZE)
        ty = int(self.player_y // TILE_SIZE)
        # check nearby tiles
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx = tx + dx
                ny = ty + dy
                if 0 <= nx < WORLD_WIDTH and 0 <= ny < WORLD_HEIGHT:
                    tile = self.tiles[nx][ny]
                    if tile.vegetation:
                        # check if player is close enough to tree center
                        cx = nx * TILE_SIZE + TILE_SIZE//2
                        cy = ny * TILE_SIZE + TILE_SIZE//2
                        if math.hypot(cx - self.player_x, cy - self.player_y) < PLAYER_ATTACK_RANGE + 20:
                            # also angle check
                            tree_angle = math.atan2(cy - self.player_y, cx - self.player_x)
                            diff = abs(tree_angle - angle)
                            if diff > math.pi: diff = 2*math.pi - diff
                            if diff < math.radians(70):
                                tile.vegetation = None
                                # Boost player HP
                                self.player_hp += (self.player_max_hp/VEGETATION_BOOST)
                                if self.player_hp >= self.player_max_hp:
                                    self.player_hp = self.player_max_hp
                            
                                # spawn wood particles
                                for _ in range(8):
                                    self.particles.append({
                                        'x': cx, 'y': cy,
                                        'vx': random.uniform(-60, 60),
                                        'vy': random.uniform(-60, 60),
                                        'life': 0.5, 'max_life': 0.5,
                                        'color': (139, 69, 19),
                                        'size': random.randint(2, 4)
                                    })
                                break
        # destroy blocks
        tx = int(world_mx // TILE_SIZE)
        ty = int(world_my // TILE_SIZE)
        if 0 <= tx < WORLD_WIDTH and 0 <= ty < WORLD_HEIGHT:
            tile = self.tiles[tx][ty]
            if tile.block_color is not None:
                dist_to_tile = math.hypot(tx*TILE_SIZE + TILE_SIZE//2 - self.player_x,
                                          ty*TILE_SIZE + TILE_SIZE//2 - self.player_y)
                if dist_to_tile < PLAYER_ATTACK_RANGE + 20:
                    tile_angle = math.atan2(ty*TILE_SIZE + TILE_SIZE//2 - self.player_y,
                                            tx*TILE_SIZE + TILE_SIZE//2 - self.player_x)
                    diff = abs(tile_angle - angle)
                    if diff > math.pi: diff = 2*math.pi - diff
                    if diff < math.radians(70):
                        tile.block_color = None

    def _spawn_death_particles(self, x, y, element):
        color = ELEMENT_COLORS.get(element, (200,200,200))
        for _ in range(20):
            angle = random.uniform(0, 2*math.pi)
            speed = random.uniform(40, 120)
            self.particles.append({
                'x': x, 'y': y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': 0.8, 'max_life': 0.8,
                'color': color,
                'size': random.randint(2, 6)
            })

    def _update_particles(self, dt):
        for p in self.particles[:]:
            p['life'] -= dt
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vx'] *= 0.95
            p['vy'] *= 0.95
            if p['life'] <= 0:
                self.particles.remove(p)

    def _update_attacks(self, dt):
        for attack in self.attacks[:]:
            dead = attack.update(dt, self.particles)
            if dead:
                self.attacks.remove(attack)
                continue
            # check collision with player
            dist = math.hypot(attack.x - self.player_x, attack.y - self.player_y)
            if dist < 18:
                self.player_hp -= attack.damage
                self.attacks.remove(attack)
                # hit effect
                for _ in range(5):
                    self.particles.append({
                        'x': self.player_x, 'y': self.player_y,
                        'vx': random.uniform(-60, 60),
                        'vy': random.uniform(-60, 60),
                        'life': 0.3, 'max_life': 0.3,
                        'color': (255, 255, 255),
                        'size': random.randint(3, 6)
                    })

    def _handle_input(self, dt):
        keys = pygame.key.get_pressed()
        # movement
        dx, dy = 0.0, 0.0
        if keys[pygame.K_a]: dx -= 1
        if keys[pygame.K_d]: dx += 1
        if keys[pygame.K_w]: dy -= 1
        if keys[pygame.K_s]: dy += 1
        length = math.hypot(dx, dy)
        if length > 0:
            dx /= length
            dy /= length

        tile = self._get_tile_at(self.player_x, self.player_y)

        PLAYER_SPEED = BASE_P_SPEED * tile.speed_impact
        
        self.player_x += dx * PLAYER_SPEED * dt
        self.player_y += dy * PLAYER_SPEED * dt


        # keep player inside world bounds
        self.player_x = max(TILE_SIZE/2, min(WORLD_WIDTH*TILE_SIZE - TILE_SIZE/2, self.player_x))
        self.player_y = max(TILE_SIZE/2, min(WORLD_HEIGHT*TILE_SIZE - TILE_SIZE/2, self.player_y))

        # attack cooldown
        self.attack_cooldown = max(0, self.attack_cooldown - dt)

    def _draw_tile(self, screen, tile_x, tile_y, tile: Tile):
        rect = pygame.Rect(tile_x - self.camera_x, tile_y - self.camera_y, TILE_SIZE, TILE_SIZE)
        if rect.right < 0 or rect.left > SCREEN_WIDTH or rect.bottom < 0 or rect.top > SCREEN_HEIGHT:
            return  # off screen

        # ground colour
        color = tile.terrain_color

        pygame.draw.rect(screen, color, rect)

        # placed block overlay
        if tile.block_color is not None:
            block_rect = pygame.Rect(tile_x - self.camera_x, tile_y - self.camera_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, BLOCK_COLORS[tile.block_color], block_rect)

        # vegetation
        if tile.vegetation:
            cx = tile_x + TILE_SIZE//2 - self.camera_x
            cy = tile_y + TILE_SIZE//2 - self.camera_y
            if tile.vegetation == "tree":
                # trunk
                pygame.draw.rect(screen, (101, 67, 33),
                                 (cx-4, cy+2, 8, 12))
                # canopy
                pygame.draw.circle(screen, (0, 128, 0), (cx, cy-4), 12)
                pygame.draw.circle(screen, (34, 139, 34), (cx-5, cy-8), 9)
                pygame.draw.circle(screen, (34, 139, 34), (cx+5, cy-8), 9)
            elif tile.vegetation == "bush":
                pygame.draw.circle(screen, (0, 100, 0), (cx, cy), 8)
                pygame.draw.circle(screen, (46, 139, 87), (cx-4, cy-2), 6)

    def _draw_creature(self, screen, creature: Creature):
        x = creature.x - self.camera_x
        y = creature.y - self.camera_y
        color = creature.get_color()
        if creature.shape == "circle":
            pygame.draw.circle(screen, color, (int(x), int(y)), creature.size)
        elif creature.shape == "square":
            rect = pygame.Rect(0, 0, creature.size*2, creature.size*2)
            rect.center = (x, y)
            pygame.draw.rect(screen, color, rect)
        elif creature.shape == "triangle":
            points = [
                (x, y - creature.size),
                (x - creature.size, y + creature.size//2),
                (x + creature.size, y + creature.size//2)
            ]
            pygame.draw.polygon(screen, color, points)
        elif creature.shape == "diamond":
            points = [
                (x, y - creature.size),
                (x + creature.size, y),
                (x, y + creature.size),
                (x - creature.size, y)
            ]
            pygame.draw.polygon(screen, color, points)
        # HP bar
        if creature.hp < creature.max_hp:
            bar_width = creature.size * 2
            hp_ratio = creature.hp / creature.max_hp
            pygame.draw.rect(screen, COLOR_HP_BG,
                             (x - bar_width//2, y - creature.size - 10, bar_width, 4))
            pygame.draw.rect(screen, (255, 0, 0),
                             (x - bar_width//2, y - creature.size - 10, int(bar_width * hp_ratio), 4))

    def _draw_ui(self, screen):
        # player HP bar
        bar_width = 200
        bar_height = 20
        hp_ratio = self.player_hp / self.player_max_hp
        pygame.draw.rect(screen, COLOR_HP_BG, (20, SCREEN_HEIGHT - 40, bar_width, bar_height))
        pygame.draw.rect(screen, (0, 255, 0) if hp_ratio > 0.5 else (255, 255, 0),
                         (20, SCREEN_HEIGHT - 40, int(bar_width * hp_ratio), bar_height))
        # selected block color
        swatch_rect = pygame.Rect(SCREEN_WIDTH - 100, SCREEN_HEIGHT - 60, 40, 40)
        pygame.draw.rect(screen, BLOCK_COLORS[self.selected_color], swatch_rect)
        pygame.draw.rect(screen, (255,255,255), swatch_rect, 2)

        # Texts
        font = pygame.font.SysFont(None, 24)
        text = font.render(f"Color {self.selected_color+1}", True, (255,255,255))
        xp_text = font.render(f"Points: {self.player_xp}", True, (255,255,255))
        screen.blit(xp_text, (40, SCREEN_HEIGHT - 60))
        screen.blit(text, (SCREEN_WIDTH - 150, SCREEN_HEIGHT - 80))


    def _increase_xp(self, amount: int):
        self.player_xp += amount

        # Adjust max hp accordingly
        self.player_max_hp = PLAYER_MAX_HP + (PLAYER_MAX_HP*(self.player_xp/64))

    def run(self):
        init_time = datetime.datetime.now().timestamp()
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    # color selection
                    if event.key == pygame.K_LEFT:
                        self.selected_color -= 1
                    elif event.key == pygame.K_RIGHT:
                        self.selected_color += 1

                    if self.selected_color < 0 or self.selected_color >= len(BLOCK_COLORS):
                        self.selected_color = 0
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # left click = attack
                        if self.attack_cooldown == 0:
                            self._player_attack()
                            self.attack_cooldown = PLAYER_ATTACK_COOLDOWN
                    elif event.button == 3:  # right click = place block
                        mx, my = pygame.mouse.get_pos()
                        world_x = mx + self.camera_x
                        world_y = my + self.camera_y
                        tx = int(world_x // TILE_SIZE)
                        ty = int(world_y // TILE_SIZE)
                        if 0 <= tx < WORLD_WIDTH and 0 <= ty < WORLD_HEIGHT:
                            tile = self.tiles[tx][ty]
                            # can place only on empty ground (no vegetation, no block, not water)
                            if tile.type != "water" and tile.block_color is None and tile.vegetation is None:
                                tile.block_color = self.selected_color

            # update
            self._handle_input(dt)

            # update creatures
            for creature in self.creatures[:]:
                # boundary
                creature.x = max(TILE_SIZE/2, min(WORLD_WIDTH*TILE_SIZE - TILE_SIZE/2, creature.x))
                creature.y = max(TILE_SIZE/2, min(WORLD_HEIGHT*TILE_SIZE - TILE_SIZE/2, creature.y))

                # SPeed
                creature_tile = self._get_tile_at(creature.x, creature.y)
                creature.speed = BASE_CREATURE_SPEED * creature_tile.speed_impact
                
                creature.update(dt, self.player_x, self.player_y, self.attacks, self.player_hp)
                # movement
                creature.x += creature.vx * dt
                creature.y += creature.vy * dt

                # simple collision with water: avoid water tiles
                tile = self._get_tile_at(creature.x, creature.y)
                if tile and tile.type == "water":
                    # push out
                    creature.x -= creature.vx * dt * 2
                    creature.y -= creature.vy * dt * 2

            self._update_attacks(dt)
            self._update_particles(dt)

            # check player death
            if self.player_hp <= 0:
                self.player_hp = self.player_max_hp
                self.player_x = WORLD_WIDTH * TILE_SIZE / 2
                self.player_y = WORLD_HEIGHT * TILE_SIZE / 2
                # respawn (reset game state could be optional)

            # restore player health
            now = datetime.datetime.now().timestamp()
            if now - init_time >= PLAYER_RECOVER_TIME:
                print(f"Player health: {self.player_hp} ->", end="")
                recovered_hp = (self.player_hp + self.player_hp * PLAYER_RECOVER_RATE)
                self.player_hp = recovered_hp
                print(f"{recovered_hp}")

                if self.player_hp > self.player_max_hp:
                    self.player_hp= self.player_max_hp

                init_time = now

            # camera follow
            self.camera_x = self.player_x - SCREEN_WIDTH / 2
            self.camera_y = self.player_y - SCREEN_HEIGHT / 2
            # clamp camera to world
            self.camera_x = max(0, min(WORLD_WIDTH * TILE_SIZE - SCREEN_WIDTH, self.camera_x))
            self.camera_y = max(0, min(WORLD_HEIGHT * TILE_SIZE - SCREEN_HEIGHT, self.camera_y))

            # draw
            self.screen.fill((0, 0, 0))
            # determine visible tile range
            start_tx = max(0, int(self.camera_x // TILE_SIZE))
            start_ty = max(0, int(self.camera_y // TILE_SIZE))
            end_tx = min(WORLD_WIDTH, int((self.camera_x + SCREEN_WIDTH) / TILE_SIZE) + 1)
            end_ty = min(WORLD_HEIGHT, int((self.camera_y + SCREEN_HEIGHT) / TILE_SIZE) + 1)

            for tx in range(start_tx, end_tx):
                for ty in range(start_ty, end_ty):
                    tile = self.tiles[tx][ty]
                    self._draw_tile(self.screen, tx * TILE_SIZE, ty * TILE_SIZE, tile)

            # draw creatures
            for creature in self.creatures:
                self._draw_creature(self.screen, creature)

            # draw attack projectiles
            for attack in self.attacks:
                x = attack.x - self.camera_x
                y = attack.y - self.camera_y
                pygame.draw.circle(self.screen, attack.color, (int(x), int(y)), 6)

            # draw particles
            for p in self.particles:
                alpha = int(255 * (p['life'] / p['max_life']))
                color = (*p['color'], alpha) if len(p['color'])==3 else p['color']
                size = p['size']
                x = p['x'] - self.camera_x
                y = p['y'] - self.camera_y
                # simple alpha not directly supported, just draw small circle
                pygame.draw.circle(self.screen, p['color'], (int(x), int(y)), size)

            # draw player
            player_screen_x = self.player_x - self.camera_x
            player_screen_y = self.player_y - self.camera_y
            pygame.draw.circle(self.screen, COLOR_PLAYER, (int(player_screen_x), int(player_screen_y)), 16)
            # player direction indicator (mouse)
            mx, my = pygame.mouse.get_pos()
            angle = math.atan2(my - player_screen_y, mx - player_screen_x)
            end_x = player_screen_x + math.cos(angle) * 25
            end_y = player_screen_y + math.sin(angle) * 25
            pygame.draw.line(self.screen, (255,255,0), (player_screen_x, player_screen_y), (end_x, end_y), 3)

            # UI
            self._draw_ui(self.screen)

            pygame.display.flip()

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    Game().run()