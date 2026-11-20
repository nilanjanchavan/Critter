"""End-to-end integration tests for browser extension navigation events and automated tab closing."""

import asyncio
import json
import os
import tempfile
from typing import AsyncGenerator
import pytest
import websockets.asyncio.client as ws_client

from critter.core.events import EventBus
from critter.core.automation.engine import AutomationEngine
from critter.core.automation.models import (
    ActionDef,
    AutomationRule,
    ConditionDef,
    TriggerDef,
)
from critter.core.automation.events import (
    AutomationExecuted,
    ExternalWebEvent,
    TabCloseRequested,
)
from critter.core.communication.auth import BridgeAuthManager
from critter.core.communication.bridge_server import BridgeServer


@pytest.fixture
def test_auth_mgr() -> BridgeAuthManager:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        auth_file = f.name
    mgr = BridgeAuthManager(auth_file=auth_file)
    yield mgr
    if os.path.exists(auth_file):
        os.remove(auth_file)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def automation_engine(bus: EventBus) -> AutomationEngine:
    eng = AutomationEngine(event_bus=bus)
    yield eng
    eng.dispose()


@pytest.fixture
async def full_stack_bridge(
    test_auth_mgr: BridgeAuthManager, bus: EventBus
) -> AsyncGenerator[BridgeServer, None]:
    server = BridgeServer(auth_manager=test_auth_mgr, event_bus=bus, host="127.0.0.1", port=0)
    await server.start_async()
    server.port = server._server.sockets[0].getsockname()[1]
    yield server
    await server.stop_async()


@pytest.mark.anyio
async def test_end_to_end_navigation_triggers_close_tab_action(
    full_stack_bridge: BridgeServer,
    automation_engine: AutomationEngine,
    test_auth_mgr: BridgeAuthManager,
    bus: EventBus,
) -> None:
    origin = "chrome-extension://autoclosingextension123"
    test_auth_mgr.add_paired_origin(origin, label="Integration Test Extension")

    # Register an automated focus guard rule that closes distraction tabs
    guard_rule = AutomationRule(
        id="integration_focus_guard",
        name="Focus Guard Auto Close",
        trigger=TriggerDef(
            type="event",
            params={
                "event_name": "ExternalWebEvent",
                "filters": {"action": "visit"},
            },
        ),
        conditions=[
            ConditionDef(
                type="url_match",
                params={"patterns": ["*tiktok.com*", "*instagram.com*"]},
            )
        ],
        actions=[
            ActionDef(
                type="close_tab",
                params={"reason": "Blocked during focus hours"},
            )
        ],
    )
    automation_engine.register_rule(guard_rule)

    executed_rules: list[str] = []
    bus.subscribe(AutomationExecuted, lambda e: executed_rules.append(e.rule_id))

    close_requests: list[TabCloseRequested] = []
    bus.subscribe(TabCloseRequested, lambda e: close_requests.append(e))

    uri = f"ws://127.0.0.1:{full_stack_bridge.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        # 1. Authenticate extension
        await ws.send(
            json.dumps({
                "type": "auth",
                "token": test_auth_mgr.token,
                "client": "critter-companion",
                "version": "1.0.0",
                "browser": "chromium",
            })
        )
        auth_ack = json.loads(await ws.recv())
        assert auth_ack["type"] == "auth_ack"
        session_id = auth_ack["session_id"]

        # 2. Extension navigates to allowed site (github.com) -> should NOT trigger close
        await ws.send(
            json.dumps({
                "type": "tab_navigated",
                "tab_id": 801,
                "url": "https://github.com/nilanjanchavan/Critter",
                "title": "Critter Repo",
                "incognito": False,
            })
        )
        await asyncio.sleep(0.05)
        assert len(executed_rules) == 0
        assert len(close_requests) == 0

        # 3. Extension navigates tab 801 to blocked site (instagram.com)
        await ws.send(
            json.dumps({
                "type": "tab_navigated",
                "tab_id": 801,
                "url": "https://www.instagram.com/reels/",
                "title": "Reels",
                "incognito": False,
            })
        )

        # 4. Automation engine catches ExternalWebEvent and fires CloseTabAction -> TabCloseRequested
        # 5. BridgeServer catches TabCloseRequested and sends close_tab command over WebSocket
        cmd_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
        cmd = json.loads(cmd_raw)

        assert cmd["type"] == "close_tab"
        assert cmd["tab_id"] == 801
        assert cmd["expected_domain"] == "www.instagram.com"
        assert cmd["session_id"] == session_id
        assert "Blocked during focus hours" in cmd["reason"]

        assert len(executed_rules) == 1
        assert executed_rules[0] == "integration_focus_guard"
        assert len(close_requests) == 1
        assert close_requests[0].tab_id == 801

        # 6. Extension responds with successful close acknowledgement
        await ws.send(
            json.dumps({
                "type": "tab_close_ack",
                "tab_id": 801,
                "session_id": session_id,
                "success": True,
            })
        )
        await asyncio.sleep(0.05)


@pytest.mark.anyio
async def test_close_tab_action_suppressed_on_missing_context(bus: EventBus) -> None:
    from critter.core.automation.actions import CloseTabAction

    action = CloseTabAction(ActionDef(type="close_tab"))
    # Context without tab_id or session_id must gracefully return False
    res = action.execute({}, event_bus=bus)
    assert res is False

