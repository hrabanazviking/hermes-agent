"""
Canonical Platform Error Hierarchy

Every platform adapter translates its library-specific exceptions
into these canonical types so the ErrorClassifier can reason uniformly.
"""

from typing import Optional


# ── Transport-independent base ──────────────────────────────────

class PlatformError(Exception):
    """Base for all platform-originated errors."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        platform_id: Optional[str] = None,
        original: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.platform_id = platform_id
        self.original = original


class PlatformConnectionError(PlatformError):
    """Network-level connection failure (DNS, TCP handshake, TLS)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("retryable", True)
        super().__init__(message, **kwargs)


class PlatformAuthError(PlatformError):
    """Authentication/authorization failure (bad token, revoked)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("retryable", False)
        super().__init__(message, **kwargs)


class PlatformRateLimitError(PlatformError):
    """Remote rate limit hit. Carries retry_after_seconds if available."""

    def __init__(
        self, message: str, *, retry_after_seconds: Optional[float] = None, **kwargs
    ):
        kwargs.setdefault("retryable", True)
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class PlatformMessageError(PlatformError):
    """Failed to deliver, edit, or delete a message. May or may not be retryable."""

    def __init__(self, message: str, *, message_id: Optional[str] = None, **kwargs):
        kwargs.setdefault("retryable", True)
        super().__init__(message, **kwargs)
        self.message_id = message_id


class PlatformParseError(PlatformError):
    """Received unparseable data from platform (malformed JSON, wrong schema)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("retryable", False)
        super().__init__(message, **kwargs)


# ── HTTP-level errors ───────────────────────────────────────────

class HTTPError(Exception):
    """Canonical HTTP error — all HTTP clients normalise to this."""

    def __init__(
        self,
        status: int,
        body: str,
        *,
        provider: Optional[str] = None,
        url: Optional[str] = None,
        original: Optional[Exception] = None,
    ):
        super().__init__(f"HTTP {status} from {provider or 'unknown'}: {body[:200]}")
        self.status = status
        self.body = body
        self.provider = provider
        self.url = url
        self.original = original

    @property
    def retryable(self) -> bool:
        """429, 502, 503, 504 are retryable. 4xx (except 429) are not."""
        return self.status in (429, 502, 503, 504)

    @property
    def is_rate_limit(self) -> bool:
        return self.status == 429


class HTTPConnectionError(HTTPError):
    """Connection-level HTTP failure (timeout, DNS, refused). No status code."""

    def __init__(self, message: str, **kwargs):
        super().__init__(0, message,  **kwargs)


# ── Internal errors ─────────────────────────────────────────────

class GatewayInternalError(Exception):
    """Base for bugs/assertions within the gateway itself."""

    def __init__(self, message: str, *, location: Optional[str] = None):
        super().__init__(message)
        self.location = location


class GatewayConfigurationError(GatewayInternalError):
    """Invalid configuration detected at startup or runtime."""


class GatewayResourceExhaustionError(Exception):
    """System resource limit hit (OOM, EMFILE, ENOSPC)."""

    def __init__(self, resource: str, current: int, limit: int):
        super().__init__(f"{resource}: {current}/{limit}")
        self.resource = resource
        self.current = current
        self.limit = limit
