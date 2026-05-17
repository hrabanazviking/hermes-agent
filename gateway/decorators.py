"""
Structured Exception Handling Protocol

Two patterns for replacing bare ``except Exception: pass`` throughout the gateway:

1. ``@classified`` decorator — wraps async functions with error classification
2. ``safe()`` context manager — scoped blocks with guaranteed logging

Usage::

    from gateway.decorators import classified, safe

    @classified(default_return=None)
    async def deliver_message(platform, msg):
        ...

    async with safe("temp_cleanup", session_id=sid) as guard:
        await adapter.delete_message(chat_id, mid)
"""

from __future__ import annotations

import functools
import inspect
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, Set, Type

from .error_classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    RecoveryAction,
    classify,
)
from .recovery_engine import RecoveryEngine

logger = logging.getLogger(__name__)

# Global recovery engine reference — set by GatewayRunner on startup
_recovery_engine: Optional[RecoveryEngine] = None


def set_recovery_engine(engine: RecoveryEngine) -> None:
    """Register the recovery engine for the decorated functions."""
    global _recovery_engine
    _recovery_engine = engine


# ── Decorator ───────────────────────────────────────────────────

def classified(
    *,
    default_return: Any = None,
    reraise_categories: Optional[Set[ErrorCategory]] = None,
    location: str = "",
):
    """Decorator that catches, classifies, and handles exceptions.

    Args:
        default_return: Value returned when an exception is caught (and not re-raised).
        reraise_categories: Set of ErrorCategory values that should be re-raised
                           rather than swallowed. Default: {INTERNAL}.
        location: Optional identifier for telemetry. Auto-detected from function name.
    """

    cats = reraise_categories or {ErrorCategory.INTERNAL}

    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            loc = location or fn.__qualname__
            try:
                result = fn(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                # On success, clear retry counter
                if _recovery_engine:
                    _recovery_engine.register_retry_success(loc)
                return result
            except BaseException as exc:
                # Never classifies KeyboardInterrupt or SystemExit
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise

                ctx = _build_context(fn, args, kwargs, loc)
                classified_err = classify(exc, ctx)

                # Log if warranted
                if classified_err.should_log:
                    log_fn = _severity_to_log(classified_err.severity)
                    log_fn(
                        "%s → %s/%s/%s: %s",
                        loc, classified_err.category.name,
                        classified_err.severity.name,
                        classified_err.action.name,
                        classified_err.message[:200],
                        extra=classified_err.context.to_dict(),
                    )

                # Execute recovery
                if _recovery_engine:
                    try:
                        await _recovery_engine.execute(classified_err)
                    except Exception as recovery_err:
                        logger.exception("Recovery execution failed: %s", recovery_err)

                # Re-raise if category demands it
                if classified_err.category in cats:
                    raise exc from None

                return default_return

        return wrapper

    return decorator


# ── Context Manager ─────────────────────────────────────────────

class _SafeGuard:
    """Holds classification result and context from a ``safe()`` block."""

    def __init__(self):
        self.classified: Optional[ClassifiedError] = None
        self.caught: Optional[BaseException] = None
        self.handled: bool = False


@asynccontextmanager
async def safe(location: str, **context_kwargs):
    """Async context manager that classifies and handles exceptions in a block.

    Usage::

        async with safe("delete_temp_bubbles", session_id=sid) as guard:
            await adapter.delete_message(chat_id, mid)

        if guard.caught:
            # guard.classified has category, severity, action
            ...
    """

    guard = _SafeGuard()
    ctx = ErrorContext(location=location, **context_kwargs)
    try:
        yield guard
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        raise
    except BaseException as exc:
        guard.caught = exc
        guard.classified = classify(exc, ctx)

        if guard.classified.should_log:
            log_fn = _severity_to_log(guard.classified.severity)
            log_fn(
                "[safe] %s → %s/%s: %s",
                location, guard.classified.category.name,
                guard.classified.severity.name,
                guard.classified.message[:200],
                extra=guard.classified.context.to_dict(),
            )

        if _recovery_engine:
            try:
                await _recovery_engine.execute(guard.classified)
            except Exception as recovery_err:
                logger.exception("Recovery execution failed: %s", recovery_err)

        guard.handled = True


# ── Helpers ─────────────────────────────────────────────────────

def _build_context(
    fn: Callable,
    args: tuple,
    kwargs: dict,
    location: str,
) -> ErrorContext:
    """Extract platform_id, session_id, etc. from function arguments."""
    ctx = ErrorContext(location=location)

    # Try to find common argument names
    sig = None
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        params = bound.arguments
    except (TypeError, ValueError):
        params = kwargs or {}

    for key in ("platform_id", "session_id", "provider", "tool_name", "user_id"):
        if key in params and isinstance(params[key], str):
            setattr(ctx, key, params[key])

    # Also check for platform objects that have .platform_id
    if not ctx.platform_id:
        for val in list(params.values()):
            if hasattr(val, "platform_id"):
                ctx.platform_id = getattr(val, "platform_id", "")
                break

    return ctx


_SEVERITY_LOG_MAP = {
    ErrorSeverity.DEBUG: logger.debug,
    ErrorSeverity.INFO: logger.info,
    ErrorSeverity.WARNING: logger.warning,
    ErrorSeverity.ERROR: logger.error,
    ErrorSeverity.CRITICAL: logger.critical,
}


def _severity_to_log(severity: ErrorSeverity):
    return _SEVERITY_LOG_MAP.get(severity, logger.warning)


# Need asyncio for CancelledError reference
import asyncio
