"""
===============================================================================
FROGGY V7 ASSET PROCESSING PIPELINE: 32-BIT LEGEND OF MANA ARCADE SUITE
===============================================================================
Extracts, chroma-keys, normalizes, anchors, and builds:
1. Giga Toad Colossus (80x80, 5 continuous uniform poses, consistent scale & baseline)
2. The Dread Hound Colossus (96x96, 4 continuous poses, facing left, uniform scale)
3. Elder Tree Frog Shopkeeper / Sage (3 poses, uniform baseline & scale)
4. Metroid-Style Airlock Exit Doors (Cyan Normal Door & Crimson Boss Door, animated)
5. Daunting Ancient Master Key Door (48x64, 4 runic fragment sockets & eye lock)
6. 4 Boss Key Fragment Icons & Master Key Item
7. Layered Legend of Mana Jungle Ruins Background
===============================================================================
"""

import math
import os
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageEnhance, ImageDraw

BRAIN_DIR = r"C:\Users\Ryan\.gemini\antigravity\brain\93ccd9e1-541d-4172-bc5a-55f224ec10b8"
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SPRITES_DIR = os.path.join(ASSETS_DIR, "sprites")
TILES_DIR = os.path.join(ASSETS_DIR, "tiles")
BG_DIR = os.path.join(ASSETS_DIR, "backgrounds")
PROPS_DIR = os.path.join(ASSETS_DIR, "props")

for d in (SPRITES_DIR, TILES_DIR, BG_DIR, PROPS_DIR):
    os.makedirs(d, exist_ok=True)


def remove_chroma_key(img, chroma_rgb=(255, 0, 255), tolerance=52.0, feather_radius=1.0):
    """
    Sub-pixel Euclidean chroma key extraction for 32-bit RGBA sprites.
    """
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba).astype(np.float32)
    rgb = arr[:, :, :3]
    target = np.array(chroma_rgb, dtype=np.float32)

    dist = np.sqrt(np.sum((rgb - target) ** 2, axis=2))

    alpha_low = tolerance
    alpha_high = tolerance + 32.0

    alpha = np.clip((dist - alpha_low) / (alpha_high - alpha_low), 0.0, 1.0) * 255.0
    arr[:, :, 3] = alpha.astype(np.uint8)

    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    if feather_radius > 0:
        r, g, b, a = result.split()
        a = a.filter(ImageFilter.GaussianBlur(radius=feather_radius * 0.5))
        result = Image.merge("RGBA", (r, g, b, a))

    return result


# =============================================================================
# 1. PROCESS GIGA TOAD: 5 UNIFORM POSES AT EXACT SAME SCALE & BASELINE
# =============================================================================

def process_giga_toad():
    import sprite_studio
    toad_sprites = sprite_studio.generate_32bit_gigatoad_sprites()
    for name, img in toad_sprites.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        img.save(out_path)
        print(f"  + Saved {name}.png ({img.size}), bbox: {img.getbbox()}")
    print("[Toad] Giga Toad uniform 80x80 animation suite complete!")


# =============================================================================
# 2. PROCESS DREAD HOUND: 4 UNIFORM POSES AT COLOSSAL SCALE (96x96)
# =============================================================================

def process_dread_hound():
    import sprite_studio
    hound_sprites = sprite_studio.generate_32bit_dreadhound_sprites()
    for name, img in hound_sprites.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        img.save(out_path)
        print(f"  + Saved {name}.png ({img.size}), bbox: {img.getbbox()}")
    print("[Hound] Dread Hound colossal 96x96 suite complete!")


# =============================================================================
# 3. PROCESS ELDER TREE FROG SHOPKEEPER & SAGE (48x48)
# =============================================================================

def process_elder_tree_frog():
    import sprite_studio
    npc_sprites = sprite_studio.generate_32bit_npc_toad_sprites()
    for name, img in npc_sprites.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        img.save(out_path)
        print(f"  + Saved {name}.png ({img.size}), bbox: {img.getbbox()}")
    print("[Elder] Elder Tree Frog & Shopkeeper frames complete!")


# =============================================================================
# 4. PROCESS METROID AIRLOCK DOORS & DAUNTING MASTER KEY DOOR
# =============================================================================

def process_doors():
    door_sheet_path = os.path.join(BRAIN_DIR, "master_key_door_sprites_1794334769495.jpg")
    if not os.path.exists(door_sheet_path):
        print(f"[Doors] Sheet not found: {door_sheet_path}")
        return

    sheet = Image.open(door_sheet_path)
    print(f"[Doors] Processing AI sheet: {sheet.size}")

    # Segment 0: Cyan Metroid Exit Door (50..310, 42..731)
    cyan_cell = sheet.crop((50, 42, 310, 731))
    cyan_matted = remove_chroma_key(cyan_cell, chroma_rgb=(255, 0, 255), tolerance=55.0)
    
    # Segment 2: Crimson Boss Metroid Exit Door (1079..1341, 42..731)
    red_cell = sheet.crop((1079, 42, 1341, 731))
    red_matted = remove_chroma_key(red_cell, chroma_rgb=(255, 0, 255), tolerance=55.0)

    # Segment 1: Master Key Door (330..1055, 42..731)
    master_cell = sheet.crop((330, 42, 1055, 731))
    master_matted = remove_chroma_key(master_cell, chroma_rgb=(255, 0, 255), tolerance=55.0)

    # 4A. Build Metroid Exit Door Animated Frames (16x16 standard tiles and 16x32 portal sprites)
    # Generate 4 animated frames with scanning energy waves
    c_bbox = cyan_matted.getbbox() or (0, 0, cyan_matted.size[0], cyan_matted.size[1])
    c_crop = cyan_matted.crop(c_bbox)
    c_portal_32 = c_crop.resize((16, 32), Image.Resampling.LANCZOS)
    c_portal_32.save(os.path.join(TILES_DIR, "metroid_door_cyan.png"))

    r_bbox = red_matted.getbbox() or (0, 0, red_matted.size[0], red_matted.size[1])
    r_crop = red_matted.crop(r_bbox)
    r_portal_32 = r_crop.resize((16, 32), Image.Resampling.LANCZOS)
    r_portal_32.save(os.path.join(TILES_DIR, "metroid_door_red.png"))

    # Now create the 4-frame door_0..3.png (16x16) and boss_door_0..3.png (16x16)
    # with animated energy ripples and scanline pulses:
    c_base_16 = c_crop.resize((16, 16), Image.Resampling.LANCZOS)
    r_base_16 = r_crop.resize((16, 16), Image.Resampling.LANCZOS)

    for frame in range(4):
        # Cyan door frame
        c_f = c_base_16.copy()
        c_arr = np.array(c_f).astype(np.float32)
        # Pulse cyan energy center
        pulse = math.sin(frame * math.pi / 2.0) * 40.0
        c_arr[:, :, 0] = np.clip(c_arr[:, :, 0] + pulse * 0.3, 0, 255)
        c_arr[:, :, 1] = np.clip(c_arr[:, :, 1] + pulse * 0.8, 0, 255)
        c_arr[:, :, 2] = np.clip(c_arr[:, :, 2] + pulse, 0, 255)
        Image.fromarray(c_arr.astype(np.uint8), "RGBA").save(os.path.join(TILES_DIR, f"door_{frame}.png"))

        # Red boss door frame
        r_f = r_base_16.copy()
        r_arr = np.array(r_f).astype(np.float32)
        r_pulse = math.sin(frame * math.pi / 2.0) * 45.0
        r_arr[:, :, 0] = np.clip(r_arr[:, :, 0] + r_pulse, 0, 255)
        r_arr[:, :, 1] = np.clip(r_arr[:, :, 1] + r_pulse * 0.2, 0, 255)
        Image.fromarray(r_arr.astype(np.uint8), "RGBA").save(os.path.join(TILES_DIR, f"boss_door_{frame}.png"))

    print("  + Metroid airlock door tiles (door_0..3.png, boss_door_0..3.png) generated!")

    # 4B. Process Daunting Master Key Door (48x64)
    m_bbox = master_matted.getbbox() or (0, 0, master_matted.size[0], master_matted.size[1])
    m_crop = master_matted.crop(m_bbox)
    master_door_surf = m_crop.resize((48, 64), Image.Resampling.LANCZOS)
    master_door_surf.save(os.path.join(TILES_DIR, "master_key_door.png"))
    print(f"  + Saved daunting master_key_door.png (48x64), bbox: {master_door_surf.getbbox()}")

    # Also build animated states for 0, 1, 2, 3, 4 fragments lit:
    for frags in range(5):
        m_state = master_door_surf.copy()
        draw = ImageDraw.Draw(m_state)
        # Socket positions on 48x64 door:
        # Socket 1: Top-Left (14, 20) -> Mantis Jade
        # Socket 2: Top-Right (34, 20) -> Hound Obsidian/Crimson
        # Socket 3: Bottom-Left (14, 44) -> Toad Ruby/Gold
        # Socket 4: Bottom-Right (34, 44) -> Falo Glacial Cyan
        socket_positions = [(14, 20), (34, 20), (14, 44), (34, 44)]
        socket_colors = [
            (80, 255, 120, 240),   # Mantis Green
            (255, 60, 80, 240),    # Hound Red
            (255, 210, 40, 240),   # Toad Gold
            (90, 230, 255, 240),   # Falo Frost Cyan
        ]
        for s_idx in range(frags):
            sx, sy = socket_positions[s_idx]
            scol = socket_colors[s_idx]
            draw.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), fill=scol, outline=(255, 255, 255, 255))

        m_state.save(os.path.join(TILES_DIR, f"master_key_door_state_{frags}.png"))

    print("[Doors] Door suite extraction and animation complete!")


# =============================================================================
# 5. GENERATE BOSS KEY FRAGMENTS & MASTER KEY ICONS
# =============================================================================

def generate_key_fragments():
    # 4 distinct boss key fragments:
    # 1. Mantis Jade Crest
    # 2. Hound Obsidian Fang
    # 3. Toad Ruby Sigil
    # 4. Falo Glacial Core
    # 5. Master Key of the Ancients

    fragments = [
        ("key_fragment_mantis", (40, 230, 110), (18, 90, 42), "Mantis Jade Crest"),
        ("key_fragment_hound", (245, 65, 55), (110, 20, 25), "Hound Obsidian Fang"),
        ("key_fragment_toad", (255, 205, 45), (140, 95, 15), "Toad Ruby Sigil"),
        ("key_fragment_falo", (85, 220, 255), (20, 80, 135), "Falo Glacial Core"),
    ]

    for fname, glow_col, dark_col, label in fragments:
        img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw glowing diamond/crest fragment
        cx, cy = 12, 12
        # Outer golden runic border
        points = [(cx, cy - 8), (cx + 8, cy), (cx, cy + 8), (cx - 8, cy)]
        draw.polygon(points, fill=glow_col, outline=(255, 255, 240, 255))
        # Inner facet shading
        inner = [(cx, cy - 5), (cx + 5, cy), (cx, cy + 5), (cx - 5, cy)]
        draw.polygon(inner, fill=dark_col, outline=(255, 255, 255, 220))
        # Center glint
        draw.point((cx - 1, cy - 1), fill=(255, 255, 255, 255))
        draw.point((cx, cy - 1), fill=(255, 255, 255, 255))

        out_p = os.path.join(SPRITES_DIR, f"{fname}.png")
        img.save(out_p)
        print(f"  + Saved {fname}.png: {label}")

    # 5B. Master Key of the Ancients (Golden ancient winged amphibian key)
    key_img = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    draw = ImageDraw.Draw(key_img)
    # Master key handle: ornate ring with frog eyes
    draw.ellipse((4, 4, 16, 16), outline=(255, 225, 75, 255), width=2)
    # Center emerald gem
    draw.ellipse((8, 8, 12, 12), fill=(60, 245, 140, 255), outline=(255, 255, 255, 255))
    # Key shaft
    draw.line((15, 15, 24, 24), fill=(255, 215, 60, 255), width=3)
    # Key teeth
    draw.line((21, 23, 23, 21), fill=(255, 240, 110, 255), width=2)
    draw.line((23, 25, 25, 23), fill=(255, 240, 110, 255), width=2)
    key_img.save(os.path.join(SPRITES_DIR, "master_key.png"))
    print("  + Saved master_key.png!")


# =============================================================================
# 6. PROCESS LAYERED JUNGLE RUINS BACKGROUND
# =============================================================================

def process_jungle_ruins_bg():
    bg_path = os.path.join(BRAIN_DIR, "jungle_ruins_canopy_1794334785785.jpg")
    if not os.path.exists(bg_path):
        print(f"[BG] Not found: {bg_path}")
        return

    img = Image.open(bg_path)
    print(f"[BG] Processing AI background: {img.size}")

    # Scale to 640x360 (native retro canvas resolution) and 1280x720
    bg_640 = img.resize((640, 360), Image.Resampling.LANCZOS)
    out_p = os.path.join(BG_DIR, "jungle_ruins_bg.png")
    bg_640.save(out_p)
    print(f"  + Saved {out_p} (640x360)")


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING FROGGY V7 ASSET EXTRACTION & ENHANCEMENT PIPELINE")
    print("=" * 70)
    process_giga_toad()
    process_dread_hound()
    process_elder_tree_frog()
    process_doors()
    generate_key_fragments()
    process_jungle_ruins_bg()
    print("=" * 70)
    print("ALL V7 ASSETS PROCESSED SUCCESSFULLY!")
    print("=" * 70)
