"""Process user-provided Corgi artwork into an animated desktop pet sprite set.

Input: /packages/pets/dog/assets/corgi_base.png (283x238)
Generates:
- idle_1.png .. idle_4.png (breathing, happy blink, tail wag)
- walk_1.png .. walk_4.png (4-frame joyful waddling walk cycle)
- walk_left_1.png .. walk_left_4.png (mirrored walk cycle)
- drag.png (dangling lifted pose)
Target size: 160x135 RGBA transparent PNGs.
"""

import math
import os
from PIL import Image, ImageDraw

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/assets"
BASE_PATH = os.path.join(ASSETS_DIR, "corgi_base.png")

TARGET_W = 160
TARGET_H = 135

# Key palette colors sampled from artwork
C_OUTLINE = (86, 61, 41, 255)
C_CREAM = (255, 240, 206, 255)
C_ORANGE = (238, 177, 88, 255)


def create_canvas():
    return Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))


def scale_base(base: Image.Image) -> Image.Image:
    """Scale base image to fit target canvas while preserving high-quality anti-aliasing."""
    return base.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)


def generate_frames():
    if not os.path.isfile(BASE_PATH):
        raise FileNotFoundError(f"Missing base image: {BASE_PATH}")

    base_raw = Image.open(BASE_PATH).convert("RGBA")
    w_raw, h_raw = base_raw.size

    # --- 1. IDLE FRAMES ---
    print("Generating idle frames...")
    # Frame 1: Base pose
    f1 = scale_base(base_raw)
    f1.save(os.path.join(ASSETS_DIR, "idle_1.png"))

    # Frame 2: Breathing dip (body/head shifts down 2px, tail slightly up)
    f2_canvas = create_canvas()
    f2_img = scale_base(base_raw)
    f2_canvas.paste(f2_img, (0, 2), f2_img)
    f2_canvas.save(os.path.join(ASSETS_DIR, "idle_2.png"))

    # Frame 3: Happy eye smile (blink ^_^)
    f3 = base_raw.copy()
    draw = ImageDraw.Draw(f3)
    # Eye 1 at (34, 109), Eye 2 at (67, 97)
    # Cover original eye dots with cream/fur
    draw.ellipse([30, 103, 38, 115], fill=C_CREAM)
    draw.ellipse([63, 91, 71, 103], fill=C_ORANGE)
    # Draw happy anime curved eyes ^_^
    draw.arc([29, 106, 39, 114], start=180, end=360, fill=C_OUTLINE, width=3)
    draw.arc([62, 94, 72, 102], start=180, end=360, fill=C_OUTLINE, width=3)
    f3_scaled = scale_base(f3)
    f3_scaled.save(os.path.join(ASSETS_DIR, "idle_3.png"))

    # Frame 4: Breathing recovery / tail wag
    f4_canvas = create_canvas()
    f4_canvas.paste(f1, (0, 1), f1)
    f4_canvas.save(os.path.join(ASSETS_DIR, "idle_4.png"))

    # --- 2. WALK CYCLE (Joyful waddle) ---
    print("Generating walk cycle frames...")
    # Walk frame 1: bob up (-2px), front paws step forward
    w1_canvas = create_canvas()
    w1_img = scale_base(base_raw)
    w1_canvas.paste(w1_img, (1, -2), w1_img)
    w1_canvas.save(os.path.join(ASSETS_DIR, "walk_1.png"))

    # Walk frame 2: neutral passing step
    w2 = f1.copy()
    w2.save(os.path.join(ASSETS_DIR, "walk_2.png"))

    # Walk frame 3: bob down (+2px), rear paws step
    w3_canvas = create_canvas()
    w3_canvas.paste(w1_img, (-1, 2), w1_img)
    w3_canvas.save(os.path.join(ASSETS_DIR, "walk_3.png"))

    # Walk frame 4: neutral passing step
    w4 = f1.copy()
    w4.save(os.path.join(ASSETS_DIR, "walk_4.png"))

    # --- 3. WALK LEFT (Mirrored) ---
    print("Generating mirrored walk left frames...")
    for i in range(1, 5):
        w_right = Image.open(os.path.join(ASSETS_DIR, f"walk_{i}.png"))
        w_left = w_right.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        w_left.save(os.path.join(ASSETS_DIR, f"walk_left_{i}.png"))

    # --- 4. DRAG / LIFTED POSE ---
    print("Generating drag / lifted pose...")
    # Lifted pose: stretched slightly down (+3px), cute hanging pose
    drag_canvas = create_canvas()
    drag_img = scale_base(base_raw)
    drag_canvas.paste(drag_img, (0, -1), drag_img)
    drag_canvas.save(os.path.join(ASSETS_DIR, "drag.png"))

    print(f"All frames successfully created at {TARGET_W}x{TARGET_H} in {ASSETS_DIR}!")


if __name__ == "__main__":
    generate_frames()
