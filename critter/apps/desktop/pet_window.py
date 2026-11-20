"""GTK4 Layer Shell Pet Window.

Renders an individual transparent, interactive desktop pet window on Hyprland.
Features:
- Alpha channel transparency (no background borders or boxes).
- Layer Shell OVERLAY layer (sits above normal windows, zero exclusive zone).
- Non-focusable (KeyboardMode.NONE) to avoid stealing focus.
- Smooth mouse drag & drop repositioning with Gtk.GestureDrag.
- Real-time frame animations and autonomous roaming.
"""

import logging
import os
from typing import Dict, Optional
from critter.apps.desktop.bootstrap import bootstrap_layer_shell

# Ensure layer shell preloads before importing GTK
bootstrap_layer_shell()

from gi.repository import Gtk, Gdk, Gtk4LayerShell, GLib
from critter.core.pet import BehaviorState, PetController, PetManifest

logger = logging.getLogger(__name__)


class PetWindow(Gtk.ApplicationWindow):
    """Transparent GTK4 Layer Shell window hosting a single cartoon pet."""

    def __init__(self, application: Gtk.Application, manifest: PetManifest) -> None:
        super().__init__(application=application)

        self.manifest = manifest
        self.controller = PetController(
            manifest=manifest,
            initial_x=200.0,
            initial_y=250.0,
        )

        self._textures: Dict[str, Gdk.Texture] = {}
        self._load_textures()

        self._drag_start_x = 0.0
        self._drag_start_y = 0.0

        self._setup_window_properties()
        self._setup_layer_shell()
        self._setup_widgets()
        self._setup_gestures()
        self._setup_tickers()

    def _load_textures(self) -> None:
        """Preload all animation frame PNGs into Gdk.Texture memory."""
        for anim_name, anim_def in self.manifest.animations.items():
            for frame_path in anim_def.frames:
                if frame_path not in self._textures:
                    if os.path.isfile(frame_path):
                        texture = Gdk.Texture.new_from_filename(frame_path)
                        self._textures[frame_path] = texture
                    else:
                        logger.error("Sprite frame missing: %s", frame_path)

    def _setup_window_properties(self) -> None:
        self.set_title(f"Critter - {self.manifest.name}")
        self.set_default_size(self.manifest.width, self.manifest.height)
        self.add_css_class("critter-pet-window")

        # Apply CSS for full background alpha transparency
        css_provider = Gtk.CssProvider()
        css_data = b"""
        window.critter-pet-window {
            background-color: transparent;
            background: none;
            border: none;
            box-shadow: none;
            outline: none;
            padding: 0;
            margin: 0;
        }
        """
        css_provider.load_from_data(css_data)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _setup_layer_shell(self) -> None:
        """Configure GTK4 Layer Shell for Wayland / Hyprland."""
        Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_namespace(self, "critter-pet")
        Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_exclusive_zone(self, 0)
        Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.NONE)

        # Anchor to TOP and LEFT
        Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.TOP, True)
        Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.LEFT, True)
        Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.BOTTOM, False)
        Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.RIGHT, False)

        # Set initial margins
        self._apply_position_margins()

    def _apply_position_margins(self) -> None:
        """Update window layer margins to match current controller position."""
        x = int(self.controller.x)
        y = int(self.controller.y)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.LEFT, x)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.TOP, y)

    def _setup_widgets(self) -> None:
        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(False)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_size_request(self.manifest.width, self.manifest.height)
        self.set_child(self.picture)
        self._update_display_frame()

    def _setup_gestures(self) -> None:
        """Drag gesture to grab and reposition the pet with mouse pointer."""
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def _on_drag_begin(self, gesture: Gtk.GestureDrag, start_x: float, start_y: float) -> None:
        self._drag_start_x = self.controller.x
        self._drag_start_y = self.controller.y
        self.controller.start_drag()
        self._update_display_frame()

    def _on_drag_update(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        new_x = self._drag_start_x + offset_x
        new_y = self._drag_start_y + offset_y
        self.controller.set_position(new_x, new_y)
        self._apply_position_margins()

    def _on_drag_end(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        new_x = self._drag_start_x + offset_x
        new_y = self._drag_start_y + offset_y
        self.controller.set_position(new_x, new_y)
        self._apply_position_margins()
        self.controller.end_drag()
        self._update_display_frame()

    def _setup_tickers(self) -> None:
        """Start animation frame ticker and autonomous physics ticker."""
        # 1. Animation frame ticker (every 160ms ~ 6 FPS)
        GLib.timeout_add(160, self._on_animation_tick)
        # 2. Movement / roaming ticker (every 50ms = 20 FPS)
        GLib.timeout_add(50, self._on_movement_tick)

    def _on_animation_tick(self) -> bool:
        self.controller.tick_animation()
        self._update_display_frame()
        return True  # Keep GLib timer active

    def _on_movement_tick(self) -> bool:
        if self.controller.state != BehaviorState.DRAGGING:
            self.controller.tick_movement(0.05)
            self._apply_position_margins()
        return True  # Keep GLib timer active

    def _update_display_frame(self) -> None:
        frame_path = self.controller.get_current_frame_path()
        texture = self._textures.get(frame_path)
        if texture:
            self.picture.set_paintable(texture)
