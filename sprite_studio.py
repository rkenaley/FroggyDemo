"""
===============================================================================
FROGGY: 32-BIT SPRITE STUDIO & IMAGE-GENERATION EXTRACTION WORKFLOW
===============================================================================
A complete pipeline for creating and converting high-resolution digital
paintings / AI-generated character sheets into 32-bit arcade-grade game sprites
(Capcom CPS-2 / Neo-Geo / Sega Saturn aesthetic).

WORKFLOW CAPABILITIES:
1. CHROMA-KEY EXTRACTION:
   Removes solid backgrounds (e.g. #FF00FF magenta or custom hues) using
   Euclidean color-distance thresholding and sub-pixel edge feathering so
   sprites have smooth, antialiased outlines without ugly halos or pixel fringing.

2. BOUNDING BOX DETECTION & AUTO-SLICING:
   Analyzes wide sprite sheets, finds character column bounds, crops to the
   subject silhouette, and normalizes sprites to game-ready resolutions.

3. ANCHOR ALIGNMENT:
   Aligns ground characters to a bottom-center anchor so that running,
   jumping, and idle poses never jitter vertically across animation frames.

4. 32-BIT PROCEDURAL SHADING & SPECULAR ENHANCEMENT:
   Applies true 32-bit RGBA radial shading, ambient occlusion, specular glints,
   and color grading directly to sprite pixels.

5. CLI & PYTHON API:
   Can be run directly via `py -3.12 sprite_studio.py --build-all` or imported
   by the engine.
===============================================================================
"""

import math
import os
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

ASSET_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SPRITES_DIR = os.path.join(ASSET_ROOT, "sprites")


def remove_chroma_key(img, chroma_rgb=(255, 0, 255), tolerance=45.0, feather_radius=1.2):
    """
    Removes solid chroma background with sub-pixel edge feathering for smooth 32-bit alpha.
    """
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba).astype(np.float32)
    rgb = arr[:, :, :3]
    target = np.array(chroma_rgb, dtype=np.float32)

    # Euclidean distance in RGB color space
    dist = np.sqrt(np.sum((rgb - target) ** 2, axis=2))

    # Soft alpha transition zone [tolerance, tolerance + 35]
    alpha_low = tolerance
    alpha_high = tolerance + 35.0

    alpha = np.clip((dist - alpha_low) / (alpha_high - alpha_low), 0.0, 1.0) * 255.0
    arr[:, :, 3] = alpha.astype(np.uint8)

    result = Image.fromarray(arr.astype(np.uint8), "RGBA")

    # Optional mild feathering on the alpha channel for anti-aliased 32-bit edges
    if feather_radius > 0:
        r, g, b, a = result.split()
        a = a.filter(ImageFilter.GaussianBlur(radius=feather_radius * 0.5))
        result = Image.merge("RGBA", (r, g, b, a))

    return result


def extract_and_anchor_sprite(sub_img, target_size=(32, 32), anchor="bottom_center", pad_fraction=0.08):
    """
    Crops to subject bounding box and fits into target_size with bottom-center foot anchoring.
    """
    # Find non-transparent bounding box
    bbox = sub_img.getbbox()
    if bbox is None:
        return Image.new("RGBA", target_size, (0, 0, 0, 0))

    cropped = sub_img.crop(bbox)
    cw, ch = cropped.size
    tw, th = target_size

    # Usable area with padding
    usable_w = int(tw * (1.0 - pad_fraction * 2))
    usable_h = int(th * (1.0 - pad_fraction * 2))

    scale = min(usable_w / max(1, cw), usable_h / max(1, ch))
    new_w = max(1, int(cw * scale))
    new_h = max(1, int(ch * scale))

    scaled = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Canvas placement
    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    if anchor == "bottom_center":
        paste_x = (tw - new_w) // 2
        paste_y = th - new_h - int(th * pad_fraction * 0.5)
    elif anchor == "center":
        paste_x = (tw - new_w) // 2
        paste_y = (th - new_h) // 2
    else:
        paste_x = (tw - new_w) // 2
        paste_y = 0

    canvas.paste(scaled, (paste_x, paste_y), scaled)
    return canvas


def slice_horizontal_sheet(sheet_path, num_cols, target_size=(32, 32), anchor="bottom_center", chroma_rgb=(255, 0, 255)):
    """
    Slices a wide multi-pose sheet into a list of normalized, alpha-matted sprites.
    """
    if not os.path.exists(sheet_path):
        print(f"[SpriteStudio] File not found: {sheet_path}")
        return []

    sheet = Image.open(sheet_path)
    sw, sh = sheet.size
    col_w = sw // num_cols

    sprites = []
    for col_idx in range(num_cols):
        box = (col_idx * col_w, 0, (col_idx + 1) * col_w, sh)
        cell = sheet.crop(box)
        matted = remove_chroma_key(cell, chroma_rgb=chroma_rgb)
        final_sprite = extract_and_anchor_sprite(matted, target_size=target_size, anchor=anchor)
        sprites.append(final_sprite)

    return sprites


# =============================================================================
# PROCEDURAL 32-BIT GRADE SPRITE GENERATOR (HIGH-FIDELITY TRUE-COLOR FALLBACK)
# =============================================================================

def generate_32bit_froggy_sprites():
    """
    Generates true 32-bit RGBA smooth-antialiased sprites for Froggy (32x32 resolution).
    Features smooth curved lighting, golden eye specular glints, rich red silk
    bandana with fluttering tails, and stitched leather boots with brass buckles.
    """
    sprites = {}

    def make_froggy_base(eye_state="open", throat_expand=0, bandana_flutter=0, leg_pose="stand"):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        arr = np.zeros((32, 32, 4), dtype=np.float32)

        # Center coordinates
        cx, cy = 16.0, 16.0

        for y in range(32):
            for x in range(32):
                dx = x - cx
                dy = y - cy

                # --- 1. Torso & Head Ellipse ---
                head_w = 7.5 + throat_expand * 0.6
                head_h = 7.2 + throat_expand * 0.4
                dist_body = math.hypot(dx / head_w, (dy + 1.5) / head_h)

                if dist_body < 1.0:
                    # Antialiased alpha edge
                    alpha = min(1.0, (1.0 - dist_body) * 4.0) * 255.0
                    # 32-bit radial spherical lighting
                    light = max(0.0, 1.0 - math.hypot((dx + 2.0) / head_w, (dy + 3.0) / head_h) * 0.85)

                    # Emerald green body with warm golden highlight
                    r = 45.0 + light * 135.0
                    g = 135.0 + light * 115.0
                    b = 55.0 + light * 45.0

                    # Pale lime belly contour (front center-bottom)
                    belly_dist = math.hypot((dx) / 5.2, (dy + 0.5) / 4.8)
                    if belly_dist < 1.0:
                        b_alpha = min(1.0, (1.0 - belly_dist) * 3.0)
                        belly_r = 195.0 + light * 50.0
                        belly_g = 240.0 + light * 15.0
                        belly_b = 130.0 + light * 30.0
                        r = r * (1.0 - b_alpha) + belly_r * b_alpha
                        g = g * (1.0 - b_alpha) + belly_g * b_alpha
                        b = b * (1.0 - b_alpha) + belly_b * b_alpha

                    arr[y, x] = [r, g, b, alpha]

                # --- 2. Big Expressive Eyes ---
                for eye_x in (cx - 5.5, cx + 5.5):
                    edx = x - eye_x
                    edy = y - (cy - 6.5)
                    eye_dist = math.hypot(edx / 3.4, edy / 3.4)

                    if eye_dist < 1.0:
                        e_alpha = min(1.0, (1.0 - eye_dist) * 4.0) * 255.0
                        if eye_state == "blink":
                            # Eyelid slit
                            if abs(edy) < 0.9:
                                arr[y, x] = [18, 55, 24, e_alpha]
                            else:
                                arr[y, x] = [70, 185, 80, e_alpha]
                        else:
                            # White socket & golden iris with ink pupil
                            iris_dist = math.hypot(edx / 2.2, edy / 2.2)
                            pupil_dist = math.hypot(edx / 1.1, edy / 1.5)

                            if pupil_dist < 0.65:
                                # Specular glint
                                if edx > -0.6 and edx < 0.3 and edy > -0.6 and edy < 0.2:
                                    arr[y, x] = [255, 255, 255, e_alpha]
                                else:
                                    arr[y, x] = [15, 18, 26, e_alpha]
                            elif iris_dist < 1.0:
                                arr[y, x] = [255, 215, 65, e_alpha]
                            else:
                                arr[y, x] = [245, 248, 240, e_alpha]

                # --- 3. Crimson Silk Ninja Bandana ---
                bandana_y = cy - 2.8
                if abs(y - bandana_y) < 1.6 and abs(dx) < 7.2:
                    # Bandana wrap across forehead
                    b_alpha = 255.0
                    b_light = 1.0 if (y - bandana_y) < -0.4 else 0.7
                    arr[y, x] = [240 * b_light, 35 * b_light, 55 * b_light, b_alpha]

                # Fluttering Bandana Tails (Trailing behind left/right)
                tail_dx = dx - 7.5
                tail_dy = dy + 2.5 + math.sin(bandana_flutter + x * 0.4) * 1.5
                if tail_dx > 0 and tail_dx < 6.0 and abs(tail_dy) < 1.4:
                    arr[y, x] = [225, 28, 48, 255]

                # --- 4. Stomping Boots (Legs & Feet) ---
                if leg_pose == "stand":
                    # Left boot & right boot
                    for bx in (cx - 4.5, cx + 4.5):
                        bdx = x - bx
                        bdy = y - (cy + 8.5)
                        b_dist = math.hypot(bdx / 2.6, bdy / 2.4)
                        if b_dist < 1.0:
                            b_alpha = min(1.0, (1.0 - b_dist) * 4.0) * 255.0
                            # Leather brown with brass buckle
                            if abs(bdx) < 1.0 and abs(bdy) < 0.8:
                                arr[y, x] = [255, 220, 60, b_alpha]  # Brass buckle
                            else:
                                arr[y, x] = [140, 85, 42, b_alpha]   # Leather
                elif leg_pose == "swim_kick":
                    # Outstretched swimming legs
                    for sx in (cx - 7.5, cx + 7.5):
                        bdx = x - sx
                        bdy = y - (cy + 9.5)
                        b_dist = math.hypot(bdx / 3.4, bdy / 1.8)
                        if b_dist < 1.0:
                            arr[y, x] = [135, 80, 40, 255]
                elif leg_pose == "run_1":
                    # Alternating stride
                    if math.hypot((x - (cx - 4)) / 2.5, (y - (cy + 7.5)) / 2.5) < 1.0:
                        arr[y, x] = [145, 88, 44, 255]
                    if math.hypot((x - (cx + 5)) / 2.5, (y - (cy + 9.5)) / 2.5) < 1.0:
                        arr[y, x] = [130, 75, 36, 255]

        # Convert array to image
        return Image.fromarray(arr.astype(np.uint8), "RGBA")

    sprites["froggy_idle_0"] = make_froggy_base(eye_state="open", throat_expand=0, bandana_flutter=0.0)
    sprites["froggy_idle_1"] = make_froggy_base(eye_state="open", throat_expand=1, bandana_flutter=0.5)
    sprites["froggy_idle_2"] = make_froggy_base(eye_state="blink", throat_expand=0, bandana_flutter=1.0)

    sprites["froggy_run_0"] = make_froggy_base(leg_pose="run_1", bandana_flutter=1.5)
    sprites["froggy_run_1"] = make_froggy_base(leg_pose="stand", bandana_flutter=2.5)
    sprites["froggy_run_2"] = make_froggy_base(leg_pose="run_1", bandana_flutter=3.5)
    sprites["froggy_run_3"] = make_froggy_base(leg_pose="stand", bandana_flutter=4.5)

    sprites["froggy_swim_0"] = make_froggy_base(leg_pose="stand", throat_expand=1)
    sprites["froggy_swim_1"] = make_froggy_base(leg_pose="swim_kick", throat_expand=0)

    sprites["froggy_jump_0"] = make_froggy_base(leg_pose="swim_kick", throat_expand=0, bandana_flutter=3.0)
    sprites["froggy_wall_0"] = make_froggy_base(leg_pose="stand", throat_expand=0, bandana_flutter=2.0)
    sprites["froggy_tongue_0"] = make_froggy_base(leg_pose="stand", throat_expand=1, bandana_flutter=1.0)

    return sprites


def generate_32bit_gigatoad_sprites():
    """
    Generates 32-bit heavyweight melee brawler boss sprites for GIGA TOAD (64x64).
    Features massive muscular shoulders, battle scars, spiked leather knuckle wraps,
    championship brawler belt, and toxic pustules.
    """
    sprites = {}

    def make_toad_boss(pose="idle", enrage=False):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        arr = np.zeros((64, 64, 4), dtype=np.float32)

        cx, cy = 32.0, 36.0

        for y in range(64):
            for x in range(64):
                dx = x - cx
                dy = y - cy

                # Heavyweight Muscular Body & Shoulders
                bw = 22.0
                bh = 18.0
                dist_body = math.hypot(dx / bw, dy / bh)

                if dist_body < 1.0:
                    alpha = min(1.0, (1.0 - dist_body) * 4.0) * 255.0
                    light = max(0.0, 1.0 - math.hypot((dx + 4.0) / bw, (dy + 6.0) / bh) * 0.9)

                    # Olive toxic bullfrog skin (or crimson if enraged!)
                    if enrage:
                        r = 165.0 + light * 85.0
                        g = 45.0 + light * 35.0
                        b = 35.0 + light * 25.0
                    else:
                        r = 65.0 + light * 75.0
                        g = 95.0 + light * 115.0
                        b = 48.0 + light * 40.0

                    # Spiked toxic pustules on shoulders
                    if (abs(dx) > 10.0 and dy < -4.0 and (int(x * 7 + y * 13) % 19 == 0)):
                        r, g, b = 245.0, 220.0, 50.0  # Glowing yellow venom wart

                    # Pale throat / chest
                    if math.hypot(dx / 12.0, (dy + 2.0) / 10.0) < 1.0:
                        r += 40.0
                        g += 45.0
                        b += 25.0

                    # Championship Brawler Belt across waist
                    if abs(dy - 8.0) < 3.2 and abs(dx) < 18.0:
                        if abs(dx) < 4.0 and abs(dy - 8.0) < 2.5:
                            r, g, b = 255.0, 215.0, 60.0  # Heavy Gold Belt Buckle
                        else:
                            r, g, b = 130.0, 28.0, 28.0   # Crimson Leather Strap

                    arr[y, x] = [min(255.0, r), min(255.0, g), min(255.0, b), alpha]

                # Heavy Brow & Fiery Yellow Eyes
                for ex in (cx - 10.0, cx + 10.0):
                    edx = x - ex
                    edy = y - (cy - 12.0)
                    if math.hypot(edx / 4.5, edy / 3.8) < 1.0:
                        arr[y, x] = [255, 225, 40, 255]
                        if math.hypot(edx / 1.6, edy / 2.6) < 0.8:
                            arr[y, x] = [20, 15, 10, 255]  # Slit Pupil

                # Heavy Brawler Fists with Spiked Knuckle Wraps
                if pose in ("idle", "panting"):
                    fist_positions = [(cx - 20.0, cy + 6.0), (cx + 20.0, cy + 6.0)]
                elif pose == "punch":
                    fist_positions = [(cx - 12.0, cy + 4.0), (cx + 26.0, cy - 2.0)]
                elif pose == "slam":
                    fist_positions = [(cx - 14.0, cy - 18.0), (cx + 14.0, cy - 18.0)]
                else:
                    fist_positions = [(cx - 18.0, cy + 8.0), (cx + 18.0, cy + 8.0)]

                for fx, fy in fist_positions:
                    fdx = x - fx
                    fdy = y - fy
                    if math.hypot(fdx / 7.5, fdy / 7.0) < 1.0:
                        # Spiked leather wrap
                        if abs(fdy) < 2.5 and abs(fdx) < 5.5:
                            arr[y, x] = [45, 38, 48, 255]  # Dark Iron Leather Wrap
                        elif (int(x + y) % 5 == 0):
                            arr[y, x] = [235, 240, 255, 255] # Steel Knuckle Spikes
                        else:
                            arr[y, x] = [60, 90, 45, 255]

        return Image.fromarray(arr.astype(np.uint8), "RGBA")

    sprites["toad_idle"] = make_toad_boss("idle")
    sprites["toad_punch"] = make_toad_boss("punch")
    sprites["toad_slam"] = make_toad_boss("slam")
    sprites["toad_dazed"] = make_toad_boss("panting")
    sprites["toad_enraged"] = make_toad_boss("idle", enrage=True)

    return sprites


def generate_32bit_dreadhound_sprites():
    """
    Generates 32-bit arcade grade sprites for THE DREAD HOUND Colossus (72x72).
    Features heavy obsidian cybernetic armor plating, curved demon horns, razor
    steel fangs, glowing crimson slit optics, and vulnerable cracked forehead crest.
    """
    sprites = {}

    def make_hound_head(pose="idle"):
        img = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        arr = np.zeros((72, 72, 4), dtype=np.float32)

        cx, cy = 40.0, 38.0

        for y in range(72):
            for x in range(72):
                dx = x - cx
                dy = y - cy

                # --- 1. Curved Demonic Cybernetic Horns ---
                hx = x - (cx + 12.0)
                hy = y - (cy - 14.0)
                horn_angle = math.atan2(hy, hx)
                horn_r = math.hypot(hx, hy)
                if 12.0 < horn_r < 22.0 and -2.4 < horn_angle < -0.4:
                    horn_thick = abs(horn_r - 17.0)
                    if horn_thick < 3.2:
                        h_alpha = min(1.0, (3.2 - horn_thick) * 2.0) * 255.0
                        light = max(0.0, 1.0 - abs(horn_angle + 1.2))
                        arr[y, x] = [140 + light * 95, 55 + light * 45, 30 + light * 25, h_alpha]

                # --- 2. Main Armored Cranium & Snout ---
                if pose == "howl":
                    rx = dx * 0.94 - dy * -0.34
                    ry = dx * -0.34 + dy * 0.94
                else:
                    rx, ry = dx, dy

                skull_dist = math.hypot((rx + 2.0) / 22.0, (ry + 2.0) / 18.0)
                snout_dist = math.hypot((rx + 16.0) / 16.0, (ry + 4.0) / 10.0)

                is_head = (skull_dist < 1.0) or (snout_dist < 1.0 and rx < 0.0)

                jaw_gap = 12.0 if pose == "lunge" else (16.0 if pose == "howl" else (6.0 if pose == "dazed" else 1.5))
                lower_jaw_dist = math.hypot((rx + 14.0) / 14.0, (ry - jaw_gap) / 8.5)
                is_lower_jaw = (lower_jaw_dist < 1.0 and rx < 4.0)

                if is_head or is_lower_jaw:
                    dist = min(skull_dist, snout_dist) if is_head else lower_jaw_dist
                    alpha = min(1.0, (1.0 - dist) * 4.0) * 255.0
                    light = max(0.0, 1.0 - math.hypot((rx + 6.0) / 22.0, (ry + 8.0) / 18.0) * 0.95)

                    if is_lower_jaw:
                        r = 45.0 + light * 75.0
                        g = 18.0 + light * 25.0
                        b = 26.0 + light * 35.0
                    else:
                        r = 55.0 + light * 95.0
                        g = 22.0 + light * 30.0
                        b = 32.0 + light * 45.0

                    if abs(rx + 6.0) < 0.8 or abs(ry + 2.0) < 0.8:
                        r, g, b = 25.0, 10.0, 15.0

                    arr[y, x] = [min(255.0, r), min(255.0, g), min(255.0, b), alpha]

                # --- 3. Mouth Interior & Fiery Throat Glow ---
                if pose in ("lunge", "howl", "dazed") and jaw_gap > 3.0:
                    mouth_dist = math.hypot((rx + 10.0) / 11.0, (ry - jaw_gap * 0.5) / (jaw_gap * 0.6))
                    if mouth_dist < 1.0:
                        m_alpha = min(1.0, (1.0 - mouth_dist) * 3.0) * 255.0
                        if pose == "howl":
                            arr[y, x] = [255, 180, 50, m_alpha]
                        elif pose == "lunge":
                            arr[y, x] = [220, 45, 45, m_alpha]
                        else:
                            arr[y, x] = [50, 12, 20, m_alpha]

                # --- 4. Razor Steel Fangs ---
                if rx < -2.0 and rx > -24.0:
                    for fx in (-6.0, -12.0, -18.0):
                        if abs(rx - fx) < 1.4 and (ry > 3.0 and ry < 9.0):
                            arr[y, x] = [240, 245, 255, 255]
                    if is_lower_jaw:
                        for fx in (-4.0, -10.0, -16.0):
                            if abs(rx - fx) < 1.2 and abs(ry - (jaw_gap - 4.0)) < 2.0:
                                arr[y, x] = [230, 235, 250, 255]

                # --- 5. Glowing Crimson Demonic / Cybernetic Eye ---
                eye_dist = math.hypot((rx + 8.0) / 4.2, (ry + 2.0) / 2.6)
                if eye_dist < 1.0:
                    e_alpha = min(1.0, (1.0 - eye_dist) * 3.5) * 255.0
                    if pose == "dazed":
                        arr[y, x] = [255, 220, 60, e_alpha]
                    else:
                        if abs(ry + 2.0) < 0.9:
                            arr[y, x] = [255, 240, 240, e_alpha]
                        else:
                            arr[y, x] = [255, 30, 60, e_alpha]

                # --- 6. Forehead Armor Crest (Vulnerable Weak Point) ---
                crest_dist = math.hypot((rx + 2.0) / 5.5, (ry + 11.0) / 4.0)
                if crest_dist < 1.0:
                    c_alpha = min(1.0, (1.0 - crest_dist) * 3.5) * 255.0
                    if pose == "dazed":
                        if math.hypot((rx + 2.0) / 3.0, (ry + 11.0) / 2.5) < 1.0:
                            arr[y, x] = [255, 225, 70, c_alpha]
                        else:
                            arr[y, x] = [255, 50, 180, c_alpha]
                    else:
                        arr[y, x] = [200, 160, 45, c_alpha]

        return Image.fromarray(arr.astype(np.uint8), "RGBA")

    sprites["hound_idle"] = make_hound_head("idle")
    sprites["hound_lunge"] = make_hound_head("lunge")
    sprites["hound_dazed"] = make_hound_head("dazed")
    sprites["hound_howl"] = make_hound_head("howl")

    # Cursed Fireball Projectile (16x16)
    p_arr = np.zeros((16, 16, 4), dtype=np.float32)
    for y in range(16):
        for x in range(16):
            p_dist = math.hypot(x - 8.0, y - 8.0) / 7.2
            if p_dist < 1.0:
                p_alpha = min(1.0, (1.0 - p_dist) * 3.5) * 255.0
                if p_dist < 0.35:
                    p_arr[y, x] = [255, 255, 240, p_alpha]
                elif p_dist < 0.7:
                    p_arr[y, x] = [255, 175, 45, p_alpha]
                else:
                    p_arr[y, x] = [245, 45, 55, p_alpha]
    sprites["hound_projectile"] = Image.fromarray(p_arr.astype(np.uint8), "RGBA")

    return sprites


def build_and_export_all_32bit_sprites():
    """
    Exports both AI-extracted sheets (if present) and procedural 32-bit sprites
    directly into assets/sprites/!
    """
    os.makedirs(SPRITES_DIR, exist_ok=True)
    print("[SpriteStudio] Generating & exporting 32-bit arcade grade sprites...")

    # 1. Check for AI generated sheets in brain / artifacts directory
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(brain_dir, "ai_froggy_32bit_sheet_1794179210492.jpg"),
        r"C:\Users\Ryan\.gemini\antigravity\brain\cf060d41-7879-4e34-9fa5-2f75901d61a0\ai_froggy_32bit_sheet_1794179210492.jpg"
    ]
    frog_sheet = next((p for p in candidates if os.path.exists(p)), None)

    if frog_sheet:
        print(f"[SpriteStudio] Processing AI Froggy sheet: {frog_sheet}")
        ai_sprites = slice_horizontal_sheet(frog_sheet, num_cols=4, target_size=(32, 32), anchor="bottom_center")
        if len(ai_sprites) >= 4:
            ai_sprites[0].save(os.path.join(SPRITES_DIR, "froggy_idle_0.png"))
            ai_sprites[1].save(os.path.join(SPRITES_DIR, "froggy_run_0.png"))
            ai_sprites[2].save(os.path.join(SPRITES_DIR, "froggy_swim_0.png"))
            ai_sprites[3].save(os.path.join(SPRITES_DIR, "froggy_tongue_0.png"))
            print("[SpriteStudio] Successfully sliced AI Froggy sheet into game sprites!")

    toad_candidates = [
        os.path.join(brain_dir, "ai_gigatoad_32bit_sheet_1794179223677.jpg"),
        r"C:\Users\Ryan\.gemini\antigravity\brain\cf060d41-7879-4e34-9fa5-2f75901d61a0\ai_gigatoad_32bit_sheet_1794179223677.jpg"
    ]
    toad_sheet = next((p for p in toad_candidates if os.path.exists(p)), None)

    if toad_sheet:
        print(f"[SpriteStudio] Processing AI Giga Toad sheet: {toad_sheet}")
        toad_ai_sprites = slice_horizontal_sheet(toad_sheet, num_cols=3, target_size=(64, 64), anchor="bottom_center")
        if len(toad_ai_sprites) >= 3:
            toad_ai_sprites[0].save(os.path.join(SPRITES_DIR, "toad_idle.png"))
            toad_ai_sprites[1].save(os.path.join(SPRITES_DIR, "toad_slam.png"))
            toad_ai_sprites[2].save(os.path.join(SPRITES_DIR, "toad_punch.png"))
            # Make dazed variant
            dazed = toad_ai_sprites[0].copy()
            dazed.save(os.path.join(SPRITES_DIR, "toad_dazed.png"))
            print("[SpriteStudio] Successfully sliced AI Giga Toad sheet into boss sprites!")

    hound_candidates = [
        os.path.join(brain_dir, "dread_hound_spritesheet_1794180405554.jpg"),
        r"C:\Users\Ryan\.gemini\antigravity\brain\cf060d41-7879-4e34-9fa5-2f75901d61a0\dread_hound_spritesheet_1794180405554.jpg"
    ]
    hound_sheet = next((p for p in hound_candidates if os.path.exists(p)), None)

    if hound_sheet:
        print(f"[SpriteStudio] Processing AI Dread Hound sheet: {hound_sheet}")
        h_img = Image.open(hound_sheet)
        # Crop to active character row bounds
        row = h_img.crop((0, 150, 1376, 580))
        sw, sh = row.size
        col_w = sw // 4
        hound_ai_sprites = []
        for i in range(4):
            cell = row.crop((i * col_w, 0, (i + 1) * col_w, sh))
            matted = remove_chroma_key(cell, tolerance=42.0)
            sprite = extract_and_anchor_sprite(matted, target_size=(72, 72), anchor="center")
            hound_ai_sprites.append(sprite)

        if len(hound_ai_sprites) >= 4:
            hound_ai_sprites[0].save(os.path.join(SPRITES_DIR, "hound_idle.png"))
            hound_ai_sprites[1].save(os.path.join(SPRITES_DIR, "hound_lunge.png"))
            hound_ai_sprites[2].save(os.path.join(SPRITES_DIR, "hound_dazed.png"))
            hound_ai_sprites[3].save(os.path.join(SPRITES_DIR, "hound_howl.png"))
            print("[SpriteStudio] Successfully sliced AI Dread Hound sheet into boss sprites!")

    # 2. Build procedural 32-bit sprites as high-fidelity base/fallbacks
    frog_32 = generate_32bit_froggy_sprites()
    for name, img in frog_32.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        if not os.path.exists(out_path):
            img.save(out_path)

    toad_32 = generate_32bit_gigatoad_sprites()
    for name, img in toad_32.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        if not os.path.exists(out_path):
            img.save(out_path)

    hound_32 = generate_32bit_dreadhound_sprites()
    for name, img in hound_32.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        if not os.path.exists(out_path):
            img.save(out_path)

    # Always ensure 32-bit true-color projectile is saved
    hound_32["hound_projectile"].save(os.path.join(SPRITES_DIR, "hound_projectile.png"))

    print("[SpriteStudio] 32-bit sprite assets successfully synchronized!")


if __name__ == "__main__":
    build_and_export_all_32bit_sprites()
