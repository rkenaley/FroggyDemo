"""
===============================================================================
FROGGY: PROCEDURAL 16-BIT PIXEL-ART & ATMOSPHERIC ASSET GENERATOR
===============================================================================
This script uses Pillow (PIL) and NumPy to generate and save crisp 16-bit
pixel-art sprite sheets, 4-bit auto-tiled terrain textures, lush jungle
foliage props, radial lighting maps, and multi-layer parallax backgrounds
into the `assets/` folder.

WHY THIS FILE EXISTS (Educational Note for Your Nephew!):
1. Real 2D games use hundreds of small images (called "tiles" and "sprites")
   stored in an `assets/` folder.
2. Instead of drawing 16 different corner/edge combinations of mossy stone by
   hand in Photoshop, we use code (Pillow + NumPy) to paint them with
   mathematical precision, add organic moss, stone cracks, and shading, and
   save them as real `.png` files you can open and inspect in Windows Explorer!
3. If `assets/` is ever deleted, `froggy_engine.py` automatically calls
   `ensure_assets_exist()` on startup to rebuild every `.png` in under 1 second.
===============================================================================
"""

import math
import os
import random
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

if getattr(sys, 'frozen', False):
    _bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    ASSET_ROOT = os.path.join(_bundle_dir, "assets")
    if not os.path.exists(ASSET_ROOT):
        ASSET_ROOT = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "assets")
else:
    ASSET_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TILES_DIR = os.path.join(ASSET_ROOT, "tiles")
SPRITES_DIR = os.path.join(ASSET_ROOT, "sprites")
PROPS_DIR = os.path.join(ASSET_ROOT, "props")
FX_DIR = os.path.join(ASSET_ROOT, "fx")
BG_DIR = os.path.join(ASSET_ROOT, "backgrounds")


def ensure_directories():
    """Creates the asset subdirectories if they do not exist yet."""
    for folder in (ASSET_ROOT, TILES_DIR, SPRITES_DIR, PROPS_DIR, FX_DIR, BG_DIR):
        os.makedirs(folder, exist_ok=True)


# =============================================================================
# 1. COLOR PALETTE & PIXEL GRID RASTERIZER (PILLOW RGBA)
# =============================================================================

PALETTE = {
    '.': None,                   # Transparent
    # --- Froggy Hero Greens & Bandana (Legend of Mana 7-Tone Painterly Palette) ---
    'E': (152, 245, 110, 255),   # Golden Sunlit Leaf Highlight
    'g': (105, 222, 94, 255),    # Light Emerald
    'G': (64, 188, 76, 255),     # Primary Mid Emerald
    'D': (32, 118, 48, 255),     # Deep Forest Moss Shadow
    'd': (18, 64, 30, 255),      # Dark Ink-Green Outline
    'L': (212, 248, 148, 255),   # Creamy Pale Lime Belly
    'l': (160, 215, 108, 255),   # Warm Shaded Belly
    'k': (102, 158, 72, 255),    # Deep Olive Throat Contour
    'W': (255, 255, 255, 255),   # Pure Specular White / Fangs
    'w': (238, 242, 230, 255),   # Soft Ivory
    'K': (16, 18, 26, 255),      # Deep Ink Black (Pupil / Outline)
    'R': (238, 45, 62, 255),     # Bandana Scarlet Red
    'r': (165, 22, 38, 255),     # Ruby Crimson Shadow
    'q': (95, 12, 24, 255),      # Deep Maroon Outline
    'X': (255, 128, 140, 255),   # Bandana Silk Highlight
    'P': (248, 112, 156, 255),   # Tongue Pink
    'p': (255, 175, 205, 255),   # Tongue Tip Highlight
    # --- Boots & Leather ---
    'b': (150, 92, 45, 255),     # Warm Leather Boot Brown
    'B': (92, 52, 26, 255),      # Dark Leather Boot Shadow
    'Y': (255, 215, 64, 255),    # Polished Brass / Golden Buckle
    'y': (205, 145, 28, 255),    # Antique Gold Shadow
    'Z': (255, 245, 160, 255),   # Star Sparkle / Gold Highlight
    # --- Enemies, Bosses & FX ---
    'O': (245, 130, 35, 255),    # Amber Chitin
    'o': (160, 65, 20, 255),     # Dark Rust Chitin
    'C': (65, 235, 255, 255),    # Bioluminescent Cyan
    'c': (24, 140, 195, 255),    # Deep Cerulean
    'V': (145, 75, 215, 255),    # Velvet Shadow Spider Violet
    'v': (75, 32, 128, 255),     # Dark Indigo Shadow
    'N': (80, 255, 235, 255),    # Spider Neon Eye Cyan
    'M': (255, 60, 195, 255),    # Magenta Boss Core
    'm': (165, 25, 118, 255),    # Deep Magenta
    'T': (58, 62, 76, 255),      # Dread Hound Stone Charcoal
    't': (36, 38, 48, 255),      # Dread Hound Iron Shadow
    'I': (102, 110, 132, 255),   # Dread Hound Steel Highlight
    'F': (255, 45, 65, 255),     # Flaming Ruby Eye / Fire Breath
    'f': (255, 145, 40, 255),    # Flame Orange
    'S': (82, 98, 132, 255),     # Stone Mid
    'H': (122, 146, 184, 255),   # Stone Highlight
}


def image_from_grid(grid_lines):
    """Converts a list of ASCII character strings into a PIL RGBA Image."""
    h = len(grid_lines)
    w = max(len(row) for row in grid_lines)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pixels = img.load()
    for y, row in enumerate(grid_lines):
        for x, ch in enumerate(row):
            col = PALETTE.get(ch)
            if col is not None:
                pixels[x, y] = col
    return img


# =============================================================================
# 2. AUTO-TILED 16x16 TERRAIN GENERATOR (JUNGLE TEMPLE & BOSS SANCTUM)
# =============================================================================

def generate_autotile_set(theme="jungle"):
    """
    Generates all 16 neighbor-bitmask tile variations (0..15) for 16x16 terrain.
    Bitmask encoding:
      Bit 1 (1) = Solid neighbor ABOVE (North)
      Bit 2 (2) = Solid neighbor RIGHT (East)
      Bit 4 (4) = Solid neighbor BELOW (South)
      Bit 8 (8) = Solid neighbor LEFT  (West)

    When North is open (bit 1 == 0), we paint lush overhanging moss & grass
    (or thorny blood-vines in the Boss Sanctum)!
    """
    rng = random.Random(42 if theme == "jungle" else 999)

    if theme == "jungle":
        stone_dark = (34, 44, 66, 255)
        stone_mid = (56, 72, 102, 255)
        stone_hi = (84, 106, 142, 255)
        mortar = (22, 28, 44, 255)
        top_bright = (118, 232, 94, 255)
        top_mid = (62, 178, 72, 255)
        top_dark = (32, 112, 48, 255)
        accent_glow = (95, 245, 225, 255)
        prefix = "terrain"
    else:
        # Sinister Emperor Mantis Sanctum theme (Obsidian, Crimson & Violet Runes)
        stone_dark = (36, 18, 34, 255)
        stone_mid = (62, 28, 54, 255)
        stone_hi = (96, 46, 82, 255)
        mortar = (18, 8, 20, 255)
        top_bright = (235, 68, 105, 255)
        top_mid = (158, 34, 68, 255)
        top_dark = (88, 18, 42, 255)
        accent_glow = (210, 95, 255, 255)
        prefix = "sanctum"

    for mask in range(16):
        has_n = bool(mask & 1)
        has_e = bool(mask & 2)
        has_s = bool(mask & 4)
        has_w = bool(mask & 8)

        img = Image.new("RGBA", (16, 16), stone_mid)
        px = img.load()

        # 1. Base Chiseled Temple Brick Masonry
        for y in range(16):
            for x in range(16):
                # Brick rows at y=0, 7, 15 and staggered vertical mortar seams
                row_band = y % 8
                brick_offset = 4 if (y // 8) % 2 == 1 else 0
                is_h_mortar = (row_band == 7)
                is_v_mortar = ((x + brick_offset) % 8 == 7)

                if is_h_mortar or is_v_mortar:
                    px[x, y] = mortar
                elif row_band == 0 or (x + brick_offset) % 8 == 0:
                    px[x, y] = stone_hi
                elif row_band >= 5:
                    px[x, y] = stone_dark
                else:
                    # Subtle organic stone texture
                    n_val = (x * 13 + y * 29 + mask * 7) % 11
                    px[x, y] = stone_dark if n_val == 0 else (stone_hi if n_val == 1 else stone_mid)

        # 2. Left & Right Exposed Chiseled Stone Borders
        if not has_w:
            for y in range(16):
                px[0, y] = mortar
                px[1, y] = stone_hi if y % 4 != 3 else stone_dark
                if y % 3 == 0:
                    px[2, y] = top_dark
        if not has_e:
            for y in range(16):
                px[15, y] = mortar
                px[14, y] = stone_dark if y % 4 != 0 else stone_hi
                if y % 3 == 1:
                    px[13, y] = top_dark

        # 3. Bottom Exposed Rocky Underside / Roots
        if not has_s:
            for x in range(16):
                px[x, 15] = mortar
                px[x, 14] = stone_dark
                if (x * 5 + mask) % 4 == 0:
                    px[x, 13] = mortar

        # 4. Top Exposed Lush Moss / Grass Overhang (When North is Air)
        if not has_n:
            moss_depths = [3, 4, 5, 4, 3, 4, 6, 5, 4, 3, 4, 5, 4, 3, 4, 3]
            for x in range(16):
                depth = moss_depths[x]
                for y in range(depth):
                    if y == 0:
                        px[x, y] = top_bright if (x % 2 == 0) else top_mid
                    elif y < depth - 1:
                        px[x, y] = top_mid
                    else:
                        px[x, y] = top_dark
                # Shadow right under the moss lip
                if depth < 15:
                    px[x, depth] = mortar
            # Tiny bioluminescent spore / dewdrop highlight on the moss
            px[5, 1] = accent_glow
            px[12, 2] = accent_glow
        else:
            # Subtle glowing moss veins inside deep wall blocks
            if (mask == 15) and (rng.random() < 0.65):
                vx = 4 + (mask * 3) % 7
                px[vx, 4] = top_dark
                px[vx + 1, 5] = top_mid
                px[vx + 2, 5] = accent_glow

        img.save(os.path.join(TILES_DIR, f"{prefix}_{mask}.png"))

    # Also generate a second interior variant for visual variety on large walls
    img_var = Image.open(os.path.join(TILES_DIR, f"{prefix}_15.png")).copy()
    px = img_var.load()
    px[10, 11] = accent_glow
    px[9, 11] = top_mid
    px[3, 3] = top_dark
    img_var.save(os.path.join(TILES_DIR, f"{prefix}_15_alt.png"))


def generate_special_tiles():
    """Generates ornate grapple idols, animated rune portals, and glowing swamp water."""
    # 1. Ornate Golden Grapple Idol (2 pulsing frames)
    grapple_f1 = [
        "....oooooooo....",
        "..ooYYYYYYYYoo..",
        ".oYYWWWWWWWWYYo.",
        ".oYWyyoooooyYYo.",
        "oYYo..cccc..oYYo",
        "oYWo.cCCCCc.oYYo",
        "oYWo.cCWWCc.oYYo",
        "oYWo.cCWWCc.oYYo",
        "oYWo.cCCCCc.oYYo",
        "oYYo..cccc..oYYo",
        ".oYWooooooooYYo.",
        ".oYYWWWWWWWWYYo.",
        "..ooYYYYYYYYoo..",
        "....oooooooo....",
        "......oooo......",
        "................",
    ]
    grapple_f2 = [row.replace('C', 'W').replace('c', 'C') for row in grapple_f1]
    image_from_grid(grapple_f1).save(os.path.join(TILES_DIR, "grapple_0.png"))
    image_from_grid(grapple_f2).save(os.path.join(TILES_DIR, "grapple_1.png"))

    # 2. Ancient Rune Portal Door (Cyan Adventure Portal & Crimson Boss Portal)
    for portal_type, (outer_c, mid_c, core_c) in [
        ("door", ((22, 95, 145, 255), (65, 215, 255, 255), (220, 255, 255, 255))),
        ("boss_door", ((125, 20, 65, 255), (245, 65, 135, 255), (255, 215, 120, 255))),
    ]:
        for frame in range(4):
            img = Image.new("RGBA", (16, 16), (14, 18, 30, 255))
            px = img.load()
            for y in range(16):
                for x in range(16):
                    # Carved stone pillar border on left/right edges
                    if x in (0, 15):
                        px[x, y] = (32, 40, 62, 255)
                    elif x in (1, 14):
                        px[x, y] = mid_c if (y + frame) % 4 == 0 else (58, 72, 104, 255)
                    else:
                        # Swirling energy vortex inside archway
                        dx = x - 7.5
                        dy = y - 7.5
                        dist = math.hypot(dx, dy)
                        wave = math.sin(dist * 1.4 - frame * (math.pi / 2.0))
                        if wave > 0.45:
                            px[x, y] = core_c
                        elif wave > -0.15:
                            px[x, y] = mid_c
                        else:
                            px[x, y] = outer_c
            img.save(os.path.join(TILES_DIR, f"{portal_type}_{frame}.png"))

    # 3. Animated Bioluminescent Swamp Water (4 frames for chasm hazards)
    for frame in range(4):
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = img.load()
        for x in range(16):
            crest = 2 + int(math.sin((x + frame * 4) * 0.45) * 1.5)
            for y in range(crest, 16):
                if y == crest:
                    px[x, y] = (140, 255, 225, 240)
                elif y == crest + 1:
                    px[x, y] = (55, 215, 185, 220)
                elif y < crest + 5:
                    px[x, y] = (25, 135, 130, 200)
                else:
                    px[x, y] = (14, 68, 82, 190)
        img.save(os.path.join(TILES_DIR, f"water_{frame}.png"))


# =============================================================================
# 3. LUSH ENVIRONMENTAL FOLIAGE & STORYTELLING PROPS
# =============================================================================

def generate_environmental_props():
    """
    Generates lush tropical ferns, glowing bioluminescent mushrooms, grass tufts,
    ancient carved frog statues, stone temple pillars, and sinister boss totems.
    """
    # 1. Lush Tropical Ferns (3 sway frames, 16x16)
    fern_base = [
        "................",
        ".......gg.......",
        ".....ggGGgg.....",
        "....gGGddGGg....",
        "..ggG..dd..Ggg..",
        ".gGGGg.dd.gGGGg.",
        "gGGdGGgddgGGdGGg",
        "GG..dGGGGGGd..GG",
        "....dGGGGGGd....",
        "..ggGddGGddGgg..",
        ".gGGd.dddd.dGGg.",
        ".GG...dddd...GG.",
        "......dddd......",
        ".....dddddd.....",
        "....dddddddd....",
        "................",
    ]
    image_from_grid(fern_base).save(os.path.join(PROPS_DIR, "fern_0.png"))
    # Swayed right frame
    fern_r = ["." + row[:-1] if i < 9 else row for i, row in enumerate(fern_base)]
    image_from_grid(fern_r).save(os.path.join(PROPS_DIR, "fern_1.png"))
    # Swayed left frame
    fern_l = [row[1:] + "." if i < 9 else row for i, row in enumerate(fern_base)]
    image_from_grid(fern_l).save(os.path.join(PROPS_DIR, "fern_2.png"))

    # 2. Bioluminescent Mushrooms (Cyan, Magenta, Gold - 16x16)
    shroom_cyan = [
        "................",
        ".....CCCCCC.....",
        "...CCWWWWWWCC...",
        "..CWWCCCCCCWWC..",
        ".CWCCCCCCCCCCWC.",
        ".CCCCCCCCCCCCCC.",
        "..cCCCCCCCCCCc..",
        "....ccWWWWcc....",
        "......WWWW......",
        "......WccW..CC..",
        "..CC..WccW.CWWC.",
        ".CWWC.WccW.CCCC.",
        ".CCCC.WccW..WW..",
        "..WW..WccW..WW..",
        ".gggggWWWWggggg.",
        "DDDDDDDDDDDDDDDD",
    ]
    shroom_magenta = [
        row.replace('C', 'M').replace('c', 'm') for row in shroom_cyan
    ]
    shroom_gold = [
        row.replace('C', 'Y').replace('c', 'O') for row in shroom_cyan
    ]
    image_from_grid(shroom_cyan).save(os.path.join(PROPS_DIR, "shroom_cyan.png"))
    image_from_grid(shroom_magenta).save(os.path.join(PROPS_DIR, "shroom_magenta.png"))
    image_from_grid(shroom_gold).save(os.path.join(PROPS_DIR, "shroom_gold.png"))

    # 3. Wild Jungle Grass & Tiny Glowing Flowers (16x8)
    grass_1 = [
        "..g.....C....g..",
        "..Gg...CCC..gG..",
        ".gGG..g.G..gGGg.",
        ".GGd.gG.G..GGdG.",
        "gGGd.GGdG.gGGdG.",
        "GGGddGGGddGGGGdG",
        "DDDDDDDDDDDDDDDD",
        "dddddddddddddddd",
    ]
    grass_2 = [
        "....Y.....g.....",
        "...YYY...gG..g..",
        ".g..G...gGG.gG..",
        ".Gg.G..gGGd.GGg.",
        "gGGdG..GGGddGGd.",
        "GGGddggGGGddGGdG",
        "DDDDDDDDDDDDDDDD",
        "dddddddddddddddd",
    ]
    image_from_grid(grass_1).save(os.path.join(PROPS_DIR, "grass_0.png"))
    image_from_grid(grass_2).save(os.path.join(PROPS_DIR, "grass_1.png"))

    # 4. Ancient Carved Frog Idol Statue (24x32 background prop)
    statue = Image.new("RGBA", (24, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(statue)
    # Pedestal
    d.rectangle([2, 24, 21, 31], fill=(45, 58, 82, 255), outline=(25, 32, 48, 255))
    d.rectangle([4, 22, 19, 24], fill=(68, 86, 118, 255))
    # Squat stone frog body
    d.ellipse([4, 8, 19, 23], fill=(56, 74, 102, 255), outline=(28, 38, 56, 255))
    # Glowing cyan eyes on the ancient statue
    d.ellipse([5, 5, 10, 10], fill=(68, 86, 118, 255), outline=(28, 38, 56, 255))
    d.ellipse([13, 5, 18, 10], fill=(68, 86, 118, 255), outline=(28, 38, 56, 255))
    d.rectangle([7, 7, 8, 8], fill=(90, 245, 255, 255))
    d.rectangle([15, 7, 16, 8], fill=(90, 245, 255, 255))
    # Moss draped over statue shoulder
    d.pieslice([4, 8, 16, 16], 180, 360, fill=(52, 158, 68, 255))
    statue.save(os.path.join(PROPS_DIR, "frog_statue.png"))

    # 5. Sinister Mantis Warning Totem (For Boss Approach & Sanctum - 24x32)
    totem = Image.new("RGBA", (24, 32), (0, 0, 0, 0))
    td = ImageDraw.Draw(totem)
    td.rectangle([9, 10, 14, 31], fill=(48, 22, 42, 255), outline=(24, 10, 22, 255))
    # Scythe blades sticking out from totem
    td.polygon([(9, 14), (1, 8), (3, 18)], fill=(185, 45, 85, 255), outline=(255, 180, 90, 255))
    td.polygon([(14, 14), (22, 8), (20, 18)], fill=(185, 45, 85, 255), outline=(255, 180, 90, 255))
    # Insect skull head with glowing crimson eyes
    td.polygon([(6, 4), (17, 4), (14, 13), (9, 13)], fill=(75, 32, 62, 255), outline=(28, 12, 26, 255))
    td.rectangle([8, 6, 10, 8], fill=(255, 55, 95, 255))
    td.rectangle([13, 6, 15, 8], fill=(255, 55, 95, 255))
    totem.save(os.path.join(PROPS_DIR, "mantis_totem.png"))


# =============================================================================
# 4. UPGRADED 16-BIT SPRITE SHEETS (FROGGY, TROOP ENEMIES & DREAD HOUND BOSS)
# =============================================================================
# LEGEND OF MANA PAINTERLY SPRITE SUITE:
# 1. Froggy: 24x24 multi-shaded sprites with golden highlights, deep moss shadows,
#    creamy lime belly, flowing scarlet hero bandana, and golden leather boots!
# 2. Swimming Frames: Breaststroke kick and glide poses for aquatic exploration.
# 3. Troop Enemies:
#    - Spiked Moss Beetle (24x20)
#    - Soldier Ant (24x22) with bronze helm & charging jab
#    - Shadow Spider (24x22) with silk thread & ceiling ambush drop
#    - Neon Buzzfly (20x20)
# 4. Power-ups:
#    - Stomping Boots (24x24) with Hermes wings & star glints
#    - Red Spore Boomerang (20x20) & in-flight projectile (16x16)
# 5. Colossal 16-Bit Side-of-Screen Boss:
#    - The Dread Hound (72x72) with snapping jaws, ruby eyes & dazed stomp phase!

def generate_froggy_sprites():
    """Generates 24x24 Legend of Mana style painterly sprites for Froggy."""
    idle_0 = [
        "........................",
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYKKWw....wYKKWw....",
        "....wYKKWw....wYKKWw....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        "..qqRRRRRRRRRRRRRRRRqq..",
        ".qXXRRRRRRRRRRRRRRRRXXq.",
        ".qq.ddGGGGGGGGGGGGdd.qq.",
        "..q.ddGGLLLLLLLLGGdd.q..",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGGLLLLLLLLGGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "...dGGd..........dGGd...",
        "..dGGd............dGGd..",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        ".dBBbBd..........dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
    ]
    idle_1 = [
        "........................",
        "........................",
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYKKWw....wYKKWw....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        ".qqqRRRRRRRRRRRRRRRRq...",
        "qXXXRRRRRRRRRRRRRRRRXq..",
        "qqq.ddGGGGGGGGGGGGdd.q..",
        ".q..ddGGLLLLLLLLGGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGGLLLLLLLLGGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "...dGGd..........dGGd...",
        "..dGGd............dGGd..",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        ".dBBbBd..........dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
    ]
    idle_2 = [
        "........................",
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYWWYw....wYWWYw....",
        ".....wKKw......wKKw.....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        "..qqRRRRRRRRRRRRRRRRqq..",
        ".qXXRRRRRRRRRRRRRRRRXXq.",
        ".qq.ddGGGGGGGGGGGGdd.qq.",
        "..q.ddGGLLLLLLLLGGdd.q..",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGGLLLLLLLLGGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "...dGGd..........dGGd...",
        "..dGGd............dGGd..",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        ".dBBbBd..........dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
    ]
    run_0 = [
        "........................",
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYKKWw....wYKKWw....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        "qqqRRRRRRRRRRRRRRRRq....",
        "qXXXRRRRRRRRRRRRRRRRXq..",
        "qq..ddGGGGGGGGGGGGdd.q..",
        "....ddGGLLLLLLLLGGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        ".dBBbBd..........dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
    ]
    run_1 = [
        "........................",
        "........ww........ww....",
        ".......wYYw......wYYw...",
        "......wYKKWw....wYKKWw..",
        ".......wwww......wwww...",
        ".......EEEEggggggEEEE...",
        ".qqqRRRRRRRRRRRRRRRRq...",
        "qXXXRRRRRRRRRRRRRRRRXq..",
        "qq..ddGGGGGGGGGGGGdd.q..",
        "....ddGGLLLLLLLLGGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGdd........ddGGd...",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        "..dBBbBd........dBBbBd..",
        "...dBBd..........dBBd...",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
    ]
    run_2 = [
        "........................",
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYKKWw....wYKKWw....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        "..qqRRRRRRRRRRRRRRRRqq..",
        ".qXXRRRRRRRRRRRRRRRRXXq.",
        ".qq.ddGGGGGGGGGGGGdd.qq.",
        "....ddGGLLLLLLLLGGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "....dbbd........dbbd....",
        "...dbbYYd......dbbYYd...",
        "...dBBbBd......dBBbBd...",
        "....dBBd........dBBd....",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
    ]
    run_3 = run_1

    jump_0 = [
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYKKWw....wYKKWw....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        "..qqRRRRRRRRRRRRRRRRqq..",
        ".qXXRRRRRRRRRRRRRRRRXXq.",
        ".qq.ddGGGGGGGGGGGGdd.qq.",
        "....ddGGLLLLLLLLGGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "...dGGd..........dGGd...",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        ".dBBbBd..........dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
    ]

    swim_0 = [
        "........................",
        "........................",
        "........ww....ww........",
        ".......wYYw..wYYw.......",
        "......wYKKWwwYKKWw......",
        ".......wwww..wwww.......",
        ".....ddEEEEggEEEEdd.....",
        "...qqRRRRRRRRRRRRRRqq...",
        "..qXXRRRRRRRRRRRRRRXXq..",
        "..qq.ddGGGGGGGGGGdd.qq..",
        "....ddGGLLLLLLLLGGdd....",
        "...ddGGLLLLLLLLLLGGdd...",
        "..dGGddGGGGGGGGGGddGGd..",
        ".dGGd..ddDDDDDDdd..dGGd.",
        "dbbd....ddDDDDdd....dbbd",
        "dbbYYd...dDDDDd...dbbYYd",
        ".dBBbBd...dddd...dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
    ]
    swim_1 = [
        "........................",
        "........................",
        "........ww....ww........",
        ".......wYYw..wYYw.......",
        "......wYKKWwwYKKWw......",
        ".......wwww..wwww.......",
        ".....ddEEEEggEEEEdd.....",
        "...qqRRRRRRRRRRRRRRqq...",
        "..qXXRRRRRRRRRRRRRRXXq..",
        "..qq.ddGGGGGGGGGGdd.qq..",
        "....ddGGLLLLLLLLGGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGGGGGGGGGGGGdd....",
        ".....ddDDDDDDDDDDdd.....",
        "......ddDD....DDdd......",
        ".......dbbd..dbbd.......",
        "......dbbYYddbbYYd......",
        "......dBBbBddBBbBd......",
        ".......dBBd..dBBd.......",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
    ]

    wall_0 = [
        "........................",
        ".........ww........ww...",
        "........wYYw......wYYw..",
        ".......wYKKWw....wYKKWw.",
        "........wwww......wwww..",
        "........EEEEggggggEEEE..",
        ".....qqRRRRRRRRRRRRRRRRq",
        "....qXXRRRRRRRRRRRRRRRRX",
        "....qq.ddGGGGGGGGGGGGddq",
        ".......ddGGLLLLLLLLGGdd.",
        ".......ddGLLLLLLLLLLGdd.",
        ".......ddGLLLLLLLLLLGdd.",
        "........ddGGGGGGGGGGdd..",
        ".......ddDDGGGGGGGGDDdd.",
        "......dGGddDDDDDDDDdd...",
        ".....dGGd...............",
        "....dGGd................",
        "....dbbd................",
        "...dbbYYd...............",
        "...dBBbBd...............",
        "....dBBd................",
        "........................",
        "........................",
        "........................",
    ]

    tongue_0 = [
        "........................",
        "......ww........ww......",
        ".....wYYw......wYYw.....",
        "....wYKKWw....wYKKWw....",
        ".....wwww......wwww.....",
        ".....EEEEggggggEEEE.....",
        "..qqRRRRRRRRRRRRRRRRqq..",
        ".qXXRRRRRRRRRRRRRRRRXXq.",
        ".qq.ddGGGGGGPPPPPPPPPPp.",
        "....ddGGLLLLPPPPPPPPPPp.",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGLLLLLLLLLLGdd....",
        "....ddGGLLLLLLLLGGdd....",
        ".....ddGGGGGGGGGGdd.....",
        "....ddDDGGGGGGGGDDdd....",
        "...dGGddDDDDDDDDddGGd...",
        "...dGGd..........dGGd...",
        "..dGGd............dGGd..",
        "..dbbd............dbbd..",
        ".dbbYYd..........dbbYYd.",
        ".dBBbBd..........dBBbBd.",
        "..dBBd............dBBd..",
        "........................",
        "........................",
    ]

    frames = {
        "froggy_idle_0.png": idle_0,
        "froggy_idle_1.png": idle_1,
        "froggy_idle_2.png": idle_2,
        "froggy_run_0.png": run_0,
        "froggy_run_1.png": run_1,
        "froggy_run_2.png": run_2,
        "froggy_run_3.png": run_3,
        "froggy_jump_0.png": jump_0,
        "froggy_swim_0.png": swim_0,
        "froggy_swim_1.png": swim_1,
        "froggy_wall_0.png": wall_0,
        "froggy_tongue_0.png": tongue_0,
    }
    for filename, grid in frames.items():
        image_from_grid(grid).save(os.path.join(SPRITES_DIR, filename))


def generate_enemy_and_boss_sprites():
    """Generates upgraded troop enemies, powerups, Emperor Mantis & Dread Hound boss."""
    beetle_0 = [
        "........................",
        ".........YY..YY.........",
        ".........YY..YY.........",
        "........yyyy.yyyy.......",
        ".......ddRRRRRRdd.......",
        ".....ddRROOOOOORRdd.....",
        "....ddROOYYYYYYOORdd....",
        "...ddROOYYYYYYYYOORdd...",
        "...dROOOOOOOOOOOOOORd...",
        "...dROOOOOOOOOOOOOORd...",
        "...dROOOOOOOOOOOOWWRd...",
        "...ddRRRRRRRRRRRRWKWRd..",
        "....dKKKKKKKKKKKKKKd....",
        "....dyyyyyyyyyyyyyyd....",
        "...dKK.dKK...dKK.dKKd...",
        "..dKK...dKK...dKK..dKKd.",
        ".dKK.....dK...dK....dKKd",
        ".dK.......d...d......dKd",
        "........................",
        "........................",
    ]
    beetle_1 = [
        "........................",
        "........................",
        ".........YY..YY.........",
        ".........YY..YY.........",
        "........yyyy.yyyy.......",
        ".......ddRRRRRRdd.......",
        ".....ddRROOOOOORRdd.....",
        "....ddROOYYYYYYOORdd....",
        "...ddROOYYYYYYYYOORdd...",
        "...dROOOOOOOOOOOOOORd...",
        "...dROOOOOOOOOOOOOORd...",
        "...dROOOOOOOOOOOOWWRd...",
        "...ddRRRRRRRRRRRRWKWRd..",
        "....dKKKKKKKKKKKKKKd....",
        "....dyyyyyyyyyyyyyyd....",
        "....dKK..dKK...dKK..d...",
        "...dKK...dKK...dKK..d...",
        "...dK.....dK....dK...d..",
        "........................",
        "........................",
    ]

    ant_0 = [
        "........................",
        "......KK..........KK....",
        ".......KK........KK.....",
        "........KK......KK......",
        ".........ddYYYYdd.......",
        "........dYYZZZZYYd......",
        ".......dYYYYYYYYYYd.....",
        "......dKKKKWWWWKKKKd....",
        ".....dWW..dWWWWd..WWd...",
        ".....dd...dWWWWd...dd...",
        "....ddbbooobbbbooobbdd..",
        "...dbooOOOOOOOOOOOood...",
        "..dboOOOOOOOOOOOOOOOod..",
        "..dboOOOOOOOOOOOOOOOod..",
        "...dbooOOOOOOOOOOOood...",
        "....ddbbooobbbbooobbdd..",
        "....dKK.dKK..dKK.dKKd...",
        "...dKK...dKK..dKK..dKKd.",
        "..dKK.....dK...dK...dKKd",
        "..dK.......d...d.....dKd",
        "........................",
        "........................",
    ]
    ant_1 = [
        "........................",
        "........................",
        "......KK..........KK....",
        ".......KK........KK.....",
        "........KK......KK......",
        ".........ddYYYYdd.......",
        "........dYYZZZZYYd......",
        ".......dYYYYYYYYYYd.....",
        "......dKKKKWWWWKKKKd....",
        ".....dWW..dWWWWd..WWd...",
        ".....dd...dWWWWd...dd...",
        "....ddbbooobbbbooobbdd..",
        "...dbooOOOOOOOOOOOood...",
        "..dboOOOOOOOOOOOOOOOod..",
        "..dboOOOOOOOOOOOOOOOod..",
        "...dbooOOOOOOOOOOOood...",
        "....ddbbooobbbbooobbdd..",
        ".....dKK..dKK..dKK..d...",
        "....dKK...dKK..dKK...d..",
        "....dK.....dK...dK....d.",
        "........................",
        "........................",
    ]
    ant_charge = [
        "........................",
        "........................",
        "........................",
        "........................",
        "....KK............KK....",
        ".....KK..........KK.....",
        "......ddYYYYYYYYdd......",
        ".....dYYZZZZZZZZYYd.....",
        "....dYYYYYYYYYYYYYYd....",
        "...dKKKKWWWWWWWWKKKKd...",
        "..dWWWWdWWWWWWWWdWWWWd..",
        "..dd...dWWWWWWWWd...dd..",
        "...ddbboooooooooobbdd...",
        "..dbooOOOOOOOOOOOOood...",
        ".dboOOOOOOOOOOOOOOOOod..",
        ".dboOOOOOOOOOOOOOOOOod..",
        "..ddbboooooooooobbdd....",
        "...dKK..dKK..dKK..dKKd..",
        "..dKK...dKK..dKK...dKKd.",
        ".dKK.....dK...dK....dKKd",
        ".dK.......d...d......dKd",
        "........................",
    ]

    spider_0 = [
        "...........ww...........",
        "...........ww...........",
        "...........ww...........",
        "....dd.............dd...",
        "...dVVd...........dVVd..",
        "..dVVVd...........dVVVd.",
        "..dvvVd...ddddd...dvVvd.",
        "...dvvd..dvvvvvd..dvvd..",
        "....dd.dvvVVVVvvd..dd...",
        "......dvVVVVVVVVvd......",
        ".....dvVVNNWWNNVVvd.....",
        ".....dvVVNNWWNNVVvd.....",
        "......dvvVVVVVVvvd......",
        ".......dvvvvvvvvd.......",
        "........dddddddd........",
        "...dd...............dd..",
        "..dVVd.............dVVd.",
        ".dVVVd.............dVVVd",
        ".dvvVd.............dvVvd",
        "..dvvd.............dvvd.",
        "...dd...............dd..",
        "........................",
    ]
    spider_1 = [
        "...........ww...........",
        "...........ww...........",
        "...........ww...........",
        "...........ww...........",
        "....dd.............dd...",
        "...dVVd...........dVVd..",
        "..dVVVd...ddddd...dVVVd.",
        "..dvvVd..dvvvvvd..dvVvd.",
        "...dvvd.dvvVVVVvvd.dvvd.",
        "....dd.dvVVVVVVVVvd.dd..",
        "......dvVVNNWWNNVVvd....",
        "......dvVVNNWWNNVVvd....",
        ".......dvvVVVVVVvvd.....",
        "........dvvvvvvvvd......",
        ".........dddddddd.......",
        "...dd...............dd..",
        "..dVVd.............dVVd.",
        ".dVVVd.............dVVVd",
        "..dvvd.............dvvd.",
        "...dd...............dd..",
        "........................",
        "........................",
    ]
    spider_drop = [
        "...........ww...........",
        "...........ww...........",
        "...........ww...........",
        "...........ww...........",
        "...........ww...........",
        "..........ddddd.........",
        ".........dvvvvvd........",
        "........dvvVVVVvvd......",
        ".......dvVVVVVVVVvd.....",
        "......dvVVNNWWNNVVvd....",
        "......dvVVNNWWNNVVvd....",
        ".......dvvWWWWWWvvd.....",
        "........dvWWWWWWvd......",
        ".........dWWWWWWd.......",
        ".........dWWWWWWd.......",
        "........dCCd..dCCd......",
        ".......dVVd....dVVd.....",
        "......dVVd......dVVd....",
        ".....dVVd........dVVd...",
        "....dvvd..........dvvd..",
        "....dd..............dd..",
        "........................",
    ]

    fly_1 = [
        "....................",
        "..CCCC........CCCC..",
        ".CWWWWC......CWWWWC.",
        ".CWWWWCCCC..CCCCWWWC",
        "..CCCCVVVV..VVVVCCCC",
        ".....VVVVVVVVVV.....",
        "....VVVVVVWWWRRR....",
        "....VVLLLLWWWRRR....",
        "....vvVVVVvvvvvv....",
        ".....vv....vv.......",
        "....KK......KK......",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
    ]
    fly_2 = [
        "....................",
        "....................",
        "....................",
        ".....VVVVVVVVVV.....",
        "....VVVVVVWWWRRR....",
        "..CCCCLLLLWWWRRRCC..",
        ".CWWWWVVVVVVVVWWWWC.",
        ".CWWWWC......CWWWWC.",
        "..CCCC........CCCC..",
        ".....vv....vv.......",
        "....KK......KK......",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
    ]

    powerup_boots = [
        "........................",
        "......ZZ........ZZ......",
        "....ZZYYZZ....ZZYYZZ....",
        "...ZZYYYYZZ..ZZYYYYZZ...",
        "....ZZYYZZ....ZZYYZZ....",
        "......ZZ........ZZ......",
        "......dd........dd......",
        ".....dbbd......dbbd.....",
        "....dbbbbd....dbbbbd....",
        "...dbbYYbbd..dbbYYbbd...",
        "...dbYYYYbd..dbYYYYbd...",
        "...dbYYYYbd..dbYYYYbd...",
        "...dbbYYbbd..dbbYYbbd...",
        "....dbbbbd....dbbbbd....",
        "....dBBBBd....dBBBBd....",
        "...dBBBBBBd..dBBBBBBd...",
        "..dBBBBBBBBddBBBBBBBBd..",
        ".dBBBBBBBBBBBBBBBBBBBBd.",
        ".dYYYYYYYYddYYYYYYYYYYd.",
        "..dZZZZZZd..dZZZZZZZZd..",
        "....dddd......dddddd....",
        "........................",
        "........................",
        "........................",
    ]

    powerup_red_boomerang = [
        "....................",
        "......RRRRRRRR......",
        "....RRXXXXXXXXRR....",
        "...RXXrrrrrrrrXXR...",
        "..RXrr........rrXR..",
        ".RXr............rXR.",
        ".RXr............rXR.",
        "RXXr............rXXR",
        "RXXr....YYYY....rXXR",
        "RXXr...YYYYYY...rXXR",
        "RXXr...YYYYYY...rXXR",
        "RXXr....YYYY....rXXR",
        "RXXr............rXXR",
        ".RXr............rXR.",
        ".RXr............rXR.",
        "..RXrr........rrXR..",
        "...RXXrrrrrrrrXXR...",
        "....RRXXXXXXXXRR....",
        "......RRRRRRRR......",
        "....................",
    ]

    boomerang_red = [
        "....RRRRRRRR....",
        "..RRXXXXXXXXRR..",
        ".RXXrrrrrrrrXXR.",
        "RXrr........rrXR",
        "RXr..........rXR",
        "RXr....YY....rXR",
        "RXr...YYYY...rXR",
        "RXr....YY....rXR",
        "RXr..........rXR",
        "RXrr........rrXR",
        ".RXXrrrrrrrrXXR.",
        "..RRXXXXXXXXRR..",
        "....RRRRRRRR....",
        "................",
        "................",
        "................",
    ]

    enemy_dict = {
        "beetle_0.png": beetle_0,
        "beetle_1.png": beetle_1,
        "fly_0.png": fly_1,
        "fly_1.png": fly_2,
        "ant_0.png": ant_0,
        "ant_1.png": ant_1,
        "ant_charge.png": ant_charge,
        "spider_0.png": spider_0,
        "spider_1.png": spider_1,
        "spider_drop.png": spider_drop,
        "powerup_boots.png": powerup_boots,
        "powerup_red_boomerang.png": powerup_red_boomerang,
        "boomerang_red.png": boomerang_red,
    }
    for name, grid in enemy_dict.items():
        image_from_grid(grid).save(os.path.join(SPRITES_DIR, name))

    # Detailed 48x48 Emperor Mantis Boss
    for state in ("armored", "exposed"):
        img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        wing_fill = (65, 195, 225, 160) if state == "armored" else (225, 75, 205, 170)
        wing_edge = (180, 250, 255, 230)
        d.polygon([(18, 14), (2, 4), (4, 24), (18, 26)], fill=wing_fill, outline=wing_edge)
        d.polygon([(29, 14), (45, 4), (43, 24), (29, 26)], fill=wing_fill, outline=wing_edge)
        d.ellipse([15, 26, 32, 44], fill=(28, 92, 46, 255), outline=(14, 42, 22, 255))
        d.line([(18, 32), (29, 32)], fill=(112, 215, 92, 255))
        d.line([(17, 36), (30, 36)], fill=(112, 215, 92, 255))
        d.line([(16, 34), (6, 42), (4, 46)], fill=(38, 128, 52, 255), width=2)
        d.line([(31, 34), (41, 42), (43, 46)], fill=(38, 128, 52, 255), width=2)

        if state == "armored":
            d.polygon([(16, 12), (31, 12), (34, 28), (13, 28)], fill=(52, 158, 64, 255), outline=(20, 62, 28, 255))
            d.polygon([(18, 14), (29, 14), (30, 26), (17, 26)], fill=(235, 175, 42, 255), outline=(255, 235, 120, 255))
            d.rectangle([(22, 16), (25, 22)], fill=(225, 65, 85, 255))
            d.polygon([(16, 16), (3, 14), (0, 28), (9, 22)], fill=(255, 212, 68, 255), outline=(225, 95, 35, 255))
            d.polygon([(31, 16), (44, 14), (47, 28), (38, 22)], fill=(255, 212, 68, 255), outline=(225, 95, 35, 255))
        else:
            d.polygon([(14, 12), (33, 12), (35, 28), (12, 28)], fill=(78, 26, 64, 255), outline=(255, 212, 68, 255))
            d.ellipse([16, 14, 31, 27], fill=(255, 58, 195, 255), outline=(255, 255, 255, 255))
            d.ellipse([20, 17, 27, 24], fill=(255, 240, 180, 255))
            d.polygon([(14, 18), (2, 22), (3, 32), (11, 25)], fill=(205, 155, 48, 255), outline=(145, 72, 24, 255))
            d.polygon([(33, 18), (45, 22), (44, 32), (36, 25)], fill=(205, 155, 48, 255), outline=(145, 72, 24, 255))

        d.polygon([(16, 6), (31, 6), (27, 14), (20, 14)], fill=(42, 142, 58, 255), outline=(18, 52, 26, 255))
        d.line([(18, 6), (12, 0)], fill=(255, 212, 68, 255), width=2)
        d.line([(29, 6), (35, 0)], fill=(255, 212, 68, 255), width=2)
        d.ellipse([14, 5, 20, 11], fill=(235, 38, 62, 255), outline=(255, 195, 95, 255))
        d.ellipse([27, 5, 33, 11], fill=(235, 38, 62, 255), outline=(255, 195, 95, 255))
        d.point([(16, 7), (29, 7)], fill=(255, 255, 255, 255))
        img.save(os.path.join(SPRITES_DIR, f"mantis_{state}.png"))

    # Colossal 72x72 Dread Hound Boss (Side-of-Screen 16-Bit Behemoth)
    for state in ("idle", "lunge", "dazed", "howl"):
        img = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Spiked Bronze Collar
        d.rectangle([54, 10, 71, 62], fill=(195, 135, 28, 255), outline=(255, 215, 64, 255))
        d.line([(58, 10), (58, 62)], fill=(255, 245, 160, 255), width=2)
        for sy in (14, 26, 38, 50):
            d.polygon([(54, sy), (44, sy + 4), (54, sy + 8)], fill=(185, 195, 212, 255), outline=(36, 38, 48, 255))

        # Cranium
        d.ellipse([14, 12, 60, 60], fill=(52, 56, 68, 255), outline=(28, 30, 38, 255))
        d.polygon([(36, 12), (54, 8), (48, 26)], fill=(36, 38, 48, 255))

        if state == "idle":
            d.polygon([(38, 22), (6, 28), (4, 46), (36, 50)], fill=(58, 62, 76, 255), outline=(28, 30, 38, 255))
            d.polygon([(10, 28), (4, 30), (8, 34)], fill=(16, 18, 26, 255))
            d.polygon([(34, 18), (22, 24), (32, 28)], fill=(255, 45, 65, 255), outline=(255, 230, 235, 255))
            d.point([(26, 23), (27, 23)], fill=(255, 255, 255, 255))
            d.polygon([(16, 32), (13, 42), (19, 34)], fill=(255, 255, 255, 255), outline=(28, 30, 38, 255))
            d.polygon([(26, 34), (23, 44), (29, 36)], fill=(255, 255, 255, 255), outline=(28, 30, 38, 255))
            d.polygon([(20, 48), (23, 38), (26, 48)], fill=(245, 245, 235, 255), outline=(28, 30, 38, 255))

        elif state == "lunge":
            d.polygon([(38, 16), (2, 16), (0, 34), (32, 38)], fill=(62, 66, 82, 255), outline=(28, 30, 38, 255))
            d.polygon([(34, 42), (4, 54), (12, 66), (38, 54)], fill=(52, 56, 68, 255), outline=(28, 30, 38, 255))
            d.polygon([(24, 34), (6, 36), (12, 52), (32, 42)], fill=(125, 22, 38, 255))
            d.polygon([(34, 14), (20, 18), (32, 24)], fill=(255, 25, 45, 255), outline=(255, 240, 240, 255))
            d.polygon([(12, 26), (8, 40), (16, 28)], fill=(255, 255, 255, 255), outline=(28, 30, 38, 255))
            d.polygon([(22, 28), (18, 42), (26, 30)], fill=(255, 255, 255, 255), outline=(28, 30, 38, 255))
            d.polygon([(16, 56), (19, 44), (22, 56)], fill=(255, 255, 255, 255), outline=(28, 30, 38, 255))

        elif state == "dazed":
            d.polygon([(38, 26), (6, 32), (6, 52), (36, 54)], fill=(45, 48, 58, 255), outline=(28, 30, 38, 255))
            d.ellipse([26, 12, 42, 24], fill=(255, 215, 64, 255), outline=(255, 255, 255, 255))
            d.polygon([(34, 14), (32, 22), (36, 18)], fill=(255, 55, 75, 255))
            d.ellipse([22, 28, 30, 36], fill=(225, 220, 140, 255), outline=(28, 30, 38, 255))
            d.line([(24, 30), (28, 34)], fill=(28, 30, 38, 255), width=2)
            d.line([(28, 30), (24, 34)], fill=(28, 30, 38, 255), width=2)
            d.polygon([(12, 44), (2, 58), (14, 62), (20, 48)], fill=(248, 112, 156, 255), outline=(175, 28, 72, 255))

        elif state == "howl":
            d.polygon([(38, 28), (12, 10), (2, 24), (28, 48)], fill=(58, 62, 76, 255), outline=(28, 30, 38, 255))
            d.polygon([(26, 44), (16, 56), (36, 54)], fill=(48, 52, 64, 255), outline=(28, 30, 38, 255))
            d.polygon([(24, 28), (12, 18), (18, 38)], fill=(125, 22, 38, 255))
            d.line([(26, 20), (36, 26)], fill=(255, 215, 64, 255), width=2)

        img.save(os.path.join(SPRITES_DIR, f"hound_{state}.png"))

    p_img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pd = ImageDraw.Draw(p_img)
    pd.ellipse([1, 1, 14, 14], outline=(255, 45, 65, 255), width=2)
    pd.ellipse([3, 3, 12, 12], outline=(255, 145, 40, 255), width=2)
    pd.ellipse([5, 5, 10, 10], fill=(255, 235, 120, 255))
    p_img.save(os.path.join(SPRITES_DIR, "hound_projectile.png"))



# =============================================================================
# 5. ADDITIVE RADIAL LIGHTING MAPS & PROCEDURAL PARALLAX BACKDROPS
# =============================================================================

def generate_lighting_maps():
    """
    Uses NumPy 2D distance fields to generate smooth radial glow textures for
    additive dynamic lighting (`pygame.BLEND_RGB_ADD`).
    """
    lights = {
        "light_cyan.png": (64, (45, 165, 195)),
        "light_emerald.png": (64, (55, 175, 85)),
        "light_gold.png": (64, (185, 140, 45)),
        "light_magenta.png": (72, (195, 45, 155)),
        "light_crimson.png": (96, (185, 30, 55)),
        "light_player.png": (88, (42, 82, 68)),
    }

    for filename, (size, (r_max, g_max, b_max)) in lights.items():
        y_idx, x_idx = np.ogrid[:size, :size]
        center = (size - 1) * 0.5
        dist = np.hypot(x_idx - center, y_idx - center) / (size * 0.5)
        falloff = np.clip(1.0 - dist, 0.0, 1.0) ** 2.2

        rgb = np.zeros((size, size, 3), dtype=np.uint8)
        rgb[:, :, 0] = (falloff * r_max).astype(np.uint8)
        rgb[:, :, 1] = (falloff * g_max).astype(np.uint8)
        rgb[:, :, 2] = (falloff * b_max).astype(np.uint8)

        Image.fromarray(rgb, mode="RGB").save(os.path.join(FX_DIR, filename))


def generate_procedural_parallax_layers():
    """
    Generates tileable multi-layer silhouette & atmospheric parallax overlays
    (640x360) that layer over or stand in for background art.
    """
    w, h = 640, 360
    themes = {
        "canopy": {
            "sky_top": (12, 24, 38),
            "sky_bot": (26, 62, 64),
            "far_col": (18, 42, 52, 220),
            "mid_col": (14, 32, 42, 240),
            "ray_col": (145, 235, 165, 28),
        },
        "temple": {
            "sky_top": (14, 18, 36),
            "sky_bot": (28, 44, 68),
            "far_col": (22, 30, 52, 220),
            "mid_col": (16, 22, 40, 240),
            "ray_col": (95, 210, 245, 24),
        },
        "cavern": {
            "sky_top": (10, 16, 32),
            "sky_bot": (18, 48, 58),
            "far_col": (16, 32, 48, 220),
            "mid_col": (12, 24, 38, 240),
            "ray_col": (80, 240, 220, 24),
        },
        "sanctum": {
            "sky_top": (24, 8, 22),
            "sky_bot": (64, 16, 38),
            "far_col": (42, 12, 30, 225),
            "mid_col": (28, 8, 22, 245),
            "ray_col": (245, 55, 105, 28),
        },
    }

    for name, cfg in themes.items():
        # 1. Base Gradient + Sunbeams / God-Rays Fallback Backdrop
        y_grad = np.linspace(0.0, 1.0, h)[:, np.newaxis]
        sky = np.zeros((h, w, 3), dtype=np.uint8)
        for c in range(3):
            sky[:, :, c] = (
                cfg["sky_top"][c] * (1.0 - y_grad) + cfg["sky_bot"][c] * y_grad
            ).astype(np.uint8)
        base_img = Image.fromarray(sky, mode="RGB").convert("RGBA")

        # Paint diagonal god-rays / light shafts
        ray_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ray_layer)
        for rx in range(40, w, 140):
            rd.polygon(
                [(rx, 0), (rx + 55, 0), (rx + 145, h), (rx + 60, h)],
                fill=cfg["ray_col"],
            )
        ray_layer = ray_layer.filter(ImageFilter.GaussianBlur(radius=6))
        base_img = Image.alpha_composite(base_img, ray_layer)
        base_img.convert("RGB").save(os.path.join(BG_DIR, f"proc_{name}_sky.png"))

        # 2. Midground Silhouette Layer (Ancient Temple Pillars, Giant Jungle Trees, Lianas)
        mid_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        md = ImageDraw.Draw(mid_img)
        rng = random.Random(hash(name) & 0xFFFFFFFF)

        # Distant stepped temple pyramids / cavern stalactites
        for tx in range(0, w, 160):
            pw = 110
            ph = rng.randint(120, 195)
            # Stepped Mesoamerican ruin silhouette
            md.rectangle([tx + 10, h - ph, tx + pw - 10, h], fill=cfg["far_col"])
            md.rectangle([tx + 24, h - ph - 28, tx + pw - 24, h - ph], fill=cfg["far_col"])
            # Glowing window slits in distant ruins
            glow_c = (95, 240, 225, 140) if name != "sanctum" else (255, 65, 115, 160)
            md.rectangle([tx + 48, h - ph - 14, tx + 54, h - ph - 4], fill=glow_c)

        # Giant Foreground/Midground Canopy Tree Trunks & Hanging Vines
        for gx in range(20, w, 128):
            trunk_w = rng.randint(22, 34)
            md.rectangle([gx, 0, gx + trunk_w, h], fill=cfg["mid_col"])
            # Root buttresses at bottom
            md.polygon(
                [(gx - 18, h), (gx, h - 70), (gx + trunk_w, h - 70), (gx + trunk_w + 18, h)],
                fill=cfg["mid_col"],
            )
            # Canopy arch leaves at top
            md.ellipse([gx - 45, -35, gx + trunk_w + 45, 58], fill=cfg["mid_col"])

        mid_img.save(os.path.join(BG_DIR, f"parallax_{name}_mid.png"))


def process_ai_backgrounds():
    """
    Processes any high-res 16-bit pixel-art backgrounds generated by the
    image-generator tool into crisp 640x360 PNGs with slight contrast/brightness
    balancing so foreground sprites and platforms pop clearly.
    """
    from PIL import ImageEnhance
    artifact_dir = r"C:\Users\Ryan\.gemini\antigravity\brain\cf060d41-7879-4e34-9fa5-2f75901d61a0"
    mapping = {
        "bg_canopy_1793678609176.jpg": "bg_canopy.png",
        "bg_temple_1793678622906.jpg": "bg_temple.png",
        "bg_cavern_1793678639086.jpg": "bg_cavern.png",
        "bg_sanctum_1793678655968.jpg": "bg_sanctum.png",
    }
    for src_name, dst_name in mapping.items():
        src_path = os.path.join(artifact_dir, src_name)
        dst_path = os.path.join(BG_DIR, dst_name)
        if os.path.exists(src_path):
            img = Image.open(src_path).convert("RGB")
            # Resize to 640x360 using Nearest Neighbor to preserve crisp pixel art edges
            img = img.resize((640, 360), Image.Resampling.NEAREST)
            # Slightly dim background brightness (0.68) so foreground gameplay tiles & Froggy pop!
            img = ImageEnhance.Brightness(img).enhance(0.68)
            img.save(dst_path)


def build_all_assets(force=False):
    """
    Main entry point: builds all PNG assets into `assets/` if missing or forced.
    """
    ensure_directories()
    marker_file = os.path.join(TILES_DIR, "terrain_0.png")
    if not force and os.path.exists(marker_file) and os.path.exists(os.path.join(SPRITES_DIR, "mantis_armored.png")):
        return

    print("[Asset Pipeline] Generating 16-bit auto-tiles, lush foliage, sprites & lighting maps...")
    generate_autotile_set("jungle")
    generate_autotile_set("sanctum")
    generate_special_tiles()
    generate_environmental_props()
    generate_froggy_sprites()
    generate_enemy_and_boss_sprites()
    generate_lighting_maps()
    generate_procedural_parallax_layers()
    process_ai_backgrounds()
    print(f"[Asset Pipeline] All assets saved to: {ASSET_ROOT}")


if __name__ == "__main__":
    build_all_assets(force=True)
