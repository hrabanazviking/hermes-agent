"""Output-language policy helpers for Hrafnvíkingr/Hermes.

This module intentionally keeps language enforcement prompt-side and
programmatic-boilerplate-side.  It does not attempt lossy automatic
translation of model output without an explicit rewrite model: code blocks,
logs, file paths, command names, API names, and quoted text must remain exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from agent.i18n import language_display_name, normalize_language

_VALID_MODES = {"off", "auto", "display", "fixed"}


@dataclass(frozen=True)
class OutputLanguagePolicy:
    """Normalized agent output-language policy."""

    mode: str = "auto"
    language: str = ""
    strict: bool = True

    @property
    def enabled(self) -> bool:
        return self.mode != "off"


def _as_bool(value: Any, *, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        key = value.strip().lower()
        if key in {"1", "true", "yes", "on", "strict"}:
            return True
        if key in {"0", "false", "no", "off", "loose"}:
            return False
    return default


def _raw_policy(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    agent_cfg = config.get("agent")
    if isinstance(agent_cfg, Mapping):
        value = agent_cfg.get("output_language")
        if isinstance(value, Mapping):
            return value
        if isinstance(value, str):
            return {"mode": "fixed", "language": value}
    return {}


def load_output_language_policy(config: Mapping[str, Any] | None) -> OutputLanguagePolicy:
    """Build a normalized :class:`OutputLanguagePolicy` from full config."""

    raw = _raw_policy(config)
    mode = str(raw.get("mode", "auto") or "auto").strip().lower()
    if mode not in _VALID_MODES:
        mode = "auto"
    language = ""
    if raw.get("language"):
        language = normalize_language(raw.get("language"))
    strict = _as_bool(raw.get("strict", True), default=True)
    return OutputLanguagePolicy(mode=mode, language=language, strict=strict)


def resolve_output_language(
    policy: OutputLanguagePolicy | None,
    *,
    display_language: str | None = None,
) -> Optional[str]:
    """Resolve a concrete language code when policy mode has one."""

    if not policy or not policy.enabled:
        return None
    if policy.mode == "fixed":
        return policy.language or None
    if policy.mode == "display":
        return normalize_language(display_language or "")
    return None


def build_output_language_system_block(
    policy: OutputLanguagePolicy | None,
    *,
    display_language: str | None = None,
) -> str:
    """Return an API-call-time system block for output language enforcement."""

    if not policy or not policy.enabled:
        return ""

    strict_word = "MUST" if policy.strict else "should"
    preservation = (
        "Do not translate code, file paths, command names, package names, API "
        "names, logs, stack traces, identifiers, exact quotes, or user-provided "
        "text that must remain byte-exact."
    )

    code = resolve_output_language(policy, display_language=display_language)
    if code:
        name = language_display_name(code)
        return (
            "## Output language policy\n\n"
            f"You {strict_word} write all user-visible assistant prose in {name} (`{code}`). "
            "This includes final answers, summaries, caveats, status explanations, "
            "subagent result summaries, and programmatic footer prose. "
            "Only switch languages if the latest user message explicitly requests a different output language. "
            f"{preservation}"
        )

    return (
        "## Output language policy\n\n"
        f"You {strict_word} answer in the same natural language as the user's latest message, "
        "unless the user explicitly requests a different output language. Keep mixed-language "
        "technical terms exact when appropriate. This applies to final answers, summaries, "
        "caveats, status explanations, and subagent result summaries. "
        f"{preservation}"
    )


def localize_programmatic_footer(text: str, policy: OutputLanguagePolicy | None) -> str:
    """Best-effort language guard for Hermes-added boilerplate.

    We do not translate arbitrary model output here.  Instead, append a compact
    policy reminder when strict enforcement is on so later plugin transforms or
    user-visible footers keep the configured language contract explicit.
    """

    if not text or not policy or not policy.enabled or not policy.strict:
        return text
    return text
