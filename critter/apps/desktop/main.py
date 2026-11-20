"""Desktop application entrypoint for Critter.

Initializes the Gtk.Application and displays the first desktop pet.
"""

import argparse
import logging
import os
import signal
import sys

from critter.apps.desktop.bootstrap import bootstrap_layer_shell, verify_layer_shell_supported

# Bootstrap dynamic linker before any GTK imports
bootstrap_layer_shell()

from gi.repository import Gtk, Gio, GLib
from critter.apps.desktop.pet_window import PetWindow
from critter.core.pet import PetManifest

logger = logging.getLogger("critter")


class CritterApplication(Gtk.Application):
    """Main application lifecycle controller."""

    def __init__(self, pet_package_dir: str) -> None:
        super().__init__(
            application_id="org.critter.CritterDesktop",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.pet_package_dir = pet_package_dir
        self.window: PetWindow | None = None

    def do_activate(self) -> None:
        if not self.window:
            manifest = PetManifest.load_from_dir(self.pet_package_dir)
            self.window = PetWindow(application=self, manifest=manifest)
            self.window.present()
            logger.info("Critter pet '%s' successfully spawned on desktop.", manifest.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Critter — Desktop Pet Automation for Linux")
    parser.add_argument(
        "--pet-dir",
        default="packages/pets/dog",
        help="Path to pet package directory (default: packages/pets/dog)",
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

    pet_dir = os.path.abspath(args.pet_dir)
    if not os.path.isdir(pet_dir):
        logger.error("Pet directory not found: %s", pet_dir)
        return 1

    if not verify_layer_shell_supported():
        logger.error("Wayland Layer Shell is not supported on this compositor/display.")
        return 1

    app = CritterApplication(pet_package_dir=pet_dir)

    # Clean signal handling for SIGINT (Ctrl+C) and SIGTERM
    def signal_handler(sig, frame):
        logger.info("Termination signal received. Exiting Critter...")
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Wake up Python signal handler periodically
    GLib.timeout_add(250, lambda: True)

    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
