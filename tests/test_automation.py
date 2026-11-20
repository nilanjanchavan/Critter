"""Unit tests for the Critter Generic Automation Engine."""

from datetime import datetime, timezone
import pytest
from critter.core.events import Event, EventBus
from critter.core.pet import BehaviorState, PetController, PetManifest
from critter.core.manager import PetManager
from critter.core.registry import PetRegistry
from critter.core.automation.models import (
    ActionDef,
    AutomationRule,
    ConditionDef,
    TriggerDef,
)
from critter.core.automation.events import (
    AutomationExecuted,
    AutomationFailed,
    AutomationTriggered,
    ExternalWebEvent,
    NotificationRequested,
    PetAnimationRequested,
)
from critter.core.automation.conditions import (
    PetStateCondition,
    TimeRangeCondition,
    URLMatchCondition,
)
from critter.core.automation.engine import AutomationEngine
from critter.core.automation.loader import (
    load_rules_from_dir,
    load_rules_from_file,
    parse_rule_from_dict,
)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def engine(bus: EventBus) -> AutomationEngine:
    eng = AutomationEngine(event_bus=bus)
    yield eng
    eng.dispose()


def test_interval_trigger_execution(engine: AutomationEngine, bus: EventBus) -> None:
    events_captured = []
    bus.subscribe(AutomationExecuted, lambda e: events_captured.append(e))

    rule = AutomationRule(
        id="test_interval",
        name="Test Interval",
        trigger=TriggerDef(type="interval", params={"interval_seconds": 10.0}),
        actions=[ActionDef(type="notification", params={"title": "Test", "message": "Fired"})],
    )
    engine.register_rule(rule)

    # Tick 5 seconds: shouldn't trigger
    executed = engine.tick(5.0)
    assert executed == []
    assert len(events_captured) == 0

    # Tick another 6 seconds (total 11s >= 10s): should trigger
    executed = engine.tick(6.0)
    assert executed == ["test_interval"]
    assert len(events_captured) == 1
    assert events_captured[0].rule_id == "test_interval"


def test_cooldown_suppression(engine: AutomationEngine) -> None:
    rule = AutomationRule(
        id="test_cooldown",
        name="Test Cooldown",
        cooldown_seconds=30.0,
        trigger=TriggerDef(type="manual"),
        actions=[ActionDef(type="sound_bell")],
    )
    engine.register_rule(rule)

    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # First manual trigger succeeds
    success1 = engine.trigger_manual("test_cooldown")
    assert success1 is True
    rule_obj = engine.get_rule("test_cooldown")
    assert rule_obj is not None
    assert rule_obj.trigger_count == 1

    # Second trigger immediately afterwards should be suppressed by cooldown
    success2 = engine.trigger_manual("test_cooldown")
    assert success2 is False
    assert rule_obj.trigger_count == 1


def test_time_range_condition() -> None:
    cond = TimeRangeCondition(
        ConditionDef(
            type="time_range",
            params={"start_time": "09:00", "end_time": "17:00", "days_of_week": [0, 1, 2, 3, 4]},
        )
    )

    # Friday 14:30 (weekday 4) -> should pass
    t_inside = datetime(2026, 11, 20, 14, 30, 0)
    assert cond.evaluate({"current_datetime": t_inside}) is True

    # Friday 19:30 -> should fail
    t_late = datetime(2026, 11, 20, 19, 30, 0)
    assert cond.evaluate({"current_datetime": t_late}) is False

    # Saturday 12:00 (weekday 5) -> should fail (not in Mon-Fri)
    t_weekend = datetime(2026, 11, 21, 12, 0, 0)
    assert cond.evaluate({"current_datetime": t_weekend}) is False


def test_url_match_condition() -> None:
    cond = URLMatchCondition(
        ConditionDef(
            type="url_match",
            params={"patterns": ["*instagram.com*", "*twitter.com*"]},
        )
    )

    assert cond.evaluate({"url": "https://www.instagram.com/p/123"}) is True
    assert cond.evaluate({"domain": "instagram.com"}) is True
    assert cond.evaluate({"url": "https://github.com/nilanjanchavan/Critter"}) is False


def test_event_trigger_and_action_dispatch(engine: AutomationEngine, bus: EventBus) -> None:
    notifications: list[NotificationRequested] = []
    anim_requests: list[PetAnimationRequested] = []

    bus.subscribe(NotificationRequested, lambda e: notifications.append(e))
    bus.subscribe(PetAnimationRequested, lambda e: anim_requests.append(e))

    rule = AutomationRule(
        id="web_guard",
        name="Web Guard",
        trigger=TriggerDef(
            type="event",
            params={
                "event_name": "ExternalWebEvent",
                "filters": {"action": "visit"},
            },
        ),
        conditions=[
            ConditionDef(type="url_match", params={"patterns": ["*youtube.com*"]})
        ],
        actions=[
            ActionDef(
                type="notification",
                params={"title": "Alert", "message": "Visiting {domain}"},
            ),
            ActionDef(
                type="pet_animation",
                params={"animation": "idle", "duration_seconds": 3.0},
            ),
        ],
    )
    engine.register_rule(rule)

    # Publish unrelated event
    bus.publish(ExternalWebEvent(url="https://google.com", domain="google.com", action="visit"))
    assert len(notifications) == 0

    # Publish matching event
    bus.publish(ExternalWebEvent(url="https://www.youtube.com/watch", domain="youtube.com", action="visit"))
    assert len(notifications) == 1
    assert notifications[0].message == "Visiting youtube.com"
    assert len(anim_requests) == 1
    assert anim_requests[0].animation == "idle"
    assert anim_requests[0].duration_seconds == 3.0


def test_pet_manager_animation_reaction(bus: EventBus) -> None:
    registry = PetRegistry()
    registry.discover()
    manager = PetManager(registry=registry, event_bus=bus)

    corgi = manager.spawn("dog")
    assert corgi.controller.current_animation == "idle"

    # Broadcast animation request
    bus.publish(PetAnimationRequested(animation="walk_left", duration_seconds=4.0))
    assert corgi.controller.current_animation == "walk_left"
    assert corgi.controller.state_time_remaining == 4.0


def test_rule_enable_disable(engine: AutomationEngine) -> None:
    rule = AutomationRule(
        id="toggleable",
        name="Toggleable",
        enabled=True,
        trigger=TriggerDef(type="manual"),
        actions=[ActionDef(type="sound_bell")],
    )
    engine.register_rule(rule)

    assert engine.trigger_manual("toggleable") is True

    # Disable
    engine.set_rule_enabled("toggleable", False)
    assert engine.trigger_manual("toggleable") is False


def test_load_automations_from_packages() -> None:
    rules = load_rules_from_dir("packages/automations")
    assert len(rules) >= 3

    rule_ids = {r.id for r in rules}
    assert "pomodoro_timer" in rule_ids
    assert "hydration_reminder" in rule_ids
    assert "distraction_guard" in rule_ids

    pomodoro = next(r for r in rules if r.id == "pomodoro_timer")
    assert pomodoro.trigger.type == "interval"
    assert len(pomodoro.actions) == 2

