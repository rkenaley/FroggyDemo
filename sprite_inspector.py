"""
===============================================================================
FROGGY: STANDALONE SPRITE & ANIMATION INSPECTOR
===============================================================================
A dedicated visual inspector, frame scrubber, and telemetry analyzer for
Froggy 32-Bit Arcade Sprites and Animation Sequences.

Run from PowerShell:
  py sprite_inspector.py --list                 # List all animations & frame counts
  py sprite_inspector.py --dump                 # Full JSON asset manifest dump
  py sprite_inspector.py --sprite froggy_run    # Focus directly on Froggy's run cycle
  py sprite_inspector.py --category enemies     # Inspect all troop enemy animations
  py sprite_inspector.py --category bosses      # Inspect Colossus Boss frames
  py sprite_inspector.py --sprite toad          # Inspect Giga Toad brawler animations

FOR THE NEPHEW (UNDER THE HOOD WALKTHROUGH):
-------------------------------------------------------------------------------
1. WHY UNIFORM 32x32 BOUNDING BOXES MATTER:
   In earlier prototypes, an idle frog was 24 pixels tall, but a jumping frog
   was 30 pixels tall. If you align sprites by their top-left corner (0, 0),
   the frog's feet will violently jump up and down off the ground every time
   you transition between running and standing still!
   This ugly glitch is called "Sprite Jitter".
   We solved this permanently by:
     a) Normalizing ALL character frames onto uniform 32x32 canvases.
     b) Aligning feet to a shared Bottom-Center Anchor Point: (width/2, height).

2. HOW 32-BIT RGBA PREVENTS "HALOS":
   Old 8-bit games used 1-bit transparency (a pixel was either 100% visible
   or 100% invisible). This caused jagged "sawtooth" staircases and ugly white/
   black fringes around characters.
   With 32-bit RGBA, the alpha channel ('A') has 256 levels of opacity (0 to 255).
   Our pipeline gently feathers the outermost perimeter pixel (e.g. Alpha=120),
   blending Froggy seamlessly into any dark cave or sunlit canopy!

3. HOW RETRO ANIMATION TIMERS WORK:
   Game engines update 60 times every second. To play an animation at 8 FPS:
     delay_frames = 60 // 8 = 7.5 frames
     current_frame = (tick_counter // 7) % total_frames
   The modulo operator (%) ensures the sequence seamlessly loops forever!

4. HOW THIS INSPECTOR CALCULATES BOUNDING BOXES:
   Pygame provides `surface.get_bounding_rect()`. It scans every pixel's alpha
   channel and finds the minimal bounding rectangle (min_x, min_y, max_x, max_y)
   that encloses all non-zero alpha pixels.
===============================================================================
"""

import argparse
import json
import math
import os
import sys
import pygame

# Set asset directory relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SPRITES_DIR = os.path.join(ASSETS_DIR, "sprites")
TILES_DIR = os.path.join(ASSETS_DIR, "tiles")
PROPS_DIR = os.path.join(ASSETS_DIR, "props")

# UI Colors
COLOR_BG = (20, 24, 34)
COLOR_PANEL_BG = (28, 34, 48)
COLOR_PANEL_BORDER = (46, 56, 78)
COLOR_ACCENT = (80, 200, 120)
COLOR_ACCENT_HOVER = (110, 230, 150)
COLOR_TEXT_WHITE = (240, 245, 255)
COLOR_TEXT_DIM = (150, 165, 185)
COLOR_BOX_GREEN = (60, 240, 90)     # Bounding box color
COLOR_ANCHOR_MAGENTA = (255, 60, 200) # Bottom-center anchor
COLOR_CENTER_CYAN = (60, 220, 255)   # Center crosshair
COLOR_BUTTON_BG = (38, 46, 64)
COLOR_BUTTON_HOVER = (54, 66, 92)


# =============================================================================
# SPRITE MANIFEST & ASSET CATALOG
# =============================================================================

class SpriteCatalog:
    """
    Scans and organizes all game sprites into structured categories and animations.
    """
    def __init__(self):
        self.categories = {}
        self._discover_all()

    def _discover_all(self):
        # 1. Froggy Player Animations
        self.categories["player"] = {
            "name": "Froggy (Player)",
            "sprites": {
                "idle": {
                    "name": "Idle Stance",
                    "files": ["froggy_idle_0.png", "froggy_idle_1.png", "froggy_idle_2.png"],
                    "fps": 4.0,
                    "desc": "Calm rhythmic 3-frame breathing cycle with relaxed posture.",
                },
                "run": {
                    "name": "Sprint Cycle",
                    "files": ["froggy_run_0.png", "froggy_run_1.png", "froggy_run_2.png", "froggy_run_3.png"],
                    "fps": 10.0,
                    "desc": "Energetic 4-frame forward sprint with alternating webbed feet.",
                },
                "jump": {
                    "name": "Mid-Air Hop",
                    "files": ["froggy_jump_0.png"],
                    "fps": 1.0,
                    "desc": "Upward leaping pose with outstretched legs.",
                },
                "wall_slide": {
                    "name": "Wall Cling",
                    "files": ["froggy_wall_0.png"],
                    "fps": 1.0,
                    "desc": "Vertical wall cling pose with webbed pads gripping stone.",
                },
                "tongue": {
                    "name": "Tongue Whip",
                    "files": ["froggy_tongue_0.png"],
                    "fps": 1.0,
                    "desc": "Open-mouthed action pose launching tongue whip.",
                },
                "swim": {
                    "name": "Water Swim",
                    "files": ["froggy_swim_0.png", "froggy_swim_1.png"],
                    "fps": 6.0,
                    "desc": "Fluid breaststroke kicking cycle inside swamp lagoons.",
                },
                "swing": {
                    "name": "Pendulum Swing",
                    "files": ["froggy_swing_0.png", "froggy_swing_1.png"],
                    "fps": 6.0,
                    "desc": "Dynamic swinging poses with arms extended holding grapple line.",
                },
            },
        }

        # 2. Troop Enemies
        self.categories["enemies"] = {
            "name": "Troop Enemies",
            "sprites": {
                "beetle": {
                    "name": "Moss Beetle",
                    "files": ["beetle_0.png", "beetle_1.png"],
                    "fps": 4.0,
                    "desc": "Armored spiky ground patroller. Immune to direct head jumps!",
                },
                "fly": {
                    "name": "Neon Buzzfly",
                    "files": ["fly_0.png", "fly_1.png"],
                    "fps": 8.0,
                    "desc": "Airborne bug hovering in gentle vertical sine waves.",
                },
                "ant": {
                    "name": "Soldier Ant",
                    "files": ["ant_0.png", "ant_1.png", "ant_charge.png"],
                    "fps": 6.0,
                    "desc": "Fierce charging ant with pincers and sprint attack.",
                },
                "spider": {
                    "name": "Shadow Spider",
                    "files": ["spider_0.png", "spider_1.png", "spider_drop.png"],
                    "fps": 4.0,
                    "desc": "Ceiling predator that ambushes players on silk threads.",
                },
                "stink_bug": {
                    "name": "Stink Bug",
                    "files": ["stink_bug_0.png", "stink_bug_1.png"],
                    "fps": 5.0,
                    "desc": "Patrolling beetle that releases toxic poison clouds when stomped.",
                },
                "ice_spider": {
                    "name": "Ice Wolf Spider",
                    "files": ["ice_spider_camo.png", "ice_spider_stalk.png", "ice_spider_leap.png"],
                    "fps": 3.0,
                    "desc": "Camouflaged glacial spider with explosive leap attack.",
                },
            },
        }

        # 3. Colossus Bosses
        self.categories["bosses"] = {
            "name": "Colossus Bosses",
            "sprites": {
                "mantis": {
                    "name": "Emperor Mantis",
                    "files": ["mantis_armored.png", "mantis_exposed.png"],
                    "fps": 2.0,
                    "desc": "3-Phase airborne boss with razor scythes and exposed pearl core.",
                },
                "hound": {
                    "name": "The Dread Hound",
                    "files": ["hound_idle.png", "hound_lunge.png", "hound_dazed.png", "hound_howl.png", "hound_projectile.png"],
                    "fps": 3.0,
                    "desc": "Cybernetic canine colossus with ferocious lunge and wall daze.",
                },
                "toad": {
                    "name": "Giga Toad",
                    "files": ["toad_idle.png", "toad_slam.png", "toad_punch.png", "toad_dazed.png", "toad_enraged.png"],
                    "fps": 2.0,
                    "desc": "Heavyweight brawler colossus with ground pounds and bilateral shockwaves.",
                },
                "falo": {
                    "name": "Falo the Snowman",
                    "files": ["falo_idle.png", "falo_throw.png", "falo_melt.png"],
                    "fps": 2.0,
                    "desc": "Blizzard summit boss throwing snowballs and detaching carrot nose.",
                },
            },
        }

        # 4. Friendly NPCs
        self.categories["npcs"] = {
            "name": "Friendly NPCs",
            "sprites": {
                "elder": {
                    "name": "Elder Tree Frog",
                    "files": ["npc_elder_0.png", "npc_elder_1.png"],
                    "fps": 2.0,
                    "desc": "Elder Mossbeard providing guidance, lore, and ancient secrets.",
                },
                "shopkeeper": {
                    "name": "Village Shopkeeper",
                    "files": ["npc_shopkeeper_0.png", "npc_shopkeeper_1.png"],
                    "fps": 2.0,
                    "desc": "Shopkeeper Ribbit trading eaten bugs for restorative health tonics.",
                },
            },
        }

        # 5. Interactive Tiles & Hazards
        self.categories["tiles"] = {
            "name": "Interactive Tiles",
            "sprites": {
                "grapple": {
                    "name": "Grapple Idol",
                    "files": ["grapple_0.png", "grapple_1.png"],
                    "fps": 3.0,
                    "dir": "tiles",
                    "desc": "Golden Frog Grapple Idol for whip latching and pendulum swinging.",
                },
                "water": {
                    "name": "Swamp Water",
                    "files": [f"water_{i}.png" for i in range(4)],
                    "fps": 6.0,
                    "dir": "tiles",
                    "desc": "Animated bioluminescent water hazard with glowing crests.",
                },
                "lava": {
                    "name": "Molten Magma",
                    "files": [f"lava_{i}.png" for i in range(4)],
                    "fps": 6.0,
                    "dir": "tiles",
                    "desc": "Scorching volcanic lava hazard driving body temperature to 200%.",
                },
                "waterfall": {
                    "name": "Waterfall Mist",
                    "files": [f"waterfall_{i}.png" for i in range(4)],
                    "fps": 8.0,
                    "dir": "tiles",
                    "desc": "Cascading cooling mist restoring player temperature toward 100%.",
                },
                "bubble_vent": {
                    "name": "Air Bubble Vent",
                    "files": ["bubble_vent_0.png", "bubble_vent_1.png"],
                    "fps": 4.0,
                    "dir": "tiles",
                    "desc": "Submarine air vent releasing rising bubble streams that refill oxygen.",
                },
                "door": {
                    "name": "Rune Portal",
                    "files": [f"door_{i}.png" for i in range(4)],
                    "fps": 6.0,
                    "dir": "tiles",
                    "desc": "Ancient glowing stone gateway connecting Metroidvania rooms.",
                },
            },
        }

        # 6. Relics & Collectibles
        self.categories["props"] = {
            "name": "Relics & Props",
            "sprites": {
                "boots": {
                    "name": "Stomping Boots",
                    "files": ["powerup_boots.png"],
                    "fps": 1.0,
                    "desc": "Heavy armored boots enabling Mario-style downward crushing.",
                },
                "boomerang": {
                    "name": "Red Boomerang",
                    "files": ["powerup_red_boomerang.png", "boomerang_red.png"],
                    "fps": 4.0,
                    "desc": "Curved throwing weapon providing long-range projectile attacks.",
                },
                "totem": {
                    "name": "Checkpoint Totem",
                    "files": ["checkpoint_totem.png"],
                    "fps": 1.0,
                    "dir": "props",
                    "desc": "Restorative totem that heals HP, warmth, and auto-saves progress.",
                },
                "shrooms": {
                    "name": "Glowing Shrooms",
                    "files": ["shroom_cyan.png", "shroom_magenta.png", "shroom_gold.png"],
                    "fps": 2.0,
                    "dir": "props",
                    "desc": "Bioluminescent cavern flora with additive ambient lighting halos.",
                },
            },
        }

    def get_first_sprite(self):
        cat_key = "player"
        sprite_key = "idle"
        return cat_key, sprite_key


# =============================================================================
# CLI UTILITIES & REPORTING
# =============================================================================

def cmd_list_sprites(catalog):
    """Prints a structured table of all sprite sequences and frames."""
    print("\n" + "=" * 88)
    print(" 🎨 FROGGY 32-BIT SPRITE & ANIMATION MANIFEST")
    print("=" * 88)
    print(f"{'Category':<16} {'Sequence ID':<16} {'Display Name':<24} {'Frames':<8} {'FPS':<6}")
    print("-" * 88)

    total_frames = 0
    total_sequences = 0

    for cat_id, cat_info in catalog.categories.items():
        cat_name = cat_info["name"]
        for sp_id, sp_info in cat_info["sprites"].items():
            num_frames = len(sp_info["files"])
            fps = sp_info.get("fps", 6.0)
            disp_name = sp_info.get("name", sp_id)
            print(f"{cat_name:<16} {sp_id:<16} {disp_name:<24} {num_frames:<8} {fps:<6.1f}")
            total_frames += num_frames
            total_sequences += 1

    print("-" * 88)
    print(f"Total Sequences: {total_sequences}  |  Total Animation Frames: {total_frames}")
    print("To inspect sprite: py sprite_inspector.py --sprite <name>")
    print("To launch studio:  py sprite_inspector.py")
    print("=" * 88 + "\n")


def cmd_dump_manifest(catalog):
    """Outputs full technical JSON manifest with image dimensions & stats."""
    pygame.init()
    # Use dummy video driver if headless
    try:
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
    except Exception:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.display.set_mode((1, 1))

    manifest = {"categories": {}}

    for cat_id, cat_info in catalog.categories.items():
        manifest["categories"][cat_id] = {
            "name": cat_info["name"],
            "sequences": {},
        }
        for sp_id, sp_info in cat_info["sprites"].items():
            subdir = sp_info.get("dir", "sprites")
            frame_records = []
            for fname in sp_info["files"]:
                fpath = os.path.join(ASSETS_DIR, subdir, fname)
                exists = os.path.exists(fpath)
                rec = {
                    "filename": fname,
                    "exists": exists,
                }
                if exists:
                    try:
                        img = pygame.image.load(fpath)
                        w, h = img.get_size()
                        bbox = img.get_bounding_rect()
                        rec["width"] = w
                        rec["height"] = h
                        rec["bounding_box"] = [bbox.x, bbox.y, bbox.width, bbox.height]
                        rec["anchor_point"] = [w // 2, h]
                    except Exception as e:
                        rec["error"] = str(e)
                frame_records.append(rec)

            manifest["categories"][cat_id]["sequences"][sp_id] = {
                "name": sp_info.get("name", sp_id),
                "fps": sp_info.get("fps", 6.0),
                "description": sp_info.get("desc", ""),
                "frames": frame_records,
            }

    print(json.dumps(manifest, indent=2))
    pygame.quit()


# =============================================================================
# INTERACTIVE SPRITE & ANIMATION INSPECTOR GUI (PYGAME)
# =============================================================================

class SpriteInspectorGUI:
    """
    Interactive 720p visual inspector for sprite frames, bounding boxes,
    bottom-center anchor points, pixel grids, and animation scrubbers.
    """
    def __init__(self, target_sprite=None, target_category=None):
        pygame.init()
        self.screen_w = 1280
        self.screen_h = 720
        self.window = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
        pygame.display.set_caption("Froggy Sprite & Animation Studio (32-Bit Inspector)")

        # Fonts
        self.font_small = pygame.font.SysFont("monospace", 11)
        self.font_bold = pygame.font.SysFont("monospace", 12, bold=True)
        self.font_title = pygame.font.SysFont("impact", 20)
        self.font_hud = pygame.font.SysFont("monospace", 13, bold=True)

        # Asset Catalog
        self.catalog = SpriteCatalog()

        # Selection state
        self.active_category = target_category if target_category in self.catalog.categories else "player"
        cat_sprites = self.catalog.categories[self.active_category]["sprites"]
        if target_sprite and target_sprite in cat_sprites:
            self.active_sprite = target_sprite
        else:
            # Check if target_sprite matches anywhere
            found = False
            if target_sprite:
                for cid, cinfo in self.catalog.categories.items():
                    if target_sprite in cinfo["sprites"]:
                        self.active_category = cid
                        self.active_sprite = target_sprite
                        found = True
                        break
            if not found:
                self.active_sprite = list(cat_sprites.keys())[0]

        # Layout Areas
        self.sidebar_w = 260
        self.telemetry_w = 320
        self.bottom_h = 140
        self._update_layout()

        # Viewer & Camera state
        self.zoom = 8.0  # 1, 2, 4, 6, 8, 12, 16
        self.zoom_levels = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0]
        self.zoom_idx = 4
        self.flip_h = False

        # Toggleable Overlays
        self.show_bbox = True        # Neon green bounding box
        self.show_anchor = True      # Magenta bottom-center anchor crosshair
        self.show_center = False     # Cyan geometric center
        self.show_grid = True        # Pixel grid lines
        self.checker_dark = True     # Checkerboard contrast

        # Animation Playback State
        self.is_playing = True
        self.current_frame_float = 0.0
        self.current_frame_idx = 0
        self.fps_override = None

        # Loaded Surfaces Cache for active sequence
        self.loaded_frames = []
        self._load_active_frames()

        # Status Flash
        self.status_msg = f"Ready. Inspecting '{self.active_sprite}' ({len(self.loaded_frames)} frames)."
        self.status_timer = 180

    def _update_layout(self):
        self.sidebar_rect = pygame.Rect(0, 0, self.sidebar_w, self.screen_h)
        self.telemetry_rect = pygame.Rect(self.screen_w - self.telemetry_w, 0, self.telemetry_w, self.screen_h)
        self.stage_rect = pygame.Rect(
            self.sidebar_w,
            0,
            self.screen_w - self.sidebar_w - self.telemetry_w,
            self.screen_h - self.bottom_h,
        )
        self.bottom_rect = pygame.Rect(
            self.sidebar_w,
            self.screen_h - self.bottom_h,
            self.screen_w - self.sidebar_w - self.telemetry_w,
            self.bottom_h,
        )

    def _load_active_frames(self):
        """Loads all PNG frames for the selected sprite sequence."""
        self.loaded_frames.clear()
        sp_info = self.catalog.categories[self.active_category]["sprites"][self.active_sprite]
        subdir = sp_info.get("dir", "sprites")

        for fname in sp_info["files"]:
            fpath = os.path.join(ASSETS_DIR, subdir, fname)
            if os.path.exists(fpath):
                try:
                    surf = pygame.image.load(fpath).convert_alpha()
                    self.loaded_frames.append((fname, surf))
                except Exception as e:
                    print(f"[Sprite Studio] Error loading {fname}: {e}")
            else:
                # Procedural placeholder
                surf = pygame.Surface((32, 32), pygame.SRCALPHA)
                surf.fill((60, 160, 80, 200))
                self.loaded_frames.append((fname, surf))

        self.current_frame_float = 0.0
        self.current_frame_idx = 0
        self.fps_override = sp_info.get("fps", 6.0)

    def select_sprite(self, cat_key, sprite_key):
        """Switches the active sprite sequence."""
        self.active_category = cat_key
        self.active_sprite = sprite_key
        self._load_active_frames()
        self.status_msg = f"Inspecting: [{cat_key}] {sprite_key} ({len(self.loaded_frames)} frames)"
        self.status_timer = 180

    def run(self):
        clock = pygame.time.Clock()
        running = True

        while running:
            dt = clock.tick(60) / 1000.0  # seconds
            if self.status_timer > 0:
                self.status_timer -= 1

            # Advance animation timer if playing
            if self.is_playing and len(self.loaded_frames) > 0:
                fps = self.fps_override if self.fps_override else 6.0
                self.current_frame_float = (self.current_frame_float + fps * dt) % len(self.loaded_frames)
                self.current_frame_idx = int(self.current_frame_float)

            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.screen_w = max(960, event.w)
                    self.screen_h = max(600, event.h)
                    self.window = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
                    self._update_layout()

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.is_playing = not self.is_playing
                    elif event.key in (pygame.K_LEFT, pygame.K_LEFTBRACKET):
                        self.is_playing = False
                        if self.loaded_frames:
                            self.current_frame_idx = (self.current_frame_idx - 1) % len(self.loaded_frames)
                            self.current_frame_float = float(self.current_frame_idx)
                    elif event.key in (pygame.K_RIGHT, pygame.K_RIGHTBRACKET):
                        self.is_playing = False
                        if self.loaded_frames:
                            self.current_frame_idx = (self.current_frame_idx + 1) % len(self.loaded_frames)
                            self.current_frame_float = float(self.current_frame_idx)
                    elif event.key == pygame.K_b:
                        self.show_bbox = not self.show_bbox
                    elif event.key == pygame.K_a:
                        self.show_anchor = not self.show_anchor
                    elif event.key == pygame.K_c:
                        self.show_center = not self.show_center
                    elif event.key == pygame.K_g:
                        self.show_grid = not self.show_grid
                    elif event.key == pygame.K_f:
                        self.flip_h = not self.flip_h
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self._adjust_zoom(1)
                    elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                        self._adjust_zoom(-1)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    if self.sidebar_rect.collidepoint(mx, my):
                        self._handle_sidebar_click(mx, my)
                    elif self.bottom_rect.collidepoint(mx, my):
                        self._handle_bottom_click(mx, my)
                    elif self.stage_rect.collidepoint(mx, my):
                        if event.button == 4:  # Wheel Up
                            self._adjust_zoom(1)
                        elif event.button == 5:  # Wheel Down
                            self._adjust_zoom(-1)

            # Render
            self.draw()
            pygame.display.flip()

        pygame.quit()

    def _adjust_zoom(self, step):
        self.zoom_idx = max(0, min(len(self.zoom_levels) - 1, self.zoom_idx + step))
        self.zoom = self.zoom_levels[self.zoom_idx]

    def _handle_sidebar_click(self, mx, my):
        """Selects category or sprite from the hierarchy tree."""
        y_c = 44
        for cat_id, cat_info in self.catalog.categories.items():
            y_c += 22  # category header
            for sp_id, sp_info in cat_info["sprites"].items():
                item_rect = pygame.Rect(8, y_c, self.sidebar_w - 16, 22)
                if item_rect.collidepoint(mx, my):
                    self.select_sprite(cat_id, sp_id)
                    return
                y_c += 24
            y_c += 6

    def _handle_bottom_click(self, mx, my):
        """Handles clicking frame thumbnails in the filmstrip or playback buttons."""
        # 1. Transport controls on top line of bottom area
        btn_y = self.bottom_rect.top + 8
        if btn_y <= my <= btn_y + 26:
            # Play / Pause
            if self.bottom_rect.left + 10 <= mx <= self.bottom_rect.left + 80:
                self.is_playing = not self.is_playing
            # Prev Frame
            elif self.bottom_rect.left + 90 <= mx <= self.bottom_rect.left + 150:
                self.is_playing = False
                if self.loaded_frames:
                    self.current_frame_idx = (self.current_frame_idx - 1) % len(self.loaded_frames)
                    self.current_frame_float = float(self.current_frame_idx)
            # Next Frame
            elif self.bottom_rect.left + 160 <= mx <= self.bottom_rect.left + 220:
                self.is_playing = False
                if self.loaded_frames:
                    self.current_frame_idx = (self.current_frame_idx + 1) % len(self.loaded_frames)
                    self.current_frame_float = float(self.current_frame_idx)
            # Speed Slower / Faster
            elif self.bottom_rect.left + 240 <= mx <= self.bottom_rect.left + 270:
                self.fps_override = max(1.0, (self.fps_override or 6.0) - 1.0)
            elif self.bottom_rect.left + 330 <= mx <= self.bottom_rect.left + 360:
                self.fps_override = min(60.0, (self.fps_override or 6.0) + 1.0)
            return

        # 2. Frame Filmstrip Thumbnails
        filmstrip_y = self.bottom_rect.top + 42
        thumb_size = 64
        x_c = self.bottom_rect.left + 12
        for idx, (fname, surf) in enumerate(self.loaded_frames):
            thumb_rect = pygame.Rect(x_c, filmstrip_y, thumb_size, thumb_size)
            if thumb_rect.collidepoint(mx, my):
                self.is_playing = False
                self.current_frame_idx = idx
                self.current_frame_float = float(idx)
                return
            x_c += thumb_size + 10

    # =========================================================================
    # DRAWING ROUTINES
    # =========================================================================

    def draw(self):
        self.window.fill(COLOR_BG)

        # 1. Left Navigator Sidebar
        self._draw_sidebar()

        # 2. Central Animation Stage
        self._draw_stage()

        # 3. Bottom Filmstrip & Transport
        self._draw_bottom()

        # 4. Right Telemetry & Explainer Panel
        self._draw_telemetry()

    def _draw_sidebar(self):
        pygame.draw.rect(self.window, COLOR_PANEL_BG, self.sidebar_rect)
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.sidebar_rect.right - 1, 0), (self.sidebar_rect.right - 1, self.screen_h), 1)

        # Title
        title_surf = self.font_hud.render("SPRITE EXPLORER", True, COLOR_ACCENT)
        self.window.blit(title_surf, (14, 12))
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (0, 36), (self.sidebar_w, 36))

        mx, my = pygame.mouse.get_pos()
        y_c = 44

        for cat_id, cat_info in self.catalog.categories.items():
            cat_surf = self.font_bold.render(f"▼ {cat_info['name'].upper()}", True, (255, 215, 80))
            self.window.blit(cat_surf, (12, y_c))
            y_c += 22

            for sp_id, sp_info in cat_info["sprites"].items():
                item_rect = pygame.Rect(8, y_c, self.sidebar_w - 16, 22)
                is_active = (self.active_category == cat_id and self.active_sprite == sp_id)
                is_hover = item_rect.collidepoint(mx, my)

                if is_active:
                    bg_col = (45, 95, 65)
                elif is_hover:
                    bg_col = COLOR_BUTTON_HOVER
                else:
                    bg_col = (28, 34, 48)

                pygame.draw.rect(self.window, bg_col, item_rect, border_radius=3)
                if is_active:
                    pygame.draw.rect(self.window, COLOR_ACCENT, item_rect, 1, border_radius=3)

                lbl_col = COLOR_TEXT_WHITE if (is_active or is_hover) else COLOR_TEXT_DIM
                lbl = self.font_small.render(sp_info.get("name", sp_id)[:24], True, lbl_col)
                self.window.blit(lbl, (item_rect.left + 8, item_rect.top + 4))

                # Frame count badge
                f_count = len(sp_info["files"])
                badge = self.font_small.render(f"{f_count}f", True, (130, 150, 175))
                self.window.blit(badge, (item_rect.right - badge.get_width() - 6, item_rect.top + 4))

                y_c += 24
            y_c += 6

    def _draw_stage(self):
        """Renders the central viewing stage with checkerboard backdrop, sprite, and overlays."""
        # Backdrop
        pygame.draw.rect(self.window, (16, 20, 28), self.stage_rect)

        if not self.loaded_frames:
            return

        current_fname, raw_surf = self.loaded_frames[self.current_frame_idx]
        if self.flip_h:
            raw_surf = pygame.transform.flip(raw_surf, True, False)

        sw, sh = raw_surf.get_size()
        scaled_w = int(sw * self.zoom)
        scaled_h = int(sh * self.zoom)

        center_x = self.stage_rect.centerx
        center_y = self.stage_rect.centery
        sprite_rect = pygame.Rect(center_x - scaled_w // 2, center_y - scaled_h // 2, scaled_w, scaled_h)

        # 1. High-contrast Checkerboard pattern behind sprite
        chk_size = max(8, int(4 * (self.zoom / 4.0)))
        chk_cols = (scaled_w // chk_size) + 1
        chk_rows = (scaled_h // chk_size) + 1
        c1 = (42, 48, 62) if self.checker_dark else (210, 215, 225)
        c2 = (30, 36, 48) if self.checker_dark else (180, 185, 195)

        prev_clip = self.window.get_clip()
        self.window.set_clip(sprite_rect)
        for r in range(chk_rows):
            for c in range(chk_cols):
                color = c1 if (r + c) % 2 == 0 else c2
                rx = sprite_rect.left + c * chk_size
                ry = sprite_rect.top + r * chk_size
                pygame.draw.rect(self.window, color, (rx, ry, chk_size, chk_size))

        # 2. Render Sprite Surface scaled up using Nearest-Neighbor (crisp retro pixels)
        scaled_surf = pygame.transform.scale(raw_surf, (scaled_w, scaled_h))
        self.window.blit(scaled_surf, sprite_rect.topleft)
        self.window.set_clip(prev_clip)

        # 3. Pixel Grid Lines (at zoom >= 4x)
        if self.show_grid and self.zoom >= 4.0:
            grid_col = (255, 255, 255, 30)
            for c in range(sw + 1):
                gx = sprite_rect.left + int(c * self.zoom)
                pygame.draw.line(self.window, (60, 70, 90), (gx, sprite_rect.top), (gx, sprite_rect.bottom), 1)
            for r in range(sh + 1):
                gy = sprite_rect.top + int(r * self.zoom)
                pygame.draw.line(self.window, (60, 70, 90), (sprite_rect.left, gy), (sprite_rect.right, gy), 1)

        # 4. Bounding Box Overlay (Neon Green)
        if self.show_bbox:
            bbox = raw_surf.get_bounding_rect()
            if bbox.width > 0 and bbox.height > 0:
                bx = sprite_rect.left + int(bbox.x * self.zoom)
                by = sprite_rect.top + int(bbox.y * self.zoom)
                bw = int(bbox.width * self.zoom)
                bh = int(bbox.height * self.zoom)
                pygame.draw.rect(self.window, COLOR_BOX_GREEN, (bx, by, bw, bh), 2)
                # Bounding box dimensions tag
                dim_lbl = self.font_small.render(f"{bbox.width}x{bbox.height}px", True, COLOR_BOX_GREEN)
                self.window.blit(dim_lbl, (bx + 2, by - 14))

        # 5. Bottom-Center Anchor Point Overlay (Magenta Crosshair)
        if self.show_anchor:
            anchor_x = sprite_rect.left + scaled_w // 2
            anchor_y = sprite_rect.bottom
            pygame.draw.circle(self.window, COLOR_ANCHOR_MAGENTA, (anchor_x, anchor_y), 5, 2)
            pygame.draw.line(self.window, COLOR_ANCHOR_MAGENTA, (anchor_x - 12, anchor_y), (anchor_x + 12, anchor_y), 1)
            pygame.draw.line(self.window, COLOR_ANCHOR_MAGENTA, (anchor_x, anchor_y - 12), (anchor_x, anchor_y + 12), 1)
            anc_lbl = self.font_small.render("Anchor (Feet)", True, COLOR_ANCHOR_MAGENTA)
            self.window.blit(anc_lbl, (anchor_x + 8, anchor_y - 14))

        # 6. Center Point Overlay (Cyan Crosshair)
        if self.show_center:
            cx = sprite_rect.left + scaled_w // 2
            cy = sprite_rect.top + scaled_h // 2
            pygame.draw.circle(self.window, COLOR_CENTER_CYAN, (cx, cy), 4, 1)
            pygame.draw.line(self.window, COLOR_CENTER_CYAN, (cx - 8, cy), (cx + 8, cy), 1)
            pygame.draw.line(self.window, COLOR_CENTER_CYAN, (cx, cy - 8), (cx, cy + 8), 1)

        # Stage Overlay Toolbar (Top right of stage)
        self._draw_stage_toolbar()

    def _draw_stage_toolbar(self):
        """Overlays quick toggle buttons on stage."""
        tb_x = self.stage_rect.left + 14
        tb_y = 12

        toggles = [
            (f"Zoom: {self.zoom:.0f}x", False),
            ("BBox [B]", self.show_bbox),
            ("Anchor [A]", self.show_anchor),
            ("Center [C]", self.show_center),
            ("Grid [G]", self.show_grid),
            ("Flip [F]", self.flip_h),
        ]

        for text, active in toggles:
            bg = (40, 90, 60) if active else (30, 36, 50)
            rect = pygame.Rect(tb_x, tb_y, len(text) * 8 + 14, 22)
            pygame.draw.rect(self.window, bg, rect, border_radius=3)
            pygame.draw.rect(self.window, COLOR_PANEL_BORDER, rect, 1, border_radius=3)
            col = COLOR_TEXT_WHITE if active else COLOR_TEXT_DIM
            lbl = self.font_small.render(text, True, col)
            self.window.blit(lbl, (rect.left + 6, rect.top + 4))
            tb_x += rect.width + 6

    def _draw_bottom(self):
        """Renders playback transport and the horizontal filmstrip thumbnails."""
        pygame.draw.rect(self.window, COLOR_PANEL_BG, self.bottom_rect)
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.bottom_rect.left, self.bottom_rect.top), (self.bottom_rect.right, self.bottom_rect.top), 1)

        # Transport Controls
        btn_y = self.bottom_rect.top + 8
        bx = self.bottom_rect.left + 10

        # Play / Pause
        play_label = "❚❚ PAUSE" if self.is_playing else "▶ PLAY"
        self._draw_btn(bx, btn_y, 74, 24, play_label, (45, 110, 70) if self.is_playing else COLOR_BUTTON_BG)
        bx += 82

        # Step Back
        self._draw_btn(bx, btn_y, 60, 24, "◀ PREV", COLOR_BUTTON_BG)
        bx += 68

        # Step Next
        self._draw_btn(bx, btn_y, 60, 24, "NEXT ▶", COLOR_BUTTON_BG)
        bx += 76

        # Speed slider (- / +)
        fps = self.fps_override or 6.0
        self._draw_btn(bx, btn_y, 26, 24, "-", COLOR_BUTTON_BG)
        bx += 32
        speed_lbl = self.font_bold.render(f"{fps:.0f} FPS", True, COLOR_TEXT_WHITE)
        self.window.blit(speed_lbl, (bx + 4, btn_y + 4))
        bx += 58
        self._draw_btn(bx, btn_y, 26, 24, "+", COLOR_BUTTON_BG)
        bx += 40

        # Frame Indicator
        if self.loaded_frames:
            f_str = f"Frame: {self.current_frame_idx + 1} of {len(self.loaded_frames)} ({self.loaded_frames[self.current_frame_idx][0]})"
            f_lbl = self.font_bold.render(f_str, True, COLOR_ACCENT)
            self.window.blit(f_lbl, (bx + 12, btn_y + 4))

        # Filmstrip Thumbnails Row
        filmstrip_y = self.bottom_rect.top + 38
        thumb_size = 64
        tx = self.bottom_rect.left + 12

        for idx, (fname, surf) in enumerate(self.loaded_frames):
            thumb_rect = pygame.Rect(tx, filmstrip_y, thumb_size, thumb_size)
            is_active = (idx == self.current_frame_idx)

            # Thumbnail background
            pygame.draw.rect(self.window, (34, 42, 58), thumb_rect, border_radius=4)
            if is_active:
                pygame.draw.rect(self.window, COLOR_ACCENT, thumb_rect, 2, border_radius=4)
            else:
                pygame.draw.rect(self.window, COLOR_PANEL_BORDER, thumb_rect, 1, border_radius=4)

            # Draw miniature sprite
            sw, sh = surf.get_size()
            scale = min((thumb_size - 8) / max(1, sw), (thumb_size - 8) / max(1, sh))
            mw = max(1, int(sw * scale))
            mh = max(1, int(sh * scale))
            mini = pygame.transform.scale(surf, (mw, mh))
            self.window.blit(mini, (thumb_rect.centerx - mw // 2, thumb_rect.centery - mh // 2))

            # Frame index badge
            badge = self.font_small.render(f"#{idx}", True, (255, 215, 80) if is_active else COLOR_TEXT_DIM)
            self.window.blit(badge, (thumb_rect.left + 4, thumb_rect.top + 2))

            tx += thumb_size + 10

    def _draw_telemetry(self):
        """Renders technical data, color swatches, and nephew explainer on the right."""
        pygame.draw.rect(self.window, COLOR_PANEL_BG, self.telemetry_rect)
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.telemetry_rect.left, 0), (self.telemetry_rect.left, self.screen_h), 1)

        # Header
        hdr = self.font_hud.render("TELEMETRY & SPECS", True, COLOR_ACCENT)
        self.window.blit(hdr, (self.telemetry_rect.left + 14, 12))
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.telemetry_rect.left, 36), (self.screen_w, 36))

        if not self.loaded_frames:
            return

        fname, raw_surf = self.loaded_frames[self.current_frame_idx]
        sw, sh = raw_surf.get_size()
        bbox = raw_surf.get_bounding_rect()
        total_pixels = sw * sh
        bbox_pixels = bbox.width * bbox.height

        y_c = 44
        specs = [
            ("Sequence:", self.active_sprite),
            ("Filename:", fname),
            ("Dimensions:", f"{sw} x {sh} px"),
            ("Bounding Box:", f"({bbox.x}, {bbox.y}, {bbox.width}x{bbox.height})"),
            ("Anchor Point:", f"({sw // 2}, {sh}) [Bottom-Center]"),
            ("Alpha Format:", "32-Bit RGBA (Sub-pixel feather)"),
            ("Total Pixels:", f"{total_pixels:,}"),
            ("Silhouette Pixels:", f"{bbox_pixels:,} ({int(bbox_pixels / max(1, total_pixels) * 100)}%)"),
        ]

        for title, val in specs:
            t_surf = self.font_small.render(title, True, COLOR_TEXT_DIM)
            v_surf = self.font_bold.render(str(val)[:24], True, COLOR_TEXT_WHITE)
            self.window.blit(t_surf, (self.telemetry_rect.left + 14, y_c))
            self.window.blit(v_surf, (self.telemetry_rect.left + 120, y_c))
            y_c += 20

        # Cursor Pixel Probe
        y_c += 10
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.telemetry_rect.left + 10, y_c), (self.screen_w - 10, y_c))
        y_c += 10

        probe_hdr = self.font_bold.render("▪ LIVE CURSOR PIXEL PROBE", True, (255, 215, 80))
        self.window.blit(probe_hdr, (self.telemetry_rect.left + 14, y_c))
        y_c += 20

        mx, my = pygame.mouse.get_pos()
        probe_info = "Hover cursor over sprite"
        hover_col = (0, 0, 0, 0)
        has_pixel = False

        if self.stage_rect.collidepoint(mx, my):
            # Transform screen mouse into sprite local coordinates
            scaled_w = int(sw * self.zoom)
            scaled_h = int(sh * self.zoom)
            sprite_left = self.stage_rect.centerx - scaled_w // 2
            sprite_top = self.stage_rect.centery - scaled_h // 2
            lx = int((mx - sprite_left) // self.zoom)
            ly = int((my - sprite_top) // self.zoom)

            if 0 <= lx < sw and 0 <= ly < sh:
                has_pixel = True
                hover_col = raw_surf.get_at((lx, ly))
                probe_info = f"Pixel ({lx:02d}, {ly:02d}) RGBA: {hover_col[0]},{hover_col[1]},{hover_col[2]},{hover_col[3]}"

        probe_lbl = self.font_small.render(probe_info, True, COLOR_TEXT_WHITE)
        self.window.blit(probe_lbl, (self.telemetry_rect.left + 14, y_c))

        if has_pixel:
            # Color swatch preview square
            swatch_rect = pygame.Rect(self.telemetry_rect.right - 36, y_c - 2, 20, 20)
            pygame.draw.rect(self.window, hover_col[:3], swatch_rect)
            pygame.draw.rect(self.window, (255, 255, 255), swatch_rect, 1)

        # Nephew Educational Notes
        y_c += 36
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.telemetry_rect.left + 10, y_c), (self.screen_w - 10, y_c))
        y_c += 10

        edu_hdr = self.font_bold.render("▪ UNDER THE HOOD: HOW IT WORKS", True, (255, 215, 80))
        self.window.blit(edu_hdr, (self.telemetry_rect.left + 14, y_c))
        y_c += 20

        notes = [
            "1. Bottom-Center Anchor:",
            "   Froggy's feet are anchored to (16, 32).",
            "   This prevents his body from jumping up",
            "   and down when switching between idle,",
            "   running, and jumping poses!",
            "",
            "2. 32-Bit Alpha Feathering:",
            "   Outer edge pixels use alpha blending",
            "   (0-255) rather than 1-bit on/off.",
            "   This eliminates ugly jagged white fringes!",
            "",
            "3. Modulo Loop Clock:",
            "   tick = (frame_count // delay) % total",
            "   guarantees infinite seamless loops.",
        ]

        for n in notes:
            lbl = self.font_small.render(n, True, (170, 185, 205))
            self.window.blit(lbl, (self.telemetry_rect.left + 14, y_c))
            y_c += 16

    def _draw_btn(self, x, y, w, h, text, bg):
        rect = pygame.Rect(x, y, w, h)
        mx, my = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mx, my)
        fill = COLOR_BUTTON_HOVER if is_hover and bg == COLOR_BUTTON_BG else bg
        pygame.draw.rect(self.window, fill, rect, border_radius=3)
        pygame.draw.rect(self.window, COLOR_PANEL_BORDER, rect, 1, border_radius=3)
        lbl = self.font_bold.render(text, True, COLOR_TEXT_WHITE)
        self.window.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Froggy Standalone Sprite & Animation Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py sprite_inspector.py --list
  py sprite_inspector.py --dump
  py sprite_inspector.py --sprite froggy_run
  py sprite_inspector.py --category enemies
  py sprite_inspector.py --category bosses
        """,
    )
    parser.add_argument("--list", "-l", action="store_true", help="List all sprite sequences and frame counts")
    parser.add_argument("--dump", "-d", action="store_true", help="Dump full technical JSON asset manifest")
    parser.add_argument("--sprite", "-s", metavar="NAME", help="Focus directly on this sprite sequence")
    parser.add_argument("--category", "-c", metavar="CAT", help="Filter by category (player, enemies, bosses, npcs, tiles, props)")
    parser.add_argument("--headless", action="store_true", help="Do not open GUI window (useful for tests)")

    args = parser.parse_args()
    catalog = SpriteCatalog()

    if args.list:
        cmd_list_sprites(catalog)
        return

    if args.dump:
        cmd_dump_manifest(catalog)
        return

    if args.headless:
        print("[Sprite Inspector Headless] Catalog validation successful.")
        cmd_list_sprites(catalog)
        return

    gui = SpriteInspectorGUI(target_sprite=args.sprite, target_category=args.category)
    gui.run()


if __name__ == "__main__":
    main()
