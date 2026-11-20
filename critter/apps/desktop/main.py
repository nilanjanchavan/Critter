"""Desktop application entrypoint for Critter.

Manages application lifecycle, CLI options, and multi-pet spawning.
Listing pets (--list-pets) executes cleanly in pure Python without initializing GTK.
"""

import argparse
import logging
import os
import signal
import sys
from typing import Dict, List

from critter.core.events import EventBus
from critter.core.manager import PetManager
from critter.core.registry import PetRegistry

logger = logging.getLogger("critter")


def handle_list_pets(search_paths: List[str]) -> int:
    """Print discovered pet packages without initializing GTK or Wayland."""
    registry = PetRegistry(search_paths=search_paths)
    try:
        packages = registry.discover()
    except Exception as exc:
        print(f"Error discovering pet packages: {exc}", file=sys.stderr)
        return 1

    if not packages:
        print("No pet packages found in search paths:", search_paths)
        return 0

    print(f"\nDiscovered {len(packages)} Critter Pet Package(s):")
    print("=" * 76)
    print(f"{'ID':<10} {'NAME':<14} {'SPECIES':<10} {'VERSION':<9} {'SIZE':<10} {'ANIMATIONS'}")
    print("-" * 76)

    for pid, pkg in packages.items():
        anims_summary = f"{len(pkg.animations)} ({', '.join(sorted(pkg.animations.keys()))})"
        size_str = f"{pkg.width}x{pkg.height}"
        print(f"{pid:<10} {pkg.name:<14} {pkg.species:<10} v{pkg.version:<8} {size_str:<10} {anims_summary}")
        if pkg.description:
            print(f"   └─ {pkg.description}")

    print("=" * 76)
    print("Launch with: critter --pets <id1>,<id2> (e.g. critter --pets dog,cat)\n")
    return 0


def run_desktop_app(pet_ids: List[str], search_paths: List[str]) -> int:
    """Bootstrap Wayland Layer Shell, initialize GTK, and launch desktop pets."""
    from critter.apps.desktop.bootstrap import bootstrap_layer_shell, verify_layer_shell_supported

    # Bootstrap dynamic linker before any GTK imports
    bootstrap_layer_shell()

    from gi.repository import Gtk, Gio, GLib
    from critter.apps.desktop.pet_window import PetWindow

    if not verify_layer_shell_supported():
        logger.critical("Wayland Layer Shell is not supported on this compositor/display.")
        return 1

    registry = PetRegistry(search_paths=search_paths)
    try:
        registry.discover()
    except Exception as exc:
        logger.critical("Failed to load pet registry: %s", exc)
        return 1

    event_bus = EventBus()
    manager = PetManager(registry=registry, event_bus=event_bus)

    class CritterApplication(Gtk.Application):
        """GTK4 application orchestrating multiple Layer Shell pet windows."""

        def __init__(self) -> None:
            super().__init__(
                application_id="org.critter.CritterDesktop",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            self.windows: Dict[str, PetWindow] = {}

        def do_activate(self) -> None:
            if not self.windows:
                for pet_id in pet_ids:
                    try:
                        instance = manager.spawn(pet_id)
                        win = PetWindow(application=self, instance=instance)
                        win.present()
                        self.windows[instance.instance_id] = win
                        logger.info("Spawned pet '%s' (%s) on desktop.", instance.custom_name, instance.instance_id)
                    except Exception as e:
                        logger.error("Failed to spawn pet '%s': %s", pet_id, e)

                if not self.windows:
                    logger.critical("No pet windows were spawned. Exiting...")
                    self.quit()

    app = CritterApplication()

    # Clean signal handling for SIGINT (Ctrl+C) and SIGTERM
    def signal_handler(sig, frame):
        logger.info("Termination signal received. Exiting Critter...")
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Wake up Python signal handler periodically
    GLib.timeout_add(250, lambda: True)

    return app.run([])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Critter — Customizable Desktop Pet Automation for Linux (Hyprland / Wayland)"
    )
    parser.add_argument(
        "--list-pets",
        action="store_true",
        help="List all discovered pet packages and exit (runs without GTK)",
    )
    parser.add_argument(
        "--pets",
        default="dog",
        help="Comma-separated pet IDs to spawn (default: dog). E.g. --pets dog,cat",
    )
    parser.add_argument(
        "--dir",
        action="append",
        dest="custom_dirs",
        default=[],
        help="Additional custom directories to search for pet packages (repeatable)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    search_paths = ["packages/pets"] + args.custom_dirs

    if args.list_pets:
        return handle_list_pets(search_paths)

    # Parse requested pet IDs
    pet_ids = [p.strip() for p in args.pets.split(",") if p.strip()]
    if not pet_ids:
        pet_ids = ["dog"]

    return run_desktop_app(pet_ids=pet_ids, search_paths=search_paths)


if __name__ == "__main__":
    sys.exit(main())
