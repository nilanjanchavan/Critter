"""Automation engine package for Critter."""

from critter.core.automation.models import (
    ActionDef,
    ActionType,
    AutomationRule,
    ConditionDef,
    ConditionType,
    TriggerDef,
    TriggerType,
)
from critter.core.automation.events import (
    AutomationExecuted,
    AutomationFailed,
    AutomationTriggered,
    ExternalWebEvent,
    NotificationRequested,
    PetAnimationRequested,
)
from critter.core.automation.engine import AutomationEngine
from critter.core.automation.loader import (
    load_rules_from_dir,
    load_rules_from_file,
    parse_rule_from_dict,
)

__all__ = [
    "ActionDef",
    "ActionType",
    "AutomationEngine",
    "AutomationExecuted",
    "AutomationFailed",
    "AutomationRule",
    "AutomationTriggered",
    "ConditionDef",
    "ConditionType",
    "ExternalWebEvent",
    "NotificationRequested",
    "PetAnimationRequested",
    "TriggerDef",
    "TriggerType",
    "load_rules_from_dir",
    "load_rules_from_file",
    "parse_rule_from_dict",
]

