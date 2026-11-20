"""Tests for Critter CLI commands and non-GTK discovery modes."""

import subprocess
import sys


def test_cli_list_pets_no_gtk() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "critter.apps.desktop.main", "--list-pets"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Discovered" in result.stdout
    assert "Corgi" in result.stdout
    assert "Mochi" in result.stdout
    # Verify no GTK initialization happened
    assert "gi.repository.Gtk" not in sys.modules


def test_cli_list_automations_no_gtk() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "critter.apps.desktop.main", "--list-automations"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Discovered" in result.stdout
    assert "pomodoro_timer" in result.stdout
    assert "hydration_reminder" in result.stdout
    assert "distraction_guard" in result.stdout

