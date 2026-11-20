"""Tests for the Critter browser extension manifest, assets, and client protocol."""

import asyncio
from datetime import datetime
import json
import os
from typing import AsyncGenerator
import pytest
import websockets.asyncio.client as ws_client

from critter.core.events import EventBus
from critter.core.automation.events import ExternalWebEvent
from critter.core.communication.auth import BridgeAuthManager
from critter.core.communication.bridge_server import BridgeServer

EXTENSION_DIR = os.path.abspath("critter/apps/browser-extension")


def test_extension_manifest_integrity_and_minimal_permissions() -> None:
    manifest_path = os.path.join(EXTENSION_DIR, "manifest.json")
    assert os.path.isfile(manifest_path), "manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Manifest V3 compliance
    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == "Critter Desktop Companion"
    assert manifest.get("version") == "1.0.0"

    # 2. Strict minimal permissions check
    permissions = manifest.get("permissions", [])
    assert set(permissions) == {"tabs", "storage"}, "Must only request 'tabs' and 'storage' permissions"
    assert "host_permissions" not in manifest or manifest["host_permissions"] == [], "No broad host permissions permitted"

    # 3. File references existence
    sw = manifest.get("background", {}).get("service_worker")
    assert sw is not None and os.path.isfile(os.path.join(EXTENSION_DIR, sw))

    popup = manifest.get("action", {}).get("default_popup")
    assert popup is not None and os.path.isfile(os.path.join(EXTENSION_DIR, popup))

    for icon_size in ["16", "48", "128"]:
        icon_rel = manifest.get("icons", {}).get(icon_size)
        assert icon_rel is not None
        icon_path = os.path.join(EXTENSION_DIR, icon_rel)
        assert os.path.isfile(icon_path), f"Icon {icon_size} must exist"
        assert os.path.getsize(icon_path) > 0, f"Icon {icon_size} must not be empty"


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def test_auth_mgr() -> BridgeAuthManager:
    auth_file = os.path.abspath(".critter_config/test_ext_auth.json")
    os.makedirs(os.path.dirname(auth_file), exist_ok=True)
    mgr = BridgeAuthManager(auth_file=auth_file)
    yield mgr
    if os.path.exists(auth_file):
        os.remove(auth_file)


@pytest.fixture
async def ext_bridge_server(test_auth_mgr: BridgeAuthManager, bus: EventBus) -> AsyncGenerator[BridgeServer, None]:
    server = BridgeServer(auth_manager=test_auth_mgr, event_bus=bus, host="127.0.0.1", port=0)
    await server.start_async()
    assigned_port = server._server.sockets[0].getsockname()[1]
    server.port = assigned_port
    yield server
    await server.stop_async()


@pytest.mark.anyio
async def test_simulated_chromium_extension_lifecycle(
    ext_bridge_server: BridgeServer, test_auth_mgr: BridgeAuthManager, bus: EventBus
) -> None:
    origin = "chrome-extension://knldjmfmopnppmplflldnbgahglbehed"
    test_auth_mgr.add_paired_origin(origin, label="Chromium Test Extension")

    web_events: list[ExternalWebEvent] = []
    bus.subscribe(ExternalWebEvent, lambda e: web_events.append(e))

    uri = f"ws://127.0.0.1:{ext_bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        # 1. Handshake Auth
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

        # 2. Tab Navigation
        await ws.send(
            json.dumps({
                "type": "tab_navigated",
                "tab_id": 501,
                "url": "https://www.instagram.com/explore/",
                "title": "Instagram",
                "incognito": False,
            })
        )
        await asyncio.sleep(0.05)

        assert len(web_events) == 1
        assert web_events[0].domain == "www.instagram.com"
        assert web_events[0].tab_id == 501
        assert web_events[0].session_id == session_id

        # 3. Safe Tab Close Flow
        close_future = asyncio.create_task(
            ext_bridge_server.request_close_tab(
                session_id=session_id,
                tab_id=501,
                expected_domain="www.instagram.com",
                rule_id="distraction_guard",
                reason="Focus guard",
                timeout=2.0,
            )
        )

        # Extension receives command
        cmd = json.loads(await ws.recv())
        assert cmd["type"] == "close_tab"
        assert cmd["tab_id"] == 501
        assert cmd["expected_domain"] == "www.instagram.com"

        # Extension acknowledges removal
        await ws.send(
            json.dumps({
                "type": "tab_close_ack",
                "tab_id": 501,
                "session_id": session_id,
                "success": True,
            })
        )

        success = await close_future
        assert success is True

        # 4. Heartbeat
        await ws.send(json.dumps({"type": "ping"}))
        pong = json.loads(await ws.recv())
        assert pong["type"] == "pong"


@pytest.mark.anyio
async def test_simulated_firefox_extension_lifecycle(
    ext_bridge_server: BridgeServer, test_auth_mgr: BridgeAuthManager, bus: EventBus
) -> None:
    origin = "moz-extension://b4b609c1-4b77-4a0b-93df-5c5ee53e5e49"
    test_auth_mgr.add_paired_origin(origin, label="Firefox Test Extension")

    uri = f"ws://127.0.0.1:{ext_bridge_server.port}"
    async with ws_client.connect(uri, additional_headers={"Origin": origin}) as ws:
        await ws.send(
            json.dumps({
                "type": "auth",
                "token": test_auth_mgr.token,
                "client": "critter-companion",
                "version": "1.0.0",
                "browser": "firefox",
            })
        )
        auth_ack = json.loads(await ws.recv())
        assert auth_ack["type"] == "auth_ack"
        assert ext_bridge_server.active_session_count == 1
