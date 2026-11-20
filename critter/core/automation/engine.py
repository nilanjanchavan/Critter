"""Central event-driven automation engine for Critter.

Pure Python, decoupled from UI/GTK, fully testable.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
from critter.core.events import Event, EventBus
from critter.core.automation.events import (
    AutomationExecuted,
    AutomationFailed,
    AutomationTriggered,
)
from critter.core.automation.models import AutomationRule, TriggerType
from critter.core.automation.triggers import (
    BaseTrigger,
    IntervalTrigger,
    create_trigger,
)
from critter.core.automation.conditions import BaseCondition, create_condition
from critter.core.automation.actions import BaseAction, create_action

logger = logging.getLogger(__name__)


class _CompiledRule:
    """Internal compiled runtime representation of an AutomationRule."""

    def __init__(self, rule: AutomationRule) -> None:
        self.rule = rule
        self.trigger: BaseTrigger = create_trigger(rule.trigger)
        self.conditions: List[BaseCondition] = [
            create_condition(c) for c in rule.conditions
        ]
        self.actions: List[BaseAction] = [
            create_action(a) for a in rule.actions
        ]


class AutomationEngine:
    """Evaluates rules against incoming events and periodic timer ticks."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus
        self._rules: Dict[str, _CompiledRule] = {}
        self._unsubscribe_bus: Optional[Callable[[], None]] = None

        if self.event_bus:
            # Subscribe to all events to check against event-based triggers
            self._unsubscribe_bus = self.event_bus.subscribe_all(self._on_event)

    def register_rule(self, rule: AutomationRule) -> None:
        """Register a new automation rule, compiling its triggers, conditions, and actions."""
        if rule.id in self._rules:
            logger.warning("Overwriting existing automation rule '%s'", rule.id)
        compiled = _CompiledRule(rule)
        self._rules[rule.id] = compiled
        logger.info("Registered automation rule '%s' (%s)", rule.name, rule.id)

    def unregister_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info("Unregistered automation rule '%s'", rule_id)
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        """Retrieve an AutomationRule definition."""
        compiled = self._rules.get(rule_id)
        return compiled.rule if compiled else None

    def list_rules(self) -> List[AutomationRule]:
        """Return all registered rules."""
        return [c.rule for c in self._rules.values()]

    def set_rule_enabled(self, rule_id: str, enabled: bool) -> bool:
        """Enable or disable a rule by ID."""
        compiled = self._rules.get(rule_id)
        if compiled:
            compiled.rule.enabled = enabled
            return True
        return False

    def tick(
        self,
        delta_time: float,
        current_time: Optional[datetime] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Advance time by delta_time and evaluate interval triggers.

        Returns a list of rule IDs that executed during this tick.
        """
        now = current_time or datetime.now(timezone.utc)
        executed_rules: List[str] = []

        for rule_id, compiled in list(self._rules.items()):
            rule = compiled.rule
            if not rule.enabled:
                continue

            # Only tick-based triggers
            if not isinstance(compiled.trigger, IntervalTrigger):
                continue

            ctx = compiled.trigger.check_tick(delta_time, now)
            if ctx is not None:
                # Merge contexts
                full_ctx = {
                    "current_datetime": now,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    **(extra_context or {}),
                    **ctx,
                }
                if self._evaluate_and_execute(compiled, full_ctx, now):
                    executed_rules.append(rule.id)

        return executed_rules

    def trigger_manual(
        self,
        rule_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Manually trigger a registered rule by ID."""
        compiled = self._rules.get(rule_id)
        if not compiled or not compiled.rule.enabled:
            return False

        now = datetime.now(timezone.utc)
        full_ctx = {
            "current_datetime": now,
            "rule_id": compiled.rule.id,
            "rule_name": compiled.rule.name,
            "manual": True,
            **(context or {}),
        }
        return self._evaluate_and_execute(compiled, full_ctx, now)

    def _on_event(self, event: Event) -> None:
        """Handler for all EventBus publications."""
        # Avoid recursion on automation events
        if isinstance(event, (AutomationTriggered, AutomationExecuted, AutomationFailed)):
            return

        now = datetime.now(timezone.utc)
        for rule_id, compiled in list(self._rules.items()):
            rule = compiled.rule
            if not rule.enabled:
                continue

            ctx = compiled.trigger.check_event(event)
            if ctx is not None:
                full_ctx = {
                    "current_datetime": now,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    **ctx,
                }
                self._evaluate_and_execute(compiled, full_ctx, now)

    def _evaluate_and_execute(
        self,
        compiled: _CompiledRule,
        context: Dict[str, Any],
        now: datetime,
    ) -> bool:
        """Check cooldown, evaluate conditions, and execute all actions."""
        rule = compiled.rule

        # Check cooldown
        if rule.is_in_cooldown(now):
            logger.debug("Rule '%s' suppressed by cooldown (%.1fs)", rule.id, rule.cooldown_seconds)
            return False

        # Publish triggered event
        if self.event_bus:
            self.event_bus.publish(
                AutomationTriggered(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    trigger_type=rule.trigger.type,
                    context=context,
                )
            )

        # Evaluate conditions
        for cond in compiled.conditions:
            try:
                passed = cond.evaluate(context)
                if not passed:
                    logger.debug("Rule '%s' condition %s did not pass", rule.id, cond.__class__.__name__)
                    return False
            except Exception as exc:
                logger.exception("Error evaluating condition %r in rule '%s': %s", cond, rule.id, exc)
                if self.event_bus:
                    self.event_bus.publish(
                        AutomationFailed(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            error=f"Condition {cond.__class__.__name__} failed: {exc}",
                        )
                    )
                return False

        # Execute actions
        actions_run: List[str] = []
        for action in compiled.actions:
            try:
                success = action.execute(context, self.event_bus)
                actions_run.append(action.__class__.__name__)
                if not success:
                    logger.warning("Action %s returned False in rule '%s'", action.__class__.__name__, rule.id)
            except Exception as exc:
                logger.exception("Action %r failed in rule '%s': %s", action, rule.id, exc)
                if self.event_bus:
                    self.event_bus.publish(
                        AutomationFailed(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            error=f"Action {action.__class__.__name__} failed: {exc}",
                        )
                    )
                return False

        # Update stats
        rule.last_triggered_at = now
        rule.trigger_count += 1

        if self.event_bus:
            self.event_bus.publish(
                AutomationExecuted(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    actions_executed=actions_run,
                    success=True,
                )
            )

        logger.info("Successfully executed automation rule '%s' (%d actions)", rule.name, len(actions_run))
        return True

    def dispose(self) -> None:
        """Clean up event bus subscriptions."""
        if self._unsubscribe_bus:
            self._unsubscribe_bus()
            self._unsubscribe_bus = None
        self._rules.clear()

