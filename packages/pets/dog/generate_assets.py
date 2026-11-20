"""Generate crisp, high-quality cartoon Corgi sprite frames using Cairo.

Renders vector-smooth 128x128 RGBA PNG frames with alpha transparency:
- idle (4 frames): natural breathing, blinking, tail wagging
- walk_right (4 frames): cheerful walking cycle facing right
- walk_left (4 frames): mirrored walking cycle facing left
- drag (1 frame): lifted dangling pose
"""

import math
import os
import cairo

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# Colors
C_ORANGE_DARK = (0.75, 0.38, 0.12, 1.0)      # Outline / shadow: #BF611E
C_ORANGE = (0.91, 0.52, 0.20, 1.0)           # Main coat: #E88533
C_ORANGE_LIGHT = (0.97, 0.65, 0.35, 1.0)     # Highlights: #F7A659
C_WHITE = (0.98, 0.98, 0.96, 1.0)            # Chest, blaze, paws: #FAFAF5
C_PINK_INNER = (0.98, 0.70, 0.72, 1.0)       # Inner ears: #FAB3B8
C_NOSE = (0.16, 0.12, 0.12, 1.0)             # Nose / eyes: #291F1F
C_TONGUE = (0.98, 0.42, 0.52, 1.0)           # Tongue: #FA6B85
C_OUTLINE = (0.24, 0.14, 0.08, 1.0)          # Soft dark outline: #3D2414


def draw_ear(ctx, cx, cy, angle, scale=1.0):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(angle)
    ctx.scale(scale, scale)

    # Outer ear
    ctx.new_path()
    ctx.move_to(-12, 0)
    ctx.curve_to(-14, -20, -8, -32, 0, -36)
    ctx.curve_to(8, -32, 14, -20, 12, 0)
    ctx.close_path()
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.5)
    ctx.stroke()

    # Inner ear
    ctx.new_path()
    ctx.move_to(-7, -2)
    ctx.curve_to(-8, -16, -4, -26, 0, -30)
    ctx.curve_to(4, -26, 8, -16, 7, -2)
    ctx.close_path()
    ctx.set_source_rgba(*C_PINK_INNER)
    ctx.fill()

    ctx.restore()


def draw_eye(ctx, cx, cy, blink=False):
    ctx.save()
    if blink:
        # Happy curved arch eye ^_^
        ctx.new_path()
        ctx.arc(cx, cy + 2, 5, math.pi * 1.1, math.pi * 1.9)
        ctx.set_source_rgba(*C_OUTLINE)
        ctx.set_line_width(2.5)
        ctx.stroke()
    else:
        # Big shiny cartoon eye
        ctx.new_path()
        ctx.arc(cx, cy, 6, 0, 2 * math.pi)
        ctx.set_source_rgba(*C_NOSE)
        ctx.fill()

        # Big highlight
        ctx.new_path()
        ctx.arc(cx - 2, cy - 2, 2.2, 0, 2 * math.pi)
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        ctx.fill()

        # Little secondary highlight
        ctx.new_path()
        ctx.arc(cx + 2, cy + 2, 1.0, 0, 2 * math.pi)
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.8)
        ctx.fill()
    ctx.restore()


def draw_corgi(ctx, *,
               facing_left=False,
               bounce_y=0.0,
               ear_angle_offset=0.0,
               tail_angle=0.0,
               front_paw_offset=(0.0, 0.0),
               rear_paw_offset=(0.0, 0.0),
               blink=False,
               tongue=False,
               dangle=False):
    """Draw a vector cartoon Corgi centered on a 128x128 surface."""
    ctx.save()

    if facing_left:
        # Mirror horizontally around center (x=64)
        ctx.translate(64, 0)
        ctx.scale(-1, 1)
        ctx.translate(-64, 0)

    # Base coordinates
    body_cx = 58
    body_cy = 78 + bounce_y
    head_cx = 78
    head_cy = 60 + bounce_y * 0.8

    # 1. Tail (drawn behind body)
    ctx.save()
    ctx.translate(32, body_cy - 4)
    ctx.rotate(math.radians(-35 + tail_angle))
    ctx.new_path()
    ctx.arc(0, 0, 8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()
    # White tip on tail nub
    ctx.new_path()
    ctx.arc(-4, 0, 4, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()
    ctx.restore()

    # 2. Back paws (far side / depth)
    ctx.save()
    ctx.set_source_rgba(C_ORANGE[0]*0.85, C_ORANGE[1]*0.85, C_ORANGE[2]*0.85, 1.0)
    # Rear-left leg
    rl_x = 40 - rear_paw_offset[0]
    rl_y = 96 + (10 if dangle else -rear_paw_offset[1])
    ctx.new_path()
    ctx.arc(rl_x, rl_y, 7, 0, 2 * math.pi)
    ctx.fill()
    # Front-left leg
    fl_x = 76 - front_paw_offset[0]
    fl_y = 96 + (10 if dangle else -front_paw_offset[1])
    ctx.new_path()
    ctx.arc(fl_x, fl_y, 7, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()

    # 3. Main Body (Cute plump rounded loaf)
    ctx.save()
    ctx.translate(body_cx, body_cy)
    ctx.scale(1.35, 1.0)
    ctx.new_path()
    ctx.arc(0, 0, 23, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.5)
    ctx.stroke()

    # White belly patch
    ctx.save()
    ctx.translate(body_cx + 4, body_cy + 8)
    ctx.scale(1.1, 0.7)
    ctx.new_path()
    ctx.arc(0, 0, 16, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()

    # 4. Front paws (near side)
    ctx.save()
    # Rear-right leg
    rr_x = 44 + rear_paw_offset[0]
    rr_y = 98 + (8 if dangle else rear_paw_offset[1])
    ctx.new_path()
    ctx.arc(rr_x, rr_y, 8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()

    # Front-right leg
    fr_x = 80 + front_paw_offset[0]
    fr_y = 98 + (8 if dangle else front_paw_offset[1])
    ctx.new_path()
    ctx.arc(fr_x, fr_y, 8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()
    ctx.restore()

    # 5. Ears (Left ear behind head, Right ear front)
    draw_ear(ctx, head_cx - 10, head_cy - 12, math.radians(-16 + ear_angle_offset), scale=0.9)
    draw_ear(ctx, head_cx + 10, head_cy - 14, math.radians(14 - ear_angle_offset), scale=1.0)

    # 6. Head
    ctx.save()
    ctx.new_path()
    ctx.arc(head_cx, head_cy, 22, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.5)
    ctx.stroke()

    # White muzzle & chest bib
    ctx.new_path()
    ctx.move_to(head_cx + 6, head_cy - 14)
    ctx.curve_to(head_cx + 2, head_cy - 4, head_cx + 2, head_cy + 8, head_cx + 12, head_cy + 12)
    ctx.curve_to(head_cx + 20, head_cy + 10, head_cx + 26, head_cy + 2, head_cx + 24, head_cy - 4)
    ctx.curve_to(head_cx + 20, head_cy - 12, head_cx + 14, head_cy - 16, head_cx + 6, head_cy - 14)
    ctx.close_path()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(1.8)
    ctx.stroke()

    # White forehead blaze
    ctx.new_path()
    ctx.move_to(head_cx - 3, head_cy - 20)
    ctx.curve_to(head_cx, head_cy - 10, head_cx + 4, head_cy - 6, head_cx + 6, head_cy - 14)
    ctx.curve_to(head_cx + 2, head_cy - 22, head_cx, head_cy - 22, head_cx - 3, head_cy - 20)
    ctx.close_path()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()

    # Cute nose button
    ctx.new_path()
    ctx.arc(head_cx + 23, head_cy - 2, 4.0, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_NOSE)
    ctx.fill()
    # Nose highlight
    ctx.new_path()
    ctx.arc(head_cx + 22, head_cy - 3, 1.2, 0, 2 * math.pi)
    ctx.set_source_rgba(1.0, 1.0, 1.0, 0.8)
    ctx.fill()

    # Cute smiling mouth
    ctx.new_path()
    ctx.move_to(head_cx + 20, head_cy + 2)
    ctx.curve_to(head_cx + 18, head_cy + 7, head_cx + 14, head_cy + 7, head_cx + 12, head_cy + 4)
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()

    # Little pink tongue
    if tongue:
        ctx.new_path()
        ctx.arc(head_cx + 17, head_cy + 8, 3.5, 0, math.pi)
        ctx.set_source_rgba(*C_TONGUE)
        ctx.fill_preserve()
        ctx.set_source_rgba(*C_OUTLINE)
        ctx.set_line_width(1.5)
        ctx.stroke()

    # Eyes
    draw_eye(ctx, head_cx + 6, head_cy - 4, blink=blink)
    draw_eye(ctx, head_cx - 8, head_cy - 4, blink=blink)

    # Rosy cheeks
    ctx.new_path()
    ctx.arc(head_cx + 10, head_cy + 5, 4.5, 0, 2 * math.pi)
    ctx.set_source_rgba(0.98, 0.5, 0.5, 0.25)
    ctx.fill()
    ctx.new_path()
    ctx.arc(head_cx - 12, head_cy + 5, 4.5, 0, 2 * math.pi)
    ctx.set_source_rgba(0.98, 0.5, 0.5, 0.25)
    ctx.fill()

    ctx.restore()
    ctx.restore()


def render_frame(filename, **kwargs):
    width, height = 128, 128
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    draw_corgi(ctx, **kwargs)
    filepath = os.path.join(ASSETS_DIR, filename)
    surface.write_to_png(filepath)
    print(f"Generated {filepath}")


def generate_all():
    print("Generating Corgi cartoon frames...")

    # --- IDLE ANIMATION (4 frames) ---
    render_frame("idle_1.png", bounce_y=0.0, tail_angle=0.0, ear_angle_offset=0.0, blink=False, tongue=False)
    render_frame("idle_2.png", bounce_y=1.5, tail_angle=18.0, ear_angle_offset=3.0, blink=False, tongue=True)
    render_frame("idle_3.png", bounce_y=-1.0, tail_angle=-15.0, ear_angle_offset=-2.0, blink=True, tongue=False)
    render_frame("idle_4.png", bounce_y=0.5, tail_angle=10.0, ear_angle_offset=1.0, blink=False, tongue=False)

    # --- WALK RIGHT ANIMATION (4 frames) ---
    render_frame("walk_1.png", bounce_y=-2.0, tail_angle=25.0,
                 front_paw_offset=(6.0, -4.0), rear_paw_offset=(-6.0, -2.0), tongue=True)
    render_frame("walk_2.png", bounce_y=0.0, tail_angle=5.0,
                 front_paw_offset=(0.0, 0.0), rear_paw_offset=(0.0, 0.0), tongue=False)
    render_frame("walk_3.png", bounce_y=-2.0, tail_angle=-25.0,
                 front_paw_offset=(-6.0, -2.0), rear_paw_offset=(6.0, -4.0), tongue=True)
    render_frame("walk_4.png", bounce_y=0.0, tail_angle=-5.0,
                 front_paw_offset=(0.0, 0.0), rear_paw_offset=(0.0, 0.0), tongue=False)

    # --- WALK LEFT ANIMATION (4 frames) ---
    render_frame("walk_left_1.png", facing_left=True, bounce_y=-2.0, tail_angle=25.0,
                 front_paw_offset=(6.0, -4.0), rear_paw_offset=(-6.0, -2.0), tongue=True)
    render_frame("walk_left_2.png", facing_left=True, bounce_y=0.0, tail_angle=5.0,
                 front_paw_offset=(0.0, 0.0), rear_paw_offset=(0.0, 0.0), tongue=False)
    render_frame("walk_left_3.png", facing_left=True, bounce_y=-2.0, tail_angle=-25.0,
                 front_paw_offset=(-6.0, -2.0), rear_paw_offset=(6.0, -4.0), tongue=True)
    render_frame("walk_left_4.png", facing_left=True, bounce_y=0.0, tail_angle=-5.0,
                 front_paw_offset=(0.0, 0.0), rear_paw_offset=(0.0, 0.0), tongue=False)

    # --- DRAG / LIFTED (1 frame) ---
    render_frame("drag.png", bounce_y=-4.0, ear_angle_offset=-6.0, tail_angle=0.0,
                 dangle=True, blink=False, tongue=True)

    print("All frames generated successfully!")


if __name__ == "__main__":
    generate_all()
