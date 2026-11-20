"""Unit and integration tests for the Critter WebSocket bridge server."""

import asyncio
from datetime import datetime, timezone
import json
import os
import tempfile
from typing import AsyncGenerator
import pytest
import websockets.asyncio.client as ws_client
from websockets.exceptions import InvalidStatus

from critter.core.events import EventBus
from critter.core.automation.events import ExternalWebEvent
from critter.core.communication.auth import BridgeAuthManager
from critter.core.communication.bridge_server import BridgeServer
from critter.core.communication.security import (
    RateLimiter,
    SecurityValidationError,
    validate_and_normalize_url,
)
from critter.core.communication.protocol import parse_inbound_message


@pytest.fixture
def auth_mgr() -> BridgeAuthManager:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    mgr = BridgeAuthManager(auth_file=path)
    yield mgr
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
async def bridge_server(auth_mgr: BridgeAuthManager, bus: EventBus) -> AsyncGenerator[BridgeServer, None]:
    # Use ephemeral port to avoid collisions
    server = BridgeServer(auth_manager=auth_mgr, event_bus=bus, host="127.0.0.1", port=0)
    await server.start_async()
    # Get actual assigned port
    assigned_port = server._server.sockets[0].getsockname()[1]
    server.port = assigned_port
    yield server
    await server.stop_async()


def test_url_validation_and_domain_derivation() -> None:
    # 1. Valid URLs
    norm_url, domain = validate_and_normalize_url("https://www.INSTAGRAM.com/explore/?ref=123")
    assert domain == "www.instagram.com"
    assert norm_url.startswith("https://www.instagram.com/explore/")

    _, domain_simple = validate_and_normalize_url("http://localhost:8080/app")
    assert domain_simple == "localhost"

    # 2. Rejection of unsafe or malformed schemes
    with pytest.raises(SecurityValidationError, match="Unsupported URL scheme 'javascript'"):
        validate_and_normalize_url("javascript:alert(1)")

    with pytest.raises(SecurityValidationError, match="Unsupported URL scheme 'file'"):
        validate_and_normalize_url("file:///etc/passwd")

    with pytest.raises(SecurityValidationError, match="Unsupported URL scheme 'chrome'"):
        validate_and_normalize_url("chrome://settings")

    with pytest.raises(SecurityValidationError, match="URL contains no valid host"):
        validate_and_normalize_url("https://")


def test_rate_limiter() -> None:
    limiter = RateLimiter(max_requests=5, window_seconds=1.0)
    for _ in range(5):
        assert limiter.allow_request() is True
    # 6th should exceed limit
    assert limiter.allow_request() is False


@pytest.mark.anyio
async def test_unauthorized_origin_rejected(bridge_server: BridgeServer) -> None:
    uri = f"ws://127.0.0.1:{bridge_server.port}"

    # Connect with an origin not in paired allowlist
    with pytest.raises(InvalidStatus) as exc_info:
        async with ws_client.connect(
            uri,
            additional_headers={"Origin": "chrome-extension://unpaired-extension-id"},
        ):
            pass
    assert exc_info.value.response.status_code == 403


@pytest.mark.anyio
async def test_successful_auth_with_paired_origin(bridge_server: BridgeServer, auth_mgr: BridgeAuthManager) -> None:
    origin = "chrome-extension://paired-extension-12345"
    auth_mgr.add_paired_origin(origin, label="Test Chrome Extension")

    uri = f"ws://127.0.0.1:{bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        # Send valid auth
        await ws.send(
            json.dumps({
                "type": "auth",
                "token": auth_mgr.token,
                "client": "test-ext",
                "version": "1.0.0",
                "browser": "chromium",
            })
        )
        response = await ws.recv()
        data = json.loads(response)
        assert data.get("type") == "auth_ack"
        assert data.get("session_id") is not None
        assert bridge_server.active_session_count == 1


@pytest.mark.anyio
async def test_auth_failure_invalid_token(bridge_server: BridgeServer, auth_mgr: BridgeAuthManager) -> None:
    origin = "chrome-extension://paired-extension-12345"
    auth_mgr.add_paired_origin(origin, label="Test Chrome Extension")

    uri = f"ws://127.0.0.1:{bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        await ws.send(
            json.dumps({
                "type": "auth",
                "token": "wrong-secret-token",
                "client": "test-ext",
            })
        )
        response = await ws.recv()
        data = json.loads(response)
        assert data.get("type") == "auth_err"
        assert data.get("reason") == "invalid_token"


@pytest.mark.anyio
async def test_tab_navigation_and_eventbus_dispatch(
    bridge_server: BridgeServer, auth_mgr: BridgeAuthManager, bus: EventBus
) -> None:
    origin = "chrome-extension://paired-extension-12345"
    auth_mgr.add_paired_origin(origin, label="Test Chrome Extension")

    captured_events: list[ExternalWebEvent] = []
    bus.subscribe(ExternalWebEvent, lambda e: captured_events.append(e))

    uri = f"ws://127.0.0.1:{bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        # 1. Authenticate
        await ws.send(json.dumps({"type": "auth", "token": auth_mgr.token}))
        ack = json.loads(await ws.recv())
        assert ack["type"] == "auth_ack"
        session_id = ack["session_id"]

        # 2. Send tab navigation
        await ws.send(
            json.dumps({
                "type": "tab_navigated",
                "tab_id": 42,
                "url": "https://www.Instagram.com/explore/",
                "title": "Explore • Instagram",
                "incognito": False,
            })
        )

        # Allow loop event processing
        await asyncio.sleep(0.05)

        assert len(captured_events) == 1
        ev = captured_events[0]
        assert ev.domain == "www.instagram.com"
        assert ev.tab_id == 42
        assert ev.action == "visit"
        assert ev.incognito is False
        assert ev.session_id == session_id


@pytest.mark.anyio
async def test_stale_tab_protection_and_safe_closing(
    bridge_server: BridgeServer, auth_mgr: BridgeAuthManager
) -> None:
    origin = "chrome-extension://paired-extension-12345"
    auth_mgr.add_paired_origin(origin, label="Test Chrome Extension")

    uri = f"ws://127.0.0.1:{bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        await ws.send(json.dumps({"type": "auth", "token": auth_mgr.token}))
        ack = json.loads(await ws.recv())
        session_id = ack["session_id"]

        # 1. Tab navigated to instagram.com
        await ws.send(
            json.dumps({
                "type": "tab_navigated",
                "tab_id": 100,
                "url": "https://instagram.com/p/abc",
                "title": "Post",
                "incognito": False,
            })
        )
        await asyncio.sleep(0.05)

        # 2. Attempt closing with WRONG expected domain (stale navigation check)
        close_wrong_domain_task = asyncio.create_task(
            bridge_server.request_close_tab(
                session_id=session_id,
                tab_id=100,
                expected_domain="twitter.com",
                rule_id="distraction_guard",
                timeout=1.0,
            )
        )
        success_wrong = await close_wrong_domain_task
        assert success_wrong is False, "Should reject close request when domain does not match expected"

        # 3. Proper matching close request
        close_task = asyncio.create_task(
            bridge_server.request_close_tab(
                session_id=session_id,
                tab_id=100,
                expected_domain="instagram.com",
                rule_id="distraction_guard",
                timeout=2.0,
            )
        )

        # Client receives command
        cmd_raw = await ws.recv()
        cmd = json.loads(cmd_raw)
        assert cmd["type"] == "close_tab"
        assert cmd["tab_id"] == 100
        assert cmd["expected_domain"] == "instagram.com"

        # Client responds with TabCloseAck
        await ws.send(
            json.dumps({
                "type": "tab_close_ack",
                "tab_id": 100,
                "session_id": session_id,
                "success": True,
            })
        )

        res = await close_task
        assert res is True


@pytest.mark.anyio
async def test_incognito_tab_close_suppressed_by_default(
    bridge_server: BridgeServer, auth_mgr: BridgeAuthManager
) -> None:
    origin = "chrome-extension://paired-extension-12345"
    auth_mgr.add_paired_origin(origin, label="Test Chrome Extension")

    uri = f"ws://127.0.0.1:{bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        await ws.send(json.dumps({"type": "auth", "token": auth_mgr.token}))
        ack = json.loads(await ws.recv())
        session_id = ack["session_id"]

        # Incognito tab
        await ws.send(
            json.dumps({
                "type": "tab_navigated",
                "tab_id": 105,
                "url": "https://instagram.com",
                "incognito": True,
            })
        )
        await asyncio.sleep(0.05)

        # Closing incognito without allow_incognito must be suppressed
        res = await bridge_server.request_close_tab(
            session_id=session_id,
            tab_id=105,
            expected_domain="instagram.com",
            rule_id="distraction_guard",
            allow_incognito=False,
        )
        assert res is False
