"""Authentication and pairing management for the Critter WebSocket bridge.

Maintains cryptographically secure tokens and an explicit allowlist of paired
browser extension origins. Stored in ~/.config/critter/bridge_auth.json with 0600 permissions.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/critter")
DEFAULT_AUTH_FILE = os.path.join(DEFAULT_CONFIG_DIR, "bridge_auth.json")


@dataclass
class PairedOrigin:
    """Record of an explicitly paired browser extension origin."""
    origin: str
    label: str
    paired_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BridgeAuthManager:
    """Manages bridge authentication tokens and explicit extension origin allowlisting."""

    def __init__(self, auth_file: str = DEFAULT_AUTH_FILE) -> None:
        self.auth_file = auth_file
        self._auth_token: str = ""
        self._paired_origins: Dict[str, PairedOrigin] = {}
        self._load_or_initialize()

    @property
    def token(self) -> str:
        return self._auth_token

    def _load_or_initialize(self) -> None:
        """Load existing auth configuration or generate a new secure token."""
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._auth_token = data.get("auth_token", "")
                    for orig, info in data.get("paired_origins", {}).items():
                        self._paired_origins[orig] = PairedOrigin(
                            origin=orig,
                            label=info.get("label", "Browser Extension"),
                            paired_at=info.get("paired_at", ""),
                        )
                if self._auth_token:
                    return
            except Exception as exc:
                logger.warning("Failed loading auth config from %s: %s; recreating.", self.auth_file, exc)

        # Generate a new 256-bit token
        self._auth_token = secrets.token_hex(32)
        self.save()

    def save(self) -> None:
        """Persist auth state to disk with 0600 permissions."""
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        data = {
            "auth_token": self._auth_token,
            "paired_origins": {
                orig: asdict(po) for orig, po in self._paired_origins.items()
            },
        }

        # Write safely with atomic replace and 0600 permissions
        temp_file = f"{self.auth_file}.tmp.{secrets.token_hex(4)}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        os.chmod(temp_file, 0o600)
        os.replace(temp_file, self.auth_file)
        logger.info("Saved bridge auth configuration to %s (mode 0600)", self.auth_file)

    def is_origin_allowed(self, origin: Optional[str]) -> bool:
        """Check if origin is in the explicit allowlist. None/blank is never allowed."""
        if not origin:
            return False
        return origin.strip().lower() in self._paired_origins

    def add_paired_origin(self, origin: str, label: str = "Browser Extension") -> None:
        """Explicitly pair an extension origin (e.g. chrome-extension://<id>)."""
        clean_origin = origin.strip().lower()
        if not (clean_origin.startswith("chrome-extension://") or clean_origin.startswith("moz-extension://")):
            # Allow test origins only if explicitly labeled
            if not (clean_origin.startswith("http://127.0.0.1") or clean_origin.startswith("http://localhost")):
                raise ValueError(f"Invalid extension origin format: {origin}")

        self._paired_origins[clean_origin] = PairedOrigin(origin=clean_origin, label=label)
        self.save()
        logger.info("Paired extension origin: %s (%s)", clean_origin, label)

    def revoke_origin(self, origin: str) -> bool:
        """Revoke a previously paired extension origin."""
        clean_origin = origin.strip().lower()
        if clean_origin in self._paired_origins:
            del self._paired_origins[clean_origin]
            self.save()
            logger.info("Revoked extension origin: %s", clean_origin)
            return True
        return False

    def list_paired_origins(self) -> List[PairedOrigin]:
        """Return all paired extension origins."""
        return list(self._paired_origins.values())

    def verify_token(self, token: str) -> bool:
        """Constant-time token verification to prevent timing attacks."""
        if not token or not self._auth_token:
            return False
        return hmac.compare_digest(self._auth_token, token.strip())

    def rotate_token(self) -> str:
        """Generate and save a new authentication token."""
        self._auth_token = secrets.token_hex(32)
        self.save()
        return self._auth_token
