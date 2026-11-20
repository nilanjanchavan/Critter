"""Automation rule loader supporting JSON rule definitions and source-based security policies."""

import json
import logging
import os
from typing import Any, Dict, List, Optional
from critter.core.automation.models import (
    ActionDef,
    AutomationRule,
    AutomationSource,
    ConditionDef,
    TriggerDef,
)

logger = logging.getLogger(__name__)


class SecurityPolicyError(Exception):
    """Raised when an automation rule violates security policy (e.g. unauthorized command execution)."""


def parse_rule_from_dict(
    data: Dict[str, Any],
    source: AutomationSource = AutomationSource.COMMUNITY,
    allow_user_shell_actions: bool = False,
) -> AutomationRule:
    """Parse an AutomationRule from a raw dictionary while enforcing source security policies."""
    if "id" not in data or "name" not in data or "trigger" not in data:
        raise ValueError("Automation rule requires 'id', 'name', and 'trigger'")

    rule_id = str(data["id"])
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

    actions = []
    for a in data.get("actions", []):
        act_type = str(a.get("type", "")).lower()

        # Security Policy Enforcement:
        if act_type == "command":
            if source == AutomationSource.COMMUNITY:
                raise SecurityPolicyError(
                    f"Security Policy: Community automation '{rule_id}' is strictly forbidden from executing shell commands ('command' action)."
                )
            elif source == AutomationSource.USER_LOCAL and not allow_user_shell_actions:
                raise SecurityPolicyError(
                    f"Security Policy: User automation '{rule_id}' contains shell command action, but explicit user authorization is disabled. Pass --allow-user-shell-actions to authorize."
                )

        actions.append(
            ActionDef(
                type=act_type,
                params=a.get("params", {}),
            )
        )

    return AutomationRule(
        id=rule_id,
        name=data["name"],
        description=data.get("description", ""),
        enabled=data.get("enabled", True),
        source=source,
        trigger=trigger,
        conditions=conditions,
        actions=actions,
        cooldown_seconds=float(data.get("cooldown_seconds", 0.0)),
        metadata=data.get("metadata", {}),
    )


def detect_source_from_path(path: str) -> AutomationSource:
    """Infer rule trust policy level from directory location."""
    user_config_dir = os.path.expanduser("~/.config/critter/automations")
    abs_path = os.path.abspath(path)
    if abs_path.startswith(os.path.abspath(user_config_dir)):
        return AutomationSource.USER_LOCAL
    return AutomationSource.COMMUNITY


def load_rules_from_file(
    file_path: str,
    source: Optional[AutomationSource] = None,
    allow_user_shell_actions: bool = False,
) -> List[AutomationRule]:
    """Load one or multiple automation rules from a JSON file with security policy checks."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Automation rules file not found: {file_path}")

    effective_source = source if source is not None else detect_source_from_path(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [
            parse_rule_from_dict(
                item,
                source=effective_source,
                allow_user_shell_actions=allow_user_shell_actions,
            )
            for item in data
        ]
    elif isinstance(data, dict):
        if "rules" in data and isinstance(data["rules"], list):
            return [
                parse_rule_from_dict(
                    item,
                    source=effective_source,
                    allow_user_shell_actions=allow_user_shell_actions,
                )
                for item in data["rules"]
            ]
        else:
            return [
                parse_rule_from_dict(
                    data,
                    source=effective_source,
                    allow_user_shell_actions=allow_user_shell_actions,
                )
            ]
    else:
        raise ValueError(f"Invalid JSON format in {file_path}")


def load_rules_from_dir(
    directory: str,
    source: Optional[AutomationSource] = None,
    allow_user_shell_actions: bool = False,
) -> List[AutomationRule]:
    """Scan a directory for .json automation rule files enforcing source trust policies."""
    if not os.path.isdir(directory):
        return []

    effective_source = source if source is not None else detect_source_from_path(directory)
    rules: List[AutomationRule] = []

    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".json"):
            full_path = os.path.join(directory, fname)
            try:
                loaded = load_rules_from_file(
                    full_path,
                    source=effective_source,
                    allow_user_shell_actions=allow_user_shell_actions,
                )
                rules.extend(loaded)
                logger.info("Loaded %d automation rule(s) from %s (source=%s)", len(loaded), fname, effective_source.value)
            except SecurityPolicyError as spe:
                logger.error("Blocked automation rule from %s: %s", full_path, spe)
            except Exception as exc:
                logger.error("Failed loading automation rules from %s: %s", full_path, exc)
    return rules

