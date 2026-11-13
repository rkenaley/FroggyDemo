"""
===============================================================================
UNIFIED 5-BOSS GENERATIVE SPRITE SHEET EXTRACTION & ANIMATION PIPELINE
===============================================================================
Processes 2x3 generative pixel-art boss sheets (on flat #FF00FF magenta) into
uniform, chroma-keyed, despilled, canonically oriented RGBA PNGs plus visual QA
contact sheets for visual inspection:
  - Emperor Mantis (64x64 RGBA, canonical RIGHT-facing)
  - The Dread Hound Colossus (96x96 RGBA, canonical LEFT-facing)
  - Falo the Frostbite Snowman (64x64 RGBA, canonical LEFT-facing)
  - The Abyssal Demon Shark (96x64 RGBA, canonical LEFT-facing)
  - Ultra-Jacked Giga Toad (96x96 RGBA, canonical LEFT-facing, enlarged + jacked)
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ARTIFACTS_DIR = r"C:\Users\Ryan\.gemini\antigravity\brain\2ab7cfc0-bcc2-418d-9f41-85a7847c2dd3"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")
SCRATCH_DIR = os.path.join(ARTIFACTS_DIR, "scratch")

SHEET_MANTIS = os.path.join(ARTIFACTS_DIR, "emperor_mantis_spritesheet_clean_1794599965884.jpg")
SHEET_HOUND = os.path.join(ARTIFACTS_DIR, "dread_hound_colossus_spritesheet_1794599931555.jpg")
SHEET_FALO = os.path.join(ARTIFACTS_DIR, "falo_snowman_spritesheet_final_1794599962408.jpg")
SHEET_SHARK = os.path.join(ARTIFACTS_DIR, "abyssal_demon_shark_spritesheet_clean_1794599957724.jpg")
SHEET_TOAD_WALK = os.path.join(ARTIFACTS_DIR, "giga_toad_spritesheet_1794599939625.jpg")
SHEET_TOAD_ACT = os.path.join(ARTIFACTS_DIR, "giga_toad_boss_action_sheet_1794599994419.jpg")


def _compute_foreground_mask(rgb: np.ndarray) -> np.ndarray:
    """Identifies non-magenta foreground pixels using chroma distance + hue guard."""
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)

    dist_mag = np.sqrt((r - 255.0) ** 2 + g ** 2 + (b - 255.0) ** 2)
    is_magenta_hue = (
        (r > 125.0)
        & (b > 125.0)
        & (g < np.minimum(r, b) - 44.0)
        & (np.abs(r - b) < 82.0)
        & (b > r * 0.65)
    )
    return (dist_mag > 110.0) & (~is_magenta_hue)


def chroma_key_and_despill(cell_img: Image.Image) -> Image.Image:
    """Removes JPEG-compressed magenta background cleanly and despills ONLY magenta-tinted edge halos."""
    arr = np.array(cell_img.convert("RGBA")).astype(np.float32)
    rgb = arr[:, :, :3]
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    # Guard warm reds/oranges/golds via b > r * 0.68 so flames, ruby cloaks, and cores stay 100% opaque!
    dist_mag = np.sqrt((r - 255.0) ** 2 + g ** 2 + (b - 255.0) ** 2)
    magenta_strength = np.clip((np.minimum(r, b) - g) / 255.0, 0.0, 1.0)
    is_mag_tint = (
        (np.minimum(r, b) > g + 34.0)
        & (np.abs(r - b) < 86.0)
        & (np.maximum(r, b) > 100.0)
        & (b > r * 0.66)
    )

    alpha = np.clip((dist_mag - 88.0) / 42.0, 0.0, 1.0) * 255.0
    alpha = np.where(is_mag_tint & (magenta_strength > 0.28), 0.0, alpha)

    is_fringe = (alpha > 0.0) & (alpha < 248.0) & (b > g + 16.0) & (b > r * 0.62)
    target_b = np.maximum(g * 1.05 + 6.0, r * 0.45)
    arr[:, :, 0] = np.where(
        is_fringe & (np.abs(r - b) < 60.0),
        np.minimum(r, np.maximum(g * 1.15 + 12.0, r * 0.65)),
        r,
    )
    arr[:, :, 2] = np.where(is_fringe, np.minimum(b, target_b), b)
    arr[:, :, 3] = alpha

    rgba = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    cleaned = np.array(rgba)
    cleaned[cleaned[:, :, 3] < 28, 3] = 0
    return Image.fromarray(cleaned, "RGBA")


def find_grid_cells(sheet_path: str) -> list[list[Image.Image]]:
    """Segments a 2x3 sprite sheet along lowest-foreground valleys so no pose clips."""
    img = Image.open(sheet_path).convert("RGB")
    arr = np.array(img)
    fg = _compute_foreground_mask(arr)

    h, w = fg.shape
    row_proj = fg.sum(axis=1)
    y_band_lo, y_band_hi = int(h * 0.34), int(h * 0.66)
    y_split = y_band_lo + int(np.argmin(row_proj[y_band_lo:y_band_hi]))

    grid_rows: list[list[Image.Image]] = []
    for y0, y1 in ((0, y_split), (y_split, h)):
        row_fg = fg[y0:y1, :]
        col_proj = row_fg.sum(axis=0)
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


def fit_to_canvas(
    sprite: Image.Image,
    canvas_size: tuple[int, int],
    target_height: int,
    max_width: int,
    baseline_y: int | None = None,
    center_vertical: bool = False,
    flip_horiz: bool = False,
    dx_offset: int = 0,
    dy_offset: int = 0,
    boost_brightness: float = 1.0,
) -> Image.Image:
    """Optionally flips sprite, preserves aspect ratio, anchors either to floor baseline or center, and exports RGBA."""
    cw, ch = canvas_size
    sp = ImageOps.mirror(sprite) if flip_horiz else sprite.copy()
    if boost_brightness != 1.0:
        sp = ImageEnhance.Brightness(sp).enhance(boost_brightness)
        sp = ImageEnhance.Contrast(sp).enhance(1.06)

    bbox = sp.getbbox()
    if bbox:
        sp = sp.crop(bbox)

    scale = min(target_height / float(max(1, sp.height)), max_width / float(max(1, sp.width)))
    new_w = max(1, int(round(sp.width * scale)))
    new_h = max(1, int(round(sp.height * scale)))
    resized = sp.resize((new_w, new_h), Image.Resampling.LANCZOS)
    resized = resized.filter(ImageFilter.UnsharpMask(radius=0.8, percent=95, threshold=3))

    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    px = (cw - new_w) // 2 + dx_offset
    if center_vertical or baseline_y is None:
        py = (ch - new_h) // 2 + dy_offset
    else:
        py = baseline_y - new_h + dy_offset
    px = max(0, min(cw - new_w, px))
    py = max(0, min(ch - new_h, py))
    canvas.paste(resized, (px, py), resized)
    canvas.putpixel((0, 0), (0, 0, 0, 0))
    return canvas


def build_contact_sheet(exports: dict[str, Image.Image], out_path: str, cols: int = 6):
    """Renders labeled checkerboard contact sheet of exported sprites for visual QA."""
    if not exports:
        return
    names = list(exports.keys())
    max_w = max(im.width for im in exports.values())
    max_h = max(im.height for im in exports.values())
    cell_w = max(112, max_w + 18)
    cell_h = max(116, max_h + 26)
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (26, 30, 42))
    draw = ImageDraw.Draw(sheet)

    for idx, name in enumerate(names):
        r = idx // cols
        c = idx % cols
        x0 = c * cell_w
        y0 = r * cell_h
        im = exports[name]
        # Subtle dark/mid checkerboard inside preview frame
        bx = x0 + (cell_w - im.width) // 2
        by = y0 + 6
        for cy in range(0, im.height, 8):
            for cx in range(0, im.width, 8):
                chk = (46, 52, 70) if ((cx // 8 + cy // 8) % 2 == 0) else (36, 40, 56)
                draw.rectangle([bx + cx, by + cy, bx + min(im.width, cx + 8) - 1, by + min(im.height, cy + 8) - 1], fill=chk)
        sheet.paste(im, (bx, by), im)
        draw.rectangle([bx, by, bx + im.width - 1, by + im.height - 1], outline=(80, 95, 130))
        draw.text((x0 + 4, y0 + im.height + 9), name[:18], fill=(220, 235, 255))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)


def export_all_bosses() -> dict[str, Image.Image]:
    os.makedirs(SPRITES_DIR, exist_ok=True)
    all_exports: dict[str, Image.Image] = {}

    # 1. EMPEROR MANTIS (64x64 RGBA, canonical RIGHT-facing)
    mantis_cells = find_grid_cells(SHEET_MANTIS)
    mantis_exports = {
        "mantis_armored": fit_to_canvas(mantis_cells[0][0], (64, 64), target_height=58, max_width=60, center_vertical=True, flip_horiz=False),
        "mantis_armored_1": fit_to_canvas(mantis_cells[0][1], (64, 64), target_height=58, max_width=60, center_vertical=True, flip_horiz=False),
        "mantis_dive": fit_to_canvas(mantis_cells[0][2], (64, 64), target_height=58, max_width=62, center_vertical=True, flip_horiz=False),
        "mantis_exposed": fit_to_canvas(mantis_cells[1][0], (64, 64), target_height=58, max_width=60, center_vertical=True, flip_horiz=False),
        "mantis_exposed_1": fit_to_canvas(mantis_cells[1][1], (64, 64), target_height=58, max_width=60, center_vertical=True, flip_horiz=False),
        "mantis_enraged": fit_to_canvas(mantis_cells[1][2], (64, 64), target_height=60, max_width=62, center_vertical=True, flip_horiz=False, boost_brightness=1.06),
    }

    # 2. THE DREAD HOUND COLOSSUS (96x96 RGBA, canonical LEFT-facing)
    hound_cells = find_grid_cells(SHEET_HOUND)
    hound_exports = {
        "hound_idle": fit_to_canvas(hound_cells[0][0], (96, 96), target_height=76, max_width=90, baseline_y=91, flip_horiz=False),
        "hound_idle_1": fit_to_canvas(hound_cells[0][1], (96, 96), target_height=78, max_width=90, baseline_y=91, flip_horiz=False),
        "hound_lunge": fit_to_canvas(hound_cells[0][2], (96, 96), target_height=76, max_width=92, baseline_y=91, flip_horiz=False),
        # Bottom row of Hound sheet faces right, so flip howl/flame/dazed to canonical LEFT!
        "hound_howl": fit_to_canvas(hound_cells[1][0], (96, 96), target_height=84, max_width=88, baseline_y=91, flip_horiz=True),
        "hound_flame": fit_to_canvas(hound_cells[1][1], (96, 96), target_height=78, max_width=92, baseline_y=91, flip_horiz=True, boost_brightness=1.05),
        "hound_dazed": fit_to_canvas(hound_cells[1][2], (96, 96), target_height=68, max_width=90, baseline_y=91, flip_horiz=True),
    }

    # 3. FALO THE FROSTBITE SNOWMAN (64x64 RGBA, canonical LEFT-facing -> flipped from sheet)
    falo_cells = find_grid_cells(SHEET_FALO)
    falo_exports = {
        "falo_idle": fit_to_canvas(falo_cells[0][0], (64, 64), target_height=58, max_width=58, baseline_y=62, flip_horiz=True),
        "falo_idle_1": fit_to_canvas(falo_cells[0][1], (64, 64), target_height=58, max_width=58, baseline_y=62, flip_horiz=True),
        "falo_throw": fit_to_canvas(falo_cells[0][2], (64, 64), target_height=58, max_width=60, baseline_y=62, flip_horiz=True),
        "falo_throw_1": fit_to_canvas(falo_cells[1][0], (64, 64), target_height=58, max_width=60, baseline_y=62, flip_horiz=True),
        "falo_vulnerable": fit_to_canvas(falo_cells[1][1], (64, 64), target_height=56, max_width=56, baseline_y=62, flip_horiz=True),
        "falo_melt": fit_to_canvas(falo_cells[1][2], (64, 64), target_height=34, max_width=58, baseline_y=62, flip_horiz=True),
    }

    # 4. ABYSSAL DEMON SHARK (96x64 RGBA, canonical LEFT-facing -> flipped from sheet)
    shark_cells = find_grid_cells(SHEET_SHARK)
    shark_exports = {
        "shark_idle": fit_to_canvas(shark_cells[0][0], (96, 64), target_height=56, max_width=90, center_vertical=True, flip_horiz=True),
        "shark_idle_1": fit_to_canvas(shark_cells[0][1], (96, 64), target_height=56, max_width=90, center_vertical=True, flip_horiz=True),
        "shark_charge": fit_to_canvas(shark_cells[0][2], (96, 64), target_height=58, max_width=92, center_vertical=True, flip_horiz=True),
        "shark_roar": fit_to_canvas(shark_cells[1][0], (96, 64), target_height=60, max_width=88, center_vertical=True, flip_horiz=True),
        "shark_dazed": fit_to_canvas(shark_cells[1][1], (96, 64), target_height=56, max_width=90, center_vertical=True, flip_horiz=True),
        "shark_enraged": fit_to_canvas(shark_cells[1][2], (96, 64), target_height=58, max_width=92, center_vertical=True, flip_horiz=True, boost_brightness=1.07),
    }

    # 5. ULTRA-JACKED GIGA TOAD (96x96 RGBA -> larger & extra jacked! canonical LEFT-facing -> flipped from sheets)
    tw_cells = find_grid_cells(SHEET_TOAD_WALK)
    ta_cells = find_grid_cells(SHEET_TOAD_ACT)

    toad_idle_0 = fit_to_canvas(tw_cells[0][0], (96, 96), target_height=84, max_width=88, baseline_y=92, flip_horiz=True)
    toad_idle_1 = fit_to_canvas(tw_cells[0][1], (96, 96), target_height=83, max_width=88, baseline_y=92, flip_horiz=True)
    toad_idle_2 = fit_to_canvas(tw_cells[0][0], (96, 96), target_height=84, max_width=88, baseline_y=92, flip_horiz=True, dy_offset=-1)
    toad_idle_3 = fit_to_canvas(tw_cells[0][1], (96, 96), target_height=83, max_width=88, baseline_y=92, flip_horiz=True, dy_offset=1)

    toad_walk_0 = fit_to_canvas(tw_cells[0][2], (96, 96), target_height=84, max_width=88, baseline_y=92, flip_horiz=True)
    toad_walk_1 = fit_to_canvas(tw_cells[1][0], (96, 96), target_height=83, max_width=88, baseline_y=92, flip_horiz=True, dy_offset=1)
    toad_walk_2 = fit_to_canvas(tw_cells[1][1], (96, 96), target_height=84, max_width=88, baseline_y=92, flip_horiz=True)
    toad_walk_3 = fit_to_canvas(tw_cells[1][2], (96, 96), target_height=84, max_width=88, baseline_y=92, flip_horiz=True)
    toad_walk_4 = fit_to_canvas(tw_cells[1][0], (96, 96), target_height=83, max_width=88, baseline_y=92, flip_horiz=True)
    toad_walk_5 = fit_to_canvas(tw_cells[0][2], (96, 96), target_height=84, max_width=88, baseline_y=92, flip_horiz=True, dy_offset=1)

    toad_slam_0 = fit_to_canvas(tw_cells[0][1], (96, 96), target_height=83, max_width=88, baseline_y=92, flip_horiz=True)
    toad_slam_1 = fit_to_canvas(ta_cells[0][0], (96, 96), target_height=93, max_width=92, baseline_y=93, flip_horiz=True)
    toad_slam_2 = fit_to_canvas(ta_cells[0][0], (96, 96), target_height=93, max_width=92, baseline_y=92, flip_horiz=True, boost_brightness=1.04)
    toad_slam_3 = fit_to_canvas(ta_cells[0][1], (96, 96), target_height=80, max_width=92, baseline_y=93, flip_horiz=True)

    toad_punch_0 = fit_to_canvas(ta_cells[0][2], (96, 96), target_height=86, max_width=90, baseline_y=92, flip_horiz=True)
    toad_punch_1 = fit_to_canvas(ta_cells[1][0], (96, 96), target_height=85, max_width=94, baseline_y=92, flip_horiz=True)
    toad_punch_2 = fit_to_canvas(ta_cells[1][0], (96, 96), target_height=86, max_width=94, baseline_y=92, flip_horiz=True, dx_offset=-1, boost_brightness=1.06)
    toad_punch_3 = fit_to_canvas(tw_cells[1][2], (96, 96), target_height=84, max_width=90, baseline_y=92, flip_horiz=True)

    toad_dazed_0 = fit_to_canvas(ta_cells[1][1], (96, 96), target_height=82, max_width=88, baseline_y=92, flip_horiz=True)
    toad_dazed_1 = fit_to_canvas(ta_cells[1][1], (96, 96), target_height=81, max_width=88, baseline_y=92, flip_horiz=True, dx_offset=-1)
    toad_dazed_2 = fit_to_canvas(ta_cells[1][1], (96, 96), target_height=82, max_width=88, baseline_y=92, flip_horiz=True, dx_offset=1)
    toad_dazed_3 = fit_to_canvas(ta_cells[1][1], (96, 96), target_height=81, max_width=88, baseline_y=92, flip_horiz=True, dy_offset=1)

    toad_enraged_0 = fit_to_canvas(ta_cells[1][2], (96, 96), target_height=93, max_width=92, baseline_y=93, flip_horiz=True)
    toad_enraged_1 = fit_to_canvas(ta_cells[1][2], (96, 96), target_height=93, max_width=92, baseline_y=93, flip_horiz=True, boost_brightness=1.10)
    toad_enraged_2 = fit_to_canvas(ta_cells[1][2], (96, 96), target_height=93, max_width=92, baseline_y=93, flip_horiz=True, dx_offset=-1, boost_brightness=1.06)
    toad_enraged_3 = fit_to_canvas(ta_cells[1][2], (96, 96), target_height=93, max_width=92, baseline_y=92, flip_horiz=True)

    toad_exports = {
        "toad_idle": toad_idle_0,
        "toad_idle_1": toad_idle_1,
        "toad_walk_0": toad_walk_0,
        "toad_walk_1": toad_walk_1,
        "toad_slam": toad_slam_3,
        "toad_punch": toad_punch_1,
        "toad_dazed": toad_dazed_0,
        "toad_enraged": toad_enraged_0,
        "toad_idle_0": toad_idle_0,
        "toad_idle_2": toad_idle_2,
        "toad_idle_3": toad_idle_3,
        "toad_walk_2": toad_walk_2,
        "toad_walk_3": toad_walk_3,
        "toad_walk_4": toad_walk_4,
        "toad_walk_5": toad_walk_5,
        "toad_slam_0": toad_slam_0,
        "toad_slam_1": toad_slam_1,
        "toad_slam_2": toad_slam_2,
        "toad_slam_3": toad_slam_3,
        "toad_punch_0": toad_punch_0,
        "toad_punch_1": toad_punch_1,
        "toad_punch_2": toad_punch_2,
        "toad_punch_3": toad_punch_3,
        "toad_dazed_0": toad_dazed_0,
        "toad_dazed_1": toad_dazed_1,
        "toad_dazed_2": toad_dazed_2,
        "toad_dazed_3": toad_dazed_3,
        "toad_enraged_0": toad_enraged_0,
        "toad_enraged_1": toad_enraged_1,
        "toad_enraged_2": toad_enraged_2,
        "toad_enraged_3": toad_enraged_3,
    }

    for group_name, group in (
        ("mantis", mantis_exports),
        ("hound", hound_exports),
        ("falo", falo_exports),
        ("shark", shark_exports),
        ("toad", toad_exports),
    ):
        for fname, surf in group.items():
            surf.save(os.path.join(SPRITES_DIR, f"{fname}.png"))
        all_exports.update(group)
        print(f"[{group_name}] Exported {len(group)} frames")

    build_contact_sheet(
        {**mantis_exports, **hound_exports, **falo_exports, **shark_exports},
        os.path.join(SCRATCH_DIR, "boss_sheets_qa_part1.png"),
        cols=6,
    )
    build_contact_sheet(
        toad_exports,
        os.path.join(SCRATCH_DIR, "boss_sheets_qa_toad.png"),
        cols=6,
    )
    print("Contact sheets saved to scratch/ for visual QA.")
    return all_exports


if __name__ == "__main__":
    export_all_bosses()
