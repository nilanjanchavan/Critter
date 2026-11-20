"""Process user-generated Canva AI Cat artwork into an animated desktop pet sprite set.

Source images:
- standing_isolated.png (282x223)
- sleeping_isolated.png (277x152)
- drag_isolated.png (290x292)

Generates:
- idle_1.png .. idle_4.png (breathing, blinking ^_^)
- walk_left_1.png .. walk_left_4.png (4-frame articulated walking cycle facing LEFT)
- walk_1.png .. walk_4.png (4-frame walking cycle facing RIGHT - flipped)
- sleep_1.png .. sleep_3.png (sleeping loaf with floating Zzz)
- drag.png (scruff-lifted dangling pose)
Target size: 128x128 RGBA transparent PNGs.
"""

import os
from PIL import Image, ImageDraw

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/assets"
STANDING_PATH = os.path.join(ASSETS_DIR, "standing_isolated.png")
SLEEPING_PATH = os.path.join(ASSETS_DIR, "sleeping_isolated.png")
DRAG_PATH = os.path.join(ASSETS_DIR, "drag_isolated.png")

CANVAS_SIZE = (128, 128)
C_OUTLINE = (60, 42, 32, 255)
C_CREAM = (255, 247, 232, 255)


def create_canvas() -> Image.Image:
    return Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))


def fit_on_canvas(img: Image.Image, max_w: int = 126, max_h: int = 110, y_offset: int = 0) -> Image.Image:
    """Scale image to fit within max bounds and center at bottom with optional y_offset."""
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = create_canvas()
    # Place at horizontal center, bottom-aligned with margin
    x = (CANVAS_SIZE[0] - new_w) // 2
    y = CANVAS_SIZE[1] - new_h - 6 + y_offset
    canvas.paste(scaled, (x, y), scaled)
    return canvas


def generate_cat_frames():
    standing_raw = Image.open(STANDING_PATH).convert("RGBA")
    sleeping_raw = Image.open(SLEEPING_PATH).convert("RGBA")
    drag_raw = Image.open(DRAG_PATH).convert("RGBA")

    w_s, h_s = standing_raw.size

    # --- 1. IDLE FRAMES ---
    print("Generating Mochi idle frames...")
    # Idle 1: Base sitting/standing pose
    idle_1 = fit_on_canvas(standing_raw)
    idle_1.save(os.path.join(ASSETS_DIR, "idle_1.png"))

    # Idle 2: Gentle breathing dip (-1.5px)
    idle_2 = fit_on_canvas(standing_raw, y_offset=2)
    idle_2.save(os.path.join(ASSETS_DIR, "idle_2.png"))

    # Idle 3: Happy anime eye blink (^_^)
    idle_3_raw = standing_raw.copy()
    draw = ImageDraw.Draw(idle_3_raw)
    # Left eye: (34, 99), Right eye: (80, 105)
    # Cover emerald eyes with surrounding cream fur
    draw.ellipse([27, 90, 41, 106], fill=C_CREAM)
    draw.ellipse([73, 97, 87, 112], fill=C_CREAM)
    # Draw smiling cat eye arcs
    draw.arc([26, 92, 42, 104], start=180, end=360, fill=C_OUTLINE, width=3)
    draw.arc([72, 98, 88, 110], start=180, end=360, fill=C_OUTLINE, width=3)
    idle_3 = fit_on_canvas(idle_3_raw)
    idle_3.save(os.path.join(ASSETS_DIR, "idle_3.png"))

    # Idle 4: Return to neutral
    idle_4 = fit_on_canvas(standing_raw, y_offset=1)
    idle_4.save(os.path.join(ASSETS_DIR, "idle_4.png"))

    # --- 2. ACTIVE WALKING STRIDE (4 frames) ---
    print("Generating Mochi active walking frames with articulated legs...")
    # Leg crop boxes in standing_raw (282x223)
    fl_box = (38, 175, 78, 223)    # Front-left
    fr_box = (78, 175, 118, 223)   # Front-right
    bl_box = (175, 175, 218, 223)  # Back-left
    br_box = (218, 175, 258, 223)  # Back-right

    fl_crop = standing_raw.crop(fl_box)
    fr_crop = standing_raw.crop(fr_box)
    bl_crop = standing_raw.crop(bl_box)
    br_crop = standing_raw.crop(br_box)

    body_trunk = standing_raw.copy()
    for box in [fl_box, fr_box, bl_box, br_box]:
        for y in range(box[1] + 5, box[3]):
            for x in range(box[0], box[2]):
                body_trunk.putpixel((x, y), (0, 0, 0, 0))

    def compose_walk(fl_angle: float, fr_angle: float, bl_angle: float, br_angle: float, bob_y: int) -> Image.Image:
        frame = Image.new("RGBA", (w_s, h_s), (0, 0, 0, 0))
        # Background legs
        rot_fr = fr_crop.rotate(fr_angle, resample=Image.Resampling.BICUBIC, center=(fr_crop.width // 2, 4))
        rot_bl = bl_crop.rotate(bl_angle, resample=Image.Resampling.BICUBIC, center=(bl_crop.width // 2, 4))
        frame.paste(rot_fr, (fr_box[0], fr_box[1] + bob_y), rot_fr)
        frame.paste(rot_bl, (bl_box[0], bl_box[1] + bob_y), rot_bl)

        # Body
        frame.paste(body_trunk, (0, bob_y), body_trunk)

        # Foreground legs
        rot_fl = fl_crop.rotate(fl_angle, resample=Image.Resampling.BICUBIC, center=(fl_crop.width // 2, 4))
        rot_br = br_crop.rotate(br_angle, resample=Image.Resampling.BICUBIC, center=(br_crop.width // 2, 4))
        frame.paste(rot_fl, (fl_box[0], fl_box[1] + bob_y), rot_fl)
        frame.paste(rot_br, (br_box[0], br_box[1] + bob_y), rot_br)
        return frame

    # 4-frame stride
    raw_w1 = compose_walk(fl_angle=12.0, fr_angle=-12.0, bl_angle=-10.0, br_angle=10.0, bob_y=-2)
    raw_w2 = compose_walk(fl_angle=0.0, fr_angle=0.0, bl_angle=0.0, br_angle=0.0, bob_y=0)
    raw_w3 = compose_walk(fl_angle=-12.0, fr_angle=12.0, bl_angle=10.0, br_angle=-10.0, bob_y=-2)
    raw_w4 = compose_walk(fl_angle=0.0, fr_angle=0.0, bl_angle=0.0, br_angle=0.0, bob_y=0)

    # Walk Left (Natural orientation - facing left)
    for i, raw_frame in enumerate([raw_w1, raw_w2, raw_w3, raw_w4], start=1):
        fitted = fit_on_canvas(raw_frame)
        fitted.save(os.path.join(ASSETS_DIR, f"walk_left_{i}.png"))

    # Walk Right (Flipped horizontally so it faces right while moving right)
    for i, raw_frame in enumerate([raw_w1, raw_w2, raw_w3, raw_w4], start=1):
        fitted = fit_on_canvas(raw_frame)
        flipped = fitted.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        flipped.save(os.path.join(ASSETS_DIR, f"walk_{i}.png"))

    # --- 3. SLEEPING FRAMES ---
    print("Generating Mochi sleeping loaf frames...")
    # Sleep 1: Natural sleeping loaf
    sleep_1 = fit_on_canvas(sleeping_raw, max_h=95, y_offset=0)
    sleep_1.save(os.path.join(ASSETS_DIR, "sleep_1.png"))

    # Sleep 2: Breathing up (+2px) with cute floating 'Z'
    sleep_2 = fit_on_canvas(sleeping_raw, max_h=95, y_offset=-2)
    draw_s2 = ImageDraw.Draw(sleep_2)
    draw_s2.text((85, 20), "z", fill=(80, 110, 180, 220))
    sleep_2.save(os.path.join(ASSETS_DIR, "sleep_2.png"))

    # Sleep 3: Floating 'Zz'
    sleep_3 = fit_on_canvas(sleeping_raw, max_h=95, y_offset=-1)
    draw_s3 = ImageDraw.Draw(sleep_3)
    draw_s3.text((88, 14), "Zz", fill=(80, 110, 180, 240))
    sleep_3.save(os.path.join(ASSETS_DIR, "sleep_3.png"))

    # --- 4. DRAG / LIFTED POSE ---
    print("Generating Mochi scruff-lifted drag frame...")
    drag_img = fit_on_canvas(drag_raw, max_w=124, max_h=124, y_offset=-3)
    drag_img.save(os.path.join(ASSETS_DIR, "drag.png"))

    print(f"All Mochi animation frames generated at {CANVAS_SIZE[0]}x{CANVAS_SIZE[1]} in {ASSETS_DIR}!")


if __name__ == "__main__":
    generate_cat_frames()
