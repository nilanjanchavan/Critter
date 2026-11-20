"""Hyprland global cursor position tracking for silky-smooth window dragging."""

import json
import logging
import os
import socket
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def get_hyprland_cursor_pos() -> Optional[Tuple[float, float]]:
    """Query current global cursor position directly from Hyprland IPC socket.

    Takes ~0.02ms with zero process forks. Returns (x, y) or None if unavailable.
    """
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None

    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
    sock_path = f"{xdg_runtime}/hypr/{sig}/.socket.sock"

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.04)
        s.connect(sock_path)
        s.sendall(b"j/cursorpos")
        data = s.recv(256)
        s.close()
        pos = json.loads(data.decode("utf-8"))
        return float(pos["x"]), float(pos["y"])
    except Exception:
        return None

