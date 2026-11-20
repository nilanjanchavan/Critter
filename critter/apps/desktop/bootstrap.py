"""Layer Shell Bootstrap & GTK4 Environment Initializer.

ARCHITECTURAL RATIONALE:
gtk4-layer-shell operates by intercepting Wayland client protocol calls
(specifically `wl_registry_add_listener` and `wl_display_roundtrip`) to register
the `zwlr_layer_shell_v1` global surface interface on Wayland compositors (Hyprland).

In Python environments, PyGObject and GTK4 dynamically link against libwayland-client.so.
If libgtk4-layer-shell is imported *after* libwayland-client has already bound its
symbols, the interception hooks are bypassed, causing `Gtk4LayerShell.is_supported()`
to fail.

By preloading `libgtk4-layer-shell.so.0` using `ctypes.CDLL` with `RTLD_GLOBAL`
BEFORE any GTK or GDK modules are loaded, the linker resolves the intercepted
symbols globally. This enables native, robust Wayland Layer Shell support on Hyprland
without requiring external wrapper scripts or manual LD_PRELOAD user exports.
"""

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)

_BOOTSTRAPPED = False


def bootstrap_layer_shell() -> None:
    """Preload libgtk4-layer-shell into the global dynamic linker table."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    lib_names = [
        "libgtk4-layer-shell.so.0",
        "libgtk4-layer-shell.so",
        "/usr/lib64/libgtk4-layer-shell.so.0",
        "/usr/lib/libgtk4-layer-shell.so.0",
    ]

    loaded = False
    for name in lib_names:
        try:
            ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)
            logger.debug("Successfully preloaded %s into RTLD_GLOBAL", name)
            loaded = True
            break
        except OSError:
            continue

    if not loaded:
        logger.warning(
            "Could not preload libgtk4-layer-shell via ctypes. "
            "Layer shell functionality may not be detected on Wayland."
        )

    # Set up required GObject Introspection versions
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        gi.require_version("Gtk4LayerShell", "1.0")
        _BOOTSTRAPPED = True
    except ValueError as e:
        logger.critical("Required GObject Introspection library version not found: %s", e)
        raise RuntimeError(f"Missing required GTK4 / LayerShell libraries: {e}") from e


def verify_layer_shell_supported() -> bool:
    """Verify whether Layer Shell is actively supported on the current display."""
    bootstrap_layer_shell()
    from gi.repository import Gtk, Gtk4LayerShell
    if not Gtk.is_initialized():
        Gtk.init()
    return bool(Gtk4LayerShell.is_supported())

