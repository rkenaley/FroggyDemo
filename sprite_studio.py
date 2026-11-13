"""
===============================================================================
FROGGY: 32-BIT SPRITE STUDIO & PROCEDURAL PAINTERLY SPRITE SUITE
===============================================================================
Builds cohesive, clean, multi-frame 16/32-bit pixel-painterly sprites for:
1. Froggy (32x32, 9 animation states, 21 frames, right-facing 3/4 profile,
   boots anchored at y=31 so Froggy never floats above platforms).
2. Giga Toad Boss (80x80, 8 frames across idle, walk, slam, punch, dazed,
   enraged, canonically left-facing with feet anchored at y=76).
3. The Dread Hound Boss (96x96, 5 frames across idle, howl, lunge, dazed +
   16x16 fireball projectile, canonically left-facing with paws at y=91).
4. Elder Mossbeard & Shopkeeper Elder Mossmantle (48x48, 4 frames each,
   grand elder toad proportions, canonically right-facing with feet at y=46).
===============================================================================
"""

import math
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance

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

    dist = np.sqrt(np.sum((rgb - target) ** 2, axis=2))
    alpha_low = tolerance
    alpha_high = tolerance + 35.0

    alpha = np.clip((dist - alpha_low) / (alpha_high - alpha_low), 0.0, 1.0) * 255.0
    arr[:, :, 3] = alpha.astype(np.uint8)

    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    if feather_radius > 0:
        r, g, b, a = result.split()
        a = a.filter(ImageFilter.GaussianBlur(radius=feather_radius * 0.5))
        result = Image.merge("RGBA", (r, g, b, a))

    return result


def extract_and_anchor_sprite(sub_img, target_size=(32, 32), anchor="bottom_center", pad_fraction=0.08):
    """
    Crops to subject bounding box and fits into target_size with bottom-center foot anchoring.
    """
    bbox = sub_img.getbbox()
    if bbox is None:
        return Image.new("RGBA", target_size, (0, 0, 0, 0))

    cropped = sub_img.crop(bbox)
    cw, ch = cropped.size
    tw, th = target_size

    usable_w = int(tw * (1.0 - pad_fraction * 2))
    usable_h = int(th * (1.0 - pad_fraction * 2))

    scale = min(usable_w / max(1, cw), usable_h / max(1, ch))
    new_w = max(1, int(cw * scale))
    new_h = max(1, int(ch * scale))

    scaled = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

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


def _apply_16bit_pixel_polish(img, dither_step=8, rim_col=(215, 235, 255)):
    """
    Applies a subtle 16-bit SNES pixel-art shading pass to an RGBA sprite:
      - Adds crisp top-left directional specular rim lighting where alpha transitions from 0 -> 255.
      - Adds ordered 2x2 Bayer dithering micro-contrast on opaque interior pixels so flat surfaces
        gain hand-pixeled richness while preserving outlines and keeping (0, 0) transparent.
    """
    arr = np.array(img.convert("RGBA"), dtype=np.int16)
    h, w, _ = arr.shape
    alpha = arr[:, :, 3]
    opaque = alpha > 160

    # Bayer 2x2 ordered dither matrix on interior pixels (skipping dark outlines)
    luma = (arr[:, :, 0] * 3 + arr[:, :, 1] * 6 + arr[:, :, 2]) // 10
    interior = opaque & (luma > 38)
    bayer = np.fromfunction(lambda yy, xx: (((yy & 1) * 2 + (xx & 1)) - 1.5), (h, w), dtype=int)
    shift = (bayer * (dither_step / 1.5)).astype(np.int16)
    for ch in range(3):
        vals = arr[:, :, ch] + np.where(interior, shift, 0)
        arr[:, :, ch] = np.clip(vals, 0, 255)

    # Top-left directional rim highlight on pixels immediately inside top or left silhouette edge
    top_edge = np.zeros_like(opaque)
    left_edge = np.zeros_like(opaque)
    top_edge[1:, :] = (~opaque[:-1, :]) & opaque[1:, :]
    left_edge[:, 1:] = (~opaque[:, :-1]) & opaque[:, 1:]
    # Only rim-tint non-black pixels inside the outline border
    rim_mask = (top_edge | left_edge) & (luma > 32)
    for ch in range(3):
        arr[:, :, ch] = np.where(rim_mask, np.clip((arr[:, :, ch] * 3 + rim_col[ch]) // 4, 0, 255), arr[:, :, ch])

    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    out.putpixel((0, 0), (0, 0, 0, 0))
    return out


def slice_horizontal_sheet(sheet_path, num_cols, target_size=(32, 32), anchor="bottom_center", chroma_rgb=(255, 0, 255)):
    """
    Slices a wide multi-pose sheet into a list of normalized, alpha-matted sprites.
    """
    if not os.path.exists(sheet_path):
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
# 1. FROGGY HERO SPRITE GENERATOR (32x32, 9 ANIMATIONS, RIGHT-FACING)
# =============================================================================

def _draw_boot(draw, x, y, w=6, h=5, point_right=True, gold_sole=True):
    """Draws a stitched leather Stomping Boot with brass buckle and tread anchored at bottom."""
    outline = (24, 16, 12, 255)
    leather_dark = (98, 54, 26, 255)
    leather_mid = (148, 88, 42, 255)
    leather_hi = (188, 122, 64, 255)
    brass = (255, 220, 68, 255)
    sole_col = (245, 200, 52, 255) if gold_sole else (62, 36, 18, 255)

    # Boot shaft & toe box (toe extends in facing direction)
    toe_ext = 2 if point_right else -2
    x0 = min(x, x + toe_ext)
    x1 = max(x + w, x + w + toe_ext)
    draw.rectangle([x, y, x + w, y + h - 1], fill=leather_mid, outline=outline)
    if point_right:
        draw.rectangle([x + 1, y + 1, x + w + 1, y + h - 1], fill=leather_mid, outline=outline)
        draw.line([(x + 2, y + 1), (x + w, y + 1)], fill=leather_hi)
    else:
        draw.rectangle([x - 1, y + 1, x + w - 1, y + h - 1], fill=leather_mid, outline=outline)
        draw.line([(x, y + 1), (x + w - 2, y + 1)], fill=leather_hi)

    # Brass buckle on instep
    bx = x + (w // 2) + (1 if point_right else -1)
    draw.rectangle([bx - 1, y + 1, bx + 1, y + 2], fill=brass)
    # Boot sole at bottom row
    draw.line([(x0 + 1, y + h), (x1 - 1, y + h)], fill=sole_col)
    draw.point([(x0, y + h), (x1, y + h)], fill=outline)


def generate_32bit_froggy_sprites():
    """
    Generates crisp, cohesive 32x32 pixel-painterly sprites for Froggy across
    all 9 animation states:
      - idle (4 frames: froggy_idle_0..3)
      - run (4 frames: froggy_run_0..3)
      - jump (2 frames: froggy_jump_0..1)
      - fall (2 frames: froggy_fall_0..1)
      - wall (2 frames: froggy_wall_0..1)
      - tongue (2 frames: froggy_tongue_0..1)
      - swing (2 frames: froggy_swing_0..1)
      - swim (4 frames: froggy_swim_0..3)
      - hurt (1 frame: froggy_hurt_0)
    Canonically faces RIGHT (3/4 heroic profile) with boots planted at y=31 on ground poses.
    """
    sprites = {}

    # Palette
    OUTLINE = (16, 48, 24, 255)
    SKIN_DARK = (32, 118, 48, 255)
    SKIN_MID = (64, 192, 76, 255)
    SKIN_BRIGHT = (118, 238, 96, 255)
    SKIN_SPEC = (175, 252, 135, 255)
    BELLY_MID = (178, 228, 118, 255)
    BELLY_BRIGHT = (224, 252, 162, 255)
    RED_OUTLINE = (88, 12, 24, 255)
    RED_DARK = (168, 22, 38, 255)
    RED_MID = (238, 42, 62, 255)
    RED_BRIGHT = (255, 118, 132, 255)
    EYE_WHITE = (248, 252, 245, 255)
    EYE_GOLD = (255, 218, 64, 255)
    PUPIL = (14, 18, 26, 255)
    TONGUE_PINK = (252, 108, 158, 255)
    TONGUE_HI = (255, 182, 212, 255)

    def make_froggy_frame(
        pose="idle",
        frame_idx=0,
        body_dx=0,
        body_dy=0,
        eye_state="open",
        throat_inflate=0,
        mouth_open=False,
        bandana_phase=0.0,
    ):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Swim posture is horizontal streamlined
        if pose == "swim":
            cx = 16 + body_dx
            cy = 16 + body_dy
            # Fluttering bandana tails trailing left
            for t_idx, ty_off in enumerate((-2, 1)):
                pts = []
                for step in range(4):
                    tx = cx - 6 - step * 2
                    ty = cy - 3 + ty_off + int(round(math.sin(bandana_phase + step * 0.9 + t_idx) * 1.4))
                    pts.append((tx, ty))
                d.line(pts, fill=RED_MID if t_idx == 0 else RED_DARK, width=2)

            # Hind legs kicking left
            if frame_idx == 0:
                # Streamlined glide
                d.line([(cx - 5, cy + 2), (cx - 13, cy + 4)], fill=SKIN_DARK, width=3)
                d.line([(cx - 5, cy + 5), (cx - 12, cy + 7)], fill=SKIN_MID, width=3)
                _draw_boot(d, cx - 15, cy + 2, w=4, h=4, point_right=False)
                _draw_boot(d, cx - 14, cy + 5, w=4, h=4, point_right=False)
            elif frame_idx == 1:
                # Frog-kick tuck (knees drawn up/out)
                d.ellipse([cx - 10, cy - 1, cx - 3, cy + 7], fill=SKIN_MID, outline=OUTLINE)
                _draw_boot(d, cx - 11, cy + 4, w=5, h=4, point_right=False)
            elif frame_idx == 2:
                # Full frog-kick thrust + water jet lines
                d.line([(cx - 4, cy + 1), (cx - 13, cy - 1)], fill=SKIN_DARK, width=3)
                d.line([(cx - 4, cy + 4), (cx - 13, cy + 7)], fill=SKIN_MID, width=3)
                _draw_boot(d, cx - 15, cy - 3, w=4, h=4, point_right=False)
                _draw_boot(d, cx - 15, cy + 5, w=4, h=4, point_right=False)
            else:
                # Recovery glide
                d.line([(cx - 5, cy + 2), (cx - 11, cy + 3)], fill=SKIN_MID, width=3)
                _draw_boot(d, cx - 13, cy + 2, w=4, h=4, point_right=False)

            # Streamlined torso & head facing right
            d.ellipse([cx - 7, cy - 5, cx + 9, cy + 6], fill=SKIN_MID, outline=OUTLINE)
            d.ellipse([cx - 4, cy - 4, cx + 6, cy + 2], fill=SKIN_BRIGHT)
            d.ellipse([cx - 2, cy, cx + 8, cy + 5], fill=BELLY_BRIGHT)

            # Bandana across brow
            d.polygon([(cx - 5, cy - 4), (cx + 8, cy - 4), (cx + 7, cy - 1), (cx - 6, cy - 1)], fill=RED_MID, outline=RED_OUTLINE)
            d.line([(cx - 3, cy - 3), (cx + 6, cy - 3)], fill=RED_BRIGHT)

            # Eyes looking forward-right
            for ex, ey, er in ((cx + 1, cy - 6, 3), (cx + 6, cy - 5, 3)):
                d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=EYE_WHITE, outline=OUTLINE)
                d.ellipse([ex - 1, ey - 2, ex + 2, ey + 2], fill=EYE_GOLD)
                d.rectangle([ex, ey - 1, ex + 2, ey + 1], fill=PUPIL)
                d.point((ex, ey - 1), fill=(255, 255, 255, 255))

            # Front breaststroke arms
            if frame_idx in (0, 3):
                d.line([(cx + 6, cy + 2), (cx + 13, cy + 1)], fill=SKIN_BRIGHT, width=3)
                d.ellipse([cx + 11, cy - 1, cx + 14, cy + 3], fill=SKIN_SPEC, outline=OUTLINE)
            else:
                d.line([(cx + 3, cy + 3), (cx - 2, cy + 8)], fill=SKIN_BRIGHT, width=3)
                d.ellipse([cx - 4, cy + 6, cx, cy + 10], fill=SKIN_MID, outline=OUTLINE)

            return img

        # Standard upright / action poses (3/4 right-facing profile)
        cx = 16 + body_dx
        cy = 16 + body_dy

        # --- 1. Bandana Tails (Trailing behind on LEFT side: x = 1..10) ---
        knot_x = cx - 6
        knot_y = cy - 5
        d.ellipse([knot_x - 2, knot_y - 2, knot_x + 2, knot_y + 2], fill=RED_DARK, outline=RED_OUTLINE)

        for tail_i in range(2):
            pts = [(knot_x, knot_y + tail_i)]
            for step in range(1, 5):
                tx = knot_x - step * 2
                if pose == "fall":
                    # Wind blows bandana tails UPWARD while falling!
                    ty = knot_y - step * 1.3 + math.sin(bandana_phase + step + tail_i) * 1.0
                elif pose == "jump":
                    # Trails downward-left on upward jump
                    ty = knot_y + step * 1.1 + math.sin(bandana_phase + step + tail_i) * 1.0
                else:
                    ty = knot_y + tail_i * 2 + math.sin(bandana_phase + step * 0.9 + tail_i * 1.2) * 1.5
                pts.append((max(1, int(round(tx))), max(1, min(30, int(round(ty))))))
            col = RED_MID if tail_i == 0 else RED_DARK
            d.line(pts, fill=col, width=2)

        # --- 2. Back (Left) Arm ---
        if pose == "run":
            arm_swing = [3, 1, -3, -1][frame_idx % 4]
            d.line([(cx - 4, cy + 1), (cx - 7 + arm_swing, cy + 5)], fill=SKIN_DARK, width=3)
            d.ellipse([cx - 9 + arm_swing, cy + 3, cx - 5 + arm_swing, cy + 7], fill=SKIN_MID, outline=OUTLINE)
        elif pose in ("jump", "swing"):
            d.line([(cx - 4, cy), (cx - 7, cy - 6)], fill=SKIN_DARK, width=3)
            d.ellipse([cx - 9, cy - 8, cx - 5, cy - 4], fill=SKIN_MID, outline=OUTLINE)
        elif pose == "fall":
            d.line([(cx - 4, cy + 1), (cx - 9, cy - 3)], fill=SKIN_DARK, width=3)
            d.ellipse([cx - 11, cy - 5, cx - 7, cy - 1], fill=SKIN_MID, outline=OUTLINE)
        elif pose == "hurt":
            d.line([(cx - 4, cy + 1), (cx - 9, cy - 2)], fill=SKIN_DARK, width=3)
        else:
            d.line([(cx - 5, cy + 1), (cx - 7, cy + 5)], fill=SKIN_DARK, width=3)
            d.ellipse([cx - 9, cy + 4, cx - 5, cy + 8], fill=SKIN_MID, outline=OUTLINE)

        # --- 3. Hind Legs & Stomping Boots (Anchored at y=31 on ground poses!) ---
        if pose in ("idle", "tongue"):
            spread = 2 if pose == "tongue" else 0
            # Left (back) leg & boot
            d.line([(cx - 3, cy + 6), (cx - 4 - spread, 26)], fill=SKIN_DARK, width=4)
            _draw_boot(d, cx - 7 - spread, 26, w=6, h=5, point_right=True)
            # Right (front) leg & boot
            d.line([(cx + 3, cy + 6), (cx + 4 + spread, 26)], fill=SKIN_MID, width=4)
            _draw_boot(d, cx + 1 + spread, 26, w=6, h=5, point_right=True)

        elif pose == "run":
            # 4-phase alternating stride with ground contact at y=31
            if frame_idx == 0:
                # Wide contact stride: back leg extended left, front leg reaching right
                d.line([(cx - 3, cy + 6), (cx - 7, 26)], fill=SKIN_DARK, width=4)
                _draw_boot(d, cx - 10, 25, w=6, h=5, point_right=True)
                d.line([(cx + 3, cy + 6), (cx + 7, 26)], fill=SKIN_MID, width=4)
                _draw_boot(d, cx + 4, 26, w=6, h=5, point_right=True)
            elif frame_idx == 1:
                # Down/plant on front-right boot, back-left boot lifting
                d.line([(cx - 2, cy + 6), (cx - 5, 24)], fill=SKIN_DARK, width=4)
                _draw_boot(d, cx - 8, 23, w=6, h=5, point_right=True)
                d.line([(cx + 2, cy + 6), (cx + 3, 26)], fill=SKIN_MID, width=4)
                _draw_boot(d, cx, 26, w=6, h=5, point_right=True)
            elif frame_idx == 2:
                # Opposite wide stride
                d.line([(cx + 2, cy + 6), (cx - 6, 26)], fill=SKIN_DARK, width=4)
                _draw_boot(d, cx - 9, 26, w=6, h=5, point_right=True)
                d.line([(cx - 1, cy + 6), (cx + 6, 25)], fill=SKIN_MID, width=4)
                _draw_boot(d, cx + 3, 24, w=6, h=5, point_right=True)
            else:
                # Passing push-off
                d.line([(cx - 2, cy + 6), (cx - 2, 26)], fill=SKIN_DARK, width=4)
                _draw_boot(d, cx - 5, 26, w=6, h=5, point_right=True)
                d.line([(cx + 2, cy + 6), (cx + 5, 24)], fill=SKIN_MID, width=4)
                _draw_boot(d, cx + 2, 23, w=6, h=5, point_right=True)

        elif pose == "jump":
            # Springing upward: hind legs stretched down-left
            off = 1 if frame_idx == 1 else 0
            d.line([(cx - 3, cy + 5), (cx - 6, 25 + off)], fill=SKIN_DARK, width=3)
            _draw_boot(d, cx - 9, 24 + off, w=6, h=5, point_right=True)
            d.line([(cx + 2, cy + 5), (cx + 2, 26 - off)], fill=SKIN_MID, width=3)
            _draw_boot(d, cx - 1, 25 - off, w=6, h=5, point_right=True)

        elif pose == "fall":
            # Knees tucked, golden boot soles aimed down ready to stomp!
            off = 1 if frame_idx == 1 else 0
            d.ellipse([cx - 7, cy + 4, cx - 1, cy + 9], fill=SKIN_DARK, outline=OUTLINE)
            d.ellipse([cx + 1, cy + 4, cx + 7, cy + 9], fill=SKIN_MID, outline=OUTLINE)
            _draw_boot(d, cx - 7, 23 + off, w=6, h=5, point_right=True, gold_sole=True)
            _draw_boot(d, cx + 1, 24 - off, w=6, h=5, point_right=True, gold_sole=True)

        elif pose == "wall":
            # Braced against right wall (x=25..31)
            off = 1 if frame_idx == 1 else 0
            d.line([(cx + 2, cy + 5), (cx + 8, 23 + off)], fill=SKIN_MID, width=3)
            _draw_boot(d, cx + 4, 22 + off, w=6, h=5, point_right=True)
            d.line([(cx - 1, cy + 6), (cx + 5, 26)], fill=SKIN_DARK, width=3)
            _draw_boot(d, cx + 1, 26, w=6, h=5, point_right=True)

        elif pose == "swing":
            # Acrobatic pendulum swing knees tucked forward
            off = 1 if frame_idx == 1 else -1
            d.line([(cx - 2, cy + 5), (cx + 1, 23 + off)], fill=SKIN_DARK, width=3)
            _draw_boot(d, cx - 2, 22 + off, w=6, h=5, point_right=True)
            d.line([(cx + 3, cy + 5), (cx + 6, 22 - off)], fill=SKIN_MID, width=3)
            _draw_boot(d, cx + 3, 21 - off, w=6, h=5, point_right=True)

        elif pose == "hurt":
            d.line([(cx - 3, cy + 6), (cx - 6, 25)], fill=SKIN_DARK, width=3)
            _draw_boot(d, cx - 9, 25, w=6, h=5, point_right=True)
            d.line([(cx + 2, cy + 6), (cx + 5, 24)], fill=SKIN_MID, width=3)
            _draw_boot(d, cx + 2, 24, w=6, h=5, point_right=True)

        # --- 4. Torso, Head & 3/4 Right-Facing Belly ---
        # Main emerald body ellipse
        d.ellipse([cx - 7, cy - 8, cx + 8, cy + 8], fill=SKIN_DARK, outline=OUTLINE)
        d.ellipse([cx - 6, cy - 7, cx + 7, cy + 7], fill=SKIN_MID)
        # Sunlit top-left forehead/shoulder highlight
        d.ellipse([cx - 4, cy - 6, cx + 4, cy + 1], fill=SKIN_BRIGHT)

        # 3/4 Right-shifted creamy lime belly & throat vocal sac
        sac_w = throat_inflate * 2
        d.ellipse([cx - 2, cy - 2, cx + 7 + sac_w, cy + 7], fill=BELLY_MID)
        d.ellipse([cx - 1, cy - 1, cx + 6 + sac_w, cy + 6], fill=BELLY_BRIGHT)

        # --- 5. Crimson Silk Ninja Headband across Forehead ---
        hb_y = cy - 6
        d.polygon(
            [(cx - 6, hb_y), (cx + 7, hb_y), (cx + 8, hb_y + 3), (cx - 7, hb_y + 3)],
            fill=RED_MID,
            outline=RED_OUTLINE,
        )
        d.line([(cx - 4, hb_y + 1), (cx + 6, hb_y + 1)], fill=RED_BRIGHT)

        # --- 6. Big Expressive Frog Eyes (Shifted Right for Clear 3/4 Profile) ---
        # Left eye (closer to center: cx - 1), Right eye (on right edge: cx + 5)
        eye_centers = [(cx - 1, cy - 9), (cx + 5, cy - 9)]
        for ex, ey in eye_centers:
            # Green upper socket ridge
            d.ellipse([ex - 3, ey - 3, ex + 3, ey + 3], fill=SKIN_MID, outline=OUTLINE)
            if eye_state == "blink":
                d.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=SKIN_BRIGHT)
                d.line([(ex - 2, ey), (ex + 2, ey)], fill=OUTLINE, width=1)
            elif eye_state == "wince":
                d.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=EYE_GOLD)
                d.line([(ex - 2, ey - 1), (ex + 1, ey + 1)], fill=PUPIL)
                d.line([(ex - 2, ey + 1), (ex + 1, ey - 1)], fill=PUPIL)
            else:
                d.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=EYE_WHITE)
                # Golden iris & right-looking pupil
                d.ellipse([ex - 1, ey - 2, ex + 2, ey + 2], fill=EYE_GOLD)
                d.rectangle([ex, ey - 1, ex + 2, ey + 1], fill=PUPIL)
                # Pure white specular glint
                d.point((ex, ey - 1), fill=(255, 255, 255, 255))

        # --- 7. Mouth / Tongue Strike Expression ---
        if mouth_open:
            # Wide open martial-arts mouth facing right with pink tongue base
            d.ellipse([cx + 1, cy - 3, cx + 9, cy + 3], fill=RED_OUTLINE, outline=OUTLINE)
            d.ellipse([cx + 3, cy - 2, cx + 12, cy + 2], fill=TONGUE_PINK, outline=RED_OUTLINE)
            d.line([(cx + 4, cy - 1), (cx + 11, cy - 1)], fill=TONGUE_HI)
        elif pose == "hurt":
            d.ellipse([cx + 2, cy - 2, cx + 6, cy + 2], fill=RED_OUTLINE, outline=OUTLINE)
        else:
            # Confident right-facing frog smile line
            d.line([(cx + 2, cy - 1), (cx + 6, cy - 1)], fill=OUTLINE)
            d.point((cx + 1, cy - 2), fill=OUTLINE)

        # --- 8. Front (Right) Arm & Webbed Hand ---
        if pose == "run":
            arm_swing = [-3, -1, 3, 1][frame_idx % 4]
            d.line([(cx + 3, cy + 1), (cx + 6 + arm_swing, cy + 4)], fill=SKIN_MID, width=3)
            d.ellipse([cx + 4 + arm_swing, cy + 2, cx + 8 + arm_swing, cy + 6], fill=SKIN_BRIGHT, outline=OUTLINE)
        elif pose == "swing":
            # Reaching straight UP to hold the grapple tongue line
            d.line([(cx + 2, cy - 1), (cx + 4, cy - 8)], fill=SKIN_MID, width=3)
            d.ellipse([cx + 2, cy - 10, cx + 6, cy - 6], fill=SKIN_BRIGHT, outline=OUTLINE)
        elif pose == "jump":
            d.line([(cx + 3, cy), (cx + 8, cy - 4)], fill=SKIN_MID, width=3)
            d.ellipse([cx + 6, cy - 6, cx + 10, cy - 2], fill=SKIN_BRIGHT, outline=OUTLINE)
        elif pose == "fall":
            d.line([(cx + 3, cy), (cx + 9, cy - 3)], fill=SKIN_MID, width=3)
            d.ellipse([cx + 7, cy - 5, cx + 11, cy - 1], fill=SKIN_BRIGHT, outline=OUTLINE)
        elif pose == "wall":
            # Webbed suction hand gripping right wall (x=26..30)
            d.line([(cx + 4, cy), (cx + 10, cy - 2)], fill=SKIN_MID, width=3)
            d.ellipse([cx + 8, cy - 4, cx + 13, cy + 1], fill=SKIN_SPEC, outline=OUTLINE)
        elif pose == "tongue":
            # Martial arts thrust palm
            d.line([(cx - 2, cy + 1), (cx - 6, cy + 3)], fill=SKIN_MID, width=3)
            d.ellipse([cx - 8, cy + 1, cx - 4, cy + 5], fill=SKIN_BRIGHT, outline=OUTLINE)
        else:
            d.line([(cx + 3, cy + 1), (cx + 6, cy + 4)], fill=SKIN_MID, width=3)
            d.ellipse([cx + 5, cy + 3, cx + 9, cy + 7], fill=SKIN_BRIGHT, outline=OUTLINE)

        return img

    # 1. IDLE (4 frames) - Smooth breathing without vertical jitter
    sprites["froggy_idle_0"] = make_froggy_frame("idle", 0, body_dx=0, body_dy=0, bandana_phase=0.0)
    sprites["froggy_idle_1"] = make_froggy_frame("idle", 1, body_dx=0, body_dy=0, throat_inflate=1, bandana_phase=1.2)
    sprites["froggy_idle_2"] = make_froggy_frame("idle", 2, body_dx=0, body_dy=0, eye_state="blink", bandana_phase=2.4)
    sprites["froggy_idle_3"] = make_froggy_frame("idle", 3, body_dx=0, body_dy=0, throat_inflate=0, bandana_phase=3.6)

    # 2. RUN (4 frames, crisp 4-step grounded stride without vertical snap jitter)
    sprites["froggy_run_0"] = make_froggy_frame("run", 0, body_dx=0, body_dy=0, bandana_phase=0.5)
    sprites["froggy_run_1"] = make_froggy_frame("run", 1, body_dx=0, body_dy=0, bandana_phase=2.0)
    sprites["froggy_run_2"] = make_froggy_frame("run", 2, body_dx=0, body_dy=0, bandana_phase=3.5)
    sprites["froggy_run_3"] = make_froggy_frame("run", 3, body_dx=0, body_dy=0, bandana_phase=5.0)

    # 3. JUMP (2 frames, upward spring)
    sprites["froggy_jump_0"] = make_froggy_frame("jump", 0, body_dy=-2, bandana_phase=1.0)
    sprites["froggy_jump_1"] = make_froggy_frame("jump", 1, body_dy=-2, bandana_phase=2.8)

    # 4. FALL (2 frames, mid-air descent with golden boot soles ready to stomp)
    sprites["froggy_fall_0"] = make_froggy_frame("fall", 0, body_dy=-1, bandana_phase=0.8)
    sprites["froggy_fall_1"] = make_froggy_frame("fall", 1, body_dy=-1, bandana_phase=2.5)

    # 5. WALL SLIDE (2 frames, gripping wall on right)
    sprites["froggy_wall_0"] = make_froggy_frame("wall", 0, body_dx=2, bandana_phase=1.0)
    sprites["froggy_wall_1"] = make_froggy_frame("wall", 1, body_dx=2, body_dy=1, bandana_phase=2.6)

    # 6. TONGUE STRIKE (2 frames, martial arts lunge, wide open mouth)
    sprites["froggy_tongue_0"] = make_froggy_frame("tongue", 0, body_dx=2, mouth_open=True, bandana_phase=1.5)
    sprites["froggy_tongue_1"] = make_froggy_frame("tongue", 1, body_dx=2, mouth_open=True, bandana_phase=3.2)

    # 7. PENDULUM SWING (2 frames, acrobatic grapple swing)
    sprites["froggy_swing_0"] = make_froggy_frame("swing", 0, body_dy=-1, bandana_phase=1.2)
    sprites["froggy_swing_1"] = make_froggy_frame("swing", 1, body_dy=-1, throat_inflate=1, bandana_phase=3.0)

    # 8. SWIM (4 frames, horizontal breaststroke & frog kick)
    sprites["froggy_swim_0"] = make_froggy_frame("swim", 0, bandana_phase=0.0)
    sprites["froggy_swim_1"] = make_froggy_frame("swim", 1, bandana_phase=1.5)
    sprites["froggy_swim_2"] = make_froggy_frame("swim", 2, bandana_phase=3.0)
    sprites["froggy_swim_3"] = make_froggy_frame("swim", 3, bandana_phase=4.5)

    # 9. HURT (1 frame, recoil wince)
    sprites["froggy_hurt_0"] = make_froggy_frame("hurt", 0, body_dx=-2, eye_state="wince", bandana_phase=2.0)

    return sprites


# =============================================================================
# 2. GIGA TOAD COLOSSUS SPRITE GENERATOR (80x80, LEFT-FACING BRAWLER)
# =============================================================================

def generate_32bit_gigatoad_sprites():
    """
    Generates uniform 80x80 pixel-painterly sprites for GIGA TOAD.
    Canonically faces LEFT (3/4 brawler profile facing left) so that when
    `self.facing_right == False`, he faces left toward Froggy, and when
    `self.facing_right == True`, `pygame.transform.flip` flips him to face right.
    Feet are anchored at y=76 (4px from bottom of 80x80 canvas), and (0, 0) is transparent.
    """
    sprites = {}

    def make_toad_frame(pose="idle", frame_idx=0, enrage=False):
        img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        OUTLINE = (18, 24, 16, 255)
        if enrage:
            SKIN_DARK = (128, 24, 24, 255)
            SKIN_MID = (195, 42, 36, 255)
            SKIN_HI = (245, 82, 52, 255)
            BELLY_DARK = (215, 135, 65, 255)
            BELLY_HI = (252, 188, 95, 255)
            WART_COL = (255, 235, 65, 255)
        else:
            SKIN_DARK = (42, 74, 34, 255)
            SKIN_MID = (72, 122, 48, 255)
            SKIN_HI = (112, 172, 68, 255)
            BELLY_DARK = (165, 182, 96, 255)
            BELLY_HI = (212, 228, 138, 255)
            WART_COL = (235, 195, 48, 255)

        BELT_RED = (168, 28, 34, 255)
        GOLD_HI = (255, 225, 68, 255)
        GOLD_DARK = (188, 132, 24, 255)
        WRAP_DARK = (38, 34, 46, 255)
        WRAP_MID = (68, 62, 82, 255)
        SPIKE_WHITE = (240, 246, 255, 255)

        # Base torso center
        bob = 2 if (frame_idx == 1 and pose in ("idle", "enraged")) else 0
        if pose == "dazed":
            bob = 5
        elif pose == "slam":
            bob = -4

        cx = 42
        cy = 44 + bob

        # Enraged flame aura behind body
        if enrage:
            for a_idx in range(7):
                ax = 16 + a_idx * 8
                ay = 14 + (a_idx % 2) * 5 - frame_idx * 3
                d.polygon(
                    [(ax, ay + 24), (ax + 5, ay), (ax + 10, ay + 24)],
                    fill=(255, 120, 30, 175),
                    outline=(255, 230, 75, 220),
                )

        # --- 1. Muscular Hind Legs & Heavy Feet (Planted at y=76) ---
        l_walk = (-4 if frame_idx == 0 else 4) if pose == "walk" else 0
        r_walk = (4 if frame_idx == 0 else -4) if pose == "walk" else 0
        foot_y = 70 if pose == "slam" else 76

        # Back-right leg
        d.ellipse([cx + 4 + r_walk, cy + 12, cx + 22 + r_walk, foot_y - 2], fill=SKIN_DARK, outline=OUTLINE)
        d.polygon(
            [(cx + 2 + r_walk, foot_y), (cx + 8 + r_walk, foot_y - 7), (cx + 24 + r_walk, foot_y - 7), (cx + 26 + r_walk, foot_y)],
            fill=SKIN_MID,
            outline=OUTLINE,
        )
        # Apply directional Bayer pixel dithering + shading helper inline via pixels
        ARM_SHADOW = (32, 74, 42, 255)
        SCAR_COL = (128, 38, 48, 255)
        BELT_TRIM = (255, 236, 128, 255)

        # Front-left leg (facing left) with sculpted calf & toe webbing
        d.ellipse([cx - 22 + l_walk, cy + 12, cx - 3 + l_walk, foot_y - 2], fill=SKIN_DARK, outline=OUTLINE)
        d.ellipse([cx - 20 + l_walk, cy + 14, cx - 6 + l_walk, foot_y - 5], fill=SKIN_MID)
        d.polygon(
            [(cx - 29 + l_walk, foot_y), (cx - 23 + l_walk, foot_y - 8), (cx - 3 + l_walk, foot_y - 7), (cx - 1 + l_walk, foot_y)],
            fill=SKIN_HI,
            outline=OUTLINE,
        )
        # Toe claws pointing left
        for claw_x in (cx - 28 + l_walk, cx - 23 + l_walk, cx + 3 + r_walk, cx + 8 + r_walk):
            d.polygon([(claw_x, foot_y), (claw_x - 4, foot_y), (claw_x - 1, foot_y - 5)], fill=SPIKE_WHITE, outline=OUTLINE)

        # --- 2. Colossal Muscular Torso, Layered Shoulders & Back Armor ---
        d.ellipse([cx - 27, cy - 23, cx + 27, cy + 23], fill=SKIN_DARK, outline=OUTLINE)
        d.ellipse([cx - 25, cy - 21, cx + 24, cy + 20], fill=SKIN_MID)
        d.ellipse([cx - 21, cy - 19, cx + 17, cy + 7], fill=SKIN_HI)

        # Sculpted pectorals & ribbed amphibian throat/belly sac (left-shifted)
        d.ellipse([cx - 25, cy - 11, cx + 9, cy + 19], fill=BELLY_DARK, outline=OUTLINE)
        d.ellipse([cx - 23, cy - 9, cx + 5, cy + 16], fill=BELLY_HI)
        # Belly scale plate striations
        for b_y in (cy - 2, cy + 4, cy + 10):
            d.arc([cx - 22, b_y - 3, cx + 2, b_y + 4], 15, 165, fill=BELLY_DARK, width=1)
        # Crossed battle scar across left chest
        d.line([(cx - 15, cy - 3), (cx - 4, cy + 6)], fill=SCAR_COL, width=2)
        d.line([(cx - 12, cy + 5), (cx - 7, cy - 4)], fill=SCAR_COL, width=1)
        for sx_dot, sy_dot in ((cx - 13, cy + 1), (cx - 8, cy + 2)):
            d.point((sx_dot, sy_dot), fill=(225, 185, 165, 255))

        # Sculpted bioluminescent toxic warts on right shoulder & back (with highlights)
        for wx, wy, wr in ((cx + 12, cy - 13, 3), (cx + 19, cy - 5, 4), (cx + 15, cy + 4, 3), (cx + 6, cy - 17, 3)):
            d.ellipse([wx - wr, wy - wr, wx + wr, wy + wr], fill=WART_COL, outline=OUTLINE)
            d.point((wx - 1, wy - 1), fill=(195, 255, 165, 255))

        # --- 3. Ornate Championship Heavyweight Belt ---
        belt_y = cy + 10
        d.rectangle([cx - 24, belt_y, cx + 23, belt_y + 8], fill=BELT_RED, outline=OUTLINE)
        d.line([(cx - 22, belt_y + 1), (cx + 21, belt_y + 1)], fill=GOLD_DARK, width=1)
        # Brass belt studs on flanks
        for rx_stud in (cx - 19, cx + 10, cx + 17):
            d.ellipse([rx_stud - 2, belt_y + 2, rx_stud + 2, belt_y + 5], fill=GOLD_HI, outline=OUTLINE)
        # Heavy gold championship buckle with glowing ruby centerpiece
        bx = cx - 8
        d.ellipse([bx - 9, belt_y - 2, bx + 9, belt_y + 10], fill=GOLD_DARK, outline=OUTLINE)
        d.ellipse([bx - 7, belt_y, bx + 7, belt_y + 8], fill=GOLD_HI)
        d.ellipse([bx - 3, belt_y + 2, bx + 3, belt_y + 6], fill=BELT_RED, outline=BELT_TRIM)
        d.point((bx - 1, belt_y + 3), fill=(255, 255, 255, 255))

        # --- 4. Heavy Furrowed Brow, Snout & Fierce Eyes (Facing LEFT) ---
        d.ellipse([cx - 24, cy - 26, cx - 10, cy - 13], fill=SKIN_MID, outline=OUTLINE)
        d.ellipse([cx - 11, cy - 27, cx + 4, cy - 13], fill=SKIN_MID, outline=OUTLINE)
        d.arc([cx - 22, cy - 25, cx - 12, cy - 17], 190, 350, fill=SKIN_HI, width=1)

        for ex, ey in ((cx - 17, cy - 19), (cx - 4, cy - 19)):
            if pose == "dazed":
                d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=(255, 245, 180, 255), outline=OUTLINE)
                d.line([(ex - 2, ey - 2), (ex + 2, ey + 2)], fill=OUTLINE, width=2)
                d.line([(ex - 2, ey + 2), (ex + 2, ey - 2)], fill=OUTLINE, width=2)
            else:
                eye_fill = (255, 65, 45, 255) if enrage else GOLD_HI
                d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=eye_fill, outline=OUTLINE)
                d.rectangle([ex - 3, ey - 2, ex - 1, ey + 2], fill=(16, 12, 12, 255))
                d.point((ex - 2, ey - 2), fill=(255, 255, 255, 255))
                d.line([(ex - 5, ey - 3), (ex + 4, ey - 6)], fill=OUTLINE, width=2)

        # Wide toad mouth with protruding tusks / roaring maw
        if pose == "dazed":
            d.ellipse([cx - 24, cy - 11, cx - 4, cy - 2], fill=(72, 16, 26, 255), outline=OUTLINE)
            d.polygon(
                [(cx - 18, cy - 6), (cx - 30, cy + 2), (cx - 22, cy + 5), (cx - 12, cy - 4)],
                fill=(248, 108, 152, 255),
                outline=OUTLINE,
            )
            for sx, sy in ((cx - 18, cy - 33), (cx - 4, cy - 36), (cx + 10, cy - 32)):
                d.line([(sx - 3, sy), (sx + 3, sy)], fill=GOLD_HI, width=2)
                d.line([(sx, sy - 3), (sx, sy + 3)], fill=(255, 255, 255, 255), width=2)
        elif pose in ("slam", "punch") or enrage:
            d.rectangle([cx - 23, cy - 12, cx - 3, cy - 4], fill=(64, 14, 22, 255), outline=OUTLINE)
            for fx in (cx - 21, cx - 15, cx - 8):
                d.polygon([(fx, cy - 4), (fx + 2, cy - 10), (fx + 4, cy - 4)], fill=SPIKE_WHITE, outline=OUTLINE)
                d.polygon([(fx + 1, cy - 12), (fx + 3, cy - 8), (fx + 5, cy - 12)], fill=SPIKE_WHITE)
        else:
            d.line([(cx - 24, cy - 9), (cx - 4, cy - 7)], fill=OUTLINE, width=2)
            for fx in (cx - 21, cx - 10):
                d.polygon([(fx, cy - 8), (fx + 2, cy - 13), (fx + 4, cy - 8)], fill=SPIKE_WHITE, outline=OUTLINE)

        # Crimson rage glow cracks when enraged
        if enrage:
            for rx1, ry1, rx2, ry2 in ((cx + 2, cy - 14, cx + 10, cy - 6), (cx - 18, cy + 2, cx - 12, cy + 8)):
                d.line([(rx1, ry1), (rx2, ry2)], fill=(255, 70, 50, 255), width=2)

        # --- 5. Colossal Brawler Fists with Taped Wraps & Steel Knuckle Spikes ---
        def draw_spiked_fist(fx, fy, radius=10, spikes_left=True):
            d.ellipse([fx - radius, fy - radius, fx + radius, fy + radius], fill=SKIN_DARK, outline=OUTLINE)
            d.ellipse([fx - radius + 1, fy - radius + 1, fx + radius - 1, fy + radius - 1], fill=SKIN_MID)
            d.ellipse([fx - radius + 3, fy - radius + 2, fx + radius - 3, fy + radius - 3], fill=SKIN_HI)
            d.rectangle([fx - radius + 1, fy - 4, fx + radius - 1, fy + 4], fill=WRAP_MID, outline=OUTLINE)
            d.line([(fx - radius + 2, fy - 1), (fx + radius - 2, fy - 1)], fill=(195, 205, 225, 255), width=1)
            d.line([(fx - radius + 2, fy + 1), (fx + radius - 2, fy + 1)], fill=WRAP_DARK, width=2)
            s_dir = -1 if spikes_left else 1
            for sy in (fy - 5, fy, fy + 5):
                sx = fx + s_dir * radius
                d.polygon(
                    [(sx, sy - 2), (sx + s_dir * 6, sy), (sx, sy + 2)],
                    fill=SPIKE_WHITE,
                    outline=OUTLINE,
                )

        if pose == "punch":
            draw_spiked_fist(cx + 22, cy + 4, radius=9, spikes_left=False)
            d.polygon([(cx - 14, cy - 10), (14, cy - 12), (14, cy + 4), (cx - 14, cy + 4)], fill=ARM_SHADOW, outline=OUTLINE)
            d.polygon([(cx - 14, cy - 9), (15, cy - 10), (15, cy + 1), (cx - 14, cy + 1)], fill=SKIN_HI)
            draw_spiked_fist(15, cy - 4, radius=11, spikes_left=True)
            d.arc([2, cy - 18, 18, cy + 10], 110, 250, fill=GOLD_HI, width=2)
            d.arc([5, cy - 14, 16, cy + 6], 110, 250, fill=(255, 255, 255, 255), width=1)
        elif pose == "slam":
            sy_off = -18 if frame_idx == 0 else -12
            d.line([(cx - 16, cy - 8), (cx - 20, cy + sy_off)], fill=SKIN_MID, width=8)
            d.line([(cx + 14, cy - 8), (cx + 18, cy + sy_off)], fill=SKIN_MID, width=8)
            draw_spiked_fist(cx - 20, cy + sy_off, radius=10, spikes_left=True)
            draw_spiked_fist(cx + 18, cy + sy_off, radius=10, spikes_left=False)
        elif pose == "dazed":
            draw_spiked_fist(cx - 24, cy + 12, radius=9, spikes_left=True)
            draw_spiked_fist(cx + 18, cy + 12, radius=9, spikes_left=False)
        else:
            f_bob = -2 if frame_idx == 1 else 0
            draw_spiked_fist(cx - 25, cy + 2 + f_bob, radius=10, spikes_left=True)
            draw_spiked_fist(cx + 20, cy + 4 - f_bob, radius=9, spikes_left=False)

        img = _apply_16bit_pixel_polish(img, dither_step=8, rim_col=(210, 245, 195))
        img.putpixel((0, 0), (0, 0, 0, 0))
        return img

    sprites["toad_idle"] = make_toad_frame("idle", 0)
    sprites["toad_idle_1"] = make_toad_frame("idle", 1)
    sprites["toad_walk_0"] = make_toad_frame("walk", 0)
    sprites["toad_walk_1"] = make_toad_frame("walk", 1)
    sprites["toad_slam"] = make_toad_frame("slam", 0)
    sprites["toad_punch"] = make_toad_frame("punch", 0)
    sprites["toad_dazed"] = make_toad_frame("dazed", 0)
    sprites["toad_enraged"] = make_toad_frame("enraged", 0, enrage=True)

    return sprites


# =============================================================================
# 3. THE DREAD HOUND COLOSSUS SPRITE GENERATOR (96x96, LEFT-FACING)
# =============================================================================

def generate_32bit_dreadhound_sprites():
    """
    Generates uniform 96x96 pixel-painterly sprites for THE DREAD HOUND.
    Canonically faces LEFT so that when `self.facing_right == False` (his default
    stance on the right wall of the sanctum, lunging left toward Froggy), he faces
    LEFT with snapping jaws, blazing crimson optics, and his glowing forehead weak-point crest.
    Paws are anchored at y=91 (5px from bottom of 96x96 canvas), and (0, 0) is transparent.
    """
    sprites = {}

    def make_hound_frame(pose="idle", frame_idx=0):
        img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        OUTLINE = (14, 14, 22, 255)
        ARMOR_DARK = (34, 36, 48, 255)
        ARMOR_MID = (56, 60, 78, 255)
        ARMOR_HI = (92, 98, 124, 255)
        FUR_DARK = (24, 22, 32, 255)
        BRONZE_DARK = (142, 88, 22, 255)
        BRONZE_HI = (238, 178, 48, 255)
        GOLD_BRIGHT = (255, 228, 75, 255)
        CRIMSON = (255, 38, 62, 255)
        FANG_WHITE = (245, 248, 255, 255)

        bob = 2 if frame_idx == 1 else 0
        if pose == "dazed":
            bob = 8
        lunge_dx = -6 if pose == "lunge" else 0
        paw_y = 91

        # --- 1. Armored Hindquarters, Ragged Wolf Mane & Spiked Tail (Right side: x=46..93) ---
        # Obsidian wolf tail with blazing hellfire ember barb
        d.polygon(
            [(79, 52 + bob), (94, 34 + bob), (89, 49 + bob), (93, 58 + bob), (79, 58 + bob)],
            fill=ARMOR_MID,
            outline=OUTLINE,
        )
        d.polygon([(88, 40 + bob), (94, 33 + bob), (91, 44 + bob)], fill=CRIMSON, outline=OUTLINE)

        # Hind leg planted at right (x=64..85, y=54..91) with riveted knee plate
        d.ellipse([63, 53 + bob, 84, paw_y - 4], fill=ARMOR_DARK, outline=OUTLINE)
        d.ellipse([66, 56 + bob, 80, paw_y - 8], fill=ARMOR_MID)
        d.polygon([(60, paw_y), (64, paw_y - 9), (82, paw_y - 8), (85, paw_y)], fill=ARMOR_MID, outline=OUTLINE)
        for cx_claw in (59, 64, 69):
            d.polygon([(cx_claw, paw_y), (cx_claw - 5, paw_y), (cx_claw - 1, paw_y - 6)], fill=FANG_WHITE, outline=OUTLINE)

        # Massive armored torso, layered spine spikes & glowing inferno furnace ribs
        for mx, my in ((50, 32 + bob), (59, 30 + bob), (68, 33 + bob), (76, 39 + bob)):
            d.polygon([(mx - 4, my + 8), (mx, my), (mx + 5, my + 9)], fill=FUR_DARK, outline=OUTLINE)
        d.ellipse([35 + lunge_dx, 35 + bob, 84, 77 + bob], fill=ARMOR_DARK, outline=OUTLINE)
        d.ellipse([38 + lunge_dx, 38 + bob, 80, 72 + bob], fill=ARMOR_MID)
        d.ellipse([43 + lunge_dx, 41 + bob, 72, 54 + bob], fill=ARMOR_HI)
        # Bronze shoulder pauldron with steel rivets
        d.ellipse([37 + lunge_dx, 38 + bob, 58 + lunge_dx, 56 + bob], fill=BRONZE_DARK, outline=OUTLINE)
        d.arc([39 + lunge_dx, 40 + bob, 56 + lunge_dx, 53 + bob], 190, 350, fill=BRONZE_HI, width=2)
        for rx in (52, 60, 68):
            d.line([(rx + lunge_dx, 48 + bob), (rx - 2 + lunge_dx, 66 + bob)], fill=CRIMSON, width=3)
            d.line([(rx + lunge_dx, 49 + bob), (rx - 2 + lunge_dx, 64 + bob)], fill=(255, 195, 75, 255), width=1)

        # Muscular front legs & steel-clawed gauntlets (x=12..54, y=56..91)
        if pose == "lunge":
            d.polygon([(38, 56), (10, 68), (15, 78), (44, 66)], fill=ARMOR_MID, outline=OUTLINE)
            for cy_claw in (68, 73, 78):
                d.polygon([(11, cy_claw), (3, cy_claw + 1), (11, cy_claw - 3)], fill=FANG_WHITE, outline=OUTLINE)
            d.polygon([(46, 62), (24, 78), (28, 86), (52, 70)], fill=ARMOR_DARK, outline=OUTLINE)
        else:
            # Sculpted armored rear & front wolf forelegs (muscular thigh -> tapered ankle -> clawed gauntlet)
            d.polygon(
                [(41, 58 + bob), (53, 58 + bob), (56, 75 + bob), (55, paw_y - 4), (42, paw_y - 4)],
                fill=ARMOR_DARK,
                outline=OUTLINE,
            )
            d.polygon([(38, paw_y), (42, paw_y - 7), (56, paw_y - 7), (58, paw_y)], fill=ARMOR_DARK, outline=OUTLINE)
            d.polygon(
                [(26, 54 + bob), (42, 54 + bob), (44, 72 + bob), (41, paw_y - 4), (27, paw_y - 4)],
                fill=ARMOR_MID,
                outline=OUTLINE,
            )
            d.line([(29, 57 + bob), (29, paw_y - 8)], fill=ARMOR_HI, width=2)
            # Riveted bronze knee-guard on front leg
            d.ellipse([26, 65 + bob, 37, 74 + bob], fill=BRONZE_DARK, outline=OUTLINE)
            d.point((30, 68 + bob), fill=BRONZE_HI)
            d.polygon([(21, paw_y), (25, paw_y - 9), (44, paw_y - 8), (46, paw_y)], fill=ARMOR_MID, outline=OUTLINE)
            for cx_claw in (21, 26, 31):
                d.polygon([(cx_claw, paw_y), (cx_claw - 5, paw_y), (cx_claw - 1, paw_y - 6)], fill=FANG_WHITE, outline=OUTLINE)

        # --- 2. Heavy Spiked Bronze Collar & Chain Links Around Neck (x=42..58) ---
        col_x = 44 + lunge_dx
        col_y = 24 + bob
        d.polygon(
            [(col_x, col_y), (col_x + 15, col_y + 4), (col_x + 11, col_y + 39), (col_x - 4, col_y + 34)],
            fill=BRONZE_DARK,
            outline=OUTLINE,
        )
        d.line([(col_x + 3, col_y + 3), (col_x, col_y + 33)], fill=BRONZE_HI, width=2)
        for sy in (col_y + 4, col_y + 15, col_y + 26):
            d.polygon([(col_x + 10, sy), (col_x + 21, sy - 3), (col_x + 12, sy + 5)], fill=FANG_WHITE, outline=OUTLINE)

        # --- 3. Sculpted Armored Wolf Skull, Horns & Snapping Jaws (Facing LEFT) ---
        hx = 28 + lunge_dx
        hy = 34 + bob
        if pose == "howl":
            hy -= 6

        # Curved serrated demon horns
        d.polygon(
            [(hx + 8, hy - 14), (hx + 35, hy - 27), (hx + 29, hy - 12), (hx + 12, hy - 6)],
            fill=BRONZE_DARK,
            outline=OUTLINE,
        )
        d.line([(hx + 10, hy - 13), (hx + 31, hy - 24)], fill=BRONZE_HI, width=2)
        d.polygon(
            [(hx + 14, hy - 10), (hx + 39, hy - 19), (hx + 33, hy - 6), (hx + 16, hy - 2)],
            fill=ARMOR_DARK,
            outline=OUTLINE,
        )

        # Armored Cranium with cheek plates
        d.ellipse([hx - 9, hy - 16, hx + 24, hy + 16], fill=ARMOR_MID, outline=OUTLINE)
        d.ellipse([hx - 5, hy - 13, hx + 18, hy + 6], fill=ARMOR_HI)
        d.line([(hx + 3, hy - 10), (hx + 14, hy + 2)], fill=CRIMSON, width=1)

        if pose == "howl":
            d.polygon(
                [(hx + 2, hy - 12), (hx - 21, hy - 22), (hx - 25, hy - 8), (hx - 2, hy + 2)],
                fill=ARMOR_MID,
                outline=OUTLINE,
            )
            d.polygon(
                [(hx, hy + 2), (hx - 21, hy + 6), (hx - 17, hy + 16), (hx + 6, hy + 12)],
                fill=ARMOR_DARK,
                outline=OUTLINE,
            )
            d.ellipse([hx - 19, hy - 10, hx - 2, hy + 6], fill=(255, 145, 35, 255), outline=CRIMSON)
            d.ellipse([hx - 14, hy - 6, hx - 6, hy + 2], fill=(255, 245, 140, 255))
        elif pose == "lunge":
            d.polygon(
                [(hx + 4, hy - 10), (hx - 23, hy - 12), (hx - 25, hy + 2), (hx + 2, hy + 4)],
                fill=ARMOR_MID,
                outline=OUTLINE,
            )
            d.line([(hx - 21, hy - 9), (hx, hy - 8)], fill=ARMOR_HI, width=2)
            d.polygon(
                [(hx + 4, hy + 6), (hx - 23, hy + 14), (hx - 18, hy + 24), (hx + 8, hy + 14)],
                fill=ARMOR_DARK,
                outline=OUTLINE,
            )
            d.polygon([(hx - 19, hy + 2), (hx, hy + 4), (hx - 17, hy + 14)], fill=(155, 22, 38, 255))
            for fx in (hx - 21, hx - 14, hx - 8):
                d.polygon([(fx, hy + 2), (fx + 2, hy + 10), (fx + 4, hy + 2)], fill=FANG_WHITE, outline=OUTLINE)
                d.polygon([(fx + 1, hy + 14), (fx + 3, hy + 6), (fx + 5, hy + 14)], fill=FANG_WHITE, outline=OUTLINE)
        elif pose == "dazed":
            d.polygon(
                [(hx + 4, hy - 6), (hx - 23, hy - 2), (hx - 22, hy + 10), (hx + 2, hy + 10)],
                fill=ARMOR_MID,
                outline=OUTLINE,
            )
            d.polygon(
                [(hx - 16, hy + 8), (hx - 26, hy + 21), (hx - 17, hy + 24), (hx - 8, hy + 10)],
                fill=(248, 108, 156, 255),
                outline=OUTLINE,
            )
        else:
            d.polygon(
                [(hx + 4, hy - 8), (hx - 23, hy - 4), (hx - 25, hy + 8), (hx + 2, hy + 10)],
                fill=ARMOR_MID,
                outline=OUTLINE,
            )
            d.line([(hx - 21, hy - 2), (hx, hy - 5)], fill=ARMOR_HI, width=2)
            d.polygon(
                [(hx + 4, hy + 8), (hx - 21, hy + 8), (hx - 18, hy + 15), (hx + 6, hy + 15)],
                fill=ARMOR_DARK,
                outline=OUTLINE,
            )
            for fx in (hx - 21, hx - 13, hx - 6):
                d.polygon([(fx, hy + 7), (fx + 2, hy + 13), (fx + 4, hy + 7)], fill=FANG_WHITE, outline=OUTLINE)

        ex, ey = hx - 2, hy - 5
        if pose == "dazed":
            d.ellipse([ex - 5, ey - 4, ex + 5, ey + 4], fill=GOLD_BRIGHT, outline=OUTLINE)
            d.line([(ex - 3, ey - 2), (ex + 3, ey + 2)], fill=OUTLINE, width=2)
            d.line([(ex - 3, ey + 2), (ex + 3, ey - 2)], fill=OUTLINE, width=2)
        else:
            d.polygon([(ex - 6, ey), (ex + 4, ey - 4), (ex + 3, ey + 3)], fill=CRIMSON, outline=OUTLINE)
            d.point([(ex - 2, ey - 1), (ex - 1, ey - 1)], fill=(255, 255, 255, 255))

        crest_x, crest_y = hx - 2, hy - 14
        if pose == "dazed":
            d.ellipse([crest_x - 7, crest_y - 5, crest_x + 7, crest_y + 5], fill=(255, 55, 195, 255), outline=(255, 255, 255, 255))
            d.ellipse([crest_x - 4, crest_y - 3, crest_x + 4, crest_y + 3], fill=GOLD_BRIGHT)
            for sx, sy in ((crest_x - 12, crest_y - 8), (crest_x, crest_y - 12), (crest_x + 12, crest_y - 8)):
                d.line([(sx - 3, sy), (sx + 3, sy)], fill=GOLD_BRIGHT, width=2)
                d.line([(sx, sy - 3), (sx, sy + 3)], fill=(255, 255, 255, 255), width=2)
        else:
            d.polygon(
                [(crest_x - 6, crest_y + 2), (crest_x, crest_y - 5), (crest_x + 6, crest_y + 2), (crest_x, crest_y + 5)],
                fill=BRONZE_HI,
                outline=OUTLINE,
            )
            d.point((crest_x, crest_y), fill=CRIMSON)

        img = _apply_16bit_pixel_polish(img, dither_step=8, rim_col=(185, 195, 235))
        img.putpixel((0, 0), (0, 0, 0, 0))
        return img

    sprites["hound_idle"] = make_hound_frame("idle", 0)
    sprites["hound_idle_1"] = make_hound_frame("idle", 1)
    sprites["hound_howl"] = make_hound_frame("howl", 0)
    sprites["hound_lunge"] = make_hound_frame("lunge", 0)
    sprites["hound_dazed"] = make_hound_frame("dazed", 0)

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


# =============================================================================
# 4. ELDER TOADS: SAGE MOSSBEARD & SHOPKEEPER MOSSMANTLE (48x48, RIGHT-FACING)
# =============================================================================

def generate_32bit_npc_toad_sprites():
    """
    Generates grand 48x48 pixel-painterly sprites for the two friendly Elder Toads:
      - `npc_elder_0..3.png`: Elder Mossbeard (Sapphire/Gold mystic robe, snowy
        sage beard & brows, gnarled staff with pulsing cyan/amber crystal orb).
      - `npc_shopkeeper_0..3.png`: Shopkeeper Elder Mossmantle (Rotund merchant
        toad with crimson/gold vest, merchant fez cap, apothecary pack, and
        glowing potion flask).
    Both canonically face RIGHT (3/4 profile facing right) with feet anchored at y=46,
    standing ~40px tall and ~34px wide (visibly grander and stouter than 32x32 Froggy).
    """
    sprites = {}
    OUTLINE = (16, 36, 24, 255)

    for frame in range(4):
        bob = 1 if frame in (1, 3) else 0
        blink = (frame == 2)

        # ---------------------------------------------------------------------
        # A. ELDER MOSSBEARD (Sage Toad - 48x48, facing RIGHT)
        # ---------------------------------------------------------------------
        elder = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        d = ImageDraw.Draw(elder)

        cx, cy = 22, 24 + bob

        # Webbed Elder Toad Feet planted at y=46
        d.ellipse([cx - 12, 41, cx - 1, 46], fill=(38, 138, 72, 255), outline=OUTLINE)
        d.ellipse([cx + 2, 41, cx + 14, 46], fill=(48, 162, 84, 255), outline=OUTLINE)

        # Grand Sapphire & Gold Mystic Cloak / Robe (wide elder silhouette)
        d.polygon(
            [(cx - 14, 43), (cx - 11, cy - 2), (cx + 11, cy - 2), (cx + 14, 43)],
            fill=(36, 72, 112, 255),
            outline=OUTLINE,
        )
        d.polygon(
            [(cx - 9, 43), (cx - 6, cy), (cx + 9, cy), (cx + 12, 43)],
            fill=(52, 98, 148, 255),
        )
        # Gold rune trim down robe front (shifted right for 3/4 profile)
        d.rectangle([cx + 1, cy, cx + 5, 43], fill=(242, 198, 64, 255), outline=OUTLINE)

        # Broad Elder Toad Head & Vocal Sac (facing right)
        d.ellipse([cx - 11, cy - 15, cx + 12, cy + 2], fill=(44, 154, 82, 255), outline=OUTLINE)
        d.ellipse([cx - 9, cy - 13, cx + 10, cy - 1], fill=(64, 188, 98, 255))
        d.ellipse([cx - 4, cy - 7, cx + 11, cy + 2], fill=(192, 236, 148, 255))

        # Wise Eyes & Bushy Snowy-White Eyebrows (shifted right)
        for ex, ey in ((cx - 2, cy - 15), (cx + 6, cy - 15)):
            d.ellipse([ex - 3, ey - 3, ex + 3, ey + 3], fill=(255, 255, 255, 255), outline=OUTLINE)
            if blink:
                d.line([(ex - 2, ey), (ex + 2, ey)], fill=OUTLINE, width=1)
            else:
                d.rectangle([ex, ey - 1, ex + 2, ey + 1], fill=(18, 24, 34, 255))
                d.point((ex, ey - 1), fill=(255, 255, 255, 255))
            # Bushy white sage brow arching above eye
            d.polygon(
                [(ex - 4, ey - 2), (ex, ey - 5), (ex + 4, ey - 2), (ex, ey - 3)],
                fill=(245, 248, 255, 255),
                outline=(165, 182, 205, 255),
            )

        # Long Flowing Snowy-White Sage Beard (draping down right-front chest)
        beard_sway = 1 if frame % 2 == 1 else 0
        d.polygon(
            [
                (cx - 5, cy - 3),
                (cx + 10, cy - 3),
                (cx + 8 + beard_sway, cy + 13),
                (cx + 2 + beard_sway, cy + 16),
                (cx - 3, cy + 11),
            ],
            fill=(245, 248, 255, 255),
            outline=(165, 182, 205, 255),
        )
        d.line([(cx + 1, cy - 1), (cx + 3 + beard_sway, cy + 12)], fill=(210, 222, 238, 255), width=1)

        # Left sleeve & hand resting on robe
        d.ellipse([cx - 13, cy + 2, cx - 6, cy + 9], fill=(44, 154, 82, 255), outline=OUTLINE)

        # Gnarled Wooden Staff held in RIGHT hand (x = 38) with pulsing Mystic Orb
        staff_x = cx + 16
        d.line([(staff_x, 12 + bob), (staff_x, 46)], fill=(128, 74, 32, 255), width=3)
        d.line([(staff_x - 1, 12 + bob), (staff_x - 1, 46)], fill=(168, 104, 48, 255), width=1)
        # Right hand gripping staff
        d.ellipse([staff_x - 4, cy + 1, staff_x + 3, cy + 7], fill=(64, 188, 98, 255), outline=OUTLINE)
        # Glowing crystal orb at top of staff
        orb_colors = [
            (95, 245, 255, 255),
            (255, 230, 85, 255),
            (135, 255, 220, 255),
            (255, 195, 65, 255),
        ]
        d.ellipse([staff_x - 5, 5 + bob, staff_x + 5, 15 + bob], fill=orb_colors[frame], outline=(255, 255, 255, 255))
        d.ellipse([staff_x - 2, 7 + bob, staff_x + 2, 11 + bob], fill=(255, 255, 255, 255))

        elder.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"npc_elder_{frame}"] = elder

        # ---------------------------------------------------------------------
        # B. SHOPKEEPER ELDER MOSSMANTLE (Merchant Toad - 48x48, facing RIGHT)
        # ---------------------------------------------------------------------
        shop = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shop)

        scx, scy = 22, 24 + bob

        # Merchant Backpack / Apothecary Pack on back-left (x = 4..14)
        sd.rounded_rectangle([scx - 17, scy - 8, scx - 7, scy + 14], radius=3, fill=(132, 78, 36, 255), outline=OUTLINE)
        sd.rectangle([scx - 15, scy - 12, scx - 9, scy - 7], fill=(235, 218, 165, 255), outline=OUTLINE)  # Rolled scroll

        # Webbed Feet planted at y=46
        sd.ellipse([scx - 12, 41, scx - 1, 46], fill=(56, 168, 68, 255), outline=OUTLINE)
        sd.ellipse([scx + 2, 41, scx + 14, 46], fill=(72, 195, 82, 255), outline=OUTLINE)

        # Rotund Merchant Belly, Crimson Velvet Vest & Cream Apron
        sd.ellipse([scx - 14, scy - 4, scx + 15, 44], fill=(178, 32, 52, 255), outline=OUTLINE)
        sd.ellipse([scx - 6, scy - 1, scx + 14, 43], fill=(245, 228, 172, 255), outline=OUTLINE)
        # Gold Vest Trim & Coin Belt Buckle
        sd.line([(scx - 5, scy), (scx - 5, 41)], fill=(255, 215, 64, 255), width=2)
        sd.rectangle([scx - 13, scy + 9, scx + 14, scy + 13], fill=(92, 48, 24, 255), outline=OUTLINE)
        sd.ellipse([scx + 2, scy + 7, scx + 10, scy + 15], fill=(255, 218, 64, 255), outline=OUTLINE)

        # Broad Jovial Toad Head (facing right)
        sd.ellipse([scx - 11, scy - 15, scx + 13, scy + 2], fill=(64, 188, 76, 255), outline=OUTLINE)
        sd.ellipse([scx - 9, scy - 13, scx + 11, scy], fill=(88, 218, 96, 255))
        sd.ellipse([scx - 3, scy - 7, scx + 12, scy + 2], fill=(218, 248, 154, 255))
        # Cheerful smile facing right
        sd.arc([scx, scy - 6, scx + 11, scy], 10, 170, fill=OUTLINE, width=2)

        # Eyes (shifted right)
        for ex, ey in ((scx - 2, scy - 14), (scx + 6, scy - 14)):
            sd.ellipse([ex - 3, ey - 3, ex + 3, ey + 3], fill=(255, 255, 255, 255), outline=OUTLINE)
            if blink:
                sd.line([(ex - 2, ey), (ex + 2, ey)], fill=OUTLINE, width=1)
            else:
                sd.rectangle([ex, ey - 1, ex + 2, ey + 1], fill=(18, 24, 34, 255))
                sd.point((ex, ey - 1), fill=(255, 255, 255, 255))

        # Jaunty Gold & Crimson Merchant Fez Cap with Tassel
        sd.polygon(
            [(scx - 8, scy - 15), (scx + 7, scy - 15), (scx + 5, scy - 22), (scx - 6, scy - 22)],
            fill=(235, 168, 38, 255),
            outline=OUTLINE,
        )
        sd.line([(scx - 6, scy - 22), (scx - 11, scy - 17)], fill=(238, 42, 62, 255), width=2)

        # Glowing Potion Flask offered in RIGHT hand (x = 36..44)
        vx = scx + 16
        vy = scy + (0 if frame % 2 == 0 else -2)
        sd.ellipse([vx - 4, vy + 2, vx + 2, vy + 8], fill=(88, 218, 96, 255), outline=OUTLINE)
        potion_col = (255, 65, 135, 255) if frame % 2 == 0 else (75, 245, 215, 255)
        sd.ellipse([vx - 4, vy - 7, vx + 6, vy + 3], fill=potion_col, outline=(255, 255, 255, 255))
        sd.rectangle([vx - 1, vy - 10, vx + 3, vy - 7], fill=(168, 112, 54, 255), outline=OUTLINE)
        sd.point([(vx - 1, vy - 4), (vx, vy - 4)], fill=(255, 255, 255, 255))

        shop.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"npc_shopkeeper_{frame}"] = shop

    return sprites


# =============================================================================
# 4B. UNDERWATER ENEMIES, MUHLASER RELIC & DEMON SHARK BOSS (PIXEL-PAINTERLY)
# =============================================================================

def generate_32bit_emperor_mantis_sprites():
    """
    Generates high-detail 64x64 16-bit SNES pixel art sprites for EMPEROR MANTIS
    (canonically facing RIGHT, matching `build_sprite_catalog` flip logic):
      - `mantis_armored.png`: Royal emerald-and-gold chitin armor, dual iridescent
        stained-glass wings, serrated scythe blades, and ruby crest jewel.
      - `mantis_exposed.png`: Shattered breastplate revealing the pulsing magenta core!
    """
    sprites = {}
    OUTLINE = (16, 12, 24, 255)
    JADE_DARK = (24, 78, 42, 255)
    JADE_MID = (44, 148, 68, 255)
    JADE_HI = (98, 218, 96, 255)
    GOLD_DARK = (162, 102, 22, 255)
    GOLD_MID = (232, 174, 48, 255)
    GOLD_HI = (255, 242, 138, 255)
    CRIMSON = (235, 42, 68, 255)
    SCYTHE_EDGE = (245, 252, 255, 255)

    for state in ("armored", "exposed"):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        is_exp = (state == "exposed")
        wing_fill = (68, 205, 238, 175) if not is_exp else (225, 72, 198, 180)
        wing_rim = (195, 252, 255, 240) if not is_exp else (255, 190, 245, 240)
        wing_vein = (135, 238, 255, 210) if not is_exp else (255, 135, 225, 210)

        # --- 1. Swept Dual Translucent Stained-Glass Wings (Top & Lower Lobes) ---
        for pts in (
            [(28, 22), (4, 6), (2, 20), (14, 30), (26, 29)],
            [(36, 22), (60, 6), (62, 20), (50, 30), (38, 29)],
            [(27, 27), (7, 25), (10, 37), (26, 35)],
            [(37, 27), (57, 25), (54, 37), (38, 35)],
        ):
            d.polygon(pts, fill=wing_fill, outline=wing_rim)
        # Radial chitin wing veins
        for x1, y1, x2, y2 in (
            (25, 23, 6, 12), (24, 26, 7, 21), (39, 23, 58, 12), (40, 26, 57, 21),
            (25, 30, 11, 32), (39, 30, 53, 32),
        ):
            d.line([(x1, y1), (x2, y2)], fill=wing_vein, width=1)

        # --- 2. Segmented Royal Abdomen & 4 Articulated Mantis Legs ---
        for lx1, ly1, lx2, ly2, lx3, ly3 in (
            (24, 39, 13, 47, 8, 57),
            (26, 44, 17, 52, 13, 60),
            (40, 39, 51, 47, 56, 57),
            (38, 44, 47, 52, 51, 60),
        ):
            d.line([(lx1, ly1), (lx2, ly2), (lx3, ly3)], fill=OUTLINE, width=4)
            d.line([(lx1, ly1), (lx2, ly2), (lx3, ly3)], fill=JADE_MID, width=2)
            d.polygon([(lx3 - 2, ly3), (lx3 + 2, ly3), (lx3, ly3 + 3)], fill=GOLD_MID, outline=OUTLINE)

        d.ellipse([21, 33, 43, 58], fill=JADE_DARK, outline=OUTLINE)
        d.ellipse([24, 35, 40, 55], fill=JADE_MID)
        d.ellipse([27, 36, 36, 46], fill=JADE_HI)
        for seg_y in (40, 45, 50):
            d.arc([23, seg_y - 2, 41, seg_y + 4], 15, 165, fill=GOLD_DARK, width=1)

        # --- 3. Thorax Breastplate (Armored Gold vs Shattered Exposed Core) ---
        if not is_exp:
            # Chiseled Royal Thorax & Imperial Gold Pauldrons
            d.polygon([(22, 18), (42, 18), (45, 36), (19, 36)], fill=JADE_DARK, outline=OUTLINE)
            d.polygon([(24, 20), (40, 20), (42, 34), (22, 34)], fill=GOLD_DARK, outline=OUTLINE)
            d.polygon([(26, 21), (38, 21), (39, 32), (25, 32)], fill=GOLD_MID)
            d.line([(26, 22), (37, 22)], fill=GOLD_HI, width=1)
            # Crimson Imperial Crest Ruby
            d.polygon([(32, 22), (36, 27), (32, 32), (28, 27)], fill=CRIMSON, outline=GOLD_HI)
            d.point((31, 25), fill=(255, 255, 255, 255))
            # Serrated Golden Scythe Raptorial Arms Raised in Combat Stance!
            for arm_pts, edge_pts in (
                ([(22, 22), (10, 14), (4, 24), (10, 38), (15, 29), (18, 24)], [(4, 24), (10, 38), (13, 30)]),
                ([(42, 22), (54, 14), (60, 24), (54, 38), (49, 29), (46, 24)], [(60, 24), (54, 38), (51, 30)]),
            ):
                d.polygon(arm_pts, fill=GOLD_MID, outline=OUTLINE)
                d.line(edge_pts, fill=SCYTHE_EDGE, width=2)
            # Forearm serration teeth
            for ty in (28, 32):
                d.line([(9, ty), (13, ty + 1)], fill=CRIMSON, width=1)
                d.line([(55, ty), (51, ty + 1)], fill=CRIMSON, width=1)
        else:
            # Cracked Armor Shells & Blazing Neon Magenta Weak Core!
            d.polygon([(20, 18), (44, 18), (46, 37), (18, 37)], fill=(68, 22, 58, 255), outline=GOLD_HI)
            d.ellipse([21, 19, 43, 36], fill=(245, 52, 188, 255), outline=(255, 255, 255, 255))
            d.ellipse([26, 22, 38, 32], fill=(255, 240, 175, 255))
            d.line([(22, 21), (26, 25)], fill=OUTLINE, width=1)
            d.line([(42, 21), (38, 25)], fill=OUTLINE, width=1)
            # Drooping damaged scythe arms
            d.polygon([(20, 24), (7, 29), (9, 43), (17, 34)], fill=GOLD_DARK, outline=OUTLINE)
            d.polygon([(44, 24), (57, 29), (55, 43), (47, 34)], fill=GOLD_DARK, outline=OUTLINE)

        # --- 4. Triangular Crowned Imperial Mantis Head & Compound Ruby Eyes ---
        d.polygon([(22, 9), (42, 9), (37, 20), (27, 20)], fill=JADE_MID, outline=OUTLINE)
        d.polygon([(25, 10), (39, 10), (35, 18), (29, 18)], fill=JADE_HI)
        # Crowned Golden Imperial Crest & Swept Antennae
        d.polygon([(27, 9), (32, 3), (37, 9)], fill=GOLD_HI, outline=OUTLINE)
        d.point((32, 6), fill=CRIMSON)
        d.line([(26, 9), (15, 1)], fill=GOLD_MID, width=2)
        d.line([(38, 9), (49, 1)], fill=GOLD_MID, width=2)
        d.point((15, 1), fill=GOLD_HI)
        d.point((49, 1), fill=GOLD_HI)

        # Menacing Compound Eyes & White Glints
        for ex in (21, 41):
            d.ellipse([ex - 3, 8, ex + 5, 16], fill=CRIMSON, outline=OUTLINE)
            d.arc([ex - 2, 9, ex + 4, 15], 190, 320, fill=(255, 185, 120, 255), width=1)
            d.point((ex + 1, 10), fill=(255, 255, 255, 255))

        img = _apply_16bit_pixel_polish(img, dither_step=7, rim_col=(255, 245, 185))
        img.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"mantis_{state}"] = img

    return sprites


def generate_32bit_underwater_and_shark_sprites():
    """
    Generates pixel-painterly sprites for the Underwater Expansion:
      - `piranha_0..1.png` (28x20, facing RIGHT): Razor Piranha schooling predator.
      - `angler_0..1.png` (32x26, facing RIGHT): Abyssal Anglerfish with glowing lure.
      - `jelly_0..1.png` (24x28): Bio-Electric Jellyfish with crackling tentacles.
      - `powerup_muhlaser.png` (24x24): The Muhlaser mouth-beam relic pickup.
      - `shark_idle.png`, `shark_idle_1.png`, `shark_charge.png`, `shark_dazed.png`,
        `shark_enraged.png` (96x64, canonically facing LEFT like Giga Toad & Dread Hound):
        DEMON SHARK Boss!
    """
    sprites = {}
    OUTLINE = (10, 16, 26, 255)

    # 1. RAZOR PIRANHA (28x20, facing RIGHT)
    for frame in range(2):
        img = Image.new("RGBA", (28, 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        tail_shift = -2 if frame == 0 else 2
        # Tail fin (left side)
        d.polygon(
            [(2, 4 + tail_shift), (9, 9), (9, 11), (2, 16 - tail_shift), (5, 10)],
            fill=(215, 42, 62, 255),
            outline=OUTLINE,
        )
        # Dorsal fin & ventral fin
        d.polygon([(10, 3), (17, 1), (19, 6), (11, 6)], fill=(235, 55, 72, 255), outline=OUTLINE)
        d.polygon([(11, 14), (16, 18), (18, 14)], fill=(215, 42, 62, 255), outline=OUTLINE)
        # Muscular piranha body (teal-emerald top scales, crimson-orange belly)
        d.ellipse([6, 4, 25, 16], fill=(28, 138, 124, 255), outline=OUTLINE)
        d.chord([6, 7, 25, 16], 0, 180, fill=(225, 68, 52, 255), outline=OUTLINE)
        d.ellipse([9, 5, 21, 10], fill=(54, 186, 162, 255))
        # Bulldog underbite jaw & interlocking razor fangs (right side)
        jaw_open = 1 if frame == 1 else 0
        d.polygon(
            [(18, 10), (27, 9 + jaw_open), (26, 15), (17, 15)],
            fill=(185, 38, 48, 255),
            outline=OUTLINE,
        )
        for tx in (20, 23, 25):
            d.polygon([(tx, 11), (tx + 1, 8), (tx + 2, 11)], fill=(255, 255, 245, 255))
        # Fierce glowing gold-crimson eye
        d.ellipse([19, 5, 24, 10], fill=(255, 225, 65, 255), outline=OUTLINE)
        d.rectangle([21, 6, 23, 8], fill=(215, 18, 32, 255))
        d.point((21, 6), fill=(255, 255, 255, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"piranha_{frame}"] = img

    # 2. ABYSSAL ANGLERFISH (32x26, facing RIGHT)
    for frame in range(2):
        img = Image.new("RGBA", (32, 26), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        bob = 1 if frame == 1 else 0
        # Tail fin
        d.polygon([(1, 8 + bob), (7, 13), (1, 19 - bob), (4, 13)], fill=(58, 36, 98, 255), outline=OUTLINE)
        # Round abyssal body (deep indigo-violet with bioluminescent spots)
        d.ellipse([5, 6, 25, 22], fill=(42, 26, 78, 255), outline=OUTLINE)
        d.ellipse([7, 8, 21, 18], fill=(68, 42, 118, 255))
        for sx, sy in ((10, 11), (13, 9), (11, 15)):
            d.point((sx, sy), fill=(95, 245, 255, 255))
        # Gaping needle-toothed maw (right side)
        d.polygon([(16, 11), (28, 9 - bob), (25, 15), (28, 20 + bob), (16, 20)], fill=(24, 12, 42, 255), outline=OUTLINE)
        for tx in (19, 22, 25):
            d.line([(tx, 10), (tx, 13)], fill=(245, 250, 255, 255), width=1)
            d.line([(tx + 1, 19), (tx + 1, 16)], fill=(245, 250, 255, 255), width=1)
        # Curved dorsal illicium stalk & glowing bioluminescent cyan-gold lure!
        d.arc([12, 1, 30, 14], 190, 355, fill=(115, 185, 225, 255), width=2)
        lure_x, lure_y = 28, 6 + bob
        d.ellipse([lure_x - 4, lure_y - 4, lure_x + 3, lure_y + 3], fill=(80, 245, 255, 180))
        d.ellipse([lure_x - 2, lure_y - 2, lure_x + 1, lure_y + 1], fill=(255, 255, 210, 255))
        # Milky abyssal eye
        d.ellipse([18, 7, 22, 11], fill=(165, 255, 240, 255), outline=OUTLINE)
        d.point((20, 9), fill=(18, 28, 48, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"angler_{frame}"] = img

    # 3. BIO-ELECTRIC JELLYFISH (24x28)
    for frame in range(2):
        img = Image.new("RGBA", (24, 28), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        squeeze = 2 if frame == 1 else 0
        # Trailing bio-electric tentacles
        for tx in (6, 10, 14, 18):
            sway = (2 if frame == 1 else -2) if (tx % 4 == 2) else (-1 if frame == 1 else 1)
            d.line([(tx, 13), (tx + sway, 20), (tx - sway, 26)], fill=(95, 245, 255, 235), width=1)
        # Electric spark arcs between tentacles on frame 1
        if frame == 1:
            d.line([(5, 17), (12, 19), (19, 16)], fill=(255, 245, 95, 255), width=1)
        # Translucent glowing bell dome (magenta core + neon cyan rim)
        d.chord([2 + squeeze, 2, 22 - squeeze, 18], 180, 360, fill=(45, 195, 235, 230), outline=OUTLINE)
        d.chord([5 + squeeze, 4, 19 - squeeze, 15], 180, 360, fill=(235, 75, 185, 240))
        d.ellipse([8, 6, 16, 11], fill=(255, 245, 165, 255))
        # Cute/alien glowing eyes on bell
        d.rectangle([7, 10, 9, 12], fill=(255, 255, 255, 255))
        d.rectangle([15, 10, 17, 12], fill=(255, 255, 255, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"jelly_{frame}"] = img

    # 4. MUHLASER RELIC ICON (`powerup_muhlaser.png`, 24x24)
    laser_icon = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    ld = ImageDraw.Draw(laser_icon)
    # Outer golden-emerald frog-jaw crest
    ld.ellipse([1, 1, 22, 22], fill=(22, 58, 68, 240), outline=(255, 215, 65, 255))
    ld.arc([3, 3, 20, 20], 110, 250, fill=(65, 225, 115, 255), width=3)
    # Blazing cyan-magenta plasma core & beam ray bursting right
    ld.ellipse([6, 6, 16, 16], fill=(75, 245, 255, 255), outline=(255, 255, 255, 255))
    ld.polygon([(11, 9), (23, 5), (23, 18), (11, 14)], fill=(95, 250, 255, 235))
    ld.polygon([(10, 10), (23, 8), (23, 15), (10, 13)], fill=(255, 255, 255, 255))
    laser_icon.putpixel((0, 0), (0, 0, 0, 0))
    sprites["powerup_muhlaser"] = laser_icon

    # 5. DEMON SHARK COLOSSUS BOSS (`shark_*`, 96x64, canonically facing LEFT)
    shark_states = ["idle", "idle_1", "charge", "dazed", "enraged"]
    for st in shark_states:
        s_img = Image.new("RGBA", (96, 64), (0, 0, 0, 0))
        sd = ImageDraw.Draw(s_img)

        is_charge = (st == "charge")
        is_dazed = (st == "dazed")
        is_enraged = (st == "enraged")
        bob = 2 if st == "idle_1" else 0

        body_dark = (22, 34, 58, 255) if not is_enraged else (68, 16, 36, 255)
        body_mid = (38, 62, 98, 255) if not is_enraged else (116, 26, 54, 255)
        body_hi = (78, 118, 168, 255) if not is_enraged else (178, 48, 84, 255)
        belly_col = (188, 212, 232, 255) if not is_enraged else (238, 168, 186, 255)
        armor_col = (54, 72, 98, 255) if not is_enraged else (142, 42, 62, 255)
        glow_col = (255, 52, 78, 255) if not is_dazed else (95, 245, 255, 255)

        # Crescent caudal tail fin with etched rune vein (x = 70..95)
        tail_wag = -3 if st in ("idle_1", "charge") else 2
        sd.polygon(
            [
                (70, 28 + bob),
                (94, 5 + tail_wag),
                (86, 30 + bob),
                (95, 55 - tail_wag),
                (70, 38 + bob),
            ],
            fill=body_dark,
            outline=OUTLINE,
        )
        sd.polygon(
            [(73, 29 + bob), (90, 10 + tail_wag), (83, 30 + bob), (90, 50 - tail_wag), (73, 36 + bob)],
            fill=body_mid,
        )
        sd.line([(76, 30 + bob), (90, 12 + tail_wag)], fill=glow_col, width=1)
        sd.line([(76, 34 + bob), (90, 48 - tail_wag)], fill=glow_col, width=1)

        # Battle-scarred colossal dorsal fin + secondary spine fin
        sd.polygon(
            [(36, 20 + bob), (48, 2 + bob), (56, 7 + bob), (53, 12 + bob), (62, 21 + bob)],
            fill=body_dark,
            outline=OUTLINE,
        )
        sd.polygon(
            [(39, 19 + bob), (48, 5 + bob), (53, 9 + bob), (58, 19 + bob)],
            fill=body_mid,
        )
        sd.line([(46, 7 + bob), (44, 18 + bob)], fill=glow_col, width=2)
        sd.polygon([(63, 22 + bob), (69, 13 + bob), (73, 23 + bob)], fill=body_dark, outline=OUTLINE)

        # Hydro-wake plasma streaks on charge pose
        if is_charge:
            for wy in (16, 28, 42):
                sd.line([(78, wy), (94, wy)], fill=(120, 250, 255, 220), width=1)

        # Fusiform armored megalodon torso (x = 7..78, y = 16..51)
        sd.ellipse([7, 16 + bob, 78, 51 + bob], fill=body_dark, outline=OUTLINE)
        sd.ellipse([11, 18 + bob, 74, 44 + bob], fill=body_mid)
        sd.ellipse([17, 20 + bob, 64, 31 + bob], fill=body_hi)
        # Riveted dorsal carapace armor plates & battle scars
        sd.polygon([(26, 17 + bob), (45, 16 + bob), (58, 22 + bob), (29, 24 + bob)], fill=armor_col, outline=OUTLINE)
        for rx_rv in (31, 38, 46):
            sd.point((rx_rv, 19 + bob), fill=(215, 230, 245, 255))
        sd.line([(48, 27 + bob), (56, 33 + bob)], fill=(215, 195, 195, 255), width=1)
        sd.line([(51, 25 + bob), (54, 34 + bob)], fill=(155, 45, 65, 255), width=1)
        # Pale armored underbelly plate with hydro-ribs
        sd.chord([11, 29 + bob, 74, 51 + bob], 0, 180, fill=belly_col, outline=OUTLINE)
        for bx in (46, 54, 62):
            sd.line([(bx, 41 + bob), (bx - 2, 48 + bob)], fill=body_mid, width=1)

        # Glowing demonic gill slits venting bio-plasma
        for gx in (34, 38, 42):
            sd.line([(gx, 25 + bob), (gx + 2, 37 + bob)], fill=OUTLINE, width=3)
            sd.line([(gx, 26 + bob), (gx + 2, 36 + bob)], fill=glow_col, width=1)
            sd.point((gx + 3, 25 + bob), fill=(255, 255, 210, 255))

        # Snout & Jaws on LEFT side (x = 2..32)
        jaw_drop = 11 if (is_charge or is_enraged) else (7 if is_dazed else 6)
        sd.polygon(
            [(2, 25 + bob), (18, 16 + bob), (32, 18 + bob), (28, 32 + bob), (6, 31 + bob)],
            fill=body_mid,
            outline=OUTLINE,
        )
        sd.line([(5, 24 + bob), (19, 17 + bob)], fill=body_hi, width=2)
        sd.point((7, 25 + bob), fill=OUTLINE)  # Flared shark nostril
        # Riveted lower jaw
        sd.polygon(
            [(5, 34 + bob + jaw_drop), (12, 46 + bob + jaw_drop), (32, 44 + bob), (28, 33 + bob)],
            fill=body_dark,
            outline=OUTLINE,
        )
        # Glowing abyssal gullet interior (clearly separates upper and lower fang rows!)
        sd.polygon(
            [(7, 31 + bob), (27, 31 + bob), (27, 36 + bob + jaw_drop), (8, 35 + bob + jaw_drop)],
            fill=(145, 16, 44, 255) if not is_charge else (245, 48, 82, 255),
        )
        # Separated razor-pointed ivory megalodon fangs!
        for tx in range(8, 26, 4):
            sd.polygon([(tx, 31 + bob), (tx + 1, 35 + bob), (tx + 3, 31 + bob)], fill=(255, 255, 245, 255))
            sd.polygon([(tx + 2, 36 + bob + jaw_drop), (tx + 3, 32 + bob + jaw_drop), (tx + 5, 36 + bob + jaw_drop)], fill=(245, 245, 235, 255))

        # Swept armored pectoral fin with rune edge
        sd.polygon(
            [(30, 41 + bob), (46, 59 + bob), (56, 56 + bob), (44, 41 + bob)],
            fill=body_dark,
            outline=OUTLINE,
        )
        sd.polygon(
            [(33, 42 + bob), (46, 55 + bob), (51, 53 + bob), (42, 42 + bob)],
            fill=body_mid,
        )
        sd.line([(36, 44 + bob), (46, 55 + bob)], fill=glow_col, width=1)

        # Demonic Horn / Brow Crest & Eye
        sd.polygon([(12, 22 + bob), (24, 17 + bob), (27, 22 + bob)], fill=(255, 195, 55, 255), outline=OUTLINE)
        if is_dazed:
            sd.ellipse([15, 22 + bob, 23, 29 + bob], fill=(45, 65, 85, 255), outline=OUTLINE)
            sd.line([(16, 23 + bob), (22, 28 + bob)], fill=(95, 245, 255, 255), width=2)
            sd.line([(22, 23 + bob), (16, 28 + bob)], fill=(95, 245, 255, 255), width=2)
            for sx, sy in ((22, 8), (34, 5), (46, 9)):
                sd.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(255, 235, 65, 255))
        else:
            sd.ellipse([15, 22 + bob, 23, 29 + bob], fill=(255, 45, 65, 255), outline=OUTLINE)
            sd.ellipse([17, 23 + bob, 21, 27 + bob], fill=(255, 235, 75, 255))
            sd.point((18, 24 + bob), fill=(255, 255, 255, 255))

        s_img = _apply_16bit_pixel_polish(s_img, dither_step=8, rim_col=(145, 225, 255))
        s_img.putpixel((0, 0), (0, 0, 0, 0))
        sprites[f"shark_{st}"] = s_img

    return sprites



# =============================================================================
# 5. EXPORT PIPELINE
# =============================================================================

def build_and_export_all_32bit_sprites():
    """
    Exports environmental V7 assets (doors, fragments, backgrounds) and then
    writes clean, consistent procedural sprites for Froggy, Emperor Mantis,
    Giga Toad, Dread Hound, Elder Mossbeard, Shopkeeper Mossmantle, Underwater
    enemies, and Demon Shark into `assets/sprites/`.
    """
    os.makedirs(SPRITES_DIR, exist_ok=True)
    print("[SpriteStudio] Generating & exporting cohesive arcade sprite suite...")

    # 1. Process environmental V7 assets (doors, fragments, background)
    try:
        import process_v7_assets
        process_v7_assets.process_doors()
        process_v7_assets.generate_key_fragments()
        process_v7_assets.process_jungle_ruins_bg()
    except Exception as e:
        print(f"[SpriteStudio] Warning: V7 environmental asset pipeline fallback: {e}")

    # 2. Export Froggy (32x32, 9 animations, 21 frames)
    frog_sprites = generate_32bit_froggy_sprites()
    for name, img in frog_sprites.items():
        img.save(os.path.join(SPRITES_DIR, f"{name}.png"))

    # 2B. Export Crowned Royal Emperor Mantis Boss (64x64, 2 frames)
    mantis_sprites = generate_32bit_emperor_mantis_sprites()
    for name, img in mantis_sprites.items():
        img.save(os.path.join(SPRITES_DIR, f"{name}.png"))

    # 3. Export Giga Toad Boss (80x80, 8 frames, left-facing)
    toad_sprites = generate_32bit_gigatoad_sprites()
    for name, img in toad_sprites.items():
        img.save(os.path.join(SPRITES_DIR, f"{name}.png"))

    # 4. Export Dread Hound Boss (96x96, 5 frames + projectile, left-facing)
    hound_sprites = generate_32bit_dreadhound_sprites()
    for name, img in hound_sprites.items():
        img.save(os.path.join(SPRITES_DIR, f"{name}.png"))

    # 5. Export Elder Toads (48x48, 4 frames each for Elder & Shopkeeper, right-facing)
    npc_sprites = generate_32bit_npc_toad_sprites()
    for name, img in npc_sprites.items():
        img.save(os.path.join(SPRITES_DIR, f"{name}.png"))

    # 6. Export Underwater Enemies, Muhlaser Relic & Demon Shark Boss
    aqua_sprites = generate_32bit_underwater_and_shark_sprites()
    for name, img in aqua_sprites.items():
        img.save(os.path.join(SPRITES_DIR, f"{name}.png"))

    print("[SpriteStudio] All character, NPC, underwater, and boss sprites exported cleanly!")


if __name__ == "__main__":
    build_and_export_all_32bit_sprites()
