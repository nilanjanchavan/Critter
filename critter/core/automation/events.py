"""Automation event definitions for Critter.

All automation events inherit from core Event and pass through the EventBus.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from critter.core.events import Event


@dataclass(kw_only=True)
class AutomationTriggered(Event):
    """Fired when an automation rule trigger condition is met."""
    rule_id: str
    rule_name: str
    trigger_type: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class AutomationExecuted(Event):
    """Fired after an automation rule executes all its actions."""
    rule_id: str
    rule_name: str
    actions_executed: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass(kw_only=True)
class AutomationFailed(Event):
    """Fired when an automation rule evaluation or execution fails."""
    rule_id: str
    rule_name: str
    error: str


@dataclass(kw_only=True)
class NotificationRequested(Event):
    """Request a desktop notification."""
    title: str
    message: str
    urgency: str = "normal"  # low, normal, critical
    icon: Optional[str] = None


@dataclass(kw_only=True)
class PetAnimationRequested(Event):
    """Request a pet to play a specific animation (e.g., celebration, alert, sleep)."""
    animation: str
    instance_id: Optional[str] = None  # None applies to all active pets
    duration_seconds: Optional[float] = None  # None plays loop until next state transition


@dataclass(kw_only=True)
class ExternalWebEvent(Event):
    """Event received from browser or web integrations."""
    url: str
    title: str = ""
    domain: str = ""
    action: str = "visit"  # visit, active_tab, closed
    tab_id: Optional[int] = None
    incognito: bool = False
    session_id: Optional[str] = None


@dataclass(kw_only=True)
class TabCloseRequested(Event):
    """Event requesting a specific browser tab to be closed via the bridge."""
    session_id: str
    tab_id: int
    expected_domain: str
    rule_id: str = ""
    reason: str = ""
    allow_incognito: bool = False

