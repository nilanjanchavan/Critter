"""Data-driven pet models and pure-Python autonomous movement controller.

Completely independent of GTK and Wayland.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import json
import os
import random
from typing import Dict, List, Optional, Tuple
from critter.core.events import Event, EventBus


class BehaviorState(Enum):
    IDLE = auto()
    WALKING = auto()
    DRAGGING = auto()


@dataclass(kw_only=True)
class AnimationDef:
    fps: int
    loop: bool
    frames: List[str]


@dataclass(kw_only=True)
class MovementConfig:
    speed: float = 75.0
    idle_min_seconds: float = 2.0
    idle_max_seconds: float = 6.0
    walk_min_seconds: float = 2.0
    walk_max_seconds: float = 5.0


@dataclass(kw_only=True)
class PetManifest:
    id: str
    name: str
    species: str
    version: str
    author: str
    description: str
    width: int
    height: int
    default_animation: str
    animations: Dict[str, AnimationDef]
    movement: MovementConfig
    package_dir: str

    @classmethod
    def load_from_dir(cls, package_dir: str) -> "PetManifest":
        manifest_path = os.path.join(package_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        animations = {
            anim_name: AnimationDef(
                fps=anim_data.get("fps", 4),
                loop=anim_data.get("loop", True),
                frames=[
                    os.path.join(package_dir, rel_path)
                    for rel_path in anim_data.get("frames", [])
                ],
            )
            for anim_name, anim_data in data.get("animations", {}).items()
        }

        mv_data = data.get("movement", {})
        movement = MovementConfig(
            speed=float(mv_data.get("speed", 75.0)),
            idle_min_seconds=float(mv_data.get("idle_min_seconds", 2.0)),
            idle_max_seconds=float(mv_data.get("idle_max_seconds", 6.0)),
            walk_min_seconds=float(mv_data.get("walk_min_seconds", 2.0)),
            walk_max_seconds=float(mv_data.get("walk_max_seconds", 5.0)),
        )

        return cls(
            id=data["id"],
            name=data["name"],
            species=data["species"],
            version=data.get("version", "1.0.0"),
            author=data.get("author", "Unknown"),
            description=data.get("description", ""),
            width=int(data.get("size", {}).get("width", 128)),
            height=int(data.get("size", {}).get("height", 128)),
            default_animation=data.get("default_animation", "idle"),
            animations=animations,
            movement=movement,
            package_dir=package_dir,
        )


@dataclass(kw_only=True)
class PetMoved(Event):
    pet_id: str
    x: float
    y: float


@dataclass(kw_only=True)
class PetAnimationChanged(Event):
    pet_id: str
    animation: str


@dataclass(kw_only=True)
class PetStateChanged(Event):
    pet_id: str
    state: BehaviorState


class PetController:
    """Manages pet coordinate physics, autonomous roaming, and animation states."""

    def __init__(
        self,
        manifest: PetManifest,
        screen_width: int = 1920,
        screen_height: int = 1080,
        initial_x: float = 300.0,
        initial_y: float = 400.0,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.manifest = manifest
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = initial_x
        self.y = initial_y
        self.event_bus = event_bus

        self.state = BehaviorState.IDLE
        self.current_animation = manifest.default_animation
        self.frame_index = 0
        self.facing_left = False

        self.target_x = initial_x
        self.target_y = initial_y
        self.state_time_remaining = random.uniform(
            manifest.movement.idle_min_seconds,
            manifest.movement.idle_max_seconds,
        )

    def set_position(self, x: float, y: float) -> None:
        """Clamp and set position within screen boundaries."""
        max_x = max(0, self.screen_width - self.manifest.width)
        max_y = max(0, self.screen_height - self.manifest.height)
        self.x = max(0.0, min(float(x), float(max_x)))
        self.y = max(0.0, min(float(y), float(max_y)))
        if self.event_bus:
            self.event_bus.publish(PetMoved(pet_id=self.manifest.id, x=self.x, y=self.y))

    def set_animation(self, animation_name: str) -> None:
        if animation_name not in self.manifest.animations:
            return
        if self.current_animation != animation_name:
            self.current_animation = animation_name
            self.frame_index = 0
            if self.event_bus:
                self.event_bus.publish(
                    PetAnimationChanged(pet_id=self.manifest.id, animation=animation_name)
                )

    def set_state(self, new_state: BehaviorState) -> None:
        if self.state != new_state:
            self.state = new_state
            if self.event_bus:
                self.event_bus.publish(
                    PetStateChanged(pet_id=self.manifest.id, state=new_state)
                )

    def start_drag(self) -> None:
        self.set_state(BehaviorState.DRAGGING)
        self.set_animation("drag")

    def end_drag(self) -> None:
        self.set_state(BehaviorState.IDLE)
        self.set_animation("idle")
        self.state_time_remaining = random.uniform(
            self.manifest.movement.idle_min_seconds,
            self.manifest.movement.idle_max_seconds,
        )

    def tick_animation(self) -> None:
        """Advance animation by one frame."""
        anim = self.manifest.animations.get(self.current_animation)
        if not anim or not anim.frames:
            return

        if self.frame_index + 1 < len(anim.frames):
            self.frame_index += 1
        elif anim.loop:
            self.frame_index = 0

    def get_current_frame_path(self) -> str:
        anim = self.manifest.animations.get(self.current_animation)
        if not anim or not anim.frames:
            return ""
        idx = min(self.frame_index, len(anim.frames) - 1)
        return anim.frames[idx]

    def tick_movement(self, delta_time: float) -> None:
        """Update autonomous movement and state transitions."""
        if self.state == BehaviorState.DRAGGING:
            return

        self.state_time_remaining -= delta_time

        if self.state == BehaviorState.IDLE:
            if self.state_time_remaining <= 0:
                # Transition from idle to walking
                self.set_state(BehaviorState.WALKING)
                self.state_time_remaining = random.uniform(
                    self.manifest.movement.walk_min_seconds,
                    self.manifest.movement.walk_max_seconds,
                )
                # Pick a destination within screen bounds
                margin = 80
                max_x = max(margin, self.screen_width - self.manifest.width - margin)
                max_y = max(margin, self.screen_height - self.manifest.height - margin)
                self.target_x = random.uniform(margin, max_x)
                self.target_y = random.uniform(margin, max_y)

                # Determine direction facing
                self.facing_left = (self.target_x < self.x)
                self.set_animation("walk_left" if self.facing_left else "walk_right")

        elif self.state == BehaviorState.WALKING:
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = (dx * dx + dy * dy) ** 0.5

            step = self.manifest.movement.speed * delta_time

            if dist <= step or self.state_time_remaining <= 0:
                # Arrived at destination or time ran out
                self.set_position(self.target_x if dist <= step else self.x,
                                  self.target_y if dist <= step else self.y)
                self.set_state(BehaviorState.IDLE)
                self.set_animation("idle")
                self.state_time_remaining = random.uniform(
                    self.manifest.movement.idle_min_seconds,
                    self.manifest.movement.idle_max_seconds,
                )
            else:
                new_x = self.x + (dx / dist) * step
                new_y = self.y + (dy / dist) * step
                self.set_position(new_x, new_y)

