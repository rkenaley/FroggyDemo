"""
===============================================================================
FROGGY: 16-BIT METROIDVANIA TECH DEMO ENGINE
===============================================================================
A complete, self-contained 2D platformer engine inspired by Super Castlevania IV,
Super Metroid, and classic 16-bit SNES titles.

Written for maximum legibility and educational value: every physics calculation,
state machine transition, procedural sprite generator, and collision step is
extensively commented so curious coders can understand every single line!

CORE FEATURES INCLUDED:
1. Procedural ASCII Pixel-Art Generator:
   - Converts human-readable text grids in memory into 16x16 and 32x32 sprite surfaces.
   - No external image files or broken paths required!
2. SNES Controller Abstraction:
   - Reads keyboard keys and physical USB/Bluetooth gamepads.
   - Separates continuous holds from single-frame 'just pressed' edge triggers.
3. Separated-Axis AABB Platformer Physics:
   - Resolves X-axis then Y-axis collisions independently to eliminate corner snagging.
   - Coyote Time (grace jump after leaving ledges) & Jump Input Buffering.
   - Variable-height jumping, wall slides, and wall jumps.
4. Super Castlevania IV 8-Directional Tongue & Grapple:
   - Aims in 8 compass directions using normalized unit vectors.
   - Latches onto Gold Grapple Blocks ('G') and runs physical pendulum math:
     Left/Right pumps swing momentum, Up/Down reels in or lets out rope.
5. Combat Loop & Tongue-Yanking (Yoshi's Island / Castlevania style):
   - 'E' Spiked Moss Beetle: Cliff-edge sensing ground patroller. Stun with Spore
     Boomerang (R) or Tongue (Y), then hit again to YANK and swallow!
   - 'F' Neon Buzzfly: Sine-wave aerial flyer. Instant tongue latch, yank, & swallow.
   - Swallowing bugs heals +1 Heart and resets mid-air Double Jump!
6. Multi-Room Metroidvania World & Automap:
   - 4 interconnected rooms parsed from ASCII character maps.
   - Smooth fade-to-black room transitions via glowing Metroidvania Door Portals ('A', 'B', 'C').
   - Super Metroid style Automap HUD in the top-right corner.
7. Multi-Phase Boss: Emperor Mantis ('M'):
   - 32x32 boss with 3 distinct combat phases (Figure-8 Hover, Dive-Bomb, Overdrive).
   - Weak-point puzzle: Stun armor with R-Button Spore Boomerang, then aim your
     8-way tongue into the exposed magenta chest core to rip out a Boss Energy Pearl!
8. Live In-Game Mouse Level Builder:
   - Left-Click: Paint Solid Brick ('#')
   - Hold [G] + Left-Click: Place Gold Grapple Ring ('G')
   - Hold [E] + Left-Click: Place Moss Beetle ('E')
   - Hold [F] + Left-Click: Place Flying Buzzfly ('F')
   - Hold [M] + Left-Click: Place Emperor Mantis Boss ('M')
   - Right-Click: Erase tile/enemy to empty air ('.')
   - Press [P]: Export live-edited room ASCII grid directly to the terminal!
   - Press [B]: Instant warp to Room 4 (Boss Sanctum) for quick testing!

CONTROLS (Keyboard / SNES Controller):
- D-Pad (8-Way Aim & Move) : Arrow Keys or W/A/S/D | Gamepad D-Pad / Left Stick
- A or B Button (Jump)     : SPACE, Z, or K        | Gamepad A / B (Face Buttons)
- Y Button (8-Way Tongue)  : X or J                | Gamepad X / Y
- R Button (Spore Weapon)  : C, U, or Left Shift   | Gamepad R Shoulder (R1)
- Toggle Telemetry HUD     : TAB
- Warp to Boss Chamber     : B
- Export Level ASCII       : P
- Quit Game                : ESCAPE
===============================================================================
"""

import math
import random
import sys
import pygame

# =============================================================================
# 1. GLOBAL ENGINE CONSTANTS & TUNING PARAMETERS
# =============================================================================

# Every tile in the game world is 16x16 pixels (authentic SNES resolution standard).
TILE_SIZE = 16

# Internal rendering canvas resolution: 480x270 (a widescreen 16:9 ratio of retro pixels).
# We render all gameplay at this low resolution, then upscale cleanly to the desktop window.
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270

# Window scaling factor (480x270 * 3 = 1440x810 monitor window).
WINDOW_SCALE = 3
WINDOW_WIDTH = INTERNAL_WIDTH * WINDOW_SCALE
WINDOW_HEIGHT = INTERNAL_HEIGHT * WINDOW_SCALE

# Target game loop framerate (60 updates & renders per second).
TARGET_FPS = 60

# --- Platformer Physics Tuning (Measured in Pixels per Frame at 60 FPS) ---
# Downward acceleration added to Froggy's vertical velocity (vy) every frame.
GRAVITY = 0.38

# Terminal fall velocity to prevent tunneling through thin floor platforms.
MAX_FALL_SPEED = 8.5

# Friction-clamped maximum fall speed when pressing against a vertical wall.
WALL_SLIDE_SPEED = 1.6

# Horizontal acceleration rates (ground has higher authority than mid-air).
MOVE_ACCEL = 0.55
AIR_ACCEL = 0.38

# Velocity dampening applied each frame when no directional input is held.
GROUND_FRICTION = 0.78
AIR_DRAG = 0.94

# Top horizontal running speed.
MAX_RUN_SPEED = 3.6

# Instant upward launch velocities when pressing the jump button.
JUMP_VELOCITY = -7.6
DOUBLE_JUMP_VELOCITY = -6.8

# Multiplier applied to upward velocity if the player releases Jump early (allows short hops).
VARIABLE_JUMP_CUTOFF = 0.45

# Velocities applied when springing off a vertical wall.
WALL_JUMP_X_SPEED = 4.4
WALL_JUMP_Y_SPEED = -7.2

# Number of frames horizontal input is locked after a wall jump so Froggy cleanly clears the wall.
WALL_JUMP_LOCK_FRAMES = 10

# Coyote Time: Grace frames allowing Froggy to jump shortly after walking off a ledge.
COYOTE_TIME_FRAMES = 6

# Jump Buffer: Remembers a jump button press made shortly before landing on the ground.
JUMP_BUFFER_FRAMES = 6

# --- Super Castlevania IV Tongue & Pendulum Grapple Constants ---
TONGUE_EXTEND_SPEED = 14.0   # Speed at which the tongue shoots outward (pixels/frame)
TONGUE_RETRACT_SPEED = 15.0  # Speed at which the tongue pulls back into Froggy's mouth
TONGUE_MAX_LENGTH = 135.0    # Maximum reach of the tongue
TONGUE_HOLD_FRAMES = 7       # Frames tongue pauses at peak extension on a miss

SWING_GRAVITY = 0.011        # Angular gravity pulling Froggy toward the vertical center
SWING_DAMPING = 0.992        # Natural air resistance / energy loss per swing frame
SWING_PUMP_FORCE = 0.0022    # Angular acceleration added when pressing Left/Right on D-Pad
SWING_REEL_SPEED = 1.5       # Rate of rope length adjustment when holding Up/Down on D-Pad
SWING_MIN_LENGTH = 28.0      # Minimum allowed rope length while swinging

# --- Player & Combat Constants ---
PLAYER_MAX_HP = 5            # Number of hearts in Froggy's health pool
PLAYER_INVULN_FRAMES = 65    # Invulnerability frames (~1.1 seconds) after taking damage
ENEMY_STUN_FRAMES = 210      # Stun duration (3.5 seconds) for upside-down Moss Beetles
BOSS_MAX_HP = 6              # Number of energy pearls required to defeat Emperor Mantis
BOSS_WEAK_EXPOSED_FRAMES = 210 # Stun window to yank the boss's exposed magenta core

# --- Metroidvania Screen Transitions ---
TRANSITION_FADE_SPEED = 18   # Alpha fade change per frame (0 to 255 in ~14 frames)
DOOR_COOLDOWN_FRAMES = 24    # Grace frames after entering a room to avoid immediately re-entering

# --- Color Palette (RGB Tuples) ---
COLOR_BG_GRID = (30, 36, 64)
COLOR_TONGUE_PINK = (242, 107, 148)
COLOR_TONGUE_TIP = (255, 168, 196)
COLOR_SPORE_CYAN = (80, 245, 210)
COLOR_HUD_TEXT = (230, 240, 255)
COLOR_DOOR_GLOW = (90, 225, 255)
COLOR_HEART_RED = (235, 65, 85)
COLOR_HEART_EMPTY = (65, 50, 75)
COLOR_BOSS_CORE = (255, 70, 210)
COLOR_BOSS_GOLD = (255, 215, 70)


# =============================================================================
# 2. PROCEDURAL PIXEL-ART SPRITE & TEXTURE GENERATOR
# =============================================================================

class SpriteSheetGenerator:
    """
    Renders 16x16 and 32x32 pixel-art sprites directly into RAM from text grids.
    Each character maps to an RGB color in PALETTE. This completely avoids broken
    external asset file paths and lets coders edit pixel art directly in code!
    """

    PALETTE = {
        '.': None,               # Transparent pixel
        'G': (76, 187, 73),      # Frog Primary Green / Mantis Emerald
        'D': (43, 122, 48),      # Dark Shaded Green
        'L': (168, 230, 110),    # Bright Lime Highlight / Frog Belly
        'W': (255, 255, 255),    # Pure White
        'K': (20, 20, 30),       # Deep Charcoal / Pupil Black
        'R': (220, 55, 65),      # Crimson Red (Hero Bandana & Beetle Shell)
        'P': (242, 107, 148),    # Tongue Pink
        'M': (255, 65, 200),     # Boss Weak-Point Neon Magenta
        'S': (72, 88, 118),      # Stone Base Blue-Gray
        'B': (46, 58, 82),       # Stone Shadow Dark Blue-Gray
        'H': (108, 130, 168),    # Stone Highlight Light Slate
        'Y': (245, 200, 66),     # Grapple Gold / Stun Stars
        'O': (225, 125, 40),     # Amber / Orange Accent
        'C': (70, 215, 255),     # Portal Cyan / Wing Membrane
        'V': (155, 85, 225),     # Violet Insect Body
    }

    @classmethod
    def make_surface_from_grid(cls, grid_lines):
        """
        Paints a transparent Pygame surface from a list of equal-length strings.
        """
        height = len(grid_lines)
        width = len(grid_lines[0])
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        for y, row in enumerate(grid_lines):
            for x, char in enumerate(row):
                color = cls.PALETTE.get(char)
                if color is not None:
                    surface.set_at((x, y), color)
        return surface

    @classmethod
    def build_tile_textures(cls):
        """
        Creates 16x16 pixel-art tiles for solid stone bricks ('#'),
        gold grapple blocks ('G'), and glowing Metroidvania doors ('DOOR').
        """
        brick_grid = [
            "HHHHHHHHGGGGHHHH",
            "SSSSSSSDGGGGDSSS",
            "SSSSSSSSDGGDSSSS",
            "BBBBBBBBSBBSBBBB",
            "KKKKKKKKSKKSKKKK",
            "HHHSSSSSSSSHHHHH",
            "SSSSSSSSSSSSSSSS",
            "BBBBBBBBBBBBBBBB",
            "KKKKKKKKKKKKKKKK",
            "HHHHHHHSSSSHHHHH",
            "SSSSSSSSSSSSSSSS",
            "SSSSSSSSSSSSSSSS",
            "BBBBBBBBBBBBBBBB",
            "KKKKKKKKKKKKKKKK",
            "SSSSHHHHHHHHSSSS",
            "BBBBBBBBBBBBBBBB",
        ]
        grapple_grid = [
            "....OOOOOOOO....",
            "..OOYYYYYYYYOO..",
            ".OYYWWWWWWWWYYO.",
            ".OYWOOOOOOOOYYO.",
            "OYYO........OYYO",
            "OYWO...YY...OYYO",
            "OYWO..YYYY..OYYO",
            "OYWO..YYYY..OYYO",
            "OYWO...YY...OYYO",
            "OYYO........OYYO",
            ".OYWOOOOOOOOYYO.",
            ".OYYWWWWWWWWYYO.",
            "..OOYYYYYYYYOO..",
            "....OOOOOOOO....",
            "......OOOO......",
            "................",
        ]
        door_grid = [
            "KKKKCCCCCCCCKKKK",
            "KKCCWWWWWWWWCCKK",
            "KCWWCCCCCCCCWWCK",
            "KCWCCWWWWWWCCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCCWWWWWWCCWCK",
            "KCWWCCCCCCCCWWCK",
            "KKCCWWWWWWWWCCKK",
            "KKKKCCCCCCCCKKKK",
        ]
        return {
            '#': cls.make_surface_from_grid(brick_grid),
            'G': cls.make_surface_from_grid(grapple_grid),
            'DOOR': cls.make_surface_from_grid(door_grid),
        }

    @classmethod
    def build_froggy_animations(cls):
        """
        Creates all animation states for Froggy, flipped for both right and left.
        """
        idle_1 = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            ".RGGGGGGGGGGGG..",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "..DDGGGGGGGGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGG......GGG..",
            ".DDDD......DDDD.",
            "................",
        ]
        idle_2 = [
            "................",
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "..DDGGGGGGGGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGGG....GGGG..",
            ".DDDDD....DDDDD.",
            "................",
        ]
        run_1 = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "...DGLLLLLLGDD..",
            "...DGGGGGGGGD...",
            "....GGGGGGGG....",
            "..GGG......GGG..",
            ".GGG........GGG.",
            "DDDD.........DDD",
            "................",
            "................",
        ]
        run_2 = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "...DGGGGGGGGD...",
            "...GGGG..GGGG...",
            "...GGG....GGG...",
            "....DDDD..DDDD..",
            "................",
            "................",
            "................",
        ]
        jump_up = [
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGG......GGG..",
            "..GG........GG..",
            ".DDD........DDD.",
            "................",
            "................",
            "................",
        ]
        wall_slide = [
            "................",
            ".....WW...WW....",
            "....WKKW.WKKW...",
            "....GGGGGGGGGG..",
            "...RRRRRRRRRRRR.",
            "...GGGGGGGGGGGGD",
            "....GGLLLLLLGGGD",
            "....GLLLLLLLLGGD",
            "....DGLLLLLLGDDD",
            ".....GGGGGGGGDD.",
            "....GGG....GGGD.",
            "...GGG......DDD.",
            "...DDD..........",
            "................",
            "................",
            "................",
        ]
        mouth_open = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGPPPPPP",
            "..GGGGGGGPPPPPPP",
            "..GGGLLLLGGGG...",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "..DDGGGGGGGGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGG......GGG..",
            ".DDDD......DDDD.",
            "................",
        ]

        raw_frames = {
            "idle": [cls.make_surface_from_grid(idle_1), cls.make_surface_from_grid(idle_2)],
            "run": [
                cls.make_surface_from_grid(run_1),
                cls.make_surface_from_grid(idle_1),
                cls.make_surface_from_grid(run_2),
                cls.make_surface_from_grid(idle_1),
            ],
            "jump": [cls.make_surface_from_grid(jump_up)],
            "wall_slide": [cls.make_surface_from_grid(wall_slide)],
            "tongue": [cls.make_surface_from_grid(mouth_open)],
        }

        animations = {"right": {}, "left": {}}
        for state_name, surface_list in raw_frames.items():
            animations["right"][state_name] = surface_list
            animations["left"][state_name] = [
                pygame.transform.flip(surf, True, False) for surf in surface_list
            ]
        return animations

    @classmethod
    def build_enemy_animations(cls):
        """
        Creates animations for Moss Beetle ('E'), Buzzfly ('F'),
        and the 32x32 Emperor Mantis boss ('M').
        """
        beetle_1 = [
            "................",
            "....W......W....",
            "....W..WW..W....",
            "...RRRRRRRRRR...",
            "..RROOOOOOOORR..",
            ".RROOYYYYYYOORR.",
            ".RROOOOOOOOOORR.",
            "RROOOOOOOOOOWWRR",
            "RRRRRRRRRRRRWKWR",
            ".KKKKKKKKKKKKKK.",
            "..YYYYYYYYYYYY..",
            "..KK...KK...KK..",
            ".KK....KK....KK.",
            ".K.....K......K.",
            "................",
            "................",
        ]
        beetle_2 = [
            "................",
            "................",
            "....W......W....",
            "....W..WW..W....",
            "...RRRRRRRRRR...",
            "..RROOOOOOOORR..",
            ".RROOYYYYYYOORR.",
            ".RROOOOOOOOOORR.",
            "RROOOOOOOOOOWWRR",
            "RRRRRRRRRRRRWKWR",
            ".KKKKKKKKKKKKKK.",
            "..YYYYYYYYYYYY..",
            "...KK..KK..KK...",
            "...KK..KK..KK...",
            "....K...K...K...",
            "................",
        ]
        fly_1 = [
            "................",
            "..CCCC....CCCC..",
            ".CWWWWC..CWWWWC.",
            ".CWWWWCCCCWWWWC.",
            "..CCCCVVVVCCCC..",
            ".....VVVVVV.....",
            "....VVVVVVWR....",
            "....VVLLLLWR....",
            "....VVVVVVVV....",
            ".....VV..VV.....",
            "....KK....KK....",
            "................",
            "................",
            "................",
            "................",
            "................",
        ]
        fly_2 = [
            "................",
            "................",
            "................",
            ".....VVVVVV.....",
            "....VVVVVVWR....",
            "..CCCCLLLLWRCC..",
            ".CWWWWVVVVWWWWC.",
            ".CWWWWC..CWWWWC.",
            "..CCCC....CCCC..",
            ".....VV..VV.....",
            "....KK....KK....",
            "................",
            "................",
            "................",
            "................",
            "................",
        ]

        # 32x32 Emperor Mantis (Armored State with raised scythes)
        mantis_armored = [
            ".....YY..................YY.....",
            "......YY................YY......",
            "..CCC..YY....GGGGGG....YY..CCC..",
            ".CWWWC..YY..GLLLLLLG..YY..CWWWC.",
            ".CWWWWC..RRRRLLLLLLRRRR..CWWWWC.",
            ".CWWWWCCRRRRKLLLLLLKRRRRCCWWWWC.",
            "..CWWWWCCCGGGGLLLLGGGGCCCWWWWC..",
            "...CCCC..GGGGGGGGGGGGGG..CCCC...",
            ".........DDDDGGGGGGDDDD.........",
            "....YYYYDDDDYYYYYYYYDDDDYYYY....",
            "...YYLLLDDDYYYYYYYYYYDDDLLLYY...",
            "..YYLLLLLDDYYYOOOOYYYDDLLLLLYY..",
            ".YYLLLLLLLDDYYOOOOYYDDLLLLLLLYY.",
            ".YWLLLLLLLDDYYYYYYYYDDLLLLLLLWY.",
            "YWWLLLLLL...DDDDDDDD...LLLLLLWWY",
            "YWWLLLL.....GGGGGGGG.....LLLLWWY",
            "YWWLL......GGLLLLLLGG......LLWWY",
            ".YWW.......GGLLLLLLGG.......WWY.",
            "..YW.......DDDDDDDDDD.......WY..",
            "...........GGLLLLLLGG...........",
            "..........GGGLLLLLLGGG..........",
            ".........DDDDDDDDDDDDDD.........",
            "........GGGGGGGGGGGGGGGG........",
            ".......DDGGGGGGGGGGGGGGDD.......",
            "......DDD..DDDDDDDDDD..DDD......",
            ".....DDD......DDDD......DDD.....",
            "....DDD..................DDD....",
            "...YY......................YY...",
            "..YY........................YY..",
            "................................",
            "................................",
            "................................",
        ]

        # 32x32 Emperor Mantis (Weak Point Exposed with glowing magenta chest core)
        mantis_exposed = [
            "................................",
            "......Y........YY........Y......",
            ".....Y...Y............Y...Y.....",
            "..........RRRR....RRRR..........",
            ".........RRRRGGGGGGGRRRR........",
            ".........RRGGLLLLLLGGRRR........",
            "...CCCC...GGGGGGGGGGGG...CCCC...",
            "..CWWWWCCCDDDDGGGGDDDDCCCWWWWC..",
            "..CWWWWC.DDDDMMPPMMDDDD.CWWWWC..",
            "...CCCC..DDDMMWWWWMMDDD..CCCC...",
            ".........DDMMPWWWWPMMDD.........",
            ".........DDMPWWWWWWPMDD.........",
            ".........DDMMPWWWWPMMDD.........",
            ".........DDDMMWWWWMMDDD.........",
            "....YYYY..DDDDMMPPMMDDDD..YYYY..",
            "...YYLLL...DDDDDDDDDD...LLLYY...",
            "..YYLLLL....GGGGGGGG....LLLLYY..",
            ".YYLLLL....GGLLLLLLGG....LLLLYY.",
            ".YWLLL.....GGLLLLLLGG.....LLLWY.",
            "..YWW......DDDDDDDDDD......WWY..",
            "...........GGLLLLLLGG...........",
            "..........GGGLLLLLLGGG..........",
            ".........DDDDDDDDDDDDDD.........",
            "........GGGGGGGGGGGGGGGG........",
            "......DDDDGGGGGGGGGGGGDDDD......",
            "....DDDD...DDDDDDDDDD...DDDD....",
            "..DDDD........DDDD........DDDD..",
            ".YY..........................YY.",
            "................................",
            "................................",
            "................................",
            "................................",
        ]

        b1_surf = cls.make_surface_from_grid(beetle_1)
        b2_surf = cls.make_surface_from_grid(beetle_2)
        b_stun = pygame.transform.flip(b1_surf, False, True)

        f1_surf = cls.make_surface_from_grid(fly_1)
        f2_surf = cls.make_surface_from_grid(fly_2)

        m_arm_r = cls.make_surface_from_grid(mantis_armored)
        m_arm_l = pygame.transform.flip(m_arm_r, True, False)
        m_exp_r = cls.make_surface_from_grid(mantis_exposed)
        m_exp_l = pygame.transform.flip(m_exp_r, True, False)

        return {
            "beetle": {
                "right": [b1_surf, b2_surf],
                "left": [pygame.transform.flip(b1_surf, True, False), pygame.transform.flip(b2_surf, True, False)],
                "stunned": [b_stun, pygame.transform.flip(b_stun, True, False)],
            },
            "fly": {
                "right": [f1_surf, f2_surf],
                "left": [pygame.transform.flip(f1_surf, True, False), pygame.transform.flip(f2_surf, True, False)],
            },
            "mantis": {
                "armored_right": m_arm_r,
                "armored_left": m_arm_l,
                "exposed_right": m_exp_r,
                "exposed_left": m_exp_l,
            },
        }


# =============================================================================
# 3. VISUAL ASCII WORLD BLUEPRINTS
# =============================================================================

# LEGEND FOR DESIGNING ROOMS:
# '.' = Empty Air
# '#' = Solid Stone Brick (16x16)
# 'G' = Gold Grapple Anchor Ring (For 8-way Castlevania IV tongue swinging!)
# 'E' = Spiked Moss Beetle (Ground patroller: Stun first, then Yank & Eat!)
# 'F' = Neon Buzzfly (Flying sine-wave insect: Instant Tongue Yank & Eat!)
# 'M' = Emperor Mantis Boss (3-phase multi-stage boss)
# 'S' = Froggy Starting Position
# 'A', 'B', 'C' = Glowing Metroidvania Transition Doors

WORLD_BLUEPRINTS = {
    # -------------------------------------------------------------------------
    # ROOM 1: MOSSY ENTRANCE HALL (Connects East via Door 'A' to Chimney Tower)
    # -------------------------------------------------------------------------
    "entrance_hall": {
        "title": "1. MOSSY ENTRANCE HALL",
        "bg_color": (20, 26, 46),
        "map_coords": (0, 1),
        "doors": {
            "A": {
                "target_room": "chimney_tower",
                "target_door": "A",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "##################################################",
            "#................................................#",
            "#................................................#",
            "#.............G....................G.............#",
            "#.......................F........................#",
            "#.........................................########",
            "#.......................E........................#",
            "#....................########....................#",
            "#.......F................................F.......#",
            "#...........######..............######...........#",
            "#................................................#",
            "#.....................................E..........#",
            "#....S...............................######......#",
            "#..######.............E..........................A",
            "#...................######.......................A",
            "#..................................E.............A",
            "##################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 2: WALL-JUMP CHIMNEY TOWER (Connects West to Room 1, East to Room 3)
    # -------------------------------------------------------------------------
    "chimney_tower": {
        "title": "2. WALL-JUMP CHIMNEY TOWER",
        "bg_color": (28, 22, 48),
        "map_coords": (1, 1),
        "doors": {
            "A": {
                "target_room": "entrance_hall",
                "target_door": "A",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
            "B": {
                "target_room": "grapple_cavern",
                "target_door": "B",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "####################################",
            "#..................................#",
            "#.................G................#",
            "#..................................B",
            "#...........................E......B",
            "#......................#############",
            "#..............###.....#...........#",
            "#......F.......###.....#...........#",
            "#..............###.....#...........#",
            "#......G.......###.....#...........#",
            "#..............###.....#...........#",
            "#..............###.....#...........#",
            "#..............###.........F.......#",
            "#..............###............E....#",
            "#..............###.........######..#",
            "#......F.......###.................#",
            "#..............###.................#",
            "#..............###..........G......#",
            "#........E.....###.................#",
            "#.....######...###.................#",
            "#..............###.........E.......#",
            "A........................######....#",
            "A..........E.......................#",
            "A.......######.....................#",
            "####################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 3: GRAPPLE SWING CAVERN (Connects West to Room 2, East to Boss)
    # -------------------------------------------------------------------------
    "grapple_cavern": {
        "title": "3. GRAPPLE SWING CAVERN",
        "bg_color": (16, 34, 44),
        "map_coords": (2, 1),
        "doors": {
            "B": {
                "target_room": "chimney_tower",
                "target_door": "B",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
            "C": {
                "target_room": "boss_sanctum",
                "target_door": "C",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "B...........G.............G.............G.............G....#",
            "B..........................................................#",
            "#########..................................................#",
            "#.................F.............F.............F............#",
            "#...................G.............G.............G..........C",
            "#........................................................E.C",
            "#......................................................#####",
            "#..........E...............................................#",
            "#.......#####.............F.............F..................#",
            "#...................###.........###.........###......E.....#",
            "#...................###.........###.........###....#####...#",
            "#...................###.........###.........###............#",
            "#...................###.........###.........###............#",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 4: EMPEROR MANTIS BOSS SANCTUM ('M' spawns the 3-Phase Boss!)
    # -------------------------------------------------------------------------
    "boss_sanctum": {
        "title": "4. EMPEROR MANTIS SANCTUM",
        "bg_color": (38, 16, 32),
        "map_coords": (3, 1),
        "doors": {
            "C": {
                "target_room": "grapple_cavern",
                "target_door": "C",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "####################################",
            "#..................................#",
            "#.......G........G........G........#",
            "#..................................#",
            "#..................................#",
            "#........................M.........#",
            "#...#####..................#####...#",
            "#..................................#",
            "#............G........G............#",
            "#..................................#",
            "#..................................#",
            "#.......#####..........#####.......#",
            "#..................................#",
            "C..................................#",
            "C..................................#",
            "C..######..................######..#",
            "####################################",
        ],
    },
}


# =============================================================================
# 4. PARTICLES & PROJECTILES
# =============================================================================

class Particle:
    """
    Lightweight pixel sparks for visual juice when jumping, hitting, or eating.
    """
    def __init__(self, x, y, vx, vy, color, lifetime):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.color = color
        self.lifetime = lifetime
        self.age = 0

    def update(self):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15  # Subtle gravity on falling sparks

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        size = 3 if (self.lifetime - self.age) > 8 else 2
        pygame.draw.rect(surface, self.color, (sx, sy, size, size))


class SporeBoomerang:
    """
    Fired with the SNES 'R' Shoulder Button.
    Travels outward, decelerates, and curves back like a classic Castlevania Cross!
    Combat Role:
    - Stuns Moss Beetles ('E') by flipping them upside down onto their backs.
    - Overloads Emperor Mantis's armor, dropping it into the 'WEAK_EXPOSED' state!
    """
    def __init__(self, x, y, dir_x, dir_y):
        self.x = float(x)
        self.y = float(y)
        self.vx = dir_x * 6.5
        self.vy = dir_y * 6.5
        # Constant backward acceleration creates the return arc
        self.return_ax = -dir_x * 0.14
        self.return_ay = -dir_y * 0.14
        self.age = 0
        self.max_age = 110
        self.radius = 5
        self.alive = True

    def update(self, room):
        self.age += 1
        self.vx += self.return_ax
        self.vy += self.return_ay
        self.x += self.vx
        self.y += self.vy

        hit_box = pygame.Rect(int(self.x - 6), int(self.y - 6), 12, 12)

        # 1. Check collision against regular enemies in the room
        for enemy in room.enemies:
            if enemy.alive and enemy.state == "PATROL" and enemy.rect.colliderect(hit_box):
                enemy.stun(knockback_dir_x=(1.0 if self.vx >= 0 else -1.0))
                room.spawn_particle_burst(enemy.center_x, enemy.center_y, COLOR_SPORE_CYAN, count=10)

        # 2. Check collision against active Emperor Mantis boss
        boss = room.get_active_boss()
        if boss and boss.alive and boss.rect.colliderect(hit_box):
            if boss.hit_by_spore_boomerang(room):
                self.alive = False  # Consumed on direct hit with the boss

        if self.age >= self.max_age:
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        screen_x = int(self.x - camera_x)
        screen_y = int(self.y - camera_y)
        # Draw spinning 4-blade cross using age as rotation angle
        angle = self.age * 0.35
        for i in range(4):
            blade_angle = angle + i * (math.pi * 0.5)
            bx = screen_x + int(math.cos(blade_angle) * 6)
            by = screen_y + int(math.sin(blade_angle) * 6)
            pygame.draw.line(surface, COLOR_SPORE_CYAN, (screen_x, screen_y), (bx, by), 2)
        pygame.draw.circle(surface, (255, 255, 255), (screen_x, screen_y), 2)


class BossScytheWave:
    """
    Crescent energy projectile fired by Emperor Mantis during Phases 1, 2, and 3.
    """
    def __init__(self, x, y, vx, vy, enraged=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.enraged = enraged
        self.radius = 7
        self.age = 0
        self.max_age = 150
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x - 5), int(self.y - 5), 10, 10)

    def update(self, room):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        if self.age >= self.max_age or room.is_point_inside_solid(self.x, self.y):
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        outer_col = (255, 90, 110) if self.enraged else (140, 255, 130)
        pygame.draw.circle(surface, outer_col, (sx, sy), self.radius, 2)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 3)


# =============================================================================
# 5. ENEMY ENTITIES & 3-PHASE BOSS AI
# =============================================================================

class BaseEnemy:
    """
    Base class for all creatures in the game.
    States:
    - "PATROL"  : Moving according to AI. Hurts Froggy on contact.
    - "STUNNED" : Upside-down or incapacitated. Harmless, ready to be yanked!
    - "YANKED"  : Latched onto Froggy's tongue and being drawn into his mouth!
    """
    def __init__(self, spawn_x, spawn_y, width, height):
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.width = width
        self.height = height
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        self.vx = 0.0
        self.vy = 0.0
        self.dir_x = 1
        self.state = "PATROL"
        self.stun_timer = 0
        self.anim_timer = random.randint(0, 30)
        self.alive = True
        self.is_boss = False
        self.can_yank_immediately = False

    @property
    def center_x(self):
        return self.x + self.width * 0.5

    @property
    def center_y(self):
        return self.y + self.height * 0.5

    def set_center(self, cx, cy):
        """Locks the enemy's coordinates to the tongue tip while being reeled in."""
        self.x = cx - self.width * 0.5
        self.y = cy - self.height * 0.5
        self.rect.topleft = (int(self.x), int(self.y))

    def stun(self, knockback_dir_x=0.0):
        self.state = "STUNNED"
        self.stun_timer = ENEMY_STUN_FRAMES
        self.vx = knockback_dir_x * 1.8
        self.vy = -3.8


class BossEnergyPearl(BaseEnemy):
    """
    Spawns when Froggy's 8-way tongue strikes Emperor Mantis's exposed chest core!
    Rips out of the boss and reels straight into Froggy's mouth, healing +1 HP
    and refreshing his double jump.
    """
    def __init__(self, x, y):
        super().__init__(x, y, width=12, height=12)
        self.state = "YANKED"
        self.can_yank_immediately = True

    def update(self, room):
        self.anim_timer += 1

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.center_x - camera_x)
        sy = int(self.center_y - camera_y)
        pygame.draw.circle(surface, COLOR_BOSS_CORE, (sx, sy), 6)
        pygame.draw.circle(surface, COLOR_BOSS_GOLD, (sx, sy), 4)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 2)


class MossBeetle(BaseEnemy):
    """
    'E' in the ASCII map: Spiked Moss Beetle.
    Uses forward-downward cliff feelers to turn around at platform edges and walls.
    Combat:
    - 1st hit (Spore or Tongue) -> Flips upside down with spinning stun stars!
    - 2nd hit (Tongue)          -> Latches on, reels into mouth, and gets eaten!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y + 2, width=14, height=14)
        self.anims = enemy_anims["beetle"]
        self.patrol_speed = 0.85
        self.can_yank_immediately = False

    def update(self, room):
        self.anim_timer += 1
        if self.state == "YANKED":
            return

        if self.state == "STUNNED":
            self.stun_timer -= 1
            self.vx *= 0.88
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=False)
            if self.stun_timer <= 0:
                self.state = "PATROL"
            return

        # Patrol AI
        self.vx = self.dir_x * self.patrol_speed
        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
        self._move_and_collide(room, turn_at_ledges=True)

    def _move_and_collide(self, room, turn_at_ledges):
        # 1. Horizontal movement and wall bounce
        self.x += self.vx
        self.rect.x = int(round(self.x))
        hit_wall = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                elif self.vx < 0:
                    self.rect.left = tile.right
                self.x = float(self.rect.x)
                hit_wall = True

        if hit_wall and self.state == "PATROL":
            self.dir_x *= -1

        # 2. Vertical movement and floor landing
        self.y += self.vy
        self.rect.y = int(round(self.y))
        on_ground = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vy > 0:
                    self.rect.bottom = tile.top
                    on_ground = True
                elif self.vy < 0:
                    self.rect.top = tile.bottom
                self.y = float(self.rect.y)
                self.vy = 0.0

        # 3. Cliff feeler probe: checks 2px in front of leading foot and 2px below floor
        if turn_at_ledges and on_ground:
            feeler_x = self.rect.right + 2 if self.dir_x > 0 else self.rect.left - 2
            feeler_y = self.rect.bottom + 2
            if not room.is_point_inside_solid(feeler_x, feeler_y):
                self.dir_x *= -1

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.rect.x - 1 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)
        if self.state in ("STUNNED", "YANKED"):
            frames = self.anims["stunned"]
            speed = 4 if (self.state == "STUNNED" and self.stun_timer < 60) else 10
            sprite = frames[(self.anim_timer // speed) % len(frames)]
            surface.blit(sprite, (sx, sy))

            if self.state == "STUNNED":
                # Draw orbiting yellow stun stars
                star_angle = self.anim_timer * 0.18
                for i in range(2):
                    ang = star_angle + i * math.pi
                    star_x = int(self.center_x - camera_x + math.cos(ang) * 7)
                    star_y = int(self.rect.top - 5 - camera_y + math.sin(ang) * 2)
                    pygame.draw.circle(surface, (255, 240, 90), (star_x, star_y), 2)
        else:
            facing_key = "right" if self.dir_x > 0 else "left"
            frames = self.anims[facing_key]
            sprite = frames[(self.anim_timer // 8) % len(frames)]
            surface.blit(sprite, (sx, sy))


class BuzzFly(BaseEnemy):
    """
    'F' in the ASCII map: Neon Buzzfly.
    Flies horizontally while bobbing up and down along a smooth sine wave.
    Unarmored: hitting it with Froggy's tongue immediately latches and yanks it
    into Froggy's mouth, resetting his mid-air double jump!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=14, height=14)
        self.anims = enemy_anims["fly"]
        self.base_y = float(spawn_y)
        self.patrol_origin_x = float(spawn_x)
        self.patrol_radius = 56.0
        self.fly_speed = 1.15
        self.can_yank_immediately = True

    def update(self, room):
        self.anim_timer += 1
        if self.state == "YANKED":
            return

        if self.state == "STUNNED":
            self.stun_timer -= 1
            self.y += 0.5
            self.rect.y = int(round(self.y))
            if self.stun_timer <= 0:
                self.state = "PATROL"
            return

        # Horizontal patrol
        self.x += self.dir_x * self.fly_speed
        self.rect.x = int(round(self.x))
        if (abs(self.x - self.patrol_origin_x) > self.patrol_radius or
                room.rect_collides_with_solid(self.rect)):
            self.dir_x *= -1
            self.x += self.dir_x * self.fly_speed * 2

        # Smooth sine-wave vertical hovering
        self.y = self.base_y + math.sin(self.anim_timer * 0.09) * 12.0
        self.rect.topleft = (int(round(self.x)), int(round(self.y)))

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.rect.x - 1 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)
        facing_key = "right" if self.dir_x > 0 else "left"
        frames = self.anims[facing_key]
        sprite = frames[(self.anim_timer // 4) % len(frames)]
        surface.blit(sprite, (sx, sy))


class EmperorMantis(BaseEnemy):
    """
    32x32 Multi-Phase SNES Metroidvania Boss ('M' in ASCII map).
    COMBAT PUZZLE:
    1. In normal flight or dive attacks, the mantis's raised scythe armor
       deflects Froggy's tongue with metallic sparks.
    2. Hitting the boss with the R-Button Spore Boomerang overloads its carapace,
       dropping it to the floor into the 'WEAK_EXPOSED' state!
    3. While 'WEAK_EXPOSED', a glowing Magenta Chest Core opens up. Striking it
       with the 8-way tongue rips out a Boss Energy Pearl, dealing 1 damage to the
       boss and healing Froggy +1 Heart!

    PHASES:
    - Phase 1 (6-5 HP): Lissajous figure-8 hover flight + single scythe waves.
    - Phase 2 (4-3 HP): 40% faster flight, predatory diagonal dive-bombs, and
      summons a Buzzfly so Froggy can eat it for mid-battle healing!
    - Phase 3 (2-1 HP): Enraged crimson overdrive + 3-way fan spread shots.
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=28, height=30)
        self.anims = enemy_anims["mantis"]
        self.is_boss = True
        self.max_hp = BOSS_MAX_HP
        self.hp = BOSS_MAX_HP
        self.home_x = float(spawn_x)
        self.home_y = float(spawn_y)
        self.flight_timer = 0.0
        self.attack_cooldown = 95

        # States: "HOVER", "DIVE_TELEGRAPH", "DIVE_ATTACK", "WEAK_EXPOSED", "RECOVERING"
        self.state = "HOVER"
        self.state_timer = 0
        self.dive_vx = 0.0
        self.dive_vy = 0.0
        self.flash_timer = 0

    @property
    def phase(self):
        if self.hp >= 5:
            return 1
        elif self.hp >= 3:
            return 2
        return 3

    @property
    def weak_point_rect(self):
        """Hitbox of the glowing chest core when exposed."""
        return pygame.Rect(int(self.center_x - 10), int(self.center_y - 10), 20, 20)

    def hit_by_spore_boomerang(self, room):
        """Step 1: Spore Boomerang overloads armor and drops boss to floor."""
        if self.state in ("HOVER", "DIVE_TELEGRAPH", "DIVE_ATTACK"):
            self.state = "WEAK_EXPOSED"
            self.stun_timer = BOSS_WEAK_EXPOSED_FRAMES
            self.vx = 0.0
            self.vy = 1.2
            self.flash_timer = 12
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_SPORE_CYAN, count=18)
            return True
        return False

    def yank_exposed_weak_point(self, room):
        """Step 2: Tongue strikes exposed core, ripping out an Energy Pearl!"""
        self.hp -= 1
        self.flash_timer = 20
        pearl = BossEnergyPearl(self.center_x, self.center_y)
        room.enemies.append(pearl)
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=24)

        if self.hp <= 0:
            # Defeat sequence!
            self.alive = False
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=45)
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=35)
        else:
            self.state = "RECOVERING"
            self.state_timer = 45
            # In Phase 2+, summon a helpful Buzzfly minion if none are present
            fly_count = sum(1 for e in room.enemies if isinstance(e, BuzzFly) and e.alive)
            if self.phase >= 2 and fly_count < 1:
                room.enemies.append(BuzzFly(self.home_x - 90, self.home_y - 20, room.enemy_anims))

        return pearl

    def update(self, room):
        self.anim_timer += 1
        if self.flash_timer > 0:
            self.flash_timer -= 1

        player = room.active_player_ref
        if player is not None:
            self.dir_x = 1 if player.center_x >= self.center_x else -1

        # --- STATE 1: WEAK POINT EXPOSED (Stunned on floor, waiting for tongue yank!) ---
        if self.state == "WEAK_EXPOSED":
            self.stun_timer -= 1
            self.vy = min(self.vy + GRAVITY * 0.65, 4.5)
            self.y += self.vy
            self.rect.y = int(round(self.y))
            for tile in room.solid_tiles:
                if self.rect.colliderect(tile):
                    if self.vy > 0:
                        self.rect.bottom = tile.top
                    self.y = float(self.rect.y)
                    self.vy = 0.0

            if self.stun_timer <= 0:
                self.state = "RECOVERING"
                self.state_timer = 35
            return

        # --- STATE 2: RECOVERING (Rising back to aerial patrol coordinates) ---
        if self.state == "RECOVERING":
            self.state_timer -= 1
            self.x += (self.home_x - self.x) * 0.07
            self.y += (self.home_y - self.y) * 0.07
            self.rect.topleft = (int(round(self.x)), int(round(self.y)))
            if self.state_timer <= 0:
                self.state = "HOVER"
                self.attack_cooldown = 55
            return

        # --- STATE 3: DIVE-BOMB TELEGRAPH (Vibrates and flashes warning ring) ---
        if self.state == "DIVE_TELEGRAPH":
            self.state_timer -= 1
            self.rect.x = int(round(self.x)) + random.randint(-2, 2)
            if self.state_timer <= 0 and player is not None:
                dx = player.center_x - self.center_x
                dy = player.center_y - self.center_y
                dist = max(1.0, math.hypot(dx, dy))
                dive_speed = 6.2 if self.phase == 2 else 7.4
                self.dive_vx = (dx / dist) * dive_speed
                self.dive_vy = (dy / dist) * dive_speed
                self.state = "DIVE_ATTACK"
                self.state_timer = 42
            return

        # --- STATE 4: HIGH-SPEED DIAGONAL DIVE-BOMB ---
        if self.state == "DIVE_ATTACK":
            self.state_timer -= 1
            self.x += self.dive_vx
            self.y += self.dive_vy
            self.rect.topleft = (int(round(self.x)), int(round(self.y)))
            if room.rect_collides_with_solid(self.rect) or self.state_timer <= 0:
                room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=10)
                self.state = "RECOVERING"
                self.state_timer = 40
            return

        # --- STATE 5: FIGURE-8 AERIAL HOVER & SCYTHE ATTACKS ---
        speed_mult = 1.0 + (self.phase - 1) * 0.38
        self.flight_timer += 0.032 * speed_mult
        # Lissajous Figure-8 Flight path
        target_x = self.home_x + math.sin(self.flight_timer) * 135.0
        target_y = self.home_y + math.sin(self.flight_timer * 2.0) * 38.0
        self.x += (target_x - self.x) * 0.1
        self.y += (target_y - self.y) * 0.1
        self.rect.topleft = (int(round(self.x)), int(round(self.y)))

        self.attack_cooldown -= 1
        if self.attack_cooldown <= 0 and player is not None:
            self._fire_scythe_attack(room, player)
            if self.phase >= 2 and random.random() < 0.55:
                self.state = "DIVE_TELEGRAPH"
                self.state_timer = 32
            self.attack_cooldown = max(42, 95 - (self.phase - 1) * 22)

    def _fire_scythe_attack(self, room, player):
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        base_angle = math.atan2(dy, dx)
        wave_speed = 3.6 if self.phase < 3 else 4.4
        # Phase 1 & 2 fire a direct wave; Phase 3 fires a 3-way fan spread!
        angles = [base_angle] if self.phase < 3 else [base_angle - 0.28, base_angle, base_angle + 0.28]
        for ang in angles:
            vx = math.cos(ang) * wave_speed
            vy = math.sin(ang) * wave_speed
            room.boss_projectiles.append(
                BossScytheWave(self.center_x, self.center_y, vx, vy, enraged=(self.phase == 3))
            )

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.rect.x - 2 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)

        # Select sprite (Armored vs Exposed)
        if self.state == "WEAK_EXPOSED":
            key = "exposed_right" if self.dir_x > 0 else "exposed_left"
        else:
            key = "armored_right" if self.dir_x > 0 else "armored_left"
        sprite = self.anims[key]

        # Draw Phase 3 Enraged Crimson Aura or Dive Telegraph Warning
        if self.phase == 3 or self.state == "DIVE_TELEGRAPH":
            aura_col = (255, 60, 90) if (self.anim_timer // 3) % 2 == 0 else COLOR_BOSS_GOLD
            pygame.draw.circle(
                surface, aura_col,
                (int(self.center_x - camera_x), int(self.center_y - camera_y)), 20, 1
            )

        surface.blit(sprite, (sx, sy))

        # When stunned ("WEAK_EXPOSED"), draw a pulsing target beacon over the chest core
        if self.state == "WEAK_EXPOSED":
            core_x = int(self.center_x - camera_x)
            core_y = int(self.center_y - 2 - camera_y)
            pulse_r = 5 + int(math.sin(self.anim_timer * 0.35) * 2)
            pygame.draw.circle(surface, COLOR_BOSS_CORE, (core_x, core_y), pulse_r, 1)

            for i in range(3):
                ang = self.anim_timer * 0.16 + i * (math.tau / 3.0)
                star_x = core_x + int(math.cos(ang) * 12)
                star_y = int(self.rect.top - 5 - camera_y + math.sin(ang) * 3)
                pygame.draw.circle(surface, COLOR_BOSS_GOLD, (star_x, star_y), 2)


# =============================================================================
# 6. ASCII TILEMAP ROOM PARSER & LIVE LEVEL BUILDER
# =============================================================================

class DoorPortal:
    """
    Represents a glowing Metroidvania doorway linking to another room.
    """
    def __init__(self, door_id, rect, target_room, target_door, spawn_offset_x, spawn_offset_y):
        self.door_id = door_id
        self.rect = rect
        self.target_room = target_room
        self.target_door = target_door
        self.spawn_offset_x = spawn_offset_x
        self.spawn_offset_y = spawn_offset_y


class TileMapRoom:
    """
    Converts an ASCII blueprint into:
    1. Greedy horizontally merged collision rectangles for super fast physics.
    2. 16x16 visual tile blits.
    3. Gold grapple blocks ('G') and Metroidvania door portals.
    4. Active entities (Moss Beetles, Buzzflies, Emperor Mantis boss).
    """
    def __init__(self, room_id, blueprint, tile_textures, enemy_anims):
        self.room_id = room_id
        self.title = blueprint["title"]
        self.bg_color = blueprint["bg_color"]
        self.map_coords = blueprint["map_coords"]
        self.door_configs = blueprint.get("doors", {})
        self.tile_textures = tile_textures
        self.enemy_anims = enemy_anims

        raw_lines = blueprint["ascii_grid"]
        self.rows = len(raw_lines)
        self.cols = max(len(line) for line in raw_lines)
        # Pad short rows with '.' so missing characters never crash
        self.grid = [list(line.ljust(self.cols, '.')) for line in raw_lines]

        self.world_width = self.cols * TILE_SIZE
        self.world_height = self.rows * TILE_SIZE

        self.solid_tiles = []
        self.visual_bricks = []
        self.grapple_nodes = []
        self.door_tiles = []
        self.doors = {}
        self.enemy_spawns = []
        self.enemies = []
        self.boss_projectiles = []
        self.particles = []
        self.default_spawn = (64, 64)
        self.active_player_ref = None
        self.boss_defeated_banner_timer = 0

        self.rebuild_geometry(respawn_enemies=True)

    def rebuild_geometry(self, respawn_enemies=True):
        """
        Parses the 2D character grid into collision boxes and spawns.
        Called on room setup AND whenever you paint a tile with your mouse!
        """
        self.solid_tiles.clear()
        self.visual_bricks.clear()
        self.grapple_nodes.clear()
        self.door_tiles.clear()
        self.doors.clear()
        self.enemy_spawns.clear()

        door_bounds = {}

        for row in range(self.rows):
            col = 0
            while col < self.cols:
                char = self.grid[row][col]
                world_x = col * TILE_SIZE
                world_y = row * TILE_SIZE

                # Case 1: Solid Brick ('#') with greedy horizontal row merging
                if char == '#':
                    start_col = col
                    while col < self.cols and self.grid[row][col] == '#':
                        self.visual_bricks.append((col * TILE_SIZE, world_y))
                        col += 1
                    merged_width = (col - start_col) * TILE_SIZE
                    self.solid_tiles.append(
                        pygame.Rect(start_col * TILE_SIZE, world_y, merged_width, TILE_SIZE)
                    )
                    continue

                # Case 2: Gold Grapple Anchor ('G')
                elif char == 'G':
                    self.grapple_nodes.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                # Case 3: Player Default Spawn ('S')
                elif char == 'S':
                    self.default_spawn = (world_x, world_y)

                # Case 4: Enemies ('E', 'F', 'M')
                elif char in ('E', 'F', 'M'):
                    self.enemy_spawns.append((char, world_x, world_y))

                # Case 5: Door Portals ('A', 'B', 'C')
                elif char in self.door_configs:
                    tile_rect = pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE)
                    self.door_tiles.append((world_x, world_y))
                    if char not in door_bounds:
                        door_bounds[char] = tile_rect
                    else:
                        door_bounds[char] = door_bounds[char].union(tile_rect)

                col += 1

        for door_char, union_rect in door_bounds.items():
            cfg = self.door_configs[door_char]
            self.doors[door_char] = DoorPortal(
                door_id=door_char,
                rect=union_rect,
                target_room=cfg["target_room"],
                target_door=cfg["target_door"],
                spawn_offset_x=cfg["spawn_offset_x"],
                spawn_offset_y=cfg["spawn_offset_y"],
            )

        if respawn_enemies:
            self.spawn_enemies()

    def spawn_enemies(self):
        """Resets and instantiates fresh enemies in the room."""
        self.enemies.clear()
        self.boss_projectiles.clear()
        self.particles.clear()
        for char, wx, wy in self.enemy_spawns:
            if char == 'E':
                self.enemies.append(MossBeetle(wx, wy, self.enemy_anims))
            elif char == 'F':
                self.enemies.append(BuzzFly(wx, wy, self.enemy_anims))
            elif char == 'M':
                self.enemies.append(EmperorMantis(wx, wy, self.enemy_anims))

    def get_active_boss(self):
        for enemy in self.enemies:
            if enemy.alive and enemy.is_boss:
                return enemy
        return None

    def spawn_particle_burst(self, x, y, color, count=12):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1.0, 3.8)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 1.0
            self.particles.append(Particle(x, y, vx, vy, color, random.randint(14, 26)))

    def update_entities(self, player):
        self.active_player_ref = player
        had_boss = self.get_active_boss() is not None

        for enemy in self.enemies:
            if enemy.alive:
                enemy.update(self)
        self.enemies = [e for e in self.enemies if e.alive]

        # Trigger victory banner when boss is defeated
        if had_boss and self.get_active_boss() is None:
            self.boss_defeated_banner_timer = 240

        if self.boss_defeated_banner_timer > 0:
            self.boss_defeated_banner_timer -= 1

        for wave in self.boss_projectiles:
            wave.update(self)
        self.boss_projectiles = [w for w in self.boss_projectiles if w.alive]

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.age < p.lifetime]

    def paint_tile_at_world_pos(self, world_x, world_y, new_char):
        col = int(world_x // TILE_SIZE)
        row = int(world_y // TILE_SIZE)
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if self.grid[row][col] in self.door_configs:
                return  # Do not accidentally overwrite room doorways
            if self.grid[row][col] != new_char:
                self.grid[row][col] = new_char
                self.rebuild_geometry(respawn_enemies=True)

    def export_ascii_to_console(self):
        """Prints copy-pasteable level Python directly to the terminal!"""
        print("\n" + "=" * 68)
        print(f"EXPORTED ASCII LEVEL FOR ROOM: '{self.room_id}' ({self.title})")
        print("Copy and paste this list into WORLD_BLUEPRINTS in froggy_engine.py:")
        print("=" * 68)
        print('"ascii_grid": [')
        for row_chars in self.grid:
            line_str = "".join(row_chars)
            print(f'    "{line_str}",')
        print("],")
        print("=" * 68 + "\n")

    def get_grapple_node_at(self, x, y):
        for node in self.grapple_nodes:
            if node.inflate(8, 8).collidepoint(x, y):
                return node
        return None

    def get_enemy_at_point(self, x, y):
        for enemy in self.enemies:
            if enemy.alive and enemy.rect.inflate(8, 8).collidepoint(x, y):
                return enemy
        return None

    def is_point_inside_solid(self, x, y):
        for tile in self.solid_tiles:
            if tile.collidepoint(x, y):
                return True
        return False

    def rect_collides_with_solid(self, rect):
        for tile in self.solid_tiles:
            if rect.colliderect(tile):
                return True
        return False

    def get_touched_door(self, player_rect):
        for door in self.doors.values():
            if door.rect.colliderect(player_rect):
                return door
        return None

    def draw(self, surface, camera_x, camera_y, pulse_timer):
        # 1. Parallax Background Grid
        grid_size = 32
        parallax_x = int(camera_x * 0.5) % grid_size
        parallax_y = int(camera_y * 0.5) % grid_size
        for x in range(-parallax_x, INTERNAL_WIDTH, grid_size):
            pygame.draw.line(surface, COLOR_BG_GRID, (x, 0), (x, INTERNAL_HEIGHT))
        for y in range(-parallax_y, INTERNAL_HEIGHT, grid_size):
            pygame.draw.line(surface, COLOR_BG_GRID, (0, y), (INTERNAL_WIDTH, y))

        # 2. Solid Bricks (View frustum culling)
        brick_tex = self.tile_textures['#']
        for bx, by in self.visual_bricks:
            sx = int(bx - camera_x)
            sy = int(by - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(brick_tex, (sx, sy))

        # 3. Gold Grapple Nodes
        grapple_tex = self.tile_textures['G']
        for node in self.grapple_nodes:
            sx = int(node.x - camera_x)
            sy = int(node.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(grapple_tex, (sx, sy))

        # 4. Glowing Metroidvania Doors
        door_tex = self.tile_textures['DOOR']
        for dx, dy in self.door_tiles:
            sx = int(dx - camera_x)
            sy = int(dy - camera_y)
            surface.blit(door_tex, (sx, sy))

        glow_radius = int(2 + math.sin(pulse_timer * 0.12) * 2)
        for door in self.doors.values():
            screen_door = door.rect.move(-int(camera_x), -int(camera_y))
            pygame.draw.rect(surface, COLOR_DOOR_GLOW, screen_door.inflate(glow_radius, glow_radius), 1)

        # 5. Enemies, Boss Projectiles, and Sparks
        for enemy in self.enemies:
            if enemy.alive:
                enemy.draw(surface, camera_x, camera_y)

        for wave in self.boss_projectiles:
            wave.draw(surface, camera_x, camera_y)

        for p in self.particles:
            p.draw(surface, camera_x, camera_y)


# =============================================================================
# 7. METROIDVANIA WORLD MANAGER
# =============================================================================

class WorldManager:
    """
    Manages room switching, visited room history for the Automap, and screen fades.
    """
    def __init__(self, blueprints, tile_textures, enemy_anims, starting_room_id):
        self.rooms = {}
        for room_id, bp in blueprints.items():
            self.rooms[room_id] = TileMapRoom(room_id, bp, tile_textures, enemy_anims)
        self.current_room = self.rooms[starting_room_id]
        self.visited_rooms = {starting_room_id}
        self.transition_state = "NONE"  # "NONE", "FADING_OUT", "FADING_IN"
        self.fade_alpha = 0
        self.pending_door = None
        self.fade_surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        self.fade_surface.fill((0, 0, 0))

    @property
    def is_transitioning(self):
        return self.transition_state != "NONE"

    def trigger_door_transition(self, door_portal):
        if self.transition_state == "NONE":
            self.pending_door = door_portal
            self.transition_state = "FADING_OUT"

    def warp_directly_to_room(self, room_id, player, camera):
        """Shortcut key [B] to jump directly into the Boss Sanctum for rapid testing!"""
        if room_id in self.rooms:
            self.current_room = self.rooms[room_id]
            self.visited_rooms.add(room_id)
            self.current_room.spawn_enemies()
            spawn_x, spawn_y = self.current_room.default_spawn
            player.teleport_to_room(spawn_x, spawn_y)
            camera.set_bounds(self.current_room.world_width, self.current_room.world_height)
            camera.snap_to(player)

    def update_transition(self, player, camera):
        if self.transition_state == "FADING_OUT":
            self.fade_alpha += TRANSITION_FADE_SPEED
            if self.fade_alpha >= 255:
                self.fade_alpha = 255
                self._execute_room_swap(player, camera)
                self.transition_state = "FADING_IN"
        elif self.transition_state == "FADING_IN":
            self.fade_alpha -= TRANSITION_FADE_SPEED
            if self.fade_alpha <= 0:
                self.fade_alpha = 0
                self.transition_state = "NONE"

    def _execute_room_swap(self, player, camera):
        target_room_id = self.pending_door.target_room
        target_door_id = self.pending_door.target_door
        offset_x = self.pending_door.spawn_offset_x
        offset_y = self.pending_door.spawn_offset_y

        self.current_room = self.rooms[target_room_id]
        self.visited_rooms.add(target_room_id)
        self.current_room.spawn_enemies()

        dest_door = self.current_room.doors.get(target_door_id)
        if dest_door is not None:
            spawn_x = dest_door.rect.centerx + offset_x - (player.width * 0.5)
            spawn_y = dest_door.rect.bottom - player.height + offset_y
        else:
            spawn_x, spawn_y = self.current_room.default_spawn

        player.teleport_to_room(spawn_x, spawn_y, facing_right=(offset_x >= 0))
        camera.set_bounds(self.current_room.world_width, self.current_room.world_height)
        camera.snap_to(player)

    def draw_fade_overlay(self, surface):
        if self.fade_alpha > 0:
            self.fade_surface.set_alpha(self.fade_alpha)
            surface.blit(self.fade_surface, (0, 0))


# =============================================================================
# 8. SNES CONTROLLER ABSTRACTION LAYER
# =============================================================================

class SNESController:
    """
    Emulates a 12-button Super Nintendo Controller with edge trigger detection.
    Reads real USB/Bluetooth gamepads (DirectInput/XInput) and keyboard keys seamlessly.
    """
    def __init__(self):
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"[SNES Controller] Connected Gamepad: {self.joystick.get_name()}")
        else:
            print("[SNES Controller] No Gamepad detected. Using Keyboard SNES fallback mapping.")

        self.held = {
            "UP": False, "DOWN": False, "LEFT": False, "RIGHT": False,
            "A": False, "B": False, "X": False, "Y": False,
            "L": False, "R": False, "START": False, "SELECT": False
        }
        self.prev_held = self.held.copy()
        self.just_pressed = {k: False for k in self.held}
        self.just_released = {k: False for k in self.held}

    def update(self):
        self.prev_held = self.held.copy()
        keys = pygame.key.get_pressed()

        # Keyboard Mapping
        self.held["LEFT"] = keys[pygame.K_LEFT] or keys[pygame.K_a]
        self.held["RIGHT"] = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        self.held["UP"] = keys[pygame.K_UP] or keys[pygame.K_w]
        self.held["DOWN"] = keys[pygame.K_DOWN] or keys[pygame.K_s]

        # Both A and B trigger Jump
        self.held["A"] = keys[pygame.K_SPACE] or keys[pygame.K_k]
        self.held["B"] = keys[pygame.K_z]

        # Y triggers the 8-directional tongue whip
        self.held["Y"] = keys[pygame.K_x] or keys[pygame.K_j]

        # R triggers the special Spore Boomerang
        self.held["R"] = keys[pygame.K_c] or keys[pygame.K_u] or keys[pygame.K_LSHIFT]

        # Physical Gamepad Layer
        if self.joystick:
            if self.joystick.get_numaxes() >= 2:
                axis_x = self.joystick.get_axis(0)
                axis_y = self.joystick.get_axis(1)
                if axis_x < -0.35: self.held["LEFT"] = True
                if axis_x > 0.35: self.held["RIGHT"] = True
                if axis_y < -0.35: self.held["UP"] = True
                if axis_y > 0.35: self.held["DOWN"] = True

            if self.joystick.get_numhats() > 0:
                hat_x, hat_y = self.joystick.get_hat(0)
                if hat_x < 0: self.held["LEFT"] = True
                if hat_x > 0: self.held["RIGHT"] = True
                if hat_y > 0: self.held["UP"] = True
                if hat_y < 0: self.held["DOWN"] = True

            num_btns = self.joystick.get_numbuttons()
            if num_btns > 0 and self.joystick.get_button(0): self.held["B"] = True
            if num_btns > 1 and self.joystick.get_button(1): self.held["A"] = True
            if num_btns > 2 and self.joystick.get_button(2): self.held["Y"] = True
            if num_btns > 5 and self.joystick.get_button(5): self.held["R"] = True

        for btn in self.held:
            self.just_pressed[btn] = self.held[btn] and not self.prev_held[btn]
            self.just_released[btn] = not self.held[btn] and self.prev_held[btn]

    @property
    def jump_held(self):
        return self.held["A"] or self.held["B"]

    @property
    def jump_just_pressed(self):
        return self.just_pressed["A"] or self.just_pressed["B"]

    @property
    def jump_just_released(self):
        return (self.just_released["A"] or self.just_released["B"]) and not self.jump_held

    def get_dpad_vector(self, default_facing_right=True):
        """
        Returns ((dx, dy), (ux, uy)) where:
        - (dx, dy) are raw integer steps (-1, 0, +1).
        - (ux, uy) is a normalized unit vector ensuring diagonals don't stretch 1.414x!
        """
        dx = (1 if self.held["RIGHT"] else 0) - (1 if self.held["LEFT"] else 0)
        dy = (1 if self.held["DOWN"] else 0) - (1 if self.held["UP"] else 0)
        if dx == 0 and dy == 0:
            ux = 1.0 if default_facing_right else -1.0
            uy = 0.0
        else:
            length = math.hypot(dx, dy)
            ux = dx / length
            uy = dy / length
        return (dx, dy), (ux, uy)


# =============================================================================
# 9. FROGGY PLAYER ENTITY
# =============================================================================

class FroggyPlayer:
    """
    Main Hero Entity.
    Handles separated-axis physics, coyote time, wall slide/jump, double jump,
    Super Castlevania IV 8-directional pendulum grapple swinging, and tongue-yank combat.
    """
    def __init__(self, spawn_x, spawn_y, animations):
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.width = 14
        self.height = 15
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)

        self.vx = 0.0
        self.vy = 0.0
        self.facing_right = True

        # Health & Combat
        self.hp = PLAYER_MAX_HP
        self.invuln_timer = 0
        self.eaten_count = 0

        # Platforming trackers
        self.on_ground = False
        self.touching_wall_dir = 0
        self.coyote_timer = 0
        self.jump_buffer_timer = 0
        self.wall_jump_lock_timer = 0
        self.double_jump_available = True
        self.door_cooldown = 0

        # Tongue & Pendulum Grapple State Machine
        # States: "INACTIVE", "EXTENDING", "HOLDING", "RETRACTING", "SWINGING"
        self.tongue_state = "INACTIVE"
        self.tongue_dir_x = 1.0
        self.tongue_dir_y = 0.0
        self.tongue_length = 0.0
        self.tongue_hold_timer = 0
        self.grapple_anchor = pygame.Vector2(0, 0)
        self.yanked_enemy = None  # Reference to enemy locked to tongue tip

        self.swing_angle = 0.0
        self.swing_angular_vel = 0.0
        self.swing_rope_length = 60.0

        self.projectiles = []
        self.animations = animations
        self.anim_state = "idle"
        self.anim_timer = 0

    @property
    def center_x(self):
        return self.x + self.width * 0.5

    @property
    def center_y(self):
        return self.y + self.height * 0.5

    def teleport_to_room(self, spawn_x, spawn_y, facing_right=True):
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.rect.topleft = (int(self.x), int(self.y))
        self.vx = 0.0
        self.vy = 0.0
        self.facing_right = facing_right
        self.tongue_state = "INACTIVE"
        self.tongue_length = 0.0
        self.yanked_enemy = None
        self.projectiles.clear()
        self.double_jump_available = True
        self.door_cooldown = DOOR_COOLDOWN_FRAMES

    def update(self, controller, room, world_manager):
        if self.door_cooldown > 0:
            self.door_cooldown -= 1
        if self.invuln_timer > 0:
            self.invuln_timer -= 1

        # 1. Update R-Button Spore Boomerangs
        if controller.just_pressed["R"] and len(self.projectiles) < 2:
            _, (ux, uy) = controller.get_dpad_vector(self.facing_right)
            self.projectiles.append(SporeBoomerang(self.center_x, self.center_y, ux, uy))

        for proj in self.projectiles:
            proj.update(room)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # 2. Movement & Tongue Updates
        if self.tongue_state == "SWINGING":
            self._update_pendulum_swing(controller, room)
        else:
            self._update_tongue_strike_and_yank(controller, room)
            self._update_standard_physics(controller, room)

        # 3. Body Collisions against Enemies and Boss Projectiles
        self._check_damage_collisions(room)
        self._update_animation_state()

        # 4. Check Metroidvania Door Portals
        if self.door_cooldown == 0:
            touched_door = room.get_touched_door(self.rect)
            if touched_door is not None:
                world_manager.trigger_door_transition(touched_door)

    def _update_tongue_strike_and_yank(self, controller, room):
        """
        8-Directional Tongue Strike.
        Detects Gold Grapple Blocks ('G'), regular enemies ('E', 'F'), and the Boss ('M').
        """
        if controller.just_pressed["Y"] and self.tongue_state == "INACTIVE":
            (dx, _), (ux, uy) = controller.get_dpad_vector(self.facing_right)
            if dx != 0:
                self.facing_right = (dx > 0)
            self.tongue_dir_x = ux
            self.tongue_dir_y = uy
            self.tongue_length = 4.0
            self.yanked_enemy = None
            self.tongue_state = "EXTENDING"

        if self.tongue_state == "EXTENDING":
            self.tongue_length += TONGUE_EXTEND_SPEED
            tip_x = self.center_x + self.tongue_dir_x * self.tongue_length
            tip_y = self.center_y + self.tongue_dir_y * self.tongue_length

            # --- Target 1: Emperor Mantis Boss Weak Point Check ---
            boss = room.get_active_boss()
            if boss and boss.alive and boss.rect.inflate(8, 8).collidepoint(tip_x, tip_y):
                if boss.state == "WEAK_EXPOSED":
                    # Success! Rip out the boss's energy pearl!
                    pearl = boss.yank_exposed_weak_point(room)
                    self.yanked_enemy = pearl
                    self.tongue_state = "RETRACTING"
                    return
                else:
                    # Armor deflects tongue with metallic sparks!
                    room.spawn_particle_burst(tip_x, tip_y, (220, 220, 240), count=8)
                    self.tongue_state = "HOLDING"
                    self.tongue_hold_timer = 4
                    return

            # --- Target 2: Regular Enemies ('E' Moss Beetle & 'F' Buzzfly) ---
            hit_enemy = room.get_enemy_at_point(tip_x, tip_y)
            if hit_enemy is not None:
                if hit_enemy.can_yank_immediately or hit_enemy.state == "STUNNED":
                    hit_enemy.state = "YANKED"
                    self.yanked_enemy = hit_enemy
                    self.tongue_state = "RETRACTING"
                    room.spawn_particle_burst(tip_x, tip_y, COLOR_TONGUE_TIP, count=8)
                else:
                    # Armored Beetle in PATROL state: Stun & Flip onto back!
                    hit_enemy.stun(knockback_dir_x=self.tongue_dir_x)
                    self.tongue_state = "RETRACTING"
                    room.spawn_particle_burst(tip_x, tip_y, (255, 230, 90), count=12)
                return

            # --- Target 3: Gold Grapple Ring ('G') -> Attach & Swing! ---
            hit_anchor = room.get_grapple_node_at(tip_x, tip_y)
            if hit_anchor is not None:
                self._attach_to_grapple(hit_anchor)
                return

            # --- Target 4: Solid Wall Collision ---
            if room.is_point_inside_solid(tip_x, tip_y):
                self.tongue_state = "HOLDING"
                self.tongue_hold_timer = TONGUE_HOLD_FRAMES // 2
                return

            if self.tongue_length >= TONGUE_MAX_LENGTH:
                self.tongue_length = TONGUE_MAX_LENGTH
                self.tongue_state = "HOLDING"
                self.tongue_hold_timer = TONGUE_HOLD_FRAMES

        elif self.tongue_state == "HOLDING":
            self.tongue_hold_timer -= 1
            if self.tongue_hold_timer <= 0:
                self.tongue_state = "RETRACTING"

        elif self.tongue_state == "RETRACTING":
            self.tongue_length -= TONGUE_RETRACT_SPEED
            tip_x = self.center_x + self.tongue_dir_x * max(0.0, self.tongue_length)
            tip_y = self.center_y + self.tongue_dir_y * max(0.0, self.tongue_length)

            # Move yanked creature with the retracting tongue tip
            if self.yanked_enemy is not None and self.yanked_enemy.alive:
                self.yanked_enemy.set_center(tip_x, tip_y)

            # Swallow creature once drawn close to Froggy's mouth!
            if self.tongue_length <= 14.0:
                self._swallow_yanked_enemy(room)

            if self.tongue_length <= 0.0:
                self.tongue_length = 0.0
                self.yanked_enemy = None
                self.tongue_state = "INACTIVE"

    def _swallow_yanked_enemy(self, room):
        """
        Consumes the yanked bug/pearl, healing +1 HP, spawning green sparks,
        and resetting Froggy's mid-air double jump!
        """
        if self.yanked_enemy is not None:
            self.yanked_enemy.alive = False
            self.yanked_enemy = None
            self.eaten_count += 1
            self.hp = min(PLAYER_MAX_HP, self.hp + 1)
            self.double_jump_available = True
            # Subtle upward hop boost if swallowing in mid-air
            if not self.on_ground and self.vy > -2.5:
                self.vy = -3.6
            room.spawn_particle_burst(self.center_x, self.center_y, (130, 255, 120), count=16)

    def _check_damage_collisions(self, room):
        """Checks if Froggy bumped into active enemies or scythe waves."""
        if self.invuln_timer > 0:
            return

        # Regular patrolling enemies
        for enemy in room.enemies:
            if enemy.alive and enemy.state == "PATROL" and self.rect.colliderect(enemy.rect):
                self._take_damage(push_from_x=enemy.center_x, room=room)
                return

        # Emperor Mantis Boss body
        boss = room.get_active_boss()
        if boss and boss.alive and boss.state != "WEAK_EXPOSED" and self.rect.colliderect(boss.rect):
            self._take_damage(push_from_x=boss.center_x, room=room)
            return

        # Boss Scythe Waves
        for wave in room.boss_projectiles:
            if wave.alive and self.rect.colliderect(wave.rect):
                wave.alive = False
                self._take_damage(push_from_x=wave.x, room=room)
                return

    def _take_damage(self, push_from_x, room):
        self.hp = max(1, self.hp - 1)
        self.invuln_timer = PLAYER_INVULN_FRAMES
        push_dir = -1.0 if self.center_x < push_from_x else 1.0
        self.vx = push_dir * 3.8
        self.vy = -4.8
        self.wall_jump_lock_timer = 10
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_HEART_RED, count=12)

    def _attach_to_grapple(self, anchor_rect):
        """Converts linear momentum into angular pendulum velocity."""
        self.grapple_anchor = pygame.Vector2(anchor_rect.centerx, anchor_rect.centery)
        rel_x = self.center_x - self.grapple_anchor.x
        rel_y = self.center_y - self.grapple_anchor.y
        self.swing_rope_length = max(SWING_MIN_LENGTH, math.hypot(rel_x, rel_y))
        self.swing_angle = math.atan2(rel_x, rel_y)

        # Dot product with tangent vector
        tangent_x = math.cos(self.swing_angle)
        tangent_y = -math.sin(self.swing_angle)
        tangential_speed = self.vx * tangent_x + self.vy * tangent_y
        self.swing_angular_vel = tangential_speed / self.swing_rope_length

        self.double_jump_available = True
        self.on_ground = False
        self.tongue_state = "SWINGING"

    def _update_pendulum_swing(self, controller, room):
        (dx, dy), _ = controller.get_dpad_vector(self.facing_right)

        # Reel rope in or out with Up/Down
        if dy != 0:
            self.swing_rope_length += dy * SWING_REEL_SPEED
            self.swing_rope_length = max(SWING_MIN_LENGTH, min(TONGUE_MAX_LENGTH, self.swing_rope_length))

        # Angular acceleration: alpha = -(g/L)*sin(theta) + player_pump
        gravity_torque = -SWING_GRAVITY * math.sin(self.swing_angle)
        player_pump = dx * SWING_PUMP_FORCE
        self.swing_angular_vel += (gravity_torque + player_pump)
        self.swing_angular_vel *= SWING_DAMPING

        next_angle = self.swing_angle + self.swing_angular_vel
        target_cx = self.grapple_anchor.x + math.sin(next_angle) * self.swing_rope_length
        target_cy = self.grapple_anchor.y + math.cos(next_angle) * self.swing_rope_length

        test_rect = pygame.Rect(
            int(target_cx - self.width * 0.5),
            int(target_cy - self.height * 0.5),
            self.width, self.height
        )

        if room.rect_collides_with_solid(test_rect):
            self.swing_angular_vel *= -0.35
        else:
            self.swing_angle = next_angle
            self.x = target_cx - self.width * 0.5
            self.y = target_cy - self.height * 0.5
            self.rect.topleft = (int(self.x), int(self.y))

        # Convert angular velocity back to Cartesian velocity for smooth release launch
        tangent_x = math.cos(self.swing_angle)
        tangent_y = -math.sin(self.swing_angle)
        linear_speed = self.swing_angular_vel * self.swing_rope_length
        self.vx = linear_speed * tangent_x
        self.vy = linear_speed * tangent_y

        if dx != 0:
            self.facing_right = (dx > 0)

        # Detach: Jump (A/B) for boosted release, or Y to let go
        if controller.jump_just_pressed:
            self.tongue_state = "RETRACTING"
            self.tongue_length = self.swing_rope_length
            self.vy = min(self.vy - 3.2, JUMP_VELOCITY * 0.85)
            self.vx *= 1.15
        elif controller.just_pressed["Y"]:
            self.tongue_state = "RETRACTING"
            self.tongue_length = self.swing_rope_length

    def _update_standard_physics(self, controller, room):
        (dx, _), _ = controller.get_dpad_vector(self.facing_right)

        if self.coyote_timer > 0: self.coyote_timer -= 1
        if self.jump_buffer_timer > 0: self.jump_buffer_timer -= 1
        if self.wall_jump_lock_timer > 0: self.wall_jump_lock_timer -= 1

        if controller.jump_just_pressed:
            self.jump_buffer_timer = JUMP_BUFFER_FRAMES

        # Horizontal Acceleration & Drag
        if self.wall_jump_lock_timer == 0:
            if dx != 0:
                accel = MOVE_ACCEL if self.on_ground else AIR_ACCEL
                self.vx += dx * accel
                self.vx = max(-MAX_RUN_SPEED, min(MAX_RUN_SPEED, self.vx))
                if self.tongue_state == "INACTIVE":
                    self.facing_right = (dx > 0)
            else:
                friction = GROUND_FRICTION if self.on_ground else AIR_DRAG
                self.vx *= friction
                if abs(self.vx) < 0.08:
                    self.vx = 0.0

        # Gravity & Wall Slide
        self.vy += GRAVITY
        is_wall_sliding = (
            not self.on_ground and
            self.touching_wall_dir != 0 and
            dx == self.touching_wall_dir and
            self.vy > 0
        )
        if is_wall_sliding:
            self.vy = min(self.vy, WALL_SLIDE_SPEED)
        else:
            self.vy = min(self.vy, MAX_FALL_SPEED)

        # Jump Execution: Ground/Coyote -> Wall Jump -> Double Jump
        if self.jump_buffer_timer > 0:
            if self.coyote_timer > 0:
                self.vy = JUMP_VELOCITY
                self.on_ground = False
                self.coyote_timer = 0
                self.jump_buffer_timer = 0
            elif self.touching_wall_dir != 0:
                self.vx = -self.touching_wall_dir * WALL_JUMP_X_SPEED
                self.vy = WALL_JUMP_Y_SPEED
                self.facing_right = (self.vx > 0)
                self.wall_jump_lock_timer = WALL_JUMP_LOCK_FRAMES
                self.jump_buffer_timer = 0
                self.double_jump_available = True
            elif self.double_jump_available:
                self.vy = DOUBLE_JUMP_VELOCITY
                self.double_jump_available = False
                self.jump_buffer_timer = 0
                if dx != 0:
                    self.vx = dx * MAX_RUN_SPEED * 0.9

        # Variable jump height cut
        if controller.jump_just_released and self.vy < 0:
            self.vy *= VARIABLE_JUMP_CUTOFF

        self._move_and_collide(room)

    def _move_and_collide(self, room):
        """Separated-Axis AABB Movement and Collision Detection."""
        # 1. Horizontal Axis
        self.x += self.vx
        self.rect.x = int(round(self.x))
        self.touching_wall_dir = 0
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                    self.touching_wall_dir = 1
                elif self.vx < 0:
                    self.rect.left = tile.right
                    self.touching_wall_dir = -1
                self.x = float(self.rect.x)
                self.vx = 0.0

        if self.touching_wall_dir == 0 and not self.on_ground:
            if room.rect_collides_with_solid(self.rect.move(-1, 0)):
                self.touching_wall_dir = -1
            elif room.rect_collides_with_solid(self.rect.move(1, 0)):
                self.touching_wall_dir = 1

        # 2. Vertical Axis
        self.y += self.vy
        self.rect.y = int(round(self.y))
        self.on_ground = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vy > 0:
                    self.rect.bottom = tile.top
                    self.on_ground = True
                    self.coyote_timer = COYOTE_TIME_FRAMES
                    self.double_jump_available = True
                elif self.vy < 0:
                    self.rect.top = tile.bottom
                self.y = float(self.rect.y)
                self.vy = 0.0

    def _update_animation_state(self):
        self.anim_timer += 1
        if self.tongue_state != "INACTIVE":
            self.anim_state = "tongue"
        elif not self.on_ground:
            if self.touching_wall_dir != 0 and self.vy > 0:
                self.anim_state = "wall_slide"
            else:
                self.anim_state = "jump"
        elif abs(self.vx) > 0.25:
            self.anim_state = "run"
        else:
            self.anim_state = "idle"

    def draw(self, surface, camera_x, camera_y):
        for proj in self.projectiles:
            proj.draw(surface, camera_x, camera_y)

        # Draw Stretchy Tongue Shaft & Sticky Tip
        if self.tongue_state != "INACTIVE":
            start_pos = (int(self.center_x - camera_x), int(self.center_y - camera_y))
            if self.tongue_state == "SWINGING":
                end_pos = (
                    int(self.grapple_anchor.x - camera_x),
                    int(self.grapple_anchor.y - camera_y)
                )
            else:
                tip_x = self.center_x + self.tongue_dir_x * self.tongue_length
                tip_y = self.center_y + self.tongue_dir_y * self.tongue_length
                end_pos = (int(tip_x - camera_x), int(tip_y - camera_y))

            pygame.draw.line(surface, COLOR_TONGUE_PINK, start_pos, end_pos, 3)
            pygame.draw.circle(surface, COLOR_TONGUE_TIP, end_pos, 4)

        # Invulnerability flicker after taking damage
        if self.invuln_timer > 0 and (self.invuln_timer // 3) % 2 == 1:
            return

        facing_key = "right" if self.facing_right else "left"
        frames = self.animations[facing_key][self.anim_state]
        frame_index = (self.anim_timer // 8) % len(frames)
        sprite = frames[frame_index]
        draw_x = int(self.rect.x - 1 - camera_x)
        draw_y = int(self.rect.y - 1 - camera_y)
        surface.blit(sprite, (draw_x, draw_y))


# =============================================================================
# 10. CAMERA, HUD, MINIMAP & BOSS HEALTH BAR
# =============================================================================

class Camera:
    """
    Smoothly tracks Froggy with horizontal look-ahead and clamps to room bounds.
    """
    def __init__(self, world_width, world_height):
        self.x = 0.0
        self.y = 0.0
        self.set_bounds(world_width, world_height)

    def set_bounds(self, world_width, world_height):
        self.world_width = world_width
        self.world_height = world_height

    def snap_to(self, player):
        self.x = player.center_x - (INTERNAL_WIDTH * 0.5)
        self.y = player.center_y - (INTERNAL_HEIGHT * 0.55)
        self._clamp()

    def update(self, player):
        look_ahead = 28.0 if player.facing_right else -28.0
        target_x = player.center_x + look_ahead - (INTERNAL_WIDTH * 0.5)
        target_y = player.center_y - (INTERNAL_HEIGHT * 0.55)
        self.x += (target_x - self.x) * 0.12
        self.y += (target_y - self.y) * 0.12
        self._clamp()

    def _clamp(self):
        max_x = max(0.0, float(self.world_width - INTERNAL_WIDTH))
        max_y = max(0.0, float(self.world_height - INTERNAL_HEIGHT))
        self.x = max(0.0, min(max_x, self.x))
        self.y = max(0.0, min(max_y, self.y))


def draw_hud_and_minimap(surface, font, player, world_manager, camera, mouse_world_pos, controller):
    """
    Renders top-left health bar, mouse level builder highlight cursor,
    aim compass, Super Metroid style Automap, and Boss Health Bar.
    """
    # 1. Mouse Tile-Builder Cursor Highlight Box (Cleanly snapped to 16x16 grid)
    mx_world, my_world = mouse_world_pos
    col = int(mx_world // TILE_SIZE)
    row = int(my_world // TILE_SIZE)
    cursor_sx = int(col * TILE_SIZE - camera.x)
    cursor_sy = int(row * TILE_SIZE - camera.y)
    pygame.draw.rect(surface, (255, 230, 90), (cursor_sx, cursor_sy, TILE_SIZE, TILE_SIZE), 1)

    # 2. 5-Heart SNES Health Bar
    for i in range(PLAYER_MAX_HP):
        hx = 8 + i * 13
        hy = 6
        color = COLOR_HEART_RED if i < player.hp else COLOR_HEART_EMPTY
        pygame.draw.rect(surface, color, (hx, hy, 10, 8), border_radius=2)
        pygame.draw.rect(surface, (255, 255, 255), (hx, hy, 10, 8), 1, border_radius=2)

    score_img = font.render(
        f"EATEN: {player.eaten_count} | {world_manager.current_room.title}",
        True, COLOR_HUD_TEXT
    )
    surface.blit(score_img, (78, 5))

    help_img = font.render(
        "PAINT: [Click] '#' | [G+Click] Ring | [E+Click] Beetle | [F+Click] Fly | [M+Click] Boss | [R-Click] Erase",
        True, (190, 215, 255)
    )
    surface.blit(help_img, (8, 18))

    # 3. Top-Right Super Metroid Style Automap
    map_origin_x = INTERNAL_WIDTH - 110
    map_origin_y = 6
    cell_w, cell_h = 22, 12

    for room_id, room in world_manager.rooms.items():
        gx, gy = room.map_coords
        cell_rect = pygame.Rect(
            map_origin_x + gx * (cell_w + 3),
            map_origin_y + gy * (cell_h + 3),
            cell_w, cell_h
        )

        if room is world_manager.current_room:
            # Active Room glows cyan with pulsing gold player dot
            pygame.draw.rect(surface, (45, 165, 220), cell_rect)
            pygame.draw.rect(surface, (255, 255, 255), cell_rect, 1)

            px_ratio = player.center_x / max(1, room.world_width)
            py_ratio = player.center_y / max(1, room.world_height)
            dot_x = cell_rect.x + int(px_ratio * (cell_w - 4)) + 2
            dot_y = cell_rect.y + int(py_ratio * (cell_h - 4)) + 2
            pygame.draw.circle(surface, (255, 230, 80), (dot_x, dot_y), 2)
        elif room_id in world_manager.visited_rooms:
            # Explored Room
            fill_col = (110, 35, 60) if room_id == "boss_sanctum" else (45, 65, 110)
            pygame.draw.rect(surface, fill_col, cell_rect)
            pygame.draw.rect(surface, (120, 150, 200), cell_rect, 1)
        else:
            # Unexplored Room Outline
            pygame.draw.rect(surface, (35, 42, 65), cell_rect, 1)

    # 4. Live 8-Way Aim Compass (Top-Right, next to Minimap)
    _, (ux, uy) = controller.get_dpad_vector(player.facing_right)
    compass_center = (map_origin_x - 16, 12)
    pygame.draw.circle(surface, (45, 55, 85), compass_center, 10)
    pygame.draw.circle(surface, (120, 150, 200), compass_center, 10, 1)
    aim_end = (int(compass_center[0] + ux * 8), int(compass_center[1] + uy * 8))
    pygame.draw.line(surface, COLOR_TONGUE_PINK, compass_center, aim_end, 2)
    pygame.draw.circle(surface, COLOR_BOSS_GOLD, aim_end, 2)

    # 5. Dedicated Boss Health Bar along bottom of screen (Active in Boss Sanctum)
    active_boss = world_manager.current_room.get_active_boss()
    if active_boss is not None and active_boss.alive:
        bar_w = 200
        bar_h = 10
        bar_x = (INTERNAL_WIDTH - bar_w) // 2
        bar_y = INTERNAL_HEIGHT - 18

        # Background frame
        pygame.draw.rect(surface, (20, 15, 30), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=3)
        pygame.draw.rect(surface, (255, 215, 70), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), 1, border_radius=3)

        # Health fill
        hp_ratio = active_boss.hp / active_boss.max_hp
        fill_w = int(bar_w * hp_ratio)
        bar_col = (255, 60, 90) if active_boss.phase == 3 else ((255, 140, 50) if active_boss.phase == 2 else (80, 220, 120))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_col, (bar_x, bar_y, fill_w, bar_h), border_radius=2)

        # Boss Name Label
        boss_label = font.render(
            f"EMPEROR MANTIS  [PHASE {active_boss.phase}]",
            True, COLOR_HUD_TEXT
        )
        surface.blit(boss_label, (bar_x + 30, bar_y - 12))

    # 6. Boss Defeated Victory Banner
    if world_manager.current_room.boss_defeated_banner_timer > 0:
        banner_surf = font.render("VICTORY! EMPEROR MANTIS DEFEATED!", True, COLOR_BOSS_GOLD)
        bx = (INTERNAL_WIDTH - banner_surf.get_width()) // 2
        by = (INTERNAL_HEIGHT // 2) - 20
        pygame.draw.rect(surface, (20, 20, 40), (bx - 8, by - 4, banner_surf.get_width() + 16, 20), border_radius=4)
        pygame.draw.rect(surface, COLOR_BOSS_GOLD, (bx - 8, by - 4, banner_surf.get_width() + 16, 20), 1, border_radius=4)
        surface.blit(banner_surf, (bx, by))


# =============================================================================
# 11. MAIN ENGINE LOOP
# =============================================================================

def main():
    pygame.init()
    pygame.display.set_caption("FROGGY - 16-Bit Metroidvania (SNES Physics, 8-Way Tongue & Multi-Phase Boss)")

    window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    snes_canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    clock = pygame.time.Clock()
    hud_font = pygame.font.SysFont("monospace", 9, bold=True)

    # Build procedural pixel art and animation assets
    controller = SNESController()
    animations = SpriteSheetGenerator.build_froggy_animations()
    tile_textures = SpriteSheetGenerator.build_tile_textures()
    enemy_anims = SpriteSheetGenerator.build_enemy_animations()

    # Build the Metroidvania World graph from ASCII blueprints
    world = WorldManager(WORLD_BLUEPRINTS, tile_textures, enemy_anims, starting_room_id="entrance_hall")
    spawn_x, spawn_y = world.current_room.default_spawn
    player = FroggyPlayer(spawn_x, spawn_y, animations)
    camera = Camera(world.current_room.world_width, world.current_room.world_height)
    camera.snap_to(player)

    show_hud = True
    pulse_timer = 0
    running = True

    while running:
        pulse_timer += 1

        # 1. Handle OS and Level-Editor Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_TAB:
                    show_hud = not show_hud
                elif event.key == pygame.K_p:
                    world.current_room.export_ascii_to_console()
                elif event.key == pygame.K_b:
                    world.warp_directly_to_room("boss_sanctum", player, camera)

        # 2. Live Mouse Level Builder (Window Mouse -> Canvas Pixel -> World Coordinate)
        mouse_win_x, mouse_win_y = pygame.mouse.get_pos()
        canvas_mx = mouse_win_x / WINDOW_SCALE
        canvas_my = mouse_win_y / WINDOW_SCALE
        world_mx = canvas_mx + camera.x
        world_my = canvas_my + camera.y

        mouse_buttons = pygame.mouse.get_pressed()
        keys = pygame.key.get_pressed()
        if mouse_buttons[0]:  # Left Click
            if keys[pygame.K_g]:
                brush_char = 'G'
            elif keys[pygame.K_e]:
                brush_char = 'E'
            elif keys[pygame.K_f]:
                brush_char = 'F'
            elif keys[pygame.K_m]:
                brush_char = 'M'
            else:
                brush_char = '#'
            world.current_room.paint_tile_at_world_pos(world_mx, world_my, brush_char)
        elif mouse_buttons[2]:  # Right Click (Erase to air)
            world.current_room.paint_tile_at_world_pos(world_mx, world_my, '.')

        # 3. Poll SNES Hardware Inputs & Step Game Simulation
        controller.update()

        if world.is_transitioning:
            world.update_transition(player, camera)
        else:
            world.current_room.update_entities(player)
            player.update(controller, world.current_room, world)
            camera.update(player)

        # 4. Render Game World to Internal Retro Canvas
        snes_canvas.fill(world.current_room.bg_color)
        world.current_room.draw(snes_canvas, camera.x, camera.y, pulse_timer)
        player.draw(snes_canvas, camera.x, camera.y)

        if show_hud:
            draw_hud_and_minimap(
                snes_canvas, hud_font, player, world, camera,
                (world_mx, world_my), controller
            )

        world.draw_fade_overlay(snes_canvas)

        # 5. Upscale SNES Retro Canvas to Monitor Window and Flip
        pygame.transform.scale(snes_canvas, (WINDOW_WIDTH, WINDOW_HEIGHT), window)
        pygame.display.flip()
        clock.tick(TARGET_FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
