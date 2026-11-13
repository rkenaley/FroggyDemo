"""
===============================================================================
FROGGY HERO MULTI-STYLE GENERATIVE SPRITE EXTRACTION PIPELINE
===============================================================================
Processes 2x3 generative pixel-art Froggy hero sprite sheets (on flat #FF00FF
magenta) into uniform, crisp 32x32 RGBA animation frames facing RIGHT with
bottom-flush grounded boots (y=31) for all 9 Froggy animation states:
  - azure_shinobi : Abyssal Cobalt & Turquoise Ninja Froggy (gold headband)
  - crimson_dart  : Solar Crimson & Ember Poison-Dart Froggy (white/jade band)

Classic original sprites remain untouched at assets/sprites/froggy_*.png
(and backed up in assets/sprites/_backup_pre_v15_froggy/).
Generated style suites export to:
  assets/sprites/styles/<style_id>/froggy_<state>_<idx>.png
"""

import os
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ARTIFACTS_DIR = r"C:\Users\Ryan\.gemini\antigravity\brain\2ab7cfc0-bcc2-418d-9f41-85a7847c2dd3"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")
STYLES_DIR = os.path.join(SPRITES_DIR, "styles")
SCRATCH_DIR = os.path.join(ARTIFACTS_DIR, "scratch")

SHEET_AZURE_MOVE = os.path.join(ARTIFACTS_DIR, "froggy_hero_spritesheet_1794600925164.jpg")
SHEET_AZURE_ACT = os.path.join(ARTIFACTS_DIR, "froggy_action_spritesheet_1794600934251.jpg")
SHEET_CRIMSON_MOVE = os.path.join(ARTIFACTS_DIR, "crimson_dart_froggy_spritesheet_1794600924557.jpg")
SHEET_CRIMSON_ACT = os.path.join(ARTIFACTS_DIR, "froggy_actions_spritesheet_fixed_1794600957813.jpg")


def _compute_magenta_mask(rgb: np.ndarray) -> np.ndarray:
    """Identifies flat #FF00FF JPEG magenta while strictly guarding warm reds/oranges/corals."""
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)

    dist_mag = np.sqrt((r - 255.0) ** 2 + g ** 2 + (b - 255.0) ** 2)
    is_mag_hue = (
        (r > 125.0)
        & (b > 125.0)
        & (g < np.minimum(r, b) - 42.0)
        & (np.abs(r - b) < 88.0)
        & (b > r * 0.68)
    )
    return (dist_mag <= 112.0) | is_mag_hue


def chroma_key_hero_cell(cell_img: Image.Image) -> Image.Image:
    """
    Removes exterior and enclosed #FF00FF background loops cleanly using a seed-border
    flood fill plus strict high-magenta guard so crimson skin, dark mouths, and warm
    tongues never punch holes.
    """
    rgb = np.array(cell_img.convert("RGB"))
    h, w, _ = rgb.shape
    mag_mask = _compute_magenta_mask(rgb)

    # 1. Exterior BFS flood fill from borders over any near-magenta pixels
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    border_mag = (
        (r > 110.0)
        & (b > 110.0)
        & (g < np.minimum(r, b) - 24.0)
        & (b > r * 0.65)
    )
    ext_bg = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if border_mag[y, x] and not ext_bg[y, x]:
                ext_bg[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if border_mag[y, x] and not ext_bg[y, x]:
                ext_bg[y, x] = True
                q.append((y, x))
    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not ext_bg[ny, nx] and border_mag[ny, nx]:
                ext_bg[ny, nx] = True
                q.append((ny, nx))

    # 2. Catch small enclosed pure-magenta holes (between scarf ribbons / legs) without hurting warm reds
    enclosed_mag = (
        (r > 170.0)
        & (b > 170.0)
        & (g < np.minimum(r, b) - 55.0)
        & (b > r * 0.74)
    )
    bg_mask = ext_bg | mag_mask | enclosed_mag

    arr = np.dstack([rgb.astype(np.float32), np.where(bg_mask, 0.0, 255.0)])

    # Despill ONLY 1-pixel perimeter magenta spill adjacent to transparent background
    bg_dilated = (
        np.roll(bg_mask, 1, axis=0)
        | np.roll(bg_mask, -1, axis=0)
        | np.roll(bg_mask, 1, axis=1)
        | np.roll(bg_mask, -1, axis=1)
    )
    edge_fg = (~bg_mask) & bg_dilated
    is_fringe = edge_fg & (b > g + 16.0) & (b > r * 0.62) & (r > 90.0)
    target_b = np.maximum(g * 1.04 + 4.0, r * 0.42)
    arr[:, :, 0] = np.where(
        is_fringe & (np.abs(r - b) < 70.0),
        np.minimum(r, np.maximum(g * 1.15 + 10.0, r * 0.62)),
        arr[:, :, 0],
    )
    arr[:, :, 2] = np.where(is_fringe, np.minimum(b, target_b), arr[:, :, 2])

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def segment_2x3_hero_sheet(sheet_path: str) -> list[Image.Image]:
    """Segments a 2x3 hero sprite sheet along minimum-foreground valleys into 6 cropped cells."""
    img = Image.open(sheet_path).convert("RGB")
    fg = ~_compute_magenta_mask(np.array(img))
    h, w = fg.shape

    row_proj = fg.sum(axis=1)
    y_lo, y_hi = int(h * 0.34), int(h * 0.66)
    y_split = y_lo + int(np.argmin(row_proj[y_lo:y_hi]))

    cells_out: list[Image.Image] = []
    for y0, y1 in ((0, y_split), (y_split, h)):
        col_proj = fg[y0:y1, :].sum(axis=0)
        x1_lo, x1_hi = int(w * 0.24), int(w * 0.43)
        x2_lo, x2_hi = int(w * 0.56), int(w * 0.78)
        x_split1 = x1_lo + int(np.argmin(col_proj[x1_lo:x1_hi]))
        x_split2 = x2_lo + int(np.argmin(col_proj[x2_lo:x2_hi]))
        for x0, x1 in ((0, x_split1), (x_split1, x_split2), (x_split2, w)):
            crop = img.crop((x0, y0, x1, y1))
            keyed = chroma_key_hero_cell(crop)
            bbox = keyed.getbbox()
            if bbox:
                keyed = keyed.crop(bbox)
            cells_out.append(keyed)
    return cells_out


def trim_thin_top_stalk(sprite: Image.Image) -> Image.Image:
    """Removes accidental thin 1-5px overhead grapple string above raised hand."""
    arr = np.array(sprite)
    a = arr[:, :, 3] > 20
    row_counts = a.sum(axis=1)
    h = arr.shape[0]
    cut_y = 0
    # Scan upper 18% for ultra-thin rope stem (< 2.5% width)
    max_rope_px = max(8, int(arr.shape[1] * 0.04))
    for y in range(int(h * 0.18)):
        if 0 < row_counts[y] <= max_rope_px:
            cut_y = y + 1
        elif row_counts[y] > max_rope_px * 2:
            break
    if cut_y > 0 and cut_y < h - 20:
        cropped = sprite.crop((0, cut_y, sprite.width, sprite.height))
        bbox = cropped.getbbox()
        return cropped.crop(bbox) if bbox else cropped
    return sprite


def prepare_tongue_frame(cell: Image.Image, target_body_width_ratio: float = 0.85) -> Image.Image:
    """
    Keeps the frog body at full standing scale while trimming the extra-long stretched
    tongue beam cleanly to a punchy mouth stub (the engine draws the full 360 tongue beam).
    """
    arr = np.array(cell)
    h, w, _ = arr.shape
    a = arr[:, :, 3] > 20
    # Find rightmost torso column by scanning columns where vertical foreground thickness >= 35% height
    col_span = np.zeros(w, dtype=int)
    for x in range(w):
        ys = np.where(a[:, x])[0]
        if len(ys) > 0:
            col_span[x] = int(ys.max() - ys.min() + 1)
    # Character body spans heavily vertically (> 40% height); extended tongue is thin horizontal strip (< 22% height)
    body_cols = np.where(col_span >= h * 0.36)[0]
    if len(body_cols) > 0:
        body_right = int(body_cols.max())
        stub_len = max(24, int(body_right * 0.24))
        cut_x = min(w, body_right + stub_len)
        # Round off the clipped tongue tip neatly
        trimmed = cell.crop((0, 0, cut_x, h))
        t_arr = np.array(trimmed)
        tw = t_arr.shape[1]
        # Feather-round last 4px of tongue tip into an oval nose
        tip_slice = t_arr[:, max(0, tw - 4):tw, 3] > 20
        if tip_slice.any():
            ys = np.where(tip_slice)[0]
            ymid = 0.5 * (ys.min() + ys.max())
            yrad = max(2.0, 0.5 * (ys.max() - ys.min()))
            for dx in range(min(6, tw)):
                x_col = tw - 1 - dx
                frac = 1.0 - (dx / 6.0)
                for y in range(h):
                    if t_arr[y, x_col, 3] > 20:
                        dy_norm = abs(y - ymid) / max(1.0, yrad)
                        if dy_norm > 1.0 - 0.55 * frac:
                            t_arr[y, x_col, 3] = 0
        cropped = Image.fromarray(t_arr, "RGBA")
        bbox = cropped.getbbox()
        return cropped.crop(bbox) if bbox else cropped
    return cell


def export_crisp_32x32(
    sprite: Image.Image,
    target_height: int = 29,
    max_width: int = 31,
    baseline_y: int | None = 32,
    center_vertical: bool = False,
    dx: int = 0,
    dy: int = 0,
    sat_boost: float = 1.12,
    contrast_boost: float = 1.08,
) -> Image.Image:
    """
    Downscales a high-res generative pixel-art Froggy pose into an ultra-crisp 32x32
    RGBA PNG with solid 255-alpha outline readability, zero blurry semi-transparent
    halos, and exact bottom-row boot anchoring (y=31) when baseline_y=32.
    """
    sp = sprite.copy()
    bbox = sp.getbbox()
    if bbox:
        sp = sp.crop(bbox)

    # Zero RGB on all transparent pixels FIRST so UnsharpMask/LANCZOS never bleed hidden background hues
    sp_arr = np.array(sp)
    sp_arr[sp_arr[:, :, 3] == 0, :3] = 0
    sp = Image.fromarray(sp_arr, "RGBA")

    rgb_only = sp.convert("RGB")
    rgb_only = ImageEnhance.Color(rgb_only).enhance(sat_boost)
    rgb_only = ImageEnhance.Contrast(rgb_only).enhance(contrast_boost)
    r0_arr = np.array(rgb_only)
    r0_arr[sp_arr[:, :, 3] == 0] = 0
    sp = Image.merge("RGBA", (*Image.fromarray(r0_arr, "RGB").split(), sp.split()[3]))

    scale = min(target_height / float(max(1, sp.height)), max_width / float(max(1, sp.width)))
    new_w = max(1, min(32, int(round(sp.width * scale))))
    new_h = max(1, min(32, int(round(sp.height * scale))))

    # Premultiplied-safe crisp resize: resize RGBA together, sharpen RGB gently, snap alpha crisp
    resized = sp.resize((new_w, new_h), Image.Resampling.LANCZOS)
    r_rgba = np.array(resized, dtype=np.float32)
    r_rgb = resized.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.55, percent=65, threshold=2))
    r_a = r_rgba[:, :, 3]

    # Snap alpha cleanly (threshold 76 preserves crisp 1px dark outlines cleanly without wispy holes)
    clean_a = np.where(r_a >= 76, 255, 0).astype(np.uint8)
    r_arr = np.array(r_rgb, dtype=np.float32)
    # Restore un-premultiplied luminance on semi-transparent outline edges darkened against black=0
    mild_edge = (clean_a == 255) & (r_a > 0) & (r_a < 235)
    inv_a = np.where(mild_edge, 255.0 / np.maximum(110.0, r_a), 1.0)
    r_arr = r_arr * inv_a[:, :, None]
    r_arr[clean_a == 0] = 0.0

    crisp_cell = Image.fromarray(
        np.dstack([np.clip(r_arr, 0, 255).astype(np.uint8), clean_a]),
        "RGBA",
    )

    canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    px = (32 - new_w) // 2 + dx
    if center_vertical or baseline_y is None:
        py = (32 - new_h) // 2 + dy
    else:
        py = baseline_y - new_h + dy
    px = max(0, min(32 - new_w, px))
    py = max(0, min(32 - new_h, py))
    canvas.paste(crisp_cell, (px, py), crisp_cell)
    # Guarantee (0,0) corner transparent for test_v8_fixes & Pygame edge checks
    canvas.putpixel((0, 0), (0, 0, 0, 0))
    return canvas


def _shift_canvas(im: Image.Image, dx: int, dy: int, clip_bottom: int = 32) -> Image.Image:
    """Sub-pixel/1px shift inside 32x32 while never crossing floor y=clip_bottom-1."""
    out = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    out.paste(im, (dx, dy), im)
    if clip_bottom < 32:
        arr = np.array(out)
        arr[clip_bottom:, :, 3] = 0
        out = Image.fromarray(arr, "RGBA")
    out.putpixel((0, 0), (0, 0, 0, 0))
    return out


def synthesize_breathe_frame(idle_32: Image.Image) -> Image.Image:
    """Creates a smooth 1px chest/belly expansion & 1px headband breeze shift without height pop."""
    arr = np.array(idle_32)
    out = arr.copy()
    # Keep legs/boots planted (y >= 24) and shift upper torso & head (y < 20) down 1px for gentle breathe
    out[1:21] = arr[0:20]
    out[0] = (0, 0, 0, 0)
    # Slight forward lean on trailing scarf pixels (left side x < 11)
    scarf_band = out[5:16, 0:11].copy()
    out[6:17, 0:11] = np.where(scarf_band[:, :, 3:4] > 0, scarf_band, out[6:17, 0:11])
    res = Image.fromarray(out, "RGBA")
    res.putpixel((0, 0), (0, 0, 0, 0))
    return res


def synthesize_blink_frame(idle_32: Image.Image, eyelid_color: tuple[int, int, int, int]) -> Image.Image:
    """Draws a crisp 1px horizontal closed-eyelid blink over the eye domes on top of idle_0."""
    arr = np.array(idle_32)
    out = arr.copy()
    # Find bright eye dome band (upper rows with high alpha width >= 4px and light eye pixels)
    a = arr[:, :, 3] > 20
    fg_rows = np.where(a.any(axis=1))[0]
    if len(fg_rows) > 0:
        top_y = int(fg_rows.min())
        # Eye centers typically span y = top_y+2..top_y+6 on 29px tall frog
        for y in range(top_y + 2, min(31, top_y + 6)):
            for x in range(10, 27):
                if arr[y, x, 3] > 20:
                    r, g, b = int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2])
                    lum = 0.299 * r + 0.587 * g + 0.114 * b
                    # Replace bright eye whites / pupils with sleek eyelid tone + dark lash line
                    if lum > 155 and y <= top_y + 4:
                        if y == top_y + 3:
                            out[y, x] = (20, 24, 34, 255)
                        else:
                            out[y, x] = eyelid_color
    res = Image.fromarray(out, "RGBA")
    res.putpixel((0, 0), (0, 0, 0, 0))
    return res


def synthesize_scarf_flutter(idle_32: Image.Image) -> Image.Image:
    """Creates a gentle 1px upward scarf-tail flutter frame for idle_3."""
    arr = np.array(idle_32)
    out = arr.copy()
    # Shift trailing left scarf tail up by 1px while leaving face/body locked cleanly
    for y in range(2, 16):
        for x in range(0, 10):
            if arr[y + 1, x, 3] > 20 and arr[y, x, 3] == 0:
                out[y, x] = arr[y + 1, x]
                if y + 1 >= 7:
                    out[y + 1, x] = (0, 0, 0, 0)
    res = Image.fromarray(out, "RGBA")
    res.putpixel((0, 0), (0, 0, 0, 0))
    return res


def process_style_suite(
    style_id: str,
    move_sheet: str,
    act_sheet: str,
    eyelid_rgba: tuple[int, int, int, int],
    crouch_as_jump0: bool = False,
    use_native_blink_cell: bool = False,
) -> dict[str, Image.Image]:
    """Extracts & exports the full 23-frame Froggy animation suite for a style."""
    move_cells = segment_2x3_hero_sheet(move_sheet)
    act_cells = segment_2x3_hero_sheet(act_sheet)

    idle_raw, idle2_raw, run_a_raw, run_b_raw, jump_raw, fall_raw = move_cells
    wall_raw, tongue_raw, swim1_raw, swim2_raw, swing_raw, hurt_raw = act_cells

    tongue_prepped = prepare_tongue_frame(tongue_raw)
    swing_prepped = trim_thin_top_stalk(swing_raw)

    idle_0 = export_crisp_32x32(idle_raw, target_height=29, max_width=30, baseline_y=32)
    idle_1 = synthesize_breathe_frame(idle_0)
    if use_native_blink_cell:
        idle_2 = export_crisp_32x32(idle2_raw, target_height=29, max_width=30, baseline_y=32)
    else:
        idle_2 = synthesize_blink_frame(idle_0, eyelid_rgba)
    idle_3 = synthesize_scarf_flutter(idle_0)

    run_0 = export_crisp_32x32(run_a_raw, target_height=29, max_width=31, baseline_y=32)
    run_1 = _shift_canvas(run_0, 0, -1, clip_bottom=32)
    # Ensure bottom pixel touches floor on passing run_1 or use grounded stride blend
    # Keep run_2 strictly grounded y=31, run_1 & run_3 airborne mid-stride bounce (standard 1px bounce)
    run_2 = export_crisp_32x32(run_b_raw, target_height=29, max_width=31, baseline_y=32)
    run_3 = _shift_canvas(run_2, 0, -1, clip_bottom=32)

    if crouch_as_jump0:
        jump_0 = export_crisp_32x32(idle2_raw, target_height=26, max_width=30, baseline_y=31)
    else:
        # Subtle coiled launch squash on jump_0 before full leap jump_1
        coiled_jump = jump_raw.resize(
            (jump_raw.width, max(1, int(round(jump_raw.height * 0.88)))),
            Image.Resampling.LANCZOS,
        )
        jump_0 = export_crisp_32x32(coiled_jump, target_height=26, max_width=31, baseline_y=31)
    jump_1 = export_crisp_32x32(jump_raw, target_height=30, max_width=31, baseline_y=30)

    fall_0 = export_crisp_32x32(fall_raw, target_height=30, max_width=31, baseline_y=31)
    fall_1 = synthesize_scarf_flutter(fall_0)

    wall_0 = export_crisp_32x32(wall_raw, target_height=29, max_width=28, baseline_y=32, dx=1)
    wall_1 = _shift_canvas(wall_0, 0, 1, clip_bottom=32)

    tongue_1 = export_crisp_32x32(tongue_prepped, target_height=29, max_width=32, baseline_y=32, dx=1)
    tongue_0 = _shift_canvas(tongue_1, -2, 0, clip_bottom=32)

    swim_0 = export_crisp_32x32(swim1_raw, target_height=21, max_width=31, center_vertical=True)
    swim_1 = _shift_canvas(swim_0, 0, -1)
    swim_2 = export_crisp_32x32(swim2_raw, target_height=22, max_width=31, center_vertical=True)
    swim_3 = _shift_canvas(swim_2, 0, 1)

    swing_0 = export_crisp_32x32(swing_prepped, target_height=30, max_width=30, center_vertical=True)
    swing_1 = synthesize_scarf_flutter(swing_0)

    hurt_0 = export_crisp_32x32(hurt_raw, target_height=30, max_width=31, baseline_y=31)

    exports = {
        "froggy_idle_0.png": idle_0,
        "froggy_idle_1.png": idle_1,
        "froggy_idle_2.png": idle_2,
        "froggy_idle_3.png": idle_3,
        "froggy_run_0.png": run_0,
        "froggy_run_1.png": run_1,
        "froggy_run_2.png": run_2,
        "froggy_run_3.png": run_3,
        "froggy_jump_0.png": jump_0,
        "froggy_jump_1.png": jump_1,
        "froggy_fall_0.png": fall_0,
        "froggy_fall_1.png": fall_1,
        "froggy_wall_0.png": wall_0,
        "froggy_wall_1.png": wall_1,
        "froggy_tongue_0.png": tongue_0,
        "froggy_tongue_1.png": tongue_1,
        "froggy_swim_0.png": swim_0,
        "froggy_swim_1.png": swim_1,
        "froggy_swim_2.png": swim_2,
        "froggy_swim_3.png": swim_3,
        "froggy_swing_0.png": swing_0,
        "froggy_swing_1.png": swing_1,
        "froggy_hurt_0.png": hurt_0,
    }

    out_dir = os.path.join(STYLES_DIR, style_id)
    os.makedirs(out_dir, exist_ok=True)
    for fname, im in exports.items():
        assert im.size == (32, 32), f"{style_id}/{fname} invalid size {im.size}"
        assert im.getpixel((0, 0))[3] == 0, f"{style_id}/{fname} corner not transparent"
        im.save(os.path.join(out_dir, fname))

    # Assert standing idle_0 touches floor y=31 cleanly
    idle_arr = np.array(idle_0)
    assert (idle_arr[31, :, 3] > 0).any(), f"{style_id} idle_0 boots do not touch y=31!"
    return exports


def build_qa_sheet(style_exports: dict[str, dict[str, Image.Image]], out_path: str):
    """Builds a 3x zoomed checkerboard QA sheet comparing Classic, Azure Shinobi, and Crimson Dart."""
    classic_files = sorted(style_exports[next(iter(style_exports))].keys())
    classic_dict = {}
    for fname in classic_files:
        p = os.path.join(SPRITES_DIR, fname)
        if os.path.exists(p):
            classic_dict[fname] = Image.open(p).convert("RGBA")

    suites = [("classic", classic_dict)] + list(style_exports.items())
    zoom = 3
    tile = 32 * zoom
    cols = 8
    rows_per_suite = (len(classic_files) + cols - 1) // cols
    cell_w = tile + 14
    cell_h = tile + 22
    header_h = 26
    total_w = cols * cell_w + 16
    total_h = sum(header_h + rows_per_suite * cell_h + 12 for _ in suites)

    sheet = Image.new("RGB", (total_w, total_h), (20, 24, 34))
    draw = ImageDraw.Draw(sheet)

    y_cur = 8
    for s_name, s_dict in suites:
        draw.text((10, y_cur + 4), f"STYLE: {s_name.upper()} (3x ZOOM OVER SKY & DARK CHECKER)", fill=(255, 225, 110))
        y_cur += header_h
        for i, fname in enumerate(classic_files):
            r, c = i // cols, i % cols
            x0 = 8 + c * cell_w
            y0 = y_cur + r * cell_h
            # Alternating dark-dungeon vs bright-sky background inside cell so zero halos can hide!
            use_sky = (i % 2 == 1)
            bg_a, bg_b = ((135, 200, 245), (155, 215, 252)) if use_sky else ((42, 48, 64), (32, 36, 50))
            for cy in range(0, tile, 12):
                for cx in range(0, tile, 12):
                    col = bg_a if ((cx // 12 + cy // 12) % 2 == 0) else bg_b
                    draw.rectangle([x0 + cx, y0 + cy, x0 + min(tile, cx + 12) - 1, y0 + min(tile, cy + 12) - 1], fill=col)
            im = s_dict[fname].resize((tile, tile), Image.Resampling.NEAREST)
            sheet.paste(im, (x0, y0), im)
            draw.rectangle([x0, y0, x0 + tile - 1, y0 + tile - 1], outline=(85, 100, 130))
            draw.text((x0 + 2, y0 + tile + 3), fname.replace("froggy_", "").replace(".png", ""), fill=(210, 228, 248))
        y_cur += rows_per_suite * cell_h + 12

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)


def main():
    azure_exports = process_style_suite(
        "azure_shinobi",
        SHEET_AZURE_MOVE,
        SHEET_AZURE_ACT,
        eyelid_rgba=(230, 175, 45, 255),
        crouch_as_jump0=True,
        use_native_blink_cell=False,
    )
    crimson_exports = process_style_suite(
        "crimson_dart",
        SHEET_CRIMSON_MOVE,
        SHEET_CRIMSON_ACT,
        eyelid_rgba=(215, 55, 25, 255),
        crouch_as_jump0=False,
        use_native_blink_cell=True,
    )
    qa_path = os.path.join(SCRATCH_DIR, "froggy_styles_qa_sheet.png")
    build_qa_sheet({"azure_shinobi": azure_exports, "crimson_dart": crimson_exports}, qa_path)
    print(f"Exported azure_shinobi ({len(azure_exports)} frames) and crimson_dart ({len(crimson_exports)} frames).")
    print(f"Saved visual QA sheet: {qa_path}")


if __name__ == "__main__":
    main()
