"""Condition evaluators for automation rules."""

from abc import ABC, abstractmethod
from datetime import datetime
import fnmatch
import logging
import re
from typing import Any, Dict, List, Optional
from critter.core.automation.models import ConditionDef, ConditionType

logger = logging.getLogger(__name__)


class BaseCondition(ABC):
    """Abstract condition evaluator."""

    def __init__(self, definition: ConditionDef) -> None:
        self.definition = definition

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if condition passes, False otherwise."""
        pass


class TimeRangeCondition(BaseCondition):
    """Checks whether the current time falls within [start_time, end_time].

    Format: 'HH:MM' (24-hour, e.g. '09:00', '17:30').
    Optional 'days_of_week': List of 0-6 (0=Mon, 6=Sun).
    """

    def __init__(self, definition: ConditionDef) -> None:
        super().__init__(definition)
        self.start_time: str = self.definition.params.get("start_time", "00:00")
        self.end_time: str = self.definition.params.get("end_time", "23:59")
        self.days_of_week: Optional[List[int]] = self.definition.params.get("days_of_week", None)

    def evaluate(self, context: Dict[str, Any]) -> bool:
        now_val = context.get("current_datetime")
        if isinstance(now_val, datetime):
            now = now_val
        else:
            now = datetime.now()

        # Day of week check
        if self.days_of_week is not None and now.weekday() not in self.days_of_week:
            return False

        # Parse start & end
        sh, sm = [int(x) for x in self.start_time.split(":")]
        eh, em = [int(x) for x in self.end_time.split(":")]

        now_minutes = now.hour * 60 + now.minute
        start_minutes = sh * 60 + sm
        end_minutes = eh * 60 + em

        if start_minutes <= end_minutes:
            return start_minutes <= now_minutes <= end_minutes
        else:
            # Range crosses midnight (e.g. 22:00 to 06:00)
            return now_minutes >= start_minutes or now_minutes <= end_minutes


class URLMatchCondition(BaseCondition):
    """Checks whether the context URL or domain matches specified patterns.

    Params:
      patterns: List of string patterns (e.g. ['*instagram.com*', '*reddit.com*'])
      field_name: Context key to match against (default: 'url', fallback: 'domain')
    """

    def __init__(self, definition: ConditionDef) -> None:
        super().__init__(definition)
        patterns_arg = self.definition.params.get("patterns", [])
        if isinstance(patterns_arg, str):
            patterns_arg = [patterns_arg]
        self.patterns: List[str] = patterns_arg
        self.field_name: str = self.definition.params.get("field_name", "url")

    def evaluate(self, context: Dict[str, Any]) -> bool:
        target_str = str(context.get(self.field_name, "") or context.get("domain", "") or context.get("url", ""))
        if not target_str:
            return False

        for pattern in self.patterns:
            if fnmatch.fnmatch(target_str.lower(), pattern.lower()):
                return True
            if pattern.lower() in target_str.lower():
                return True
        return False


class PetStateCondition(BaseCondition):
    """Checks whether a pet's current state matches target_state.

    Params:
      target_state: 'IDLE', 'WALKING', 'SLEEPING', 'DRAGGING'
      instance_id: Optional specific pet instance ID.
    """

    def __init__(self, definition: ConditionDef) -> None:
        super().__init__(definition)
        self.target_state: str = str(self.definition.params.get("target_state", "")).upper()
        self.instance_id: Optional[str] = self.definition.params.get("instance_id")

    def evaluate(self, context: Dict[str, Any]) -> bool:
        # Context may contain pet_state or active pets map
        current_state = context.get("state") or context.get("pet_state")
        if current_state:
            return str(current_state).upper() == self.target_state

        pets = context.get("pets", {})
        if self.instance_id and self.instance_id in pets:
            return str(pets[self.instance_id].controller.state.name).upper() == self.target_state

        # If any pet matches
        for p in pets.values():
            if str(p.controller.state.name).upper() == self.target_state:
                return True

        return False


def create_condition(definition: ConditionDef) -> BaseCondition:
    """Factory creating BaseCondition instances."""
    cond_type = definition.type.lower()
    if cond_type == ConditionType.TIME_RANGE.value:
        return TimeRangeCondition(definition)
    elif cond_type == ConditionType.URL_MATCH.value:
        return URLMatchCondition(definition)
    elif cond_type == ConditionType.PET_STATE.value:
        return PetStateCondition(definition)
    else:
        logger.warning("Unknown condition type '%s'", definition.type)
        raise ValueError(f"Unknown condition type: {definition.type}")
