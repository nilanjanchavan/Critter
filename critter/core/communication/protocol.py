"""Strict message protocol and schema validation for the WebSocket bridge."""

from dataclasses import asdict, dataclass
import json
from typing import Any, Dict, Optional


class ProtocolError(Exception):
    """Raised when an inbound message violates protocol schema."""


@dataclass(kw_only=True)
class InboundMessage:
    """Base for inbound messages."""
    type: str


@dataclass(kw_only=True)
class AuthMessage(InboundMessage):
    token: str
    client: str = "critter-extension"
    version: str = "1.0.0"
    browser: str = "chromium"


@dataclass(kw_only=True)
class TabNavigatedMessage(InboundMessage):
    tab_id: int
    url: str
    title: str = ""
    incognito: bool = False


@dataclass(kw_only=True)
class TabActivatedMessage(InboundMessage):
    tab_id: int
    url: str
    title: str = ""
    incognito: bool = False


@dataclass(kw_only=True)
class TabClosedMessage(InboundMessage):
    tab_id: int


@dataclass(kw_only=True)
class TabCloseAckMessage(InboundMessage):
    tab_id: int
    session_id: str
    success: bool
    error: Optional[str] = None


@dataclass(kw_only=True)
class PingMessage(InboundMessage):
    pass


# --- Outbound Messages ---

@dataclass(kw_only=True)
class OutboundMessage:
    type: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass(kw_only=True)
class AuthAckMessage(OutboundMessage):
    type: str = "auth_ack"
    session_id: str
    server_version: str = "0.1.0"


@dataclass(kw_only=True)
class AuthErrMessage(OutboundMessage):
    type: str = "auth_err"
    reason: str


@dataclass(kw_only=True)
class CloseTabCommand(OutboundMessage):
    type: str = "close_tab"
    session_id: str
    tab_id: int
    expected_url: str
    expected_domain: str
    rule_id: str
    reason: str = ""


@dataclass(kw_only=True)
class PongMessage(OutboundMessage):
    type: str = "pong"


@dataclass(kw_only=True)
class ErrorMessage(OutboundMessage):
    type: str = "error"
    code: str
    message: str


def parse_inbound_message(raw_text: str) -> InboundMessage:
    """Parse and strictly validate an inbound JSON message against schema."""
    try:
        data = json.loads(raw_text)
    except Exception as exc:
        raise ProtocolError(f"Malformed JSON: {exc}")

    if not isinstance(data, dict):
        raise ProtocolError("Message payload must be a JSON object")

    msg_type = data.get("type")
    if not msg_type or not isinstance(msg_type, str):
        raise ProtocolError("Message missing valid 'type' field")

    if msg_type == "auth":
        token = data.get("token")
        if not token or not isinstance(token, str):
            raise ProtocolError("Auth message requires non-empty string 'token'")
        return AuthMessage(
            type="auth",
            token=token,
            client=str(data.get("client", "critter-extension")),
            version=str(data.get("version", "1.0.0")),
            browser=str(data.get("browser", "chromium")),
        )

    elif msg_type == "tab_navigated":
        tab_id = data.get("tab_id")
        url = data.get("url")
        if not isinstance(tab_id, int):
            raise ProtocolError("tab_navigated requires integer 'tab_id'")
        if not url or not isinstance(url, str):
            raise ProtocolError("tab_navigated requires string 'url'")
        return TabNavigatedMessage(
            type="tab_navigated",
            tab_id=tab_id,
            url=url,
            title=str(data.get("title", "")),
            incognito=bool(data.get("incognito", False)),
        )

    elif msg_type == "tab_activated":
        tab_id = data.get("tab_id")
        url = data.get("url")
        if not isinstance(tab_id, int):
            raise ProtocolError("tab_activated requires integer 'tab_id'")
        if not url or not isinstance(url, str):
            raise ProtocolError("tab_activated requires string 'url'")
        return TabActivatedMessage(
            type="tab_activated",
            tab_id=tab_id,
            url=url,
            title=str(data.get("title", "")),
            incognito=bool(data.get("incognito", False)),
        )

    elif msg_type == "tab_closed":
        tab_id = data.get("tab_id")
        if not isinstance(tab_id, int):
            raise ProtocolError("tab_closed requires integer 'tab_id'")
        return TabClosedMessage(type="tab_closed", tab_id=tab_id)

    elif msg_type == "tab_close_ack":
        tab_id = data.get("tab_id")
        session_id = data.get("session_id")
        success = data.get("success")
        if not isinstance(tab_id, int) or not isinstance(session_id, str) or not isinstance(success, bool):
            raise ProtocolError("tab_close_ack requires int tab_id, str session_id, and bool success")
        return TabCloseAckMessage(
            type="tab_close_ack",
            tab_id=tab_id,
            session_id=session_id,
            success=success,
            error=str(data.get("error")) if data.get("error") is not None else None,
        )

    elif msg_type == "ping":
        return PingMessage(type="ping")

    else:
        raise ProtocolError(f"Unrecognized message type '{msg_type}'")

