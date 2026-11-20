"""Pet Lifecycle Manager.

Manages active pet instances on the desktop. Completely decoupled from GTK.
Supports spawning multiple instances of the same or different packages,
individual/global pause/resume, and visibility toggles.
"""

import logging
import uuid
from typing import Dict, List, Optional
from critter.core.events import Event, EventBus
from critter.core.pet import PetController, PetInstance, PetManifest
from critter.core.registry import PetRegistry

logger = logging.getLogger(__name__)


class PetNotFoundError(Exception):
    """Raised when an operation references a non-existent pet package or instance."""


class PetManager:
    """Orchestrates active pet instances."""

    def __init__(self, registry: Optional[PetRegistry] = None, event_bus: Optional[EventBus] = None) -> None:
        self.registry = registry or PetRegistry()
        self.event_bus = event_bus or EventBus()
        self._instances: Dict[str, PetInstance] = {}

    def spawn(
        self,
        package_id: str,
        custom_name: Optional[str] = None,
        initial_x: Optional[float] = None,
        initial_y: Optional[float] = None,
    ) -> PetInstance:
        """Spawn a new desktop pet instance from a registered package."""
        manifest = self.registry.get(package_id)
        if not manifest:
            # Try to discover if not yet loaded
            self.registry.discover()
            manifest = self.registry.get(package_id)
            if not manifest:
                raise PetNotFoundError(f"Pet package '{package_id}' not found in registry.")

        # Generate unique instance ID: e.g. 'dog_1', 'dog_2'
        existing_with_id = [inst_id for inst_id in self._instances if inst_id.startswith(f"{package_id}_")]
        seq_num = len(existing_with_id) + 1
        instance_id = f"{package_id}_{seq_num}"

        name = custom_name or f"{manifest.name} #{seq_num}"

        # Default staggered position so multiple pets don't overlap on spawn
        total_instances = len(self._instances)
        x = initial_x if initial_x is not None else 150.0 + total_instances * 180.0
        y = initial_y if initial_y is not None else 250.0 + total_instances * 60.0

        controller = PetController(
            manifest=manifest,
            instance_id=instance_id,
            custom_name=name,
            initial_x=x,
            initial_y=y,
            event_bus=self.event_bus,
        )

        instance = PetInstance(
            instance_id=instance_id,
            manifest=manifest,
            controller=controller,
            custom_name=name,
            is_visible=True,
        )

        self._instances[instance_id] = instance
        logger.info("Spawned pet instance '%s' (%s) at (%.1f, %.1f)", instance_id, name, x, y)
        return instance

    def remove(self, instance_id: str) -> bool:
        """Remove an active pet instance."""
        if instance_id in self._instances:
            inst = self._instances.pop(instance_id)
            logger.info("Removed pet instance '%s' (%s)", instance_id, inst.custom_name)
            return True
        return False

    def get_instance(self, instance_id: str) -> Optional[PetInstance]:
        return self._instances.get(instance_id)

    def list_instances(self) -> List[PetInstance]:
        return list(self._instances.values())

    def pause_instance(self, instance_id: str) -> None:
        inst = self.get_instance(instance_id)
        if inst:
            inst.controller.pause()

    def resume_instance(self, instance_id: str) -> None:
        inst = self.get_instance(instance_id)
        if inst:
            inst.controller.resume()

    def pause_all(self) -> None:
        """Pause all active pets."""
        for inst in self._instances.values():
            inst.controller.pause()

    def resume_all(self) -> None:
        """Resume all active pets."""
        for inst in self._instances.values():
            inst.controller.resume()

    def hide_instance(self, instance_id: str) -> None:
        inst = self.get_instance(instance_id)
        if inst:
            inst.is_visible = False

    def show_instance(self, instance_id: str) -> None:
        inst = self.get_instance(instance_id)
        if inst:
            inst.is_visible = True

    def hide_all(self) -> None:
        for inst in self._instances.values():
            inst.is_visible = False

    def show_all(self) -> None:
        for inst in self._instances.values():
            inst.is_visible = True
