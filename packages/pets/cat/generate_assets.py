"""Generate adorable, high-quality cartoon Cat (Mochi) sprite frames using Cairo.

Renders 128x128 RGBA transparent PNG frames:
- idle (4 frames): alert sitting cat, swishing tail, cute blinks
- walk_left (4 frames): graceful stealthy cat walk cycle facing left
- walk_right (4 frames): mirrored walk cycle facing right
- sleep (3 frames): curled up sleeping cat loaf with gentle breathing and 'Zzz'
- drag (1 frame): lifted by scruff with dangling paws
"""

import math
import os
import cairo

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# Mochi the Calico Cat Palette
C_WHITE = (0.99, 0.98, 0.96, 1.0)           # Base cream coat
C_ORANGE = (0.92, 0.55, 0.22, 1.0)          # Calico orange patch: #EB8C38
C_BROWN = (0.32, 0.22, 0.16, 1.0)           # Dark calico patch / outline: #523829
C_OUTLINE = (0.24, 0.16, 0.12, 1.0)         # Soft dark outline: #3D291F
C_EYE_GREEN = (0.20, 0.72, 0.55, 1.0)       # Emerald green eyes: #33B88C
C_EYE_PUPIL = (0.12, 0.10, 0.10, 1.0)       # Slit pupil
C_PINK_NOSE = (0.98, 0.58, 0.65, 1.0)       # Pastel pink nose & inner ear
C_CHEEK = (0.98, 0.60, 0.65, 0.30)          # Soft blush


def draw_cat_ear(ctx, cx, cy, angle, scale=1.0, is_orange=False):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(angle)
    ctx.scale(scale, scale)

    # Outer pointed cat ear
    ctx.new_path()
    ctx.move_to(-12, 0)
    ctx.curve_to(-14, -16, -6, -32, 0, -36)
    ctx.curve_to(6, -32, 14, -16, 12, 0)
    ctx.close_path()

    ctx.set_source_rgba(*(C_ORANGE if is_orange else C_WHITE))
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.4)
    ctx.stroke()

    # Inner pink ear fluff
    ctx.new_path()
    ctx.move_to(-6, -4)
    ctx.curve_to(-8, -14, -3, -26, 0, -28)
    ctx.curve_to(3, -26, 8, -14, 6, -4)
    ctx.close_path()
    ctx.set_source_rgba(*C_PINK_NOSE)
    ctx.fill()

    ctx.restore()


def draw_cat_eye(ctx, cx, cy, blink=False, surprised=False):
    ctx.save()
    if blink:
        # Happy cat smile line ^
        ctx.new_path()
        ctx.arc(cx, cy + 2, 5.5, math.pi * 1.15, math.pi * 1.85)
        ctx.set_source_rgba(*C_OUTLINE)
        ctx.set_line_width(2.6)
        ctx.stroke()
    else:
        # Big beautiful anime cat eye
        ctx.new_path()
        ctx.arc(cx, cy, 6.5, 0, 2 * math.pi)
        ctx.set_source_rgba(*C_EYE_GREEN)
        ctx.fill()

        # Cat pupil
        ctx.new_path()
        if surprised:
            ctx.arc(cx, cy, 4.0, 0, 2 * math.pi)
        else:
            ctx.save()
            ctx.translate(cx, cy)
            ctx.scale(0.55, 1.0)
            ctx.arc(0, 0, 5.0, 0, 2 * math.pi)
            ctx.restore()
        ctx.set_source_rgba(*C_EYE_PUPIL)
        ctx.fill()

        # Specular glint
        ctx.new_path()
        ctx.arc(cx - 2, cy - 2.5, 2.2, 0, 2 * math.pi)
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        ctx.fill()
    ctx.restore()


def draw_whiskers(ctx, cx, cy, facing_left=True):
    ctx.save()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(1.6)

    direction = -1 if facing_left else 1
    # Top whisker
    ctx.new_path()
    ctx.move_to(cx, cy - 2)
    ctx.curve_to(cx + direction * 10, cy - 6, cx + direction * 18, cy - 8, cx + direction * 24, cy - 8)
    ctx.stroke()

    # Mid whisker
    ctx.new_path()
    ctx.move_to(cx, cy)
    ctx.curve_to(cx + direction * 10, cy, cx + direction * 18, cy + 1, cx + direction * 26, cy + 1)
    ctx.stroke()

    # Bottom whisker
    ctx.new_path()
    ctx.move_to(cx, cy + 2)
    ctx.curve_to(cx + direction * 10, cy + 5, cx + direction * 18, cy + 9, cx + direction * 24, cy + 11)
    ctx.stroke()

    ctx.restore()


def render_cat_idle(filename: str, *, tail_swish: float = 0.0, blink: bool = False, breathe_y: float = 0.0):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 128, 128)
    ctx = cairo.Context(surface)

    # Center anchors (sitting cat pose)
    body_x, body_y = 66, 78 + breathe_y
    head_x, head_y = 60, 50 + breathe_y * 0.7

    # 1. Long swishing tail behind body
    ctx.save()
    ctx.translate(92, body_y + 12)
    ctx.rotate(math.radians(-40 + tail_swish))
    ctx.new_path()
    ctx.move_to(0, 0)
    ctx.curve_to(16, -15, 24, -38, 18, -52)
    ctx.curve_to(14, -58, 6, -56, 10, -48)
    ctx.curve_to(14, -36, 6, -18, -4, -6)
    ctx.close_path()
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()
    ctx.restore()

    # 2. Sitting Body (plump pear shape)
    ctx.save()
    ctx.translate(body_x, body_y)
    ctx.scale(1.1, 1.25)
    ctx.new_path()
    ctx.arc(0, 0, 22, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Calico dark patch on back
    ctx.save()
    ctx.translate(body_x + 12, body_y - 8)
    ctx.scale(1.2, 0.9)
    ctx.new_path()
    ctx.arc(0, 0, 11, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_BROWN)
    ctx.fill()

    # 3. Dainty Front Paws
    ctx.new_path()
    ctx.arc(body_x - 14, body_y + 24, 7, 0, 2 * math.pi)
    ctx.arc(body_x - 1, body_y + 24, 7, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()

    # 4. Ears
    draw_cat_ear(ctx, head_x - 14, head_y - 12, math.radians(-18), scale=0.95, is_orange=True)
    draw_cat_ear(ctx, head_x + 14, head_y - 12, math.radians(18), scale=0.95, is_orange=False)

    # 5. Head
    ctx.new_path()
    ctx.arc(head_x, head_y, 22, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Calico patch over left ear/eye
    ctx.save()
    ctx.new_path()
    ctx.arc(head_x - 10, head_y - 8, 13, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill()
    ctx.restore()

    # Eyes
    draw_cat_eye(ctx, head_x - 9, head_y + 1, blink=blink)
    draw_cat_eye(ctx, head_x + 9, head_y + 1, blink=blink)

    # Cute nose button
    ctx.new_path()
    ctx.move_to(head_x - 2.5, head_y + 7)
    ctx.line_to(head_x + 2.5, head_y + 7)
    ctx.line_to(head_x, head_y + 10)
    ctx.close_path()
    ctx.set_source_rgba(*C_PINK_NOSE)
    ctx.fill()

    # Cute cat mouth (:3)
    ctx.new_path()
    ctx.arc(head_x - 3.5, head_y + 12, 3.5, 0, math.pi)
    ctx.arc(head_x + 3.5, head_y + 12, 3.5, 0, math.pi)
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(1.8)
    ctx.stroke()

    # Whiskers
    draw_whiskers(ctx, head_x - 12, head_y + 10, facing_left=True)
    draw_whiskers(ctx, head_x + 12, head_y + 10, facing_left=False)

    # Blush
    ctx.new_path()
    ctx.arc(head_x - 14, head_y + 10, 4.5, 0, 2 * math.pi)
    ctx.arc(head_x + 14, head_y + 10, 4.5, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_CHEEK)
    ctx.fill()

    surface.write_to_png(os.path.join(ASSETS_DIR, filename))


def render_cat_walk(filename: str, *, facing_left: bool = True, leg_phase: float = 0.0, bob_y: float = 0.0):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 128, 128)
    ctx = cairo.Context(surface)

    if not facing_left:
        ctx.translate(64, 0)
        ctx.scale(-1, 1)
        ctx.translate(-64, 0)

    body_x, body_y = 68, 72 + bob_y
    head_x, head_y = 44, 52 + bob_y * 0.8

    # Tail
    ctx.save()
    ctx.translate(100, body_y - 2)
    ctx.rotate(math.radians(-25 + leg_phase * 15))
    ctx.new_path()
    ctx.curve_to(12, -8, 22, -24, 16, -38)
    ctx.curve_to(12, -42, 6, -40, 8, -34)
    ctx.curve_to(12, -22, 6, -10, 0, 0)
    ctx.close_path()
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()
    ctx.restore()

    # Far Legs
    ctx.save()
    ctx.translate(92 - leg_phase * 8, body_y + 18)
    ctx.new_path()
    ctx.arc(0, 4, 6, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()
    ctx.restore()

    ctx.save()
    ctx.translate(56 + leg_phase * 8, body_y + 18)
    ctx.new_path()
    ctx.arc(0, 4, 6, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()
    ctx.restore()

    # Sleek Body
    ctx.save()
    ctx.translate(body_x, body_y)
    ctx.scale(1.5, 0.95)
    ctx.new_path()
    ctx.arc(0, 0, 22, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Calico patch on back
    ctx.save()
    ctx.translate(body_x + 8, body_y - 6)
    ctx.scale(1.2, 0.8)
    ctx.new_path()
    ctx.arc(0, 0, 10, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_BROWN)
    ctx.fill()

    # Near Legs
    ctx.save()
    ctx.translate(84 + leg_phase * 8, body_y + 20)
    ctx.new_path()
    ctx.arc(0, 4, 7, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()
    ctx.restore()

    ctx.save()
    ctx.translate(46 - leg_phase * 8, body_y + 20)
    ctx.new_path()
    ctx.arc(0, 4, 7, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()
    ctx.restore()

    # Ears
    draw_cat_ear(ctx, head_x - 12, head_y - 12, math.radians(-16), scale=0.9, is_orange=True)
    draw_cat_ear(ctx, head_x + 12, head_y - 12, math.radians(16), scale=0.9, is_orange=False)

    # Head
    ctx.new_path()
    ctx.arc(head_x, head_y, 20, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Calico patch
    ctx.new_path()
    ctx.arc(head_x - 8, head_y - 6, 11, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill()

    # Eye (single clear expressive side eye)
    draw_cat_eye(ctx, head_x - 6, head_y)

    # Nose & Whiskers
    ctx.new_path()
    ctx.arc(head_x - 16, head_y + 4, 2.8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_PINK_NOSE)
    ctx.fill()

    draw_whiskers(ctx, head_x - 12, head_y + 6, facing_left=True)

    surface.write_to_png(os.path.join(ASSETS_DIR, filename))


def render_cat_sleep(filename: str, *, breathe_y: float = 0.0, z_frame: int = 1):
    """Curled up cat loaf sleeping with floating Zzz."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 128, 128)
    ctx = cairo.Context(surface)

    cx, cy = 64, 78 + breathe_y

    # Sleeping curled loaf
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(1.35, 1.0)
    ctx.new_path()
    ctx.arc(0, 0, 24, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Wrapped tail
    ctx.new_path()
    ctx.arc(cx + 10, cy + 12, 22, math.pi * 0.1, math.pi * 0.9)
    ctx.set_source_rgba(*C_ORANGE)
    ctx.set_line_width(7.0)
    ctx.stroke()
    ctx.new_path()
    ctx.arc(cx + 10, cy + 12, 22, math.pi * 0.1, math.pi * 0.9)
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(1.5)
    ctx.stroke()

    # Head tucked in
    head_x, head_y = cx - 18, cy - 2
    ctx.new_path()
    ctx.arc(head_x, head_y, 16, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.4)
    ctx.stroke()

    # Calico patch
    ctx.new_path()
    ctx.arc(head_x - 6, head_y - 6, 8, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_ORANGE)
    ctx.fill()

    # Ears folded down
    draw_cat_ear(ctx, head_x - 10, head_y - 8, math.radians(-35), scale=0.75, is_orange=True)
    draw_cat_ear(ctx, head_x + 8, head_y - 10, math.radians(10), scale=0.75, is_orange=False)

    # Closed peaceful eyes (~.~)
    ctx.new_path()
    ctx.arc(head_x - 6, head_y + 2, 4.0, math.pi * 0.15, math.pi * 0.85)
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.2)
    ctx.stroke()

    # Floating cute Zzz
    ctx.save()
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_source_rgba(0.40, 0.55, 0.85, 0.85)
    z_y = cy - 26 - (z_frame * 4)
    ctx.set_font_size(11 + z_frame * 2)
    ctx.move_to(cx + 14 + (z_frame * 4), z_y)
    ctx.show_text("Z" * z_frame)
    ctx.restore()

    surface.write_to_png(os.path.join(ASSETS_DIR, filename))


def render_cat_drag(filename: str):
    """Lifted by scruff dangling pose."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 128, 128)
    ctx = cairo.Context(surface)

    cx, cy = 64, 60

    # Scruff pull point
    ctx.new_path()
    ctx.arc(cx, cy - 24, 6, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill()

    # Dangling elongated body
    ctx.save()
    ctx.translate(cx, cy + 10)
    ctx.scale(0.85, 1.45)
    ctx.new_path()
    ctx.arc(0, 0, 18, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    # Hanging legs
    ctx.new_path()
    ctx.arc(cx - 10, cy + 38, 5.5, 0, 2 * math.pi)
    ctx.arc(cx + 10, cy + 38, 5.5, 0, 2 * math.pi)
    ctx.arc(cx - 7, cy + 16, 5.0, 0, 2 * math.pi)
    ctx.arc(cx + 7, cy + 16, 5.0, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.0)
    ctx.stroke()

    # Head
    head_x, head_y = cx, cy - 10
    ctx.new_path()
    ctx.arc(head_x, head_y, 18, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_WHITE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(2.6)
    ctx.stroke()

    draw_cat_ear(ctx, head_x - 12, head_y - 12, math.radians(-20), scale=0.85, is_orange=True)
    draw_cat_ear(ctx, head_x + 12, head_y - 12, math.radians(20), scale=0.85, is_orange=False)

    # Surprised wide eyes (O_O)
    draw_cat_eye(ctx, head_x - 7, head_y, surprised=True)
    draw_cat_eye(ctx, head_x + 7, head_y, surprised=True)

    # Little 'o' mouth
    ctx.new_path()
    ctx.arc(head_x, head_y + 10, 3.0, 0, 2 * math.pi)
    ctx.set_source_rgba(*C_PINK_NOSE)
    ctx.fill_preserve()
    ctx.set_source_rgba(*C_OUTLINE)
    ctx.set_line_width(1.6)
    ctx.stroke()

    surface.write_to_png(os.path.join(ASSETS_DIR, filename))


def generate_all():
    print("Generating Mochi the Cat frames...")

    # Idle
    render_cat_idle("idle_1.png", tail_swish=0.0, blink=False, breathe_y=0.0)
    render_cat_idle("idle_2.png", tail_swish=12.0, blink=False, breathe_y=1.5)
    render_cat_idle("idle_3.png", tail_swish=-10.0, blink=True, breathe_y=-0.5)
    render_cat_idle("idle_4.png", tail_swish=6.0, blink=False, breathe_y=0.5)

    # Walk Left (natural)
    render_cat_walk("walk_left_1.png", facing_left=True, leg_phase=1.0, bob_y=-2.0)
    render_cat_walk("walk_left_2.png", facing_left=True, leg_phase=0.0, bob_y=0.0)
    render_cat_walk("walk_left_3.png", facing_left=True, leg_phase=-1.0, bob_y=-2.0)
    render_cat_walk("walk_left_4.png", facing_left=True, leg_phase=0.0, bob_y=0.0)

    # Walk Right (mirrored)
    render_cat_walk("walk_1.png", facing_left=False, leg_phase=1.0, bob_y=-2.0)
    render_cat_walk("walk_2.png", facing_left=False, leg_phase=0.0, bob_y=0.0)
    render_cat_walk("walk_3.png", facing_left=False, leg_phase=-1.0, bob_y=-2.0)
    render_cat_walk("walk_4.png", facing_left=False, leg_phase=0.0, bob_y=0.0)

    # Sleep
    render_cat_sleep("sleep_1.png", breathe_y=0.0, z_frame=1)
    render_cat_sleep("sleep_2.png", breathe_y=1.5, z_frame=2)
    render_cat_sleep("sleep_3.png", breathe_y=0.0, z_frame=3)

    # Drag
    render_cat_drag("drag.png")

    print(f"All Mochi frames generated in {ASSETS_DIR}!")


if __name__ == "__main__":
    generate_all()

