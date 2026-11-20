"""Tests for community automation security policies and source separation."""

import json
import os
import tempfile
import pytest

from critter.core.automation.models import AutomationSource
from critter.core.automation.loader import (
    SecurityPolicyError,
    load_rules_from_file,
    parse_rule_from_dict,
)


def test_community_automation_rejects_command_action() -> None:
    malicious_community_rule = {
        "id": "community_rule_with_command",
        "name": "Community Package With Shell",
        "trigger": {"type": "manual"},
        "actions": [
            {
                "type": "command",
                "params": {"command": "rm -rf /tmp/danger"},
            }
        ],
    }

    # Must raise SecurityPolicyError when parsed as COMMUNITY source
    with pytest.raises(SecurityPolicyError, match="strictly forbidden from executing shell commands"):
        parse_rule_from_dict(
            malicious_community_rule,
            source=AutomationSource.COMMUNITY,
            allow_user_shell_actions=True,  # Even if user shell flag is on, community must fail!
        )


def test_user_local_automation_requires_explicit_authorization() -> None:
    user_rule = {
        "id": "my_local_backup_script",
        "name": "User Local Script",
        "trigger": {"type": "manual"},
        "actions": [
            {
                "type": "command",
                "params": {"command": "echo 'backup'"},
            }
        ],
    }

    # 1. Without authorization: must fail
    with pytest.raises(SecurityPolicyError, match="explicit user authorization is disabled"):
        parse_rule_from_dict(
            user_rule,
            source=AutomationSource.USER_LOCAL,
            allow_user_shell_actions=False,
        )

    # 2. With explicit authorization: succeeds
    rule = parse_rule_from_dict(
        user_rule,
        source=AutomationSource.USER_LOCAL,
        allow_user_shell_actions=True,
    )
    assert rule.id == "my_local_backup_script"
    assert rule.source == AutomationSource.USER_LOCAL
    assert len(rule.actions) == 1
    assert rule.actions[0].type == "command"


def test_community_package_file_rejection() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "id": "suspicious_download",
                "name": "Suspicious Download",
                "trigger": {"type": "manual"},
                "actions": [{"type": "command", "params": {"command": "whoami"}}],
            },
            f,
        )
        temp_path = f.name

    try:
        # File outside ~/.config/critter/automations is treated as COMMUNITY
        with pytest.raises(SecurityPolicyError):
            load_rules_from_file(temp_path, allow_user_shell_actions=True)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
