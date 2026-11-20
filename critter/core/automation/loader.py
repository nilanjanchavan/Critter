"""Automation rule loader supporting JSON rule definitions."""

import json
import logging
import os
from typing import Any, Dict, List
from critter.core.automation.models import (
    ActionDef,
    AutomationRule,
    ConditionDef,
    TriggerDef,
)

logger = logging.getLogger(__name__)


def parse_rule_from_dict(data: Dict[str, Any]) -> AutomationRule:
    """Parse an AutomationRule from a raw dictionary."""
    if "id" not in data or "name" not in data or "trigger" not in data:
        raise ValueError("Automation rule requires 'id', 'name', and 'trigger'")

    trigger_data = data["trigger"]
    trigger = TriggerDef(
        type=trigger_data["type"],
        params=trigger_data.get("params", {}),
    )

    conditions = [
        ConditionDef(
            type=c["type"],
            params=c.get("params", {}),
        )
        for c in data.get("conditions", [])
    ]

    actions = [
        ActionDef(
            type=a["type"],
            params=a.get("params", {}),
        )
        for a in data.get("actions", [])
    ]

    return AutomationRule(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        enabled=data.get("enabled", True),
        trigger=trigger,
        conditions=conditions,
        actions=actions,
        cooldown_seconds=float(data.get("cooldown_seconds", 0.0)),
        metadata=data.get("metadata", {}),
    )


def load_rules_from_file(file_path: str) -> List[AutomationRule]:
    """Load one or multiple automation rules from a JSON file."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Automation rules file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [parse_rule_from_dict(item) for item in data]
    elif isinstance(data, dict):
        # Could be single rule or dict with "rules" key
        if "rules" in data and isinstance(data["rules"], list):
            return [parse_rule_from_dict(item) for item in data["rules"]]
        else:
            return [parse_rule_from_dict(data)]
    else:
        raise ValueError(f"Invalid JSON format in {file_path}")


def load_rules_from_dir(directory: str) -> List[AutomationRule]:
    """Scan a directory for .json automation rule files."""
    if not os.path.isdir(directory):
        return []

    rules: List[AutomationRule] = []
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".json"):
            full_path = os.path.join(directory, fname)
            try:
                loaded = load_rules_from_file(full_path)
                rules.extend(loaded)
                logger.info("Loaded %d automation rule(s) from %s", len(loaded), fname)
            except Exception as exc:
                logger.error("Failed loading automation rules from %s: %s", full_path, exc)
    return rules
