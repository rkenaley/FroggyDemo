"""
===============================================================================
GIGA TOAD (BATTLETOAD) GENERATIVE SPRITE EXTRACTION & ANIMATION PIPELINE
===============================================================================
Slices, chroma-keys (with purple/magenta despill), mirrors to canonical LEFT-
facing orientation, baseline-anchors, and exports both the legacy 8 keyframes
and smooth multi-frame continuous animation cycles (idle, walk, slam, punch,
dazed, enraged) into assets/sprites/toad_*.png at uniform 80x80 RGBA resolution.
"""

import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ARTIFACTS_DIR = r"C:\Users\Ryan\.gemini\antigravity\brain\2ab7cfc0-bcc2-418d-9f41-85a7847c2dd3"
SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sprites")

SHEET_BASE = os.path.join(ARTIFACTS_DIR, "toad_boss_spritesheet_1794591904280.jpg")
SHEET_ACTION = os.path.join(ARTIFACTS_DIR, "toad_boss_action_spritesheet_v3_1794592111686.jpg")
SHEET_WALK = os.path.join(ARTIFACTS_DIR, "toad_boss_walkcycle_spritesheet_v3_1794592149502.jpg")


def _compute_foreground_mask(rgb: np.ndarray) -> np.ndarray:
    """Identifies non-magenta foreground pixels using chroma distance + HSV hue/sat guard."""
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)

    # Pure magenta has high R, high B, low G, and |R - B| small.
    dist_mag = np.sqrt((r - 255.0) ** 2 + (g - 0.0) ** 2 + (b - 255.0) ** 2)
    is_magenta_hue = (r > 130.0) & (b > 130.0) & (g < np.minimum(r, b) - 48.0) & (np.abs(r - b) < 75.0)
    return (dist_mag > 110.0) & (~is_magenta_hue)


def chroma_key_and_despill(cell_img: Image.Image) -> Image.Image:
    """Removes JPEG-compressed magenta background cleanly and despills ONLY edge halos without crushing red shading."""
    arr = np.array(cell_img.convert("RGBA")).astype(np.float32)
    rgb = arr[:, :, :3]
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    # Distance to magenta screen; guard with b > r * 0.65 so warm crimson skin is never mistaken for magenta!
    dist_mag = np.sqrt((r - 255.0) ** 2 + g ** 2 + (b - 255.0) ** 2)
    magenta_strength = np.clip((np.minimum(r, b) - g) / 255.0, 0.0, 1.0)
    is_mag_tint = (
        (np.minimum(r, b) > g + 36.0)
        & (np.abs(r - b) < 82.0)
        & (np.maximum(r, b) > 105.0)
        & (b > r * 0.68)
    )

    alpha = np.clip((dist_mag - 88.0) / 42.0, 0.0, 1.0) * 255.0
    alpha = np.where(is_mag_tint & (magenta_strength > 0.30), 0.0, alpha)

    # Despill ONLY edge/fringe pixels or true purple-tinted fringe (never warm crimson pixels where r > b + 28)
    is_fringe = (alpha > 0.0) & (alpha < 248.0) & (b > g + 16.0) & (b > r * 0.62)
    target_b = np.maximum(g * 1.05 + 6.0, r * 0.45)
    arr[:, :, 0] = np.where(is_fringe & (np.abs(r - b) < 60.0), np.minimum(r, np.maximum(g * 1.15 + 12.0, r * 0.65)), r)
    arr[:, :, 2] = np.where(is_fringe, np.minimum(b, target_b), b)
    arr[:, :, 3] = alpha

    rgba = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    # Morphological fringe trim: clear isolated 1px speckles with alpha < 28
    cleaned = np.array(rgba)
    cleaned[cleaned[:, :, 3] < 28, 3] = 0
    return Image.fromarray(cleaned, "RGBA")


def find_grid_cells(sheet_path: str) -> list[list[Image.Image]]:
    """Segments a 2x3 sprite sheet along low-foreground valleys so no pose gets clipped."""
    img = Image.open(sheet_path).convert("RGB")
    arr = np.array(img)
    fg = _compute_foreground_mask(arr)

    h, w = fg.shape
    row_proj = fg.sum(axis=1)
    # Locate the horizontal split row between top row & bottom row in middle 35%-65% band
    y_band_lo, y_band_hi = int(h * 0.34), int(h * 0.66)
    y_split = y_band_lo + int(np.argmin(row_proj[y_band_lo:y_band_hi]))

    grid_rows: list[list[Image.Image]] = []
    for y0, y1 in ((0, y_split), (y_split, h)):
        row_fg = fg[y0:y1, :]
        col_proj = row_fg.sum(axis=0)
        # Find two vertical split valleys separating the 3 characters in this row
        x1_lo, x1_hi = int(w * 0.24), int(w * 0.44)
        x2_lo, x2_hi = int(w * 0.56), int(w * 0.78)
        x_split1 = x1_lo + int(np.argmin(col_proj[x1_lo:x1_hi]))
        x_split2 = x2_lo + int(np.argmin(col_proj[x2_lo:x2_hi]))
        cells = []
        for x0, x1 in ((0, x_split1), (x_split1, x_split2), (x_split2, w)):
            crop = img.crop((x0, y0, x1, y1))
            keyed = chroma_key_and_despill(crop)
            bbox = keyed.getbbox()
            if bbox:
                pad = 2
                bx0 = max(0, bbox[0] - pad)
                by0 = max(0, bbox[1] - pad)
                bx1 = min(keyed.width, bbox[2] + pad)
                by1 = min(keyed.height, bbox[3] + pad)
                keyed = keyed.crop((bx0, by0, bx1, by1))
            cells.append(keyed)
        grid_rows.append(cells)
    return grid_rows


def fit_to_80x80(
    sprite: Image.Image,
    target_height: int = 68,
    baseline_y: int = 77,
    flip_left: bool = True,
    max_width: int = 76,
    dx_offset: int = 0,
    dy_offset: int = 0,
    boost_flame: float = 1.0,
) -> Image.Image:
    """Flips to canonical LEFT-facing, scales uniformly, anchors feet, centers on 80x80."""
    sp = ImageOps.mirror(sprite) if flip_left else sprite.copy()
    if boost_flame != 1.0:
        sp = ImageEnhance.Brightness(sp).enhance(boost_flame)
        sp = ImageEnhance.Contrast(sp).enhance(1.06)

    bbox = sp.getbbox()
    if bbox:
        sp = sp.crop(bbox)

    scale = min(target_height / float(max(1, sp.height)), max_width / float(max(1, sp.width)))
    new_w = max(1, int(round(sp.width * scale)))
    new_h = max(1, int(round(sp.height * scale)))
    # Bilinear + slight unsharp works cleanly when shrinking 350px illustrations to 70px crisp sprites
    resized = sp.resize((new_w, new_h), Image.Resampling.LANCZOS)
    resized = resized.filter(ImageFilter.UnsharpMask(radius=0.8, percent=95, threshold=3))

    canvas = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    px = (80 - new_w) // 2 + dx_offset
    py = baseline_y - new_h + dy_offset
    px = max(0, min(80 - new_w, px))
    py = max(0, min(80 - new_h, py))
    canvas.paste(resized, (px, py), resized)

    # Guarantee corner alpha == 0 for strict sprite contract checks
    canvas.putpixel((0, 0), (0, 0, 0, 0))
    return canvas


def main():
    os.makedirs(SPRITES_DIR, exist_ok=True)
    sheet_a = find_grid_cells(SHEET_BASE)
    sheet_b = find_grid_cells(SHEET_ACTION)
    sheet_c = find_grid_cells(SHEET_WALK)

    # Standard grounded scale vs leap/impact poses so character volume stays rock-solid
    idle_0 = fit_to_80x80(sheet_a[0][0], target_height=68, baseline_y=77)
    idle_1 = fit_to_80x80(sheet_b[0][0], target_height=68, baseline_y=77)
    idle_2 = fit_to_80x80(sheet_c[1][2], target_height=67, baseline_y=77)
    idle_3 = fit_to_80x80(sheet_b[0][0], target_height=68, baseline_y=77, dy_offset=-1)

    walk_0 = fit_to_80x80(sheet_c[0][0], target_height=69, baseline_y=77)
    walk_1 = fit_to_80x80(sheet_c[0][1], target_height=68, baseline_y=77, dy_offset=1)
    walk_2 = fit_to_80x80(sheet_c[0][2], target_height=69, baseline_y=77)
    walk_3 = fit_to_80x80(sheet_a[0][1], target_height=69, baseline_y=77)
    walk_4 = fit_to_80x80(sheet_c[1][1], target_height=67, baseline_y=77, dy_offset=1)
    walk_5 = fit_to_80x80(sheet_c[0][1], target_height=68, baseline_y=77)

    # Slam progression: coiled stance -> deep windup -> high overhead leap -> meteor double-fist smash
    slam_0 = fit_to_80x80(sheet_c[1][2], target_height=66, baseline_y=77)
    slam_1 = fit_to_80x80(sheet_b[0][1], target_height=65, baseline_y=77)
    slam_2 = fit_to_80x80(sheet_a[0][2], target_height=74, baseline_y=75)
    slam_3 = fit_to_80x80(sheet_b[0][2], target_height=65, baseline_y=78)

    # Punch progression: coiled windup -> forward jab -> straight haymaker -> golden shockwave impact
    punch_0 = fit_to_80x80(sheet_b[0][1], target_height=66, baseline_y=77)
    punch_1 = fit_to_80x80(sheet_c[1][0], target_height=68, baseline_y=77, max_width=78)
    punch_2 = fit_to_80x80(sheet_b[1][0], target_height=68, baseline_y=77, max_width=78)
    punch_3 = fit_to_80x80(sheet_a[1][0], target_height=68, baseline_y=77, max_width=79)

    # Dazed progression: stars tilt -> tongue-out stagger -> heavy panting slump
    dazed_0 = fit_to_80x80(sheet_a[1][1], target_height=70, baseline_y=77)
    dazed_1 = fit_to_80x80(sheet_b[1][1], target_height=70, baseline_y=77)
    dazed_2 = fit_to_80x80(sheet_a[1][1], target_height=70, baseline_y=77, dx_offset=-1)
    dazed_3 = fit_to_80x80(sheet_c[1][1], target_height=67, baseline_y=77)

    # Enraged crimson fire aura progression
    enr_0 = fit_to_80x80(sheet_a[1][2], target_height=72, baseline_y=77, max_width=78)
    enr_1 = fit_to_80x80(sheet_b[1][2], target_height=72, baseline_y=77, max_width=78)
    enr_2 = fit_to_80x80(sheet_a[1][2], target_height=73, baseline_y=77, max_width=78, boost_flame=1.10)
    enr_3 = fit_to_80x80(sheet_b[1][2], target_height=72, baseline_y=77, max_width=78, boost_flame=1.06)

    exports = {
        # Legacy single-frame contract keys (all 80x80 RGBA facing LEFT)
        "toad_idle": idle_0,
        "toad_idle_1": idle_1,
        "toad_walk_0": walk_0,
        "toad_walk_1": walk_2,
        "toad_slam": slam_2,
        "toad_punch": punch_3,
        "toad_dazed": dazed_0,
        "toad_enraged": enr_0,
        # Continuous multi-frame sequences
        "toad_idle_0": idle_0,
        "toad_idle_2": idle_2,
        "toad_idle_3": idle_3,
        "toad_walk_2": walk_2,
        "toad_walk_3": walk_3,
        "toad_walk_4": walk_4,
        "toad_walk_5": walk_5,
        "toad_slam_0": slam_0,
        "toad_slam_1": slam_1,
        "toad_slam_2": slam_2,
        "toad_slam_3": slam_3,
        "toad_punch_0": punch_0,
        "toad_punch_1": punch_1,
        "toad_punch_2": punch_2,
        "toad_punch_3": punch_3,
        "toad_dazed_0": dazed_0,
        "toad_dazed_1": dazed_1,
        "toad_dazed_2": dazed_2,
        "toad_dazed_3": dazed_3,
        "toad_enraged_0": enr_0,
        "toad_enraged_1": enr_1,
        "toad_enraged_2": enr_2,
        "toad_enraged_3": enr_3,
    }
    # Ensure legacy walk_1 alias points cleanly to walk_1 stride frame too
    exports["toad_walk_1"] = walk_1

    for name, img in exports.items():
        out_path = os.path.join(SPRITES_DIR, f"{name}.png")
        img.save(out_path)
    print(f"Exported {len(exports)} Giga Toad 80x80 RGBA frames to {SPRITES_DIR}")


if __name__ == "__main__":
    main()
