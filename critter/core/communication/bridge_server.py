"""Local WebSocket bridge server for Critter browser extensions.

Binds strictly to 127.0.0.1.
Enforces origin allowlisting, token-based authentication, strict schema validation,
rate limiting, server-side domain normalization, and safe tab-closing semantics.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Callable, Dict, Optional, Set
import uuid

import websockets.asyncio.server as wss
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from critter.core.events import EventBus
from critter.core.automation.events import ExternalWebEvent
from critter.core.communication.auth import BridgeAuthManager, DEFAULT_AUTH_FILE
from critter.core.communication.protocol import (
    AuthAckMessage,
    AuthErrMessage,
    AuthMessage,
    CloseTabCommand,
    ErrorMessage,
    InboundMessage,
    PingMessage,
    PongMessage,
    ProtocolError,
    TabActivatedMessage,
    TabCloseAckMessage,
    TabClosedMessage,
    TabNavigatedMessage,
    parse_inbound_message,
)
from critter.core.communication.security import (
    MAX_MESSAGE_SIZE_BYTES,
    RateLimiter,
    SecurityValidationError,
    mask_url_for_logs,
    validate_and_normalize_url,
)

logger = logging.getLogger(__name__)


@dataclass
class TabState:
    """State tracking for a known tab in an active browser session."""
    tab_id: int
    url: str
    domain: str
    title: str = ""
    incognito: bool = False
    last_updated: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class BridgeSession:
    """Represents an active authenticated browser connection."""

    def __init__(self, session_id: str, websocket: wss.ServerConnection, origin: str) -> None:
        self.session_id = session_id
        self.websocket = websocket
        self.origin = origin
        self.authenticated = False
        self.client_info: Dict[str, str] = {}
        self.rate_limiter = RateLimiter(max_requests=30, window_seconds=1.0)
        self.active_tabs: Dict[int, TabState] = {}
        self.pending_close_acks: Dict[int, asyncio.Future[bool]] = {}

    async def send_message(self, msg: Any) -> None:
        """Send a protocol message serialized as JSON."""
        if hasattr(msg, "to_json"):
            text = msg.to_json()
        else:
            text = str(msg)
        await self.websocket.send(text)


class BridgeServer:
    """Secure WebSocket bridge server bound to 127.0.0.1."""

    def __init__(
        self,
        auth_manager: Optional[BridgeAuthManager] = None,
        event_bus: Optional[EventBus] = None,
        host: str = "127.0.0.1",
        port: int = 8765,
        thread_dispatch: Optional[Callable[[Callable[[], None]], None]] = None,
    ) -> None:
        # Enforce loopback binding only
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError(f"BridgeServer must bind exclusively to loopback (127.0.0.1), got '{host}'")

        self.host = "127.0.0.1"
        self.port = port
        self.auth_manager = auth_manager or BridgeAuthManager()
        self.event_bus = event_bus
        self.thread_dispatch = thread_dispatch

        self._server: Optional[wss.Server] = None
        self._sessions: Dict[str, BridgeSession] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and self._server is not None

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    def process_request(
        self, connection: wss.ServerConnection, request: Request
    ) -> Optional[Response]:
        """Validate WebSocket Origin header before accepting connection handshake."""
        origin = request.headers.get("Origin")

        # Reject missing origin
        if not origin:
            logger.warning("Rejected bridge connection: missing Origin header from %s", connection.remote_address)
            return Response(
                status_code=403,
                reason_phrase="Forbidden",
                headers=Headers(),
                body=b"Forbidden: Missing Origin header\n",
            )

        clean_origin = origin.strip().lower()
        if not self.auth_manager.is_origin_allowed(clean_origin):
            logger.warning("Rejected bridge connection: origin '%s' not in paired allowlist", clean_origin)
            return Response(
                status_code=403,
                reason_phrase="Forbidden",
                headers=Headers(),
                body=b"Forbidden: Origin not in paired allowlist\n",
            )

        return None

    async def handle_connection(self, websocket: wss.ServerConnection) -> None:
        """Handle individual WebSocket connection lifecycle."""
        origin = websocket.request.headers.get("Origin", "")
        session_id = uuid.uuid4().hex
        session = BridgeSession(session_id=session_id, websocket=websocket, origin=origin)

        logger.debug("Bridge client connected from %s (session: %s, origin: %s)", websocket.remote_address, session_id, origin)

        try:
            # 1. Require Authentication within 3.0 seconds
            try:
                raw_auth = await asyncio.wait_for(websocket.recv(), timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning("Auth timeout for session %s", session_id)
                await session.send_message(AuthErrMessage(reason="auth_timeout"))
                await websocket.close(1008, "Auth timeout")
                return

            try:
                auth_msg = parse_inbound_message(raw_auth)
            except ProtocolError as pe:
                logger.warning("Invalid auth payload for session %s: %s", session_id, pe)
                await session.send_message(AuthErrMessage(reason="malformed_auth"))
                await websocket.close(1008, "Malformed auth")
                return

            if not isinstance(auth_msg, AuthMessage):
                logger.warning("First message not auth for session %s", session_id)
                await session.send_message(AuthErrMessage(reason="first_message_must_be_auth"))
                await websocket.close(1008, "First message must be auth")
                return

            if not self.auth_manager.verify_token(auth_msg.token):
                logger.warning("Invalid authentication token for session %s", session_id)
                await session.send_message(AuthErrMessage(reason="invalid_token"))
                await websocket.close(1008, "Invalid token")
                return

            # Authentication successful
            session.authenticated = True
            session.client_info = {
                "client": auth_msg.client,
                "version": auth_msg.version,
                "browser": auth_msg.browser,
            }
            self._sessions[session_id] = session

            await session.send_message(
                AuthAckMessage(session_id=session_id, server_version="0.1.0")
            )
            logger.info("Session %s authenticated successfully (%s %s)", session_id, auth_msg.browser, auth_msg.client)

            # 2. Main message loop
            async for raw_message in websocket:
                if not session.rate_limiter.allow_request():
                    logger.warning("Rate limit exceeded for session %s; closing", session_id)
                    await session.send_message(ErrorMessage(code="rate_limit", message="Rate limit exceeded"))
                    await websocket.close(1008, "Rate limit exceeded")
                    break

                try:
                    msg = parse_inbound_message(raw_message)
                    await self._dispatch_message(session, msg)
                except ProtocolError as pe:
                    logger.warning("Protocol error from session %s: %s", session_id, pe)
                    await session.send_message(ErrorMessage(code="protocol_error", message=str(pe)))
                except SecurityValidationError as sve:
                    logger.warning("Security validation error from session %s: %s", session_id, sve)
                    await session.send_message(ErrorMessage(code="security_error", message=str(sve)))
                except Exception as exc:
                    logger.exception("Unexpected error processing message in session %s: %s", session_id, exc)

        except websockets.exceptions.ConnectionClosed:
            logger.debug("Session %s connection closed cleanly", session_id)
        except Exception as exc:
            logger.error("Session %s encountered exception: %s", session_id, exc)
        finally:
            self._sessions.pop(session_id, None)
            logger.debug("Cleaned up session %s", session_id)

    async def _dispatch_message(self, session: BridgeSession, msg: InboundMessage) -> None:
        """Process verified inbound messages from authenticated sessions."""
        if isinstance(msg, PingMessage):
            await session.send_message(PongMessage())

        elif isinstance(msg, TabNavigatedMessage):
            normalized_url, normalized_domain = validate_and_normalize_url(msg.url)
            session.active_tabs[msg.tab_id] = TabState(
                tab_id=msg.tab_id,
                url=normalized_url,
                domain=normalized_domain,
                title=msg.title,
                incognito=msg.incognito,
            )
            logger.info("Tab %d navigated to %s (session %s)", msg.tab_id, mask_url_for_logs(normalized_domain), session.session_id)
            self._publish_web_event(
                url=normalized_url,
                domain=normalized_domain,
                title=msg.title,
                action="visit",
                tab_id=msg.tab_id,
                incognito=msg.incognito,
                session_id=session.session_id,
            )

        elif isinstance(msg, TabActivatedMessage):
            normalized_url, normalized_domain = validate_and_normalize_url(msg.url)
            session.active_tabs[msg.tab_id] = TabState(
                tab_id=msg.tab_id,
                url=normalized_url,
                domain=normalized_domain,
                title=msg.title,
                incognito=msg.incognito,
            )
            logger.debug("Tab %d activated: %s", msg.tab_id, mask_url_for_logs(normalized_domain))
            self._publish_web_event(
                url=normalized_url,
                domain=normalized_domain,
                title=msg.title,
                action="active_tab",
                tab_id=msg.tab_id,
                incognito=msg.incognito,
                session_id=session.session_id,
            )

        elif isinstance(msg, TabClosedMessage):
            closed_tab = session.active_tabs.pop(msg.tab_id, None)
            domain = closed_tab.domain if closed_tab else ""
            url = closed_tab.url if closed_tab else ""
            self._publish_web_event(
                url=url,
                domain=domain,
                title="",
                action="closed",
                tab_id=msg.tab_id,
                incognito=closed_tab.incognito if closed_tab else False,
                session_id=session.session_id,
            )

        elif isinstance(msg, TabCloseAckMessage):
            logger.info("Received TabCloseAck for tab %d (success=%s, err=%s)", msg.tab_id, msg.success, msg.error)
            fut = session.pending_close_acks.pop(msg.tab_id, None)
            if fut and not fut.done():
                fut.set_result(msg.success)

    def _publish_web_event(
        self,
        url: str,
        domain: str,
        title: str,
        action: str,
        tab_id: int,
        incognito: bool,
        session_id: str,
    ) -> None:
        """Publish ExternalWebEvent to EventBus (optionally marshalled to main thread)."""
        if not self.event_bus:
            return

        event = ExternalWebEvent(
            url=url,
            domain=domain,
            title=title,
            action=action,
            tab_id=tab_id,
            incognito=incognito,
            session_id=session_id,
        )

        def emit():
            self.event_bus.publish(event)

        if self.thread_dispatch:
            self.thread_dispatch(emit)
        else:
            emit()

    async def request_close_tab(
        self,
        session_id: str,
        tab_id: int,
        expected_domain: str,
        rule_id: str,
        reason: str = "",
        allow_incognito: bool = False,
        timeout: float = 4.0,
    ) -> bool:
        """Safely request closing a specific tab with domain validation and incognito exclusion.

        Returns True if the extension acknowledged successful closure, False otherwise.
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("Cannot close tab: session %s not found or disconnected", session_id)
            return False

        tab = session.active_tabs.get(tab_id)
        if not tab:
            logger.warning("Cannot close tab %d: tab not tracked in session %s", tab_id, session_id)
            return False

        # Exclude incognito tabs by default for privacy
        if tab.incognito and not allow_incognito:
            logger.warning("Suppressed closing incognito tab %d for privacy protection", tab_id)
            return False

        # Stale tab check: Ensure domain still matches
        if expected_domain and tab.domain.lower() != expected_domain.lower():
            logger.warning("Suppressed closing tab %d: current domain %s != expected %s (user navigated away)", tab_id, tab.domain, expected_domain)
            return False

        cmd = CloseTabCommand(
            session_id=session_id,
            tab_id=tab_id,
            expected_url=tab.url,
            expected_domain=tab.domain,
            rule_id=rule_id,
            reason=reason,
        )

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[bool] = loop.create_future()
        session.pending_close_acks[tab_id] = ack_future

        try:
            await session.send_message(cmd)
            success = await asyncio.wait_for(ack_future, timeout=timeout)
            return success
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for TabCloseAck for tab %d", tab_id)
            return False
        except Exception as exc:
            logger.error("Error sending CloseTabCommand to tab %d: %s", tab_id, exc)
            return False
        finally:
            session.pending_close_acks.pop(tab_id, None)

    async def start_async(self) -> None:
        """Start the WebSocket server on asyncio event loop."""
        self._loop = asyncio.get_running_loop()
        self._server = await wss.serve(
            self.handle_connection,
            host=self.host,
            port=self.port,
            process_request=self.process_request,
            max_size=MAX_MESSAGE_SIZE_BYTES,
        )
        self._running = True
        logger.info("BridgeServer listening strictly on ws://%s:%d (max_size=%d bytes)", self.host, self.port, MAX_MESSAGE_SIZE_BYTES)

    async def stop_async(self) -> None:
        """Stop the WebSocket server and close active client sessions."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for session in list(self._sessions.values()):
            try:
                await session.websocket.close(1001, "Server shutting down")
            except Exception:
                pass
        self._sessions.clear()
        logger.info("BridgeServer stopped cleanly.")


class BridgeServerThread:
    """Helper running BridgeServer in a dedicated daemon thread."""

    def __init__(self, bridge_server: BridgeServer) -> None:
        self.bridge_server = bridge_server
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started_event = threading.Event()

    def start(self) -> None:
        """Start server in background thread."""
        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.bridge_server.start_async())
            self._started_event.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True, name="critter-bridge-server")
        self._thread.start()
        self._started_event.wait(timeout=5.0)

    def stop(self) -> None:
        """Stop background thread and server."""
        if self._loop and self.bridge_server.is_running:
            future = asyncio.run_coroutine_threadsafe(self.bridge_server.stop_async(), self._loop)
            try:
                future.result(timeout=4.0)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
