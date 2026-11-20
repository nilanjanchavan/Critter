"""Desktop application entrypoint for Critter.

Manages application lifecycle, CLI options, and multi-pet spawning.
Listing pets (--list-pets) executes cleanly in pure Python without initializing GTK.
"""

import argparse
import logging
import os
import signal
import sys
from typing import Dict, List, Optional

from critter.core.events import EventBus
from critter.core.manager import PetManager
from critter.core.registry import PetRegistry
from critter.core.automation import AutomationEngine, load_rules_from_dir
from critter.core.communication import BridgeAuthManager, BridgeServer, BridgeServerThread

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


def handle_list_automations(search_paths: List[str]) -> int:
    """Print discovered automation rules without initializing GTK."""
    all_rules = []
    for p in search_paths:
        all_rules.extend(load_rules_from_dir(p))

    if not all_rules:
        print("No automation rules found in search paths:", search_paths)
        return 0

    print(f"\nDiscovered {len(all_rules)} Automation Rule(s):")
    print("=" * 86)
    print(f"{'ID':<22} {'NAME':<24} {'TRIGGER':<14} {'ACTIONS':<12} {'ENABLED'}")
    print("-" * 86)

    for r in all_rules:
        trigger_str = f"{r.trigger.type}"
        if r.trigger.type == "interval":
            sec = r.trigger.params.get("interval_seconds", 0)
            trigger_str += f" ({sec:.0f}s)"
        elif r.trigger.type == "event":
            trigger_str += f" ({r.trigger.params.get('event_name', '')})"

        actions_str = f"{len(r.actions)} ({', '.join(a.type for a in r.actions)})"
        enabled_str = "yes" if r.enabled else "no"
        print(f"{r.id:<22} {r.name:<24} {trigger_str:<14} {actions_str:<12} {enabled_str}")
        if r.description:
            print(f"   └─ {r.description}")

    print("=" * 86)
    print("Configure with: critter --automations all (or --automations pomodoro_timer,hydration_reminder)\n")
    return 0


def handle_bridge_token() -> int:
    """Print the bridge authentication token for browser extension pairing."""
    auth_mgr = BridgeAuthManager()
    print(f"\nCritter Bridge Auth Token:\n{auth_mgr.token}\n")
    print("Paste this token into the Critter Companion browser extension popup to authenticate.\n")
    return 0


def handle_pair_origin(origin: str, label: str = "Browser Extension") -> int:
    """Explicitly pair an extension origin in the allowlist."""
    auth_mgr = BridgeAuthManager()
    try:
        auth_mgr.add_paired_origin(origin, label=label)
        print(f"\n[+] Successfully paired extension origin: {origin} ({label})\n")
        return 0
    except Exception as exc:
        print(f"Error pairing origin: {exc}", file=sys.stderr)
        return 1


def handle_revoke_origin(origin: str) -> int:
    """Revoke a previously paired extension origin."""
    auth_mgr = BridgeAuthManager()
    if auth_mgr.revoke_origin(origin):
        print(f"\n[-] Successfully revoked extension origin: {origin}\n")
        return 0
    else:
        print(f"Origin '{origin}' was not found in paired list.", file=sys.stderr)
        return 1


def handle_list_origins() -> int:
    """List all explicitly paired extension origins."""
    auth_mgr = BridgeAuthManager()
    origins = auth_mgr.list_paired_origins()
    print(f"\nPaired Extension Origins ({len(origins)}):")
    print("=" * 76)
    if not origins:
        print("  (None paired yet. Use `critter --pair-origin <origin>` to pair an extension)")
    else:
        for po in origins:
            print(f"  • {po.origin:<40} ({po.label}) [paired: {po.paired_at[:19]}]")
    print("=" * 76 + "\n")
    return 0


def handle_run_bridge(port: int = 8765) -> int:
    """Run standalone WebSocket bridge server without initializing GTK."""
    import asyncio
    auth_mgr = BridgeAuthManager()
    event_bus = EventBus()
    bridge_server = BridgeServer(auth_manager=auth_mgr, event_bus=event_bus, host="127.0.0.1", port=port)

    print(f"\nStarting Critter WebSocket bridge on ws://127.0.0.1:{port}...")
    print(f"Auth Token: {auth_mgr.token}")
    paired = auth_mgr.list_paired_origins()
    print(f"Paired Origins ({len(paired)}):")
    if not paired:
        print("  (None. Pair in another terminal with: critter --pair-origin <origin>)")
    else:
        for po in paired:
            print(f"  • {po.origin} ({po.label})")

    async def run():
        await bridge_server.start_async()
        print("\n[✓] Bridge server running. Ready for browser extension connections.")
        print("Press Ctrl+C to stop.\n")
        while bridge_server.is_running:
            await asyncio.sleep(1.0)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopping bridge server...")
    return 0


def handle_package_cli(args_list: List[str]) -> int:
    """Handle 'critter package' subcommands (validate, export, install) without GTK."""
    parser = argparse.ArgumentParser(
        prog="critter package",
        description="Critter Pet Package Management (validate, export, install)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Validate
    val_p = subparsers.add_parser("validate", help="Validate a pet package directory or archive")
    val_p.add_argument("path", help="Path to package directory, .tar.gz, or .zip")

    # Export
    exp_p = subparsers.add_parser("export", help="Export a pet package to a clean distributable archive")
    exp_p.add_argument("package_id", help="ID of package in registry or path to package directory")
    exp_p.add_argument("--output", "-o", help="Custom destination path for archive")
    exp_p.add_argument("--format", "-f", default="tar.gz", choices=["tar.gz", "zip"], help="Archive format (default: tar.gz)")

    # Install
    inst_p = subparsers.add_parser("install", help="Safely validate and install a pet package")
    inst_p.add_argument("archive", help="Path to .tar.gz or .zip package archive")
    inst_p.add_argument("--dest", "-d", help="Custom destination directory for installed package")
    inst_p.add_argument("--force", action="store_true", help="Replace existing community package if already installed")

    args = parser.parse_args(args_list)

    from critter.core.packaging import (
        validate_package,
        export_package,
        install_package,
    )

    if args.subcommand == "validate":
        try:
            res = validate_package(args.path)
            print(f"\n[✓] Package Validation Succeeded:")
            print("=" * 60)
            print(f"  Package ID:   {res.package_id}")
            print(f"  Name:         {res.name}")
            print(f"  Species:      {res.species}")
            print(f"  Version:      v{res.version}")
            print(f"  Dimensions:   {res.width}x{res.height} px")
            print(f"  Animations:   {res.animation_count} ({res.frame_count} total frames)")
            print(f"  Total Size:   {res.total_size_bytes:,} bytes ({res.file_count} files)")
            print("=" * 60 + "\n")
            return 0
        except Exception as exc:
            print(f"\n[✗] Validation Failed: {exc}\n", file=sys.stderr)
            return 1

    elif args.subcommand == "export":
        try:
            archive_path, sha256 = export_package(
                args.package_id,
                output_path=args.output,
                archive_format=args.format,
            )
            print(f"\n[✓] Successfully Exported Pet Package:")
            print("=" * 70)
            print(f"  Archive:   {archive_path}")
            print(f"  SHA-256:   {sha256}")
            print(f"  Checksum:  {archive_path}.sha256")
            print("=" * 70 + "\n")
            return 0
        except Exception as exc:
            print(f"\n[✗] Export Failed: {exc}\n", file=sys.stderr)
            return 1

    elif args.subcommand == "install":
        try:
            dest = install_package(args.archive, target_base_dir=getattr(args, "dest", None), force=args.force)
            print(f"\n[✓] Successfully Installed Pet Package:")
            print("=" * 70)
            print(f"  Installed Location: {dest}")
            print(f"  Available in:       critter --list-pets")
            print("=" * 70 + "\n")
            return 0
        except Exception as exc:
            print(f"\n[✗] Installation Failed: {exc}\n", file=sys.stderr)
            return 1

    return 0


def run_desktop_app(
    pet_ids: List[str],
    search_paths: List[str],
    automations_spec: str = "all",
    automation_paths: Optional[List[str]] = None,
) -> int:
    """Bootstrap Wayland Layer Shell, initialize GTK, and launch desktop pets & automations."""
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

    # Initialize Automation Engine
    automation_paths = automation_paths or ["packages/automations"]
    automation_engine = AutomationEngine(event_bus=event_bus)
    all_rules = []
    for a_path in automation_paths:
        all_rules.extend(load_rules_from_dir(a_path))

    # Configure enabled rules based on CLI spec
    if automations_spec.lower() == "none":
        for r in all_rules:
            r.enabled = False
    elif automations_spec.lower() != "all":
        selected_ids = {s.strip() for s in automations_spec.split(",") if s.strip()}
        for r in all_rules:
            r.enabled = (r.id in selected_ids)

    for r in all_rules:
        automation_engine.register_rule(r)

    # GLib 1-second timer to advance interval automations cheaply
    GLib.timeout_add_seconds(1, lambda: (automation_engine.tick(1.0), True)[1])

    # Start WebSocket Bridge Server on background thread
    bridge_server = BridgeServer(
        event_bus=event_bus,
        thread_dispatch=lambda fn: GLib.idle_add(lambda: (fn(), False)[1]),
    )
    bridge_thread = BridgeServerThread(bridge_server)
    bridge_thread.start()

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
        bridge_thread.stop()
        automation_engine.dispose()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Wake up Python signal handler periodically
    GLib.timeout_add(250, lambda: True)

    return app.run([])


def main() -> int:
    # Package management subcommands (pure Python CLI without GTK)
    if len(sys.argv) > 1 and sys.argv[1] == "package":
        return handle_package_cli(sys.argv[2:])

    parser = argparse.ArgumentParser(
        description="Critter — Customizable Desktop Pet Automation for Linux (Hyprland / Wayland)"
    )
    parser.add_argument(
        "--list-pets",
        action="store_true",
        help="List all discovered pet packages and exit (runs without GTK)",
    )
    parser.add_argument(
        "--list-automations",
        action="store_true",
        help="List all discovered automation rules and exit (runs without GTK)",
    )
    parser.add_argument(
        "--bridge-token",
        action="store_true",
        help="Display the bridge secret token for browser extension pairing and exit",
    )
    parser.add_argument(
        "--pair-origin",
        metavar="ORIGIN",
        help="Pair an extension origin in the bridge allowlist (e.g. chrome-extension://<id>)",
    )
    parser.add_argument(
        "--revoke-origin",
        metavar="ORIGIN",
        help="Revoke an extension origin from the bridge allowlist",
    )
    parser.add_argument(
        "--list-origins",
        action="store_true",
        help="List all currently paired extension origins and exit",
    )
    parser.add_argument(
        "--bridge",
        action="store_true",
        help="Run standalone WebSocket bridge server for browser extension testing and exit",
    )
    parser.add_argument(
        "--pets",
        default="dog",
        help="Comma-separated pet IDs to spawn (default: dog). E.g. --pets dog,cat",
    )
    parser.add_argument(
        "--automations",
        default="all",
        help="Automations to enable: 'all', 'none', or comma-separated rule IDs (default: all)",
    )
    parser.add_argument(
        "--dir",
        action="append",
        dest="custom_dirs",
        default=[],
        help="Additional custom directories to search for pet packages (repeatable)",
    )
    parser.add_argument(
        "--automations-dir",
        action="append",
        dest="custom_automation_dirs",
        default=[],
        help="Additional custom directories to search for automation rules (repeatable)",
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
    automation_paths = ["packages/automations"] + args.custom_automation_dirs

    # Non-GUI CLI actions
    if args.list_pets:
        return handle_list_pets(search_paths)

    if args.list_automations:
        return handle_list_automations(automation_paths)

    if args.bridge_token:
        return handle_bridge_token()

    if args.pair_origin:
        return handle_pair_origin(args.pair_origin)

    if args.revoke_origin:
        return handle_revoke_origin(args.revoke_origin)

    if args.list_origins:
        return handle_list_origins()

    if args.bridge:
        return handle_run_bridge()

    # Parse requested pet IDs
    pet_ids = [p.strip() for p in args.pets.split(",") if p.strip()]
    if not pet_ids:
        pet_ids = ["dog"]

    return run_desktop_app(
        pet_ids=pet_ids,
        search_paths=search_paths,
        automations_spec=args.automations,
        automation_paths=automation_paths,
    )


if __name__ == "__main__":
    sys.exit(main())
