"""Declarative schemas and models for automation rules."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class TriggerType(str, Enum):
    INTERVAL = "interval"
    EVENT = "event"
    CRON = "cron"
    MANUAL = "manual"


class ConditionType(str, Enum):
    TIME_RANGE = "time_range"
    URL_MATCH = "url_match"
    PET_STATE = "pet_state"
    CUSTOM = "custom"


class ActionType(str, Enum):
    NOTIFICATION = "notification"
    PET_ANIMATION = "pet_animation"
    COMMAND = "command"
    SOUND_BELL = "sound_bell"
    CLOSE_TAB = "close_tab"


class AutomationSource(str, Enum):
    BUILTIN = "builtin"
    COMMUNITY = "community"
    USER_LOCAL = "user_local"


@dataclass(kw_only=True)
class TriggerDef:
    """Trigger configuration for a rule."""
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ConditionDef:
    """Pre-condition that must evaluate to True before actions execute."""
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ActionDef:
    """Action to execute when trigger and conditions succeed."""
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class AutomationRule:
    """An end-to-end declarative automation rule."""
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    trigger: TriggerDef
    conditions: List[ConditionDef] = field(default_factory=list)
    actions: List[ActionDef] = field(default_factory=list)
    cooldown_seconds: float = 0.0
    source: AutomationSource = AutomationSource.COMMUNITY
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_in_cooldown(self, current_time: datetime) -> bool:
        """Check whether the rule is currently in cooldown."""
        if self.cooldown_seconds <= 0 or self.last_triggered_at is None:
            return False
        elapsed = (current_time - self.last_triggered_at).total_seconds()
        return elapsed < self.cooldown_seconds

