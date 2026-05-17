"""
ErrorClassifier — Centralised Error Taxonomy for the Gateway

All catch blocks route through `classify()` for consistent:
- Categorisation (TRANSIENT / PERMANENT / INTERNAL / EXTERNAL / RESOURCE)
- Severity assignment
- Recovery action recommendation
"""

from __future__ import annotations

import hmac
import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Taxonomy ────────────────────────────────────────────────────

class ErrorCategory(Enum):
    TRANSIENT = auto()   # Will likely resolve on retry (network, rate limit)
    PERMANENT = auto()   # Requires operator change (bad auth, invalid config)
    INTERNAL = auto()    # Bug in gateway code (TypeError from our logic)
    EXTERNAL = auto()    # Upstream service bug (provider 500, malformed JSON)
    RESOURCE = auto()    # System resource exhaustion (OOM, EMFILE)
    UNKNOWN = auto()     # Cannot classify — needs human review


class ErrorSeverity(Enum):
    DEBUG = auto()       # Expected, no real impact
    INFO = auto()        # Notable but harmless
    WARNING = auto()     # Degraded service, auto-recovery attempted
    ERROR = auto()       # User-visible failure
    CRITICAL = auto()    # Gateway health at risk


class RecoveryAction(Enum):
    RETRY_IMMEDIATE = auto()
    RETRY_BACKOFF = auto()
    RETRY_NEVER = auto()
    PAUSE_PLATFORM = auto()
    CIRCUIT_BREAK = auto()
    ALERT_ADMIN = auto()
    IGNORE = auto()
    SHUTDOWN_GRACEFUL = auto()


# ── Data structures ──────────────────────────────────────────────

@dataclass
class ErrorContext:
    """Metadata captured at the error site for classification and forensics."""

    location: str = ""            # function/module where error was caught
    platform_id: str = ""
    session_id: str = ""
    tool_name: str = ""
    provider: str = ""
    retry_count: int = 0
    user_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "platform_id": self.platform_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "provider": self.provider,
            "retry_count": self.retry_count,
            "user_id": self.user_id,
            **self.extra,
        }


@dataclass
class ClassifiedError:
    """The output of classification: what happened, how bad, what to do."""

    category: ErrorCategory
    severity: ErrorSeverity
    action: RecoveryAction
    original_exception: BaseException
    context: ErrorContext
    message: str

    # Derived
    traceback_hash: str = ""

    def __post_init__(self):
        if not self.traceback_hash:
            tb = getattr(self.original_exception, "__traceback__", None)
            if tb is not None:
                # Hash the top 3 frames for deduplication
                frames: List[str] = []
                cur = tb
                for _ in range(3):
                    if cur is None:
                        break
                    code = cur.tb_frame.f_code
                    frames.append(f"{code.co_filename}:{code.co_name}:{cur.tb_lineno}")
                    cur = cur.tb_next
                self.traceback_hash = hmac.new(
                    b"hermes-error-hash",
                    "|".join(frames).encode(),
                    hashlib.sha256,
                ).hexdigest()[:12]

    @property
    def should_log(self) -> bool:
        return self.severity != ErrorSeverity.DEBUG

    @property
    def should_alert(self) -> bool:
        return self.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.name,
            "severity": self.severity.name,
            "action": self.action.name,
            "message": self.message,
            "exception_type": type(self.original_exception).__qualname__,
            "traceback_hash": self.traceback_hash,
            **self.context.to_dict(),
        }


# ── Classification Engine ───────────────────────────────────────

class ErrorClassifier:
    """Centralised error taxonomy.

    Rules are checked in order; the first matching rule wins.
    Rules can be extended via ``register_rule()`` for provider-specific patterns.
    """

    # (category, severity, action)
    _default_rules: List[tuple] = [
        # --- Resource exhaustion ---
        (MemoryError, None, None, ErrorCategory.RESOURCE, ErrorSeverity.CRITICAL,
         RecoveryAction.SHUTDOWN_GRACEFUL),

        # --- HTTP status codes (from HTTPError) ---
        ("HTTPError:429", None, None, ErrorCategory.TRANSIENT, ErrorSeverity.WARNING,
         RecoveryAction.RETRY_BACKOFF),
        ("HTTPError:502", None, None, ErrorCategory.EXTERNAL, ErrorSeverity.WARNING,
         RecoveryAction.RETRY_BACKOFF),
        ("HTTPError:503", None, None, ErrorCategory.EXTERNAL, ErrorSeverity.WARNING,
         RecoveryAction.RETRY_BACKOFF),
        ("HTTPError:504", None, None, ErrorCategory.EXTERNAL, ErrorSeverity.WARNING,
         RecoveryAction.RETRY_BACKOFF),
        ("HTTPError:401", None, None, ErrorCategory.PERMANENT, ErrorSeverity.ERROR,
         RecoveryAction.ALERT_ADMIN),
        ("HTTPError:403", None, None, ErrorCategory.PERMANENT, ErrorSeverity.ERROR,
         RecoveryAction.ALERT_ADMIN),

        # --- Moonshot / schema errors ---
        ("HTTPError:400", re.compile(r"\$ref|schema|recursive", re.I), None,
         ErrorCategory.EXTERNAL, ErrorSeverity.ERROR, RecoveryAction.RETRY_NEVER),
        ("HTTPError:400", None, None,
         ErrorCategory.PERMANENT, ErrorSeverity.ERROR, RecoveryAction.ALERT_ADMIN),

        # --- Platform errors ---
        ("PlatformConnectionError", None, None,
         ErrorCategory.TRANSIENT, ErrorSeverity.WARNING, RecoveryAction.RETRY_BACKOFF),
        ("PlatformAuthError", None, None,
         ErrorCategory.PERMANENT, ErrorSeverity.ERROR, RecoveryAction.ALERT_ADMIN),
        ("PlatformRateLimitError", None, None,
         ErrorCategory.TRANSIENT, ErrorSeverity.WARNING, RecoveryAction.RETRY_BACKOFF),
        ("PlatformMessageError", None, None,
         ErrorCategory.TRANSIENT, ErrorSeverity.WARNING, RecoveryAction.RETRY_IMMEDIATE),

        # --- Connection errors ---
        ("ConnectionError", None, None,
         ErrorCategory.TRANSIENT, ErrorSeverity.WARNING, RecoveryAction.RETRY_BACKOFF),
        ("asyncio.TimeoutError", None, None,
         ErrorCategory.TRANSIENT, ErrorSeverity.WARNING, RecoveryAction.RETRY_BACKOFF),

        # --- Internal bugs ---
        ("GatewayInternalError", None, None,
         ErrorCategory.INTERNAL, ErrorSeverity.CRITICAL, RecoveryAction.ALERT_ADMIN),

        # --- System errors ---
        ("PermissionError", None, None,
         ErrorCategory.PERMANENT, ErrorSeverity.ERROR, RecoveryAction.ALERT_ADMIN),
        ("FileNotFoundError", None, None,
         ErrorCategory.PERMANENT, ErrorSeverity.ERROR, RecoveryAction.ALERT_ADMIN),

        # --- Catch-all ---
    ]

    # Provider-specific rules: (provider_regex, exc_type_name, msg_regex, cat, sev, action)
    _provider_rules: List[tuple] = []

    @classmethod
    def classify(
        cls, exc: BaseException, context: Optional[ErrorContext] = None
    ) -> ClassifiedError:
        """Classify an exception and return a ClassifiedError with recovery action."""

        ctx = context or ErrorContext()
        exc_type_name = type(exc).__qualname__
        exc_msg = str(exc)

        # Determine HTTP status if possible
        http_status: Optional[int] = None
        http_provider: Optional[str] = None
        if hasattr(exc, "status"):
            http_status = getattr(exc, "status", None)
        if hasattr(exc, "provider"):
            http_provider = getattr(exc, "provider", None)

        # --- Check rules ---
        for rule in cls._default_rules:
            match_type, match_msg_re, match_provider, cat, sev, action = rule

            # Type match
            if isinstance(match_type, str):
                if match_type.startswith("HTTPError:"):
                    code = int(match_type.split(":")[1])
                    if exc_type_name != "HTTPError":
                        continue  # Not an HTTPError at all — skip
                    if http_status != code:
                        continue  # Wrong HTTP status code
                elif exc_type_name != match_type:
                    continue
            elif not isinstance(exc, match_type):
                continue

            # Message regex match
            if match_msg_re is not None and not match_msg_re.search(exc_msg):
                continue

            # Provider match
            if match_provider is not None:
                prov = http_provider or ctx.provider
                if not match_provider.search(prov):
                    continue

            # Rule matched!
            message = f"[{cat.name}] {exc_type_name}: {exc_msg[:200]}"
            return ClassifiedError(
                category=cat,
                severity=sev,
                action=action,
                original_exception=exc,
                context=ctx,
                message=message,
            )

        # --- Check provider rules ---
        for prov_re, match_type, msg_re, cat, sev, action in cls._provider_rules:
            prov = http_provider or ctx.provider
            if not prov_re.search(prov):
                continue
            if match_type and exc_type_name != match_type:
                continue
            if msg_re and not msg_re.search(exc_msg):
                continue
            message = f"[{cat.name}] {prov}: {exc_type_name}: {exc_msg[:200]}"
            return ClassifiedError(
                category=cat, severity=sev, action=action,
                original_exception=exc, context=ctx, message=message,
            )

        # --- Fallback ---
        message = f"[UNKNOWN] {exc_type_name}: {exc_msg[:200]}"
        logger.warning("Unclassified error: %s", message)
        return ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.WARNING,
            action=RecoveryAction.ALERT_ADMIN,
            original_exception=exc,
            context=ctx,
            message=message,
        )

    @classmethod
    def register_rule(
        cls,
        exc_type_name: str,
        msg_pattern: Optional[str] = None,
        provider_pattern: Optional[str] = None,
        *,
        category: ErrorCategory,
        severity: ErrorSeverity,
        action: RecoveryAction,
    ):
        """Register a provider-specific classification rule."""
        msg_re = re.compile(msg_pattern, re.I) if msg_pattern else None
        prov_re = re.compile(provider_pattern, re.I) if provider_pattern else re.compile(".*")
        cls._provider_rules.append((prov_re, exc_type_name, msg_re, category, severity, action))


# ── Singleton ───────────────────────────────────────────────────

# The classifier is stateless (rules are class-level), so no instance needed.
classify = ErrorClassifier.classify
register_rule = ErrorClassifier.register_rule
