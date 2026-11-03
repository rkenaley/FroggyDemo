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
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

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
    # --- Froggy Hero Greens & Bandana ---
    'G': (72, 196, 78, 255),     # Mid Emerald Skin
    'g': (112, 228, 96, 255),    # Bright Top Highlight Green
    'D': (38, 128, 52, 255),     # Deep Shadow Green
    'd': (22, 76, 36, 255),      # Dark Outline Green
    'L': (185, 242, 125, 255),   # Light Yellow-Green Belly
    'l': (140, 205, 92, 255),    # Shaded Belly
    'W': (255, 255, 255, 255),   # Pure White (Eye / Specular)
    'K': (18, 20, 32, 255),      # Deep Ink Black
    'R': (232, 52, 68, 255),     # Bandana Crimson
    'r': (158, 26, 44, 255),     # Bandana Shadow
    'P': (248, 112, 156, 255),   # Tongue Pink
    'p': (255, 175, 205, 255),   # Tongue Tip Highlight
    # --- Enemies, Gold & Bioluminescence ---
    'Y': (255, 212, 68, 255),    # Bright Gold
    'y': (204, 142, 32, 255),    # Antique Gold Shadow
    'O': (235, 122, 38, 255),    # Amber Orange
    'o': (155, 64, 22, 255),     # Dark Rust
    'C': (72, 232, 255, 255),    # Bioluminescent Cyan
    'c': (28, 145, 195, 255),    # Deep Cerulean
    'V': (168, 84, 238, 255),    # Neon Violet
    'v': (98, 42, 155, 255),     # Dark Purple
    'M': (255, 68, 198, 255),    # Magenta Boss Core
    'm': (175, 28, 122, 255),    # Dark Magenta
    'S': (82, 98, 132, 255),     # Stone Mid
    'B': (48, 60, 86, 255),      # Stone Dark
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
# 4. UPGRADED 16-BIT SPRITE SHEETS (FROGGY, ENEMIES & EMPEROR MANTIS BOSS)
# =============================================================================

def generate_froggy_sprites():
    """
    Generates multi-shaded 18x18 pixel-art sprites for Froggy with:
    - 5-tone emerald shading, bright yellow-green vocal sac & belly
    - Expressive eyes with pupils and specular shine
    - Flowing crimson hero bandana with animated trailing tails
    """
    idle_1 = [
        "..................",
        ".....WW....WW.....",
        "....WKKW..WKKW....",
        "....gggggggggg....",
        "...RRRRRRRRRRRR...",
        ".rrRRRRRRRRRRRRR..",
        "rR.GGGGGGGGGGGGg..",
        "...GGGLLLLLLGGG...",
        "...GGLLLLLLLLGG...",
        "...DDGLLLLLLGDD...",
        "...DDGGGGGGGGDD...",
        "....DGGGGGGGGD....",
        "....GGG....GGG....",
        "...gGG......GGg...",
        "..DDDD......DDDD..",
        "..................",
    ]
    idle_2 = [
        "..................",
        "..................",
        ".....WW....WW.....",
        "....WKKW..WKKW....",
        "....gggggggggg....",
        "..rRRRRRRRRRRRR...",
        ".rrGGGGGGGGGGGGg..",
        "...GGLLLLLLLLGG...",
        "...GGLLLLLLLLGG...",
        "...DDGLLLLLLGDD...",
        "...DDGGGGGGGGDD...",
        "....DGGGGGGGGD....",
        "....GGG....GGG....",
        "...gGGG....GGGg...",
        "..DDDDD....DDDDD..",
        "..................",
    ]
    run_1 = [
        "..................",
        ".....WW....WW.....",
        "....WKKW..WKKW....",
        "....gggggggggg....",
        ".rrRRRRRRRRRRRR...",
        "rr.GGGGGGGGGGGGg..",
        "...GGGLLLLLLGGG...",
        "...GGLLLLLLLLGG...",
        "....DGLLLLLLGDD...",
        "....DGGGGGGGGD....",
        ".....GGGGGGGG.....",
        "...gGG......GGg...",
        "..gGG........GGg..",
        ".DDDD.........DDD.",
        "..................",
        "..................",
    ]
    run_2 = [
        "..................",
        ".....WW....WW.....",
        "....WKKW..WKKW....",
        "....gggggggggg....",
        "..rRRRRRRRRRRRR...",
        "rr.GGGGGGGGGGGGg..",
        "...GGGLLLLLLGGG...",
        "...GGLLLLLLLLGG...",
        "...DDGLLLLLLGDD...",
        "....DGGGGGGGGD....",
        "....GGGG..GGGG....",
        "....GGG....GGG....",
        ".....DDDD..DDDD...",
        "..................",
        "..................",
        "..................",
    ]
    jump_up = [
        ".....WW....WW.....",
        "....WKKW..WKKW....",
        "....gggggggggg....",
        "..rRRRRRRRRRRRR...",
        ".rrGGGGGGGGGGGGg..",
        "r..GGGLLLLLLGGG...",
        "...GGLLLLLLLLGG...",
        "...DDGLLLLLLGDD...",
        "....DGGGGGGGGD....",
        "....GGG....GGG....",
        "...gGG......GGg...",
        "...GG........GG...",
        "..DDD........DDD..",
        "..................",
        "..................",
        "..................",
    ]
    wall_slide = [
        "..................",
        "......WW...WW.....",
        ".....WKKW.WKKW....",
        ".....gggggggggg...",
        "....RRRRRRRRRRRRr.",
        "....GGGGGGGGGGGGD.",
        ".....GGLLLLLLGGGD.",
        ".....GLLLLLLLLGGD.",
        ".....DGLLLLLLGDDD.",
        "......GGGGGGGGDD..",
        ".....GGG....GGGD..",
        "....GGG......DDD..",
        "....DDD...........",
        "..................",
        "..................",
        "..................",
    ]
    mouth_open = [
        "..................",
        ".....WW....WW.....",
        "....WKKW..WKKW....",
        "....gggggggggg....",
        "..rRRRRRRRRRRRR...",
        "rr.GGGGGGGGPPPPPPp",
        "...GGGGGGGPPPPPPPp",
        "...GGGLLLLGGGG....",
        "...GGLLLLLLLLGG...",
        "...DDGLLLLLLGDD...",
        "...DDGGGGGGGGDD...",
        "....DGGGGGGGGD....",
        "....GGG....GGG....",
        "...gGG......GGg...",
        "..DDDD......DDDD..",
        "..................",
    ]

    frames = {
        "froggy_idle_0.png": idle_1,
        "froggy_idle_1.png": idle_2,
        "froggy_run_0.png": run_1,
        "froggy_run_1.png": idle_1,
        "froggy_run_2.png": run_2,
        "froggy_run_3.png": idle_2,
        "froggy_jump_0.png": jump_up,
        "froggy_wall_0.png": wall_slide,
        "froggy_tongue_0.png": mouth_open,
    }
    for filename, grid in frames.items():
        image_from_grid(grid).save(os.path.join(SPRITES_DIR, filename))


def generate_enemy_and_boss_sprites():
    """
    Generates upgraded enemy sprites and a rich, intimidating 40x40 pixel-art
    Emperor Mantis Boss sprite (both Armored and Exposed-Core states).
    """
    beetle_1 = [
        "................",
        "....Y......Y....",
        "....Y..gg..Y....",
        "...RRRRRRRRRR...",
        "..RROOOOOOOORR..",
        ".RROOYYYYYYOORR.",
        ".RROOOOOOOOOORR.",
        "RROOOOOOOOOOWWRR",
        "RRRRRRRRRRRRWKWR",
        ".KKKKKKKKKKKKKK.",
        "..yyyyyyyyyyyy..",
        "..KK...KK...KK..",
        ".KK....KK....KK.",
        ".K.....K......K.",
        "................",
        "................",
    ]
    beetle_2 = [
        "................",
        "................",
        "....Y......Y....",
        "....Y..gg..Y....",
        "...RRRRRRRRRR...",
        "..RROOOOOOOORR..",
        ".RROOYYYYYYOORR.",
        ".RROOOOOOOOOORR.",
        "RROOOOOOOOOOWWRR",
        "RRRRRRRRRRRRWKWR",
        ".KKKKKKKKKKKKKK.",
        "..yyyyyyyyyyyy..",
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
        "....vvVVVVvv....",
        ".....vv..vv.....",
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
        ".....vv..vv.....",
        "....KK....KK....",
        "................",
        "................",
        "................",
        "................",
        "................",
    ]

    image_from_grid(beetle_1).save(os.path.join(SPRITES_DIR, "beetle_0.png"))
    image_from_grid(beetle_2).save(os.path.join(SPRITES_DIR, "beetle_1.png"))
    image_from_grid(fly_1).save(os.path.join(SPRITES_DIR, "fly_0.png"))
    image_from_grid(fly_2).save(os.path.join(SPRITES_DIR, "fly_1.png"))

    # Detailed 36x36 Emperor Mantis Boss (Procedural High-Bit-Depth Pixel Art)
    for state in ("armored", "exposed"):
        img = Image.new("RGBA", (36, 36), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # 1. Sweeping Translucent Insectoid Wings
        wing_fill = (65, 195, 225, 155) if state == "armored" else (215, 85, 195, 165)
        wing_edge = (180, 250, 255, 230)
        d.polygon([(14, 11), (1, 3), (3, 18), (14, 20)], fill=wing_fill, outline=wing_edge)
        d.polygon([(21, 11), (34, 3), (32, 18), (21, 20)], fill=wing_fill, outline=wing_edge)

        # 2. Segmented Insect Abdomen & Spiked Hind Legs
        d.ellipse([11, 20, 24, 32], fill=(28, 92, 46, 255), outline=(14, 42, 22, 255))
        d.line([(13, 24), (22, 24)], fill=(112, 215, 92, 255))
        d.line([(12, 27), (23, 27)], fill=(112, 215, 92, 255))
        # Spiked Hind Legs
        d.line([(12, 26), (5, 31), (3, 35)], fill=(38, 128, 52, 255), width=2)
        d.line([(23, 26), (30, 31), (32, 35)], fill=(38, 128, 52, 255), width=2)
        d.point([(3, 35), (4, 35), (32, 35), (31, 35)], fill=(255, 212, 68, 255))

        # 3. Thoracic Carapace (Armored Gold Shield vs. Cracked Open Magenta Core)
        if state == "armored":
            d.polygon([(12, 10), (23, 10), (25, 22), (10, 22)], fill=(52, 158, 64, 255), outline=(20, 62, 28, 255))
            # Golden Royal Mantis Breastplate
            d.polygon([(14, 11), (21, 11), (22, 20), (13, 20)], fill=(235, 175, 42, 255), outline=(255, 235, 120, 255))
            d.rectangle([16, 13, 19, 17], fill=(225, 65, 85, 255))
        else:
            # Shattered breastplate exposing the pulsing Magenta-Gold Energy Core!
            d.polygon([(10, 10), (25, 10), (26, 22), (9, 22)], fill=(78, 26, 64, 255), outline=(255, 212, 68, 255))
            d.ellipse([12, 11, 23, 21], fill=(255, 58, 195, 255), outline=(255, 255, 255, 255))
            d.ellipse([15, 13, 20, 19], fill=(255, 240, 180, 255))

        # 4. Serrated Raptorial Scythe Forearms
        if state == "armored":
            # Raised lethal scythes
            d.polygon([(12, 13), (2, 11), (0, 21), (7, 17)], fill=(255, 212, 68, 255), outline=(225, 95, 35, 255))
            d.polygon([(23, 13), (33, 11), (35, 21), (28, 17)], fill=(255, 212, 68, 255), outline=(225, 95, 35, 255))
            # White serrated razor teeth
            d.point([(1, 18), (3, 19), (5, 18), (34, 18), (32, 19), (30, 18)], fill=(255, 255, 255, 255))
        else:
            # Recoiled open scythes (stunned!)
            d.polygon([(10, 14), (1, 17), (2, 24), (8, 19)], fill=(205, 155, 48, 255), outline=(145, 72, 24, 255))
            d.polygon([(25, 14), (34, 17), (33, 24), (27, 19)], fill=(205, 155, 48, 255), outline=(145, 72, 24, 255))

        # 5. Crowned Mantis Head, Antennae & Glowing Crimson Compound Eyes
        d.polygon([(12, 5), (23, 5), (20, 11), (15, 11)], fill=(42, 142, 58, 255), outline=(18, 52, 26, 255))
        # Swept-back Royal Antennae
        d.line([(14, 5), (9, 0)], fill=(255, 212, 68, 255), width=1)
        d.line([(21, 5), (26, 0)], fill=(255, 212, 68, 255), width=1)
        # Fierce Compound Eyes
        d.ellipse([10, 4, 15, 9], fill=(235, 38, 62, 255), outline=(255, 195, 95, 255))
        d.ellipse([20, 4, 25, 9], fill=(235, 38, 62, 255), outline=(255, 195, 95, 255))
        d.point([(12, 6), (22, 6)], fill=(255, 255, 255, 255))

        img.save(os.path.join(SPRITES_DIR, f"mantis_{state}.png"))


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
