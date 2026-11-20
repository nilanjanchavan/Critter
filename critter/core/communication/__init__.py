"""WebSocket communication bridge for Critter browser extensions."""

from critter.core.communication.auth import BridgeAuthManager, PairedOrigin
try:
    from critter.core.communication.bridge_server import (
        BridgeServer,
        BridgeServerThread,
        BridgeSession,
        TabState,
    )
except ImportError:
    BridgeServer = None  # type: ignore
    BridgeServerThread = None  # type: ignore
    BridgeSession = None  # type: ignore
    TabState = None  # type: ignore
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
    validate_and_normalize_url,
)

__all__ = [
    "AuthAckMessage",
    "AuthErrMessage",
    "AuthMessage",
    "BridgeAuthManager",
    "BridgeServer",
    "BridgeServerThread",
    "BridgeSession",
    "CloseTabCommand",
    "ErrorMessage",
    "InboundMessage",
    "MAX_MESSAGE_SIZE_BYTES",
    "PairedOrigin",
    "PingMessage",
    "PongMessage",
    "ProtocolError",
    "RateLimiter",
    "SecurityValidationError",
    "TabActivatedMessage",
    "TabCloseAckMessage",
    "TabClosedMessage",
    "TabNavigatedMessage",
    "TabState",
    "parse_inbound_message",
    "validate_and_normalize_url",
]

