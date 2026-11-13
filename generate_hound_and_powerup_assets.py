import os
import math
import random
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
BG_DIR = os.path.join(BASE_DIR, "backgrounds")
SPRITES_DIR = os.path.join(BASE_DIR, "sprites")

os.makedirs(BG_DIR, exist_ok=True)
os.makedirs(SPRITES_DIR, exist_ok=True)

def generate_hound_palace_background():
    w, h = 640, 360
    img = Image.new("RGBA", (w, h), (18, 8, 16, 255))
    d = ImageDraw.Draw(img)

    # 1. Vertical gradient for vaulted stone hall (dark ceiling to dark stone floor)
    y_grad = np.linspace(0.0, 1.0, h)[:, np.newaxis]
    bg_arr = np.zeros((h, w, 3), dtype=np.uint8)
    top_c = (20, 6, 18)
    bot_c = (48, 14, 32)
    for c in range(3):
        bg_arr[:, :, c] = (top_c[c] * (1.0 - y_grad) + bot_c[c] * y_grad).astype(np.uint8)
    base_img = Image.fromarray(bg_arr, mode="RGB").convert("RGBA")
    bd = ImageDraw.Draw(base_img)

    # 2. Vaulted ceiling gothic ribs
    for arch_x in range(40, w + 40, 80):
        # Rib curves meeting at vaulted ceiling
        bd.arc([arch_x - 70, -20, arch_x + 70, 180], start=180, end=360, fill=(70, 20, 45, 180), width=3)
        bd.arc([arch_x - 70, -20, arch_x + 70, 180], start=180, end=360, fill=(35, 10, 25, 255), width=1)

    # 3. Gothic Rose Window in Center (crimson & gold stained glass)
    win_cx, win_cy = w // 2, 110
    win_r = 54
    # Outer stone frame
    bd.ellipse([win_cx - win_r - 6, win_cy - win_r - 6, win_cx + win_r + 6, win_cy + win_r + 6], fill=(30, 10, 24, 255), outline=(90, 28, 55, 255), width=3)
    # Stained glass deep crimson
    bd.ellipse([win_cx - win_r, win_cy - win_r, win_cx + win_r, win_cy + win_r], fill=(120, 18, 38, 240), outline=(220, 50, 70, 255), width=2)
    # Internal radial petals (8-fold rosette)
    for i in range(8):
        ang = i * (math.tau / 8)
        pet_x = win_cx + int(math.cos(ang) * (win_r * 0.6))
        pet_y = win_cy + int(math.sin(ang) * (win_r * 0.6))
        bd.line([(win_cx, win_cy), (win_cx + int(math.cos(ang) * win_r), win_cy + int(math.sin(ang) * win_r))], fill=(40, 12, 28, 255), width=2)
        bd.ellipse([pet_x - 10, pet_y - 10, pet_x + 10, pet_y + 10], fill=(200, 35, 60, 200), outline=(255, 180, 60, 220), width=1)
    # Center golden eye
    bd.ellipse([win_cx - 12, win_cy - 12, win_cx + 12, win_cy + 12], fill=(255, 195, 45, 255), outline=(120, 20, 40, 255), width=2)
    bd.ellipse([win_cx - 5, win_cy - 8, win_cx + 5, win_cy + 8], fill=(30, 8, 16, 255)) # Slit pupil

    # 4. Massive stone pillars with iron bands
    for px in (45, 135, 225, 415, 505, 595):
        pw = 32
        bd.rectangle([px - pw // 2, 0, px + pw // 2, h], fill=(26, 10, 22, 255), outline=(50, 16, 36, 255), width=2)
        # Pillar highlight
        bd.line([(px - pw // 2 + 4, 0), (px - pw // 2 + 4, h)], fill=(75, 26, 52, 255), width=2)
        # Iron bands
        for by in range(40, h, 60):
            bd.rectangle([px - pw // 2 - 3, by, px + pw // 2 + 3, by + 6], fill=(65, 30, 45, 255), outline=(25, 8, 18, 255), width=1)
            # Hanging iron chains
            for step in range(0, 40, 6):
                cy = by + 6 + step
                bd.ellipse([px - 3, cy, px + 3, cy + 5], outline=(85, 40, 58, 240), width=1)

    # 5. Wall Braziers with blazing crimson-gold embers
    for bx in (90, 180, 460, 550):
        by = 220
        # Iron bracket
        bd.polygon([(bx - 12, by), (bx + 12, by), (bx + 8, by + 16), (bx - 8, by + 16)], fill=(45, 18, 30, 255), outline=(20, 6, 14, 255))
        # Fire glow
        bd.ellipse([bx - 14, by - 16, bx + 14, by + 4], fill=(255, 60, 40, 220))
        bd.ellipse([bx - 8, by - 12, bx + 8, by + 2], fill=(255, 195, 45, 255))
        bd.ellipse([bx - 4, by - 8, bx + 4, by], fill=(255, 255, 220, 255))

    # 6. Low atmospheric fog / mist
    fog = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for fy in range(h - 90, h, 8):
        alpha = int(45 * ((fy - (h - 90)) / 90.0))
        fd.rectangle([0, fy, w, fy + 8], fill=(85, 20, 45, alpha))
    fog = fog.filter(ImageFilter.GaussianBlur(radius=8))
    base_img = Image.alpha_composite(base_img, fog)

    # Save
    base_img.convert("RGB").save(os.path.join(BG_DIR, "bg_hound_palace.png"))
    base_img.convert("RGB").save(os.path.join(BG_DIR, "proc_hound_palace_sky.png"))
    print("Generated bg_hound_palace.png & proc_hound_palace_sky.png!")

    # 7. Front Parallax Framing Layer: parallax_hound_palace_mid.png
    mid_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    md = ImageDraw.Draw(mid_img)
    # Foreground gothic arch silhouettes on sides
    for side_x in (0, w - 70):
        md.rectangle([side_x, 0, side_x + 70, h], fill=(22, 8, 18, 235), outline=(50, 16, 36, 255))
        for y_arch in range(30, h, 80):
            md.arc([side_x - 20, y_arch, side_x + 90, y_arch + 70], start=180, end=360, fill=(75, 24, 48, 255), width=3)
    mid_img.save(os.path.join(BG_DIR, "parallax_hound_palace_mid.png"))
    print("Generated parallax_hound_palace_mid.png!")

def generate_powerup_sprites():
    # 1. Vitality Heart Container (24x24) - Relic 'V'
    # Sacred winged golden heart container with brilliant ruby jewel and 6th HP glow!
    vh = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vh)
    
    # Outer gold winged crest
    vd.ellipse([1, 6, 22, 21], fill=(220, 170, 30, 255), outline=(90, 60, 10, 255))
    vd.polygon([(2, 11), (22, 11), (12, 23)], fill=(220, 170, 30, 255))
    # Golden wings
    vd.polygon([(0, 6), (5, 3), (7, 10), (2, 12)], fill=(255, 215, 65, 255), outline=(110, 75, 15, 255))
    vd.polygon([(23, 6), (18, 3), (16, 10), (21, 12)], fill=(255, 215, 65, 255), outline=(110, 75, 15, 255))
    # Deep ruby heart core
    vd.ellipse([4, 6, 12, 14], fill=(235, 35, 65, 255))
    vd.ellipse([11, 6, 19, 14], fill=(235, 35, 65, 255))
    vd.polygon([(4, 10), (19, 10), (12, 21)], fill=(235, 35, 65, 255))
    # Bright inner highlight & glints
    vd.ellipse([6, 7, 9, 10], fill=(255, 140, 165, 255))
    vd.point((7, 8), fill=(255, 255, 255, 255))
    vd.point((14, 8), fill=(255, 255, 255, 255))
    vh.save(os.path.join(SPRITES_DIR, "powerup_heart_container.png"))
    print("Generated powerup_heart_container.png!")

    # 2. Falo's Heart (24x24) - Relic Snowflake item
    fh = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fh)
    cx, cy = 12, 12
    # Outer icy glow halo
    fd.ellipse([2, 2, 21, 21], fill=(80, 190, 255, 65))
    fd.ellipse([4, 4, 19, 19], fill=(130, 225, 255, 120))
    # 6-fold crystal snowflake branches
    for i in range(6):
        ang = i * (math.pi / 3.0)
        ex = cx + math.cos(ang) * 9.5
        ey = cy + math.sin(ang) * 9.5
        fd.line([(cx, cy), (ex, ey)], fill=(255, 255, 255, 255), width=2)
        # Side crystal barbs
        barb_dist = 5.5
        bx = cx + math.cos(ang) * barb_dist
        by = cy + math.sin(ang) * barb_dist
        for side in (-0.55, 0.55):
            sx = bx + math.cos(ang + side) * 3.5
            sy = by + math.sin(ang + side) * 3.5
            fd.line([(bx, by), (sx, sy)], fill=(180, 240, 255, 255), width=1)
        # Diamond tip
        fd.rectangle([int(ex - 1), int(ey - 1), int(ex + 1), int(ey + 1)], fill=(225, 250, 255, 255))
    # Center diamond jewel
    fd.polygon([(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)], fill=(210, 245, 255, 255), outline=(55, 140, 235, 255))
    fd.point((cx, cy), fill=(255, 255, 255, 255))
    fh.save(os.path.join(SPRITES_DIR, "powerup_falo_heart.png"))
    print("Generated powerup_falo_heart.png!")

    # 3. Muhlaser Beam Relic ('L')
    lh = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lh)
    # Energy prism
    ld.ellipse([2, 4, 21, 19], fill=(20, 80, 110, 255), outline=(50, 180, 230, 255), width=2)
    # Glowing mouth emitter lens
    ld.ellipse([5, 6, 18, 17], fill=(85, 240, 255, 230))
    ld.ellipse([8, 8, 15, 15], fill=(255, 255, 255, 255))
    # Beam arcs
    ld.arc([1, 2, 22, 21], start=120, end=240, fill=(110, 250, 255, 255), width=2)
    ld.arc([1, 2, 22, 21], start=300, end=60, fill=(110, 250, 255, 255), width=2)
    lh.save(os.path.join(SPRITES_DIR, "powerup_muhlaser.png"))
    print("Generated powerup_muhlaser.png!")

if __name__ == "__main__":
    generate_hound_palace_background()
    generate_powerup_sprites()
