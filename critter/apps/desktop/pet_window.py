"""GTK4 Layer Shell Pet Window.

Renders an individual transparent, interactive desktop pet window on Hyprland.
Features:
- Alpha channel transparency (no background borders or boxes).
- Layer Shell OVERLAY layer (sits above normal windows, zero exclusive zone).
- Non-focusable (KeyboardMode.NONE) to avoid stealing focus.
- Silky-smooth Hyprland IPC cursor-tracking drag and drop.
- Real-time frame animations and autonomous roaming.
- Independent multi-instance support with unique Wayland surface namespaces.
"""

import logging
import os
from typing import Dict, Optional
from critter.apps.desktop.bootstrap import bootstrap_layer_shell
from critter.apps.desktop.cursor import get_hyprland_cursor_pos

# Ensure layer shell preloads before importing GTK
bootstrap_layer_shell()

from gi.repository import Gtk, Gdk, Gtk4LayerShell, GLib
from critter.core.pet import BehaviorState, PetController, PetInstance, PetManifest

logger = logging.getLogger(__name__)

_CSS_INITIALIZED = False


def ensure_css_provider_installed() -> None:
    """Ensure the transparent CSS provider is registered once globally."""
    global _CSS_INITIALIZED
    if _CSS_INITIALIZED:
        return

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
        _CSS_INITIALIZED = True


class PetWindow(Gtk.ApplicationWindow):
    """Transparent GTK4 Layer Shell window hosting an individual cartoon pet instance."""

    def __init__(
        self,
        application: Gtk.Application,
        instance: Optional[PetInstance] = None,
        manifest: Optional[PetManifest] = None,
    ) -> None:
        super().__init__(application=application)

        if instance is not None:
            self.instance = instance
            self.manifest = instance.manifest
            self.controller = instance.controller
        elif manifest is not None:
            self.manifest = manifest
            self.controller = PetController(manifest=manifest)
            self.instance = PetInstance(
                instance_id=manifest.id,
                manifest=manifest,
                controller=self.controller,
                custom_name=manifest.name,
            )
        else:
            raise ValueError("Must provide either an instance or manifest to PetWindow.")

        self._textures: Dict[str, Gdk.Texture] = {}
        self._load_textures()

        self._grab_offset_x = float(self.manifest.width // 2)
        self._grab_offset_y = float(self.manifest.height // 2)
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
        self.set_title(f"Critter - {self.instance.custom_name}")
        self.set_default_size(self.manifest.width, self.manifest.height)
        self.add_css_class("critter-pet-window")
        ensure_css_provider_installed()

    def _setup_layer_shell(self) -> None:
        """Configure GTK4 Layer Shell for Wayland / Hyprland."""
        Gtk4LayerShell.init_for_window(self)
        namespace = f"critter-pet-{self.instance.instance_id}"
        Gtk4LayerShell.set_namespace(self, namespace)
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
        """Drag gesture to grab and reposition this specific pet instance."""
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def _on_drag_begin(self, gesture: Gtk.GestureDrag, start_x: float, start_y: float) -> None:
        self.controller.start_drag()
        self._update_display_frame()

        cur = get_hyprland_cursor_pos()
        if cur:
            self._grab_offset_x = cur[0] - self.controller.x
            self._grab_offset_y = cur[1] - self.controller.y
        else:
            self._grab_offset_x = start_x
            self._grab_offset_y = start_y
            self._drag_start_x = self.controller.x
            self._drag_start_y = self.controller.y

        # Run 60 FPS (16ms) smooth drag updater while dragging
        GLib.timeout_add(16, self._on_drag_tick)

    def _on_drag_tick(self) -> bool:
        if self.controller.state != BehaviorState.DRAGGING:
            return False  # Discontinue timer when drag ends

        cur = get_hyprland_cursor_pos()
        if cur:
            new_x = cur[0] - self._grab_offset_x
            new_y = cur[1] - self._grab_offset_y
            self.controller.set_position(new_x, new_y)
            self._apply_position_margins()
        return True

    def _on_drag_update(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        if not get_hyprland_cursor_pos():
            new_x = self._drag_start_x + offset_x
            new_y = self._drag_start_y + offset_y
            self.controller.set_position(new_x, new_y)
            self._apply_position_margins()

    def _on_drag_end(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        self.controller.end_drag()
        self._update_display_frame()

    def _setup_tickers(self) -> None:
        """Start animation frame ticker and autonomous physics ticker."""
        GLib.timeout_add(160, self._on_animation_tick)
        GLib.timeout_add(50, self._on_movement_tick)

    def _on_animation_tick(self) -> bool:
        if not self.controller.is_paused and self.instance.is_visible:
            self.controller.tick_animation()
            self._update_display_frame()
        return True

    def _on_movement_tick(self) -> bool:
        if not self.controller.is_paused and self.instance.is_visible:
            if self.controller.state != BehaviorState.DRAGGING:
                self.controller.tick_movement(0.05)
                self._apply_position_margins()
        return True

    def _update_display_frame(self) -> None:
        frame_path = self.controller.get_current_frame_path()
        texture = self._textures.get(frame_path)
        if texture:
            self.picture.set_paintable(texture)

    def pause(self) -> None:
        self.controller.pause()

    def resume(self) -> None:
        self.controller.resume()

    def set_pet_visible(self, visible: bool) -> None:
        self.instance.is_visible = visible
        self.set_visible(visible)
