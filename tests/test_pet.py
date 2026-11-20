"""Unit tests for PetManifest and PetController."""

import os
import pytest
from critter.core.events import EventBus
from critter.core.pet import BehaviorState, PetController, PetManifest, PetMoved


@pytest.fixture
def dog_manifest():
    manifest_dir = os.path.abspath("packages/pets/dog")
    return PetManifest.load_from_dir(manifest_dir)


def test_manifest_loading(dog_manifest):
    assert dog_manifest.id == "dog"
    assert dog_manifest.name == "Corgi"
    assert dog_manifest.species == "dog"
    assert dog_manifest.width == 128
    assert dog_manifest.height == 128
    assert "idle" in dog_manifest.animations
    assert "walk_right" in dog_manifest.animations
    assert "walk_left" in dog_manifest.animations
    assert "drag" in dog_manifest.animations

    # Verify frame files exist on disk
    for anim in dog_manifest.animations.values():
        for frame in anim.frames:
            assert os.path.isfile(frame), f"Frame file missing: {frame}"


def test_pet_controller_bounds(dog_manifest):
    controller = PetController(
        manifest=dog_manifest,
        screen_width=1920,
        screen_height=1080,
        initial_x=500,
        initial_y=500,
    )

    # Move outside left/top
    controller.set_position(-100, -200)
    assert controller.x == 0.0
    assert controller.y == 0.0

    # Move outside right/bottom
    controller.set_position(3000, 2000)
    assert controller.x == 1920 - 128
    assert controller.y == 1080 - 128


def test_pet_dragging_state(dog_manifest):
    bus = EventBus()
    controller = PetController(manifest=dog_manifest, event_bus=bus)

    assert controller.state == BehaviorState.IDLE
    assert controller.current_animation == "idle"

    controller.start_drag()
    assert controller.state == BehaviorState.DRAGGING
    assert controller.current_animation == "drag"

    controller.end_drag()
    assert controller.state == BehaviorState.IDLE
    assert controller.current_animation == "idle"


def test_pet_movement_tick(dog_manifest):
    controller = PetController(
        manifest=dog_manifest,
        initial_x=100,
        initial_y=100,
    )
    # Force state to walking towards (200, 100)
    controller.set_state(BehaviorState.WALKING)
    controller.target_x = 200.0
    controller.target_y = 100.0
    controller.state_time_remaining = 5.0

    # Advance 0.5 seconds at 75 px/sec = 37.5 px
    controller.tick_movement(0.5)
    assert controller.x == pytest.approx(137.5, 0.1)
    assert controller.y == pytest.approx(100.0, 0.1)


def test_animation_frame_tick(dog_manifest):
    controller = PetController(manifest=dog_manifest)
    controller.set_animation("idle")

    initial_idx = controller.frame_index
    controller.tick_animation()
    assert controller.frame_index == (initial_idx + 1) % len(dog_manifest.animations["idle"].frames)
