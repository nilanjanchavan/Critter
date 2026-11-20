"""Security validations, URL normalization, and rate limiting for the WebSocket bridge."""

from collections import deque
import logging
import re
import time
from typing import Deque, Optional, Tuple
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# Enforce 64 KB message size limit
MAX_MESSAGE_SIZE_BYTES = 64 * 1024

# Allowed URL schemes from the browser extension
ALLOWED_SCHEMES = {"http", "https"}

# Basic domain regex (RFC 1035 / RFC 1123 compliant)
DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-_]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$|"
    r"^localhost$|"
    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
)


class SecurityValidationError(Exception):
    """Raised when incoming bridge data violates security constraints."""


def validate_and_normalize_url(raw_url: str) -> Tuple[str, str]:
    """Validate URL, enforce http/https scheme, and derive normalized domain server-side.

    Returns:
        (normalized_url, normalized_domain)

    Raises:
        SecurityValidationError: if scheme is unsupported, domain is invalid, or URL is malformed.
    """
    if not raw_url or not isinstance(raw_url, str):
        raise SecurityValidationError("Missing or non-string URL")

    clean_url = raw_url.strip()
    if len(clean_url) > 4096:
        raise SecurityValidationError("URL exceeds maximum length (4096 chars)")

    try:
        parts = urlsplit(clean_url)
    except Exception as exc:
        raise SecurityValidationError(f"Malformed URL: {exc}")

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SecurityValidationError(
            f"Unsupported URL scheme '{scheme}'. Only http and https are permitted."
        )

    # Derive domain strictly server-side
    hostname = parts.hostname
    if not hostname:
        raise SecurityValidationError("URL contains no valid host or domain")

    normalized_domain = hostname.lower().rstrip(".")

    if not DOMAIN_REGEX.match(normalized_domain):
        raise SecurityValidationError(f"Invalid domain structure: {normalized_domain}")

    # Reassemble normalized URL (preserving path/query, but ensuring clean scheme and lowercase host)
    netloc = normalized_domain
    if parts.port and not ((scheme == "http" and parts.port == 80) or (scheme == "https" and parts.port == 443)):
        netloc = f"{netloc}:{parts.port}"

    normalized_url = f"{scheme}://{netloc}{parts.path or '/'}"
    if parts.query:
        normalized_url += f"?{parts.query}"

    return normalized_url, normalized_domain


def mask_url_for_logs(domain: str) -> str:
    """Return a privacy-preserving representation of the site for application logs."""
    return f"[{domain}]"


class RateLimiter:
    """Sliding-window rate limiter per WebSocket client."""

    def __init__(self, max_requests: int = 30, window_seconds: float = 1.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: Deque[float] = deque()

    def allow_request(self) -> bool:
        """Check if a new request is permitted within the rate limit window."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Evict timestamps outside the sliding window
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_requests:
            return False

        self._timestamps.append(now)
        return True

