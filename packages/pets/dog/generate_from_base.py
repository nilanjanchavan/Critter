"""Generate high-quality animation frames from the user's custom Corgi artwork.

Fixes:
1. Direction: The base artwork faces LEFT.
   - walk_left_1..4 face LEFT (moving towards left).
   - walk_right_1..4 are FLIPPED horizontally (moving towards right).
2. Blinking: Fixed exact pixel coordinates on the actual eyes (y ≈ 92, NOT snout).
3. Moving legs: Separately isolates and articulates all 4 legs in an alternating
   quadruped walking stride so the paws actively step forward and backward.
"""

import os
from PIL import Image, ImageDraw

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/assets"
BASE_PATH = os.path.join(ASSETS_DIR, "corgi_base.png")

TARGET_W = 160
TARGET_H = 135

C_OUTLINE = (86, 61, 41, 255)
C_ORANGE = (238, 177, 88, 255)


def create_canvas() -> Image.Image:
    return Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))


def scale_to_target(img: Image.Image) -> Image.Image:
    return img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)


def generate_frames():
    if not os.path.isfile(BASE_PATH):
        raise FileNotFoundError(f"Missing base image: {BASE_PATH}")

    base_raw = Image.open(BASE_PATH).convert("RGBA")
    w_raw, h_raw = base_raw.size

    # --- 1. SEGMENT LEGS FOR ACTIVE WALKING ANIMATION ---
    # Crop boxes for the 4 legs in 283x238 space
    fl_box = (44, 180, 82, 238)    # Front-left (foreground)
    fr_box = (84, 180, 126, 238)   # Front-right (background/mid)
    bl_box = (192, 185, 226, 238)  # Back-left (background)
    br_box = (226, 180, 260, 238)  # Back-right (foreground)

    fl_crop = base_raw.crop(fl_box)
    fr_crop = base_raw.crop(fr_box)
    bl_crop = base_raw.crop(bl_box)
    br_crop = base_raw.crop(br_box)

    # Body trunk with leg bottom areas cleared
    body_trunk = base_raw.copy()
    for box in [fl_box, fr_box, bl_box, br_box]:
        for y in range(box[1] + 6, box[3]):
            for x in range(box[0], box[2]):
                body_trunk.putpixel((x, y), (0, 0, 0, 0))

    def compose_walk_frame(fl_angle: float, fr_angle: float, bl_angle: float, br_angle: float, bob_y: int) -> Image.Image:
        """Compose a frame with legs rotated around hip/shoulder pivots."""
        frame = Image.new("RGBA", (w_raw, h_raw), (0, 0, 0, 0))

        # 1. Background legs
        rot_fr = fr_crop.rotate(fr_angle, resample=Image.Resampling.BICUBIC, center=(fr_crop.width // 2, 4))
        rot_bl = bl_crop.rotate(bl_angle, resample=Image.Resampling.BICUBIC, center=(bl_crop.width // 2, 4))
        frame.paste(rot_fr, (fr_box[0], fr_box[1] + bob_y), rot_fr)
        frame.paste(rot_bl, (bl_box[0], bl_box[1] + bob_y), rot_bl)

        # 2. Main body trunk
        frame.paste(body_trunk, (0, bob_y), body_trunk)

        # 3. Foreground legs
        rot_fl = fl_crop.rotate(fl_angle, resample=Image.Resampling.BICUBIC, center=(fl_crop.width // 2, 4))
        rot_br = br_crop.rotate(br_angle, resample=Image.Resampling.BICUBIC, center=(br_crop.width // 2, 4))
        frame.paste(rot_fl, (fl_box[0], fl_box[1] + bob_y), rot_fl)
        frame.paste(rot_br, (br_box[0], br_box[1] + bob_y), rot_br)

        return frame

    # --- 2. GENERATE IDLE FRAMES (Faces LEFT by default) ---
    print("Generating idle frames...")
    # Frame 1: Base pose
    idle_1 = scale_to_target(base_raw)
    idle_1.save(os.path.join(ASSETS_DIR, "idle_1.png"))

    # Frame 2: Breathing dip (body sinks 2px)
    idle_2_canvas = create_canvas()
    idle_2_canvas.paste(idle_1, (0, 2), idle_1)
    idle_2_canvas.save(os.path.join(ASSETS_DIR, "idle_2.png"))

    # Frame 3: Happy eye-blink (precisely on the actual eyes!)
    idle_3_raw = base_raw.copy()
    draw = ImageDraw.Draw(idle_3_raw)
    # Left eye: x=[22..33], y=[85..98]
    for y in range(85, 99):
        for x in range(21, 34):
            p = base_raw.getpixel((x, y))
            if p[:3] == (86, 61, 41):
                idle_3_raw.putpixel((x, y), C_ORANGE)
    # Right eye: x=[57..70], y=[87..100]
    for y in range(87, 101):
        for x in range(56, 71):
            p = base_raw.getpixel((x, y))
            if p[:3] == (86, 61, 41):
                idle_3_raw.putpixel((x, y), C_ORANGE)
    # Draw happy smiling eye arcs ^_^
    draw.arc([21, 88, 33, 98], start=180, end=360, fill=C_OUTLINE, width=3)
    draw.arc([57, 89, 69, 99], start=180, end=360, fill=C_OUTLINE, width=3)

    idle_3 = scale_to_target(idle_3_raw)
    idle_3.save(os.path.join(ASSETS_DIR, "idle_3.png"))

    # Frame 4: Return to ready
    idle_4_canvas = create_canvas()
    idle_4_canvas.paste(idle_1, (0, 1), idle_1)
    idle_4_canvas.save(os.path.join(ASSETS_DIR, "idle_4.png"))

    # --- 3. GENERATE ACTIVE WALKING STRIDE (4 frames) ---
    print("Generating active walk cycles with moving legs...")
    # Frame 1: Stride A (front-left steps forward, front-right back, etc.)
    # Note: Facing LEFT, so forward is counter-clockwise (+) for front-left
    raw_w1 = compose_walk_frame(fl_angle=12.0, fr_angle=-12.0, bl_angle=-10.0, br_angle=10.0, bob_y=-2)
    # Frame 2: Passing pose (legs passing neutral)
    raw_w2 = compose_walk_frame(fl_angle=0.0, fr_angle=0.0, bl_angle=0.0, br_angle=0.0, bob_y=0)
    # Frame 3: Stride B (front-left steps back, front-right forward, etc.)
    raw_w3 = compose_walk_frame(fl_angle=-12.0, fr_angle=12.0, bl_angle=10.0, br_angle=-10.0, bob_y=-2)
    # Frame 4: Passing pose
    raw_w4 = compose_walk_frame(fl_angle=0.0, fr_angle=0.0, bl_angle=0.0, br_angle=0.0, bob_y=0)

    # WALKING LEFT: Natural orientation (artwork faces LEFT)
    for i, raw_frame in enumerate([raw_w1, raw_w2, raw_w3, raw_w4], start=1):
        scaled = scale_to_target(raw_frame)
        scaled.save(os.path.join(ASSETS_DIR, f"walk_left_{i}.png"))

    # WALKING RIGHT: Horizontally FLIPPED (so the head faces RIGHT while moving right!)
    for i, raw_frame in enumerate([raw_w1, raw_w2, raw_w3, raw_w4], start=1):
        scaled = scale_to_target(raw_frame)
        flipped = scaled.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        flipped.save(os.path.join(ASSETS_DIR, f"walk_{i}.png"))

    # --- 4. DRAG / LIFTED POSE ---
    print("Generating drag / lifted pose...")
    drag_raw = compose_walk_frame(fl_angle=-4.0, fr_angle=-4.0, bl_angle=6.0, br_angle=6.0, bob_y=-3)
    drag_scaled = scale_to_target(drag_raw)
    drag_scaled.save(os.path.join(ASSETS_DIR, "drag.png"))

    print(f"All frames regenerated at {TARGET_W}x{TARGET_H} in {ASSETS_DIR}!")


if __name__ == "__main__":
    generate_frames()
