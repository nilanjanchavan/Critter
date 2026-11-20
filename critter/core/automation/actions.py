"""Action executors for automation rules."""

from abc import ABC, abstractmethod
import logging
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional
from critter.core.events import EventBus
from critter.core.automation.events import NotificationRequested, PetAnimationRequested
from critter.core.automation.models import ActionDef, ActionType

logger = logging.getLogger(__name__)


class BaseAction(ABC):
    """Abstract action executor."""

    def __init__(self, definition: ActionDef) -> None:
        self.definition = definition

    @abstractmethod
    def execute(self, context: Dict[str, Any], event_bus: Optional[EventBus] = None) -> bool:
        """Execute the action. Returns True on success, False on failure."""
        pass


class NotificationAction(BaseAction):
    """Shows a desktop notification and/or publishes NotificationRequested."""

    def __init__(self, definition: ActionDef) -> None:
        super().__init__(definition)
        self.title_template: str = self.definition.params.get("title", "Critter Reminder")
        self.message_template: str = self.definition.params.get("message", "")
        self.urgency: str = self.definition.params.get("urgency", "normal")
        self.icon: Optional[str] = self.definition.params.get("icon")

    def execute(self, context: Dict[str, Any], event_bus: Optional[EventBus] = None) -> bool:
        try:
            # Interpolate context fields safely
            title = self.title_template.format(**context) if "{" in self.title_template else self.title_template
            message = self.message_template.format(**context) if "{" in self.message_template else self.message_template
        except Exception:
            title = self.title_template
            message = self.message_template

        # 1. Publish internal event on EventBus
        if event_bus:
            event_bus.publish(
                NotificationRequested(
                    title=title,
                    message=message,
                    urgency=self.urgency,
                    icon=self.icon,
                )
            )

        # 2. Trigger native Linux notification via notify-send if installed
        notify_send = shutil.which("notify-send")
        if notify_send:
            try:
                cmd = [notify_send, "-u", self.urgency, "-a", "Critter", title, message]
                if self.icon:
                    cmd.extend(["-i", self.icon])
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.warning("notify-send execution failed: %s", e)

        return True


class PetAnimationAction(BaseAction):
    """Triggers an animation on one or all pets (e.g. celebrate, alert, sleep)."""

    def __init__(self, definition: ActionDef) -> None:
        super().__init__(definition)
        self.animation: str = self.definition.params.get("animation", "idle")
        self.instance_id: Optional[str] = self.definition.params.get("instance_id")
        self.duration_seconds: Optional[float] = (
            float(self.definition.params["duration_seconds"])
            if "duration_seconds" in self.definition.params
            else None
        )

    def execute(self, context: Dict[str, Any], event_bus: Optional[EventBus] = None) -> bool:
        instance_id = self.instance_id or context.get("instance_id")
        if event_bus:
            event_bus.publish(
                PetAnimationRequested(
                    animation=self.animation,
                    instance_id=instance_id,
                    duration_seconds=self.duration_seconds,
                )
            )
            return True
        return False


class SoundBellAction(BaseAction):
    """Emits an audible notification / terminal bell."""

    def execute(self, context: Dict[str, Any], event_bus: Optional[EventBus] = None) -> bool:
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
            return True
        except Exception as exc:
            logger.warning("SoundBellAction failed: %s", exc)
            return False


class CommandAction(BaseAction):
    """Executes a non-blocking shell command."""

    def __init__(self, definition: ActionDef) -> None:
        super().__init__(definition)
        self.command_template: str = self.definition.params.get("command", "")

    def execute(self, context: Dict[str, Any], event_bus: Optional[EventBus] = None) -> bool:
        if not self.command_template:
            return False

        try:
            cmd = self.command_template.format(**context)
        except Exception:
            cmd = self.command_template

        try:
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as exc:
            logger.error("CommandAction failed for command '%s': %s", cmd, exc)
            return False


def create_action(definition: ActionDef) -> BaseAction:
    """Factory creating BaseAction instances."""
    act_type = definition.type.lower()
    if act_type == ActionType.NOTIFICATION.value:
        return NotificationAction(definition)
    elif act_type == ActionType.PET_ANIMATION.value:
        return PetAnimationAction(definition)
    elif act_type == ActionType.SOUND_BELL.value:
        return SoundBellAction(definition)
    elif act_type == ActionType.COMMAND.value:
        return CommandAction(definition)
    else:
        logger.warning("Unknown action type '%s'", definition.type)
        raise ValueError(f"Unknown action type: {definition.type}")

