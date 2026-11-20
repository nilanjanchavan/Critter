"""Trigger evaluators for automation rules."""

from abc import ABC, abstractmethod
from datetime import datetime
import logging
from typing import Any, Dict, Optional
from critter.core.events import Event
from critter.core.automation.models import TriggerDef, TriggerType

logger = logging.getLogger(__name__)


class BaseTrigger(ABC):
    """Abstract base class for trigger handlers."""

    def __init__(self, definition: TriggerDef) -> None:
        self.definition = definition

    def check_tick(self, delta_time: float, current_time: datetime) -> Optional[Dict[str, Any]]:
        """Evaluate periodic tick. Returns context dict if triggered, None otherwise."""
        return None

    def check_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Evaluate an incoming event. Returns context dict if matched, None otherwise."""
        return None


class IntervalTrigger(BaseTrigger):
    """Trigger that fires periodically every `interval_seconds`."""

    def __init__(self, definition: TriggerDef) -> None:
        super().__init__(definition)
        self.interval_seconds = float(self.definition.params.get("interval_seconds", 60.0))
        self.elapsed: float = 0.0

    def check_tick(self, delta_time: float, current_time: datetime) -> Optional[Dict[str, Any]]:
        self.elapsed += delta_time
        if self.elapsed >= self.interval_seconds:
            self.elapsed = 0.0
            return {
                "triggered_at": current_time.isoformat(),
                "interval_seconds": self.interval_seconds,
            }
        return None

    def reset(self) -> None:
        self.elapsed = 0.0


class EventTrigger(BaseTrigger):
    """Trigger that fires when an event of matching class/name and criteria arrives."""

    def __init__(self, definition: TriggerDef) -> None:
        super().__init__(definition)
        self.event_name: str = self.definition.params.get("event_name", "")
        self.filters: Dict[str, Any] = self.definition.params.get("filters", {})

    def check_event(self, event: Event) -> Optional[Dict[str, Any]]:
        event_cls_name = event.__class__.__name__
        if self.event_name and self.event_name != event_cls_name:
            return None

        # Check attribute filters
        for key, expected_val in self.filters.items():
            val = getattr(event, key, None)
            if val != expected_val:
                return None

        # Return event fields as context
        context = {
            "event_type": event_cls_name,
            "timestamp": event.timestamp.isoformat(),
        }
        for k, v in event.__dict__.items():
            if not k.startswith("_"):
                context[k] = v
        return context


class ManualTrigger(BaseTrigger):
    """Trigger for manually invoked automations."""
    pass


def create_trigger(definition: TriggerDef) -> BaseTrigger:
    """Factory creating the appropriate BaseTrigger instance."""
    trigger_type = definition.type.lower()
    if trigger_type == TriggerType.INTERVAL.value:
        return IntervalTrigger(definition)
    elif trigger_type == TriggerType.EVENT.value:
        return EventTrigger(definition)
    elif trigger_type == TriggerType.MANUAL.value:
        return ManualTrigger(definition)
    else:
        logger.warning("Unknown trigger type '%s'; defaulting to ManualTrigger", definition.type)
        return ManualTrigger(definition)
