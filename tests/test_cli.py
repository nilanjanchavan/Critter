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


def test_cli_bridge_token_and_origin_management_no_gtk() -> None:
    # 1. Check token output
    res_tok = subprocess.run(
        [sys.executable, "-m", "critter.apps.desktop.main", "--bridge-token"],
        capture_output=True,
        text=True,
    )
    assert res_tok.returncode == 0
    assert "Critter Bridge Auth Token:" in res_tok.stdout

    # 2. Pair test origin
    test_origin = "chrome-extension://testcliorigin12345"
    res_pair = subprocess.run(
        [sys.executable, "-m", "critter.apps.desktop.main", "--pair-origin", test_origin],
        capture_output=True,
        text=True,
    )
    assert res_pair.returncode == 0
    assert f"Successfully paired extension origin: {test_origin}" in res_pair.stdout

    # 3. List paired origins
    res_list = subprocess.run(
        [sys.executable, "-m", "critter.apps.desktop.main", "--list-origins"],
        capture_output=True,
        text=True,
    )
    assert res_list.returncode == 0
    assert test_origin in res_list.stdout

    # 4. Revoke origin
    res_rev = subprocess.run(
        [sys.executable, "-m", "critter.apps.desktop.main", "--revoke-origin", test_origin],
        capture_output=True,
        text=True,
    )
    assert res_rev.returncode == 0
    assert f"Successfully revoked extension origin: {test_origin}" in res_rev.stdout

