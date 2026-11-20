"""Generate adorable, kawaii cartoon Corgi sprite frames using Cairo.

Fixes perspective: Proper side-profile with ONE large, expressive anime eye,
chubby loaf body, perky corgi ears, fluffy ruff, and cute stubby legs.
"""

import math
import os
import cairo

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# Kawaii Corgi Palette
C_FUR_MAIN = (0.93, 0.58, 0.24, 1.0)       # Warm golden honey: #EDA93D
C_FUR_SHADOW = (0.78, 0.44, 0.16, 1.0)     # Background depth: #C77029
C_WHITE = (0.99, 0.98, 0.95, 1.0)          # Fluffy white cream: #FDFBF2
C_WHITE_SHADOW = (0.86, 0.86, 0.84, 1.0)   # Shadow white
C_INNER_EAR = (0.99, 0.72, 0.75, 1.0)      # Soft pastel pink: #FDB8BF
C_CHEEK = (0.99, 0.55, 0.58, 0.35)         # Cute blush: #FD8C94
C_NOSE = (0.15, 0.12, 0.12, 1.0)           # Dark nose button: #261F1F
C_TONGUE = (0.99, 0.42, 0.52, 1.0)         # Happy pink tongue: #FD6B85
C_OUTLINE = (0.28, 0.16, 0.08, 1.0)        # Soft chocolate outline: #472914
C_EYE_PUPIL = (0.16, 0.12, 0.10, 1.0)      # Deep warm eye


def draw_ear(ctx, cx, cy, angle, scale=1.0, is_background=False):
    """Draw a large, iconic perky Corgi ear."""
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(angle)
    ctx.scale(scale, scale)

    # Outer ear curve
    ctx.new_path()
    ctx.move_to(-13, 0)
    ctx.curve_to(-16, -18, -10, -38, 0, -42)
    ctx.curve_to(10, -38, 16, -18, 13, 0)
    ctx.close_path()

    fill_color = C_FUR_SHADOW if is_background else C_FUR_MAIN
    ctx.set_source_rgba(*fill_color)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Inner pink fluff
    ctx.new_path()
    ctx.move_to(-7, -4)
    ctx.curve_to(-9, -16, -5, -30, 0, -34)
    ctx.curve_to(5, -30, 9, -16, 7, -4)
    ctx.close_path()
    inner_color = (C_INNER_EAR[0]*0.85, C_INNER_EAR[1]*0.85, C_INNER_EAR[2]*0.85, 1.0) if is_background else C_INNER_EAR
    ctx.set_source_rgba(*inner_color)
    ctx.fill()

    ctx.restore()


def draw_kawaii_corgi(
    ctx,
    *,
    facing_left=False,
    bounce_y=0.0,
    ear_tilt=0.0,
    tail_angle=0.0,
    front_leg_angle=0.0,
    back_leg_angle=0.0,
    happy_blink=False,
    tongue_out=True,
    is_dangling=False,
):
    """Draw an adorable side-profile cartoon Corgi centered on a 128x128 canvas."""
    ctx.save()

    if facing_left:
        ctx.translate(64, 0)
        ctx.scale(-1, 1)
        ctx.translate(-64, 0)

    # Center anchors
    body_x, body_y = 56, 76 + bounce_y
    head_x, head_y = 80, 56 + bounce_y * 0.7

    # 1. Background Ear (far side)
    draw_ear(ctx, head_x - 12, head_y - 12, math.radians(-18 + ear_tilt), scale=0.85, is_background=True)

    # 2. Tail (behind body, cute fluffy heart nub)
    ctx.save()
    ctx.translate(28, body_y - 6)
    ctx.rotate(math.radians(-25 + tail_angle))
    ctx.new_path()
    ctx.arc(0, 0, 10, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_FUR_MAIN)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()
    # Fluffy white tip
    ctx.new_path()
    ctx.arc(-4, 0, 5, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()
    ctx.restore()

    # 3. Far/Background Legs
    ctx.save()
    ctx.translate(38, body_y + 16)
    if is_dangling:
        ctx.rotate(math.radians(-10))
    else:
        ctx.rotate(math.radians(-back_leg_angle))
    ctx.new_path()
    ctx.arc(0, 6, 7, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_FUR_SHADOW)
    ctx.fill()
    ctx.restore()

    ctx.save()
    ctx.translate(76, body_y + 16)
    if is_dangling:
        ctx.rotate(math.radians(-15))
    else:
        ctx.rotate(math.radians(-front_leg_angle))
    ctx.new_path()
    ctx.arc(0, 6, 7, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_FUR_SHADOW)
    ctx.fill()
    ctx.restore()

    # 4. Chubby Loaf Body
    ctx.save()
    ctx.translate(body_x, body_y)
    ctx.scale(1.42, 1.0)
    ctx.new_path()
    ctx.arc(0, 0, 23, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_FUR_MAIN)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # White tummy patch
    ctx.save()
    ctx.translate(body_x + 6, body_y + 9)
    ctx.scale(1.15, 0.65)
    ctx.new_path()
    ctx.arc(0, 0, 15, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()

    # 5. Near/Foreground Legs (Cute stubby paws)
    ctx.save()
    ctx.translate(44, body_y + 18)
    if is_dangling:
        ctx.rotate(math.radians(10))
    else:
        ctx.rotate(math.radians(back_leg_angle))
    ctx.new_path()
    ctx.arc(0, 6, 8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()
    ctx.restore()

    ctx.save()
    ctx.translate(82, body_y + 18)
    if is_dangling:
        ctx.rotate(math.radians(15))
    else:
        ctx.rotate(math.radians(front_leg_angle))
    ctx.new_path()
    ctx.arc(0, 6, 8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()
    ctx.restore()

    # 6. Foreground Ear
    draw_ear(ctx, head_x + 6, head_y - 12, math.radians(12 - ear_tilt), scale=1.0, is_background=False)

    # 7. Head & Muzzle
    ctx.new_path()
    ctx.arc(head_x, head_y, 22, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_FUR_MAIN)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Fluffy white chest ruff (connects head to body)
    ctx.new_path()
    ctx.move_to(head_x - 4, head_y + 16)
    ctx.curve_to(head_x + 4, head_y + 24, head_x + 16, head_y + 24, head_x + 20, head_y + 14)
    ctx.curve_to(head_x + 12, head_y + 8, head_x, head_y + 8, head_x - 4, head_y + 16)
    ctx.close_path()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()

    # Rounded snout / muzzle pointing forward to the right
    ctx.new_path()
    ctx.move_to(head_x + 10, head_y - 6)
    ctx.curve_to(head_x + 18, head_y - 8, head_x + 28, head_y - 4, head_x + 29, head_y + 3)
    ctx.curve_to(head_x + 29, head_y + 11, head_x + 18, head_y + 15, head_x + 8, head_y + 12)
    ctx.close_path()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()

    # Cute black nose button
    ctx.new_path()
    ctx.arc(head_x + 27, head_y + 1, 4.2, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_NOSE)
    ctx.fill()
    # Specular glint on nose
    ctx.new_path()
    ctx.arc(head_x + 26, head_y - 0.5, 1.2, 0, 2 * math.pi)
    ctx.set_source_rgba(1.0, 1.0, 1.0, 0.85)
    ctx.fill()

    # Cute open mouth / smile
    ctx.new_path()
    ctx.move_to(head_x + 24, head_y + 5)
    ctx.curve_to(head_x + 21, head_y + 10, head_x + 15, head_y + 11, head_x + 12, head_y + 7)
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()

    # Pink tongue sticking out cheerfully
    if tongue_out:
        ctx.new_path()
        ctx.arc(head_x + 18, head_y + 10, 4.0, 0, math.pi)
        ctx.set_source_rgba(*C_TONGUE)
        ctx.fill_preserve()
        ctx.set_source_rgba(*C_OUTLINE)
        ctx.set_line_width(1.6)
        ctx.stroke()

    # 8. Single Kawaii Eye (Side profile: ONE clear adorable eye!)
    eye_x, eye_y = head_x + 8, head_y - 3

    if happy_blink:
        ctx.new_path()
        ctx.arc(eye_x, eye_y + 2, 6.0, math.pi * 1.15, math.pi * 1.85)
        ctx.set_source_rgba(*C_OUTLINE)
        ctx.set_line_width(2.8)
        ctx.stroke()
    else:
        ctx.new_path()
        ctx.arc(eye_x, eye_y, 7.0, 0, 2 * math.pi)
        ctx.set_source_rgba(*C_EYE_PUPIL)
        ctx.fill()

        # Primary specular highlight (top-left)
        ctx.new_path()
        ctx.arc(eye_x - 2.2, eye_y - 2.2, 2.6, 0, 2 * math.pi)
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        ctx.fill()

        # Secondary highlight (bottom-right)
        ctx.new_path()
        ctx.arc(eye_x + 2.5, eye_y + 2.5, 1.2, 0, 2 * math.pi)
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.8)
        ctx.fill()

    # Rosy cheek blush below the eye
    ctx.new_path()
    ctx.arc(eye_x, eye_y + 9, 6.0, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_CHEEK)
    ctx.fill()

    ctx.restore()


def render_frame(filename, **kwargs):
    width, height = 128, 128
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    draw_kawaii_corgi(ctx, **kwargs)
    filepath = os.path.join(ASSETS_DIR, filename)
    surface.write_to_png(filepath)
    print(f"Generated {filepath}")


def generate_all():
    print("Generating Kawaii Corgi cartoon frames...")

    # --- IDLE ANIMATION (4 frames) ---
    render_frame("idle_1.png", bounce_y=0.0, tail_angle=0.0, ear_tilt=0.0, happy_blink=False, tongue_out=True)
    render_frame("idle_2.png", bounce_y=1.5, tail_angle=18.0, ear_tilt=3.0, happy_blink=False, tongue_out=True)
    render_frame("idle_3.png", bounce_y=-1.0, tail_angle=-16.0, ear_tilt=-2.0, happy_blink=True, tongue_out=False)
    render_frame("idle_4.png", bounce_y=0.5, tail_angle=10.0, ear_tilt=1.0, happy_blink=False, tongue_out=True)

    # --- WALK RIGHT ANIMATION (4 frames) ---
    render_frame("walk_1.png", bounce_y=-2.0, tail_angle=24.0, ear_tilt=3.0,
                 front_leg_angle=22.0, back_leg_angle=-22.0, happy_blink=False, tongue_out=True)
    render_frame("walk_2.png", bounce_y=0.5, tail_angle=6.0, ear_tilt=0.0,
                 front_leg_angle=0.0, back_leg_angle=0.0, happy_blink=False, tongue_out=False)
    render_frame("walk_3.png", bounce_y=-2.0, tail_angle=-24.0, ear_tilt=-3.0,
                 front_leg_angle=-22.0, back_leg_angle=22.0, happy_blink=False, tongue_out=True)
    render_frame("walk_4.png", bounce_y=0.5, tail_angle=-6.0, ear_tilt=0.0,
                 front_leg_angle=0.0, back_leg_angle=0.0, happy_blink=False, tongue_out=False)

    # --- WALK LEFT ANIMATION (4 frames) ---
    render_frame("walk_left_1.png", facing_left=True, bounce_y=-2.0, tail_angle=24.0, ear_tilt=3.0,
                 front_leg_angle=22.0, back_leg_angle=-22.0, happy_blink=False, tongue_out=True)
    render_frame("walk_left_2.png", facing_left=True, bounce_y=0.5, tail_angle=6.0, ear_tilt=0.0,
                 front_leg_angle=0.0, back_leg_angle=0.0, happy_blink=False, tongue_out=False)
    render_frame("walk_left_3.png", facing_left=True, bounce_y=-2.0, tail_angle=-24.0, ear_tilt=-3.0,
                 front_leg_angle=-22.0, back_leg_angle=22.0, happy_blink=False, tongue_out=True)
    render_frame("walk_left_4.png", facing_left=True, bounce_y=0.5, tail_angle=-6.0, ear_tilt=0.0,
                 front_leg_angle=0.0, back_leg_angle=0.0, happy_blink=False, tongue_out=False)

    # --- DRAG / DANGLING (1 frame) ---
    render_frame("drag.png", bounce_y=-4.0, ear_tilt=-6.0, tail_angle=0.0,
                 is_dangling=True, happy_blink=False, tongue_out=True)

    print("All Kawaii Corgi frames regenerated successfully!")


if __name__ == "__main__":
    generate_all()
