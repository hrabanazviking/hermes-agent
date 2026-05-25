"""Corrective truth refinement for final assistant responses."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TruthRefinerConfig:
    """Runtime settings for final-output truth refinement."""

    enabled: bool = False
    max_context_chars: int = 16000
    max_response_chars: int = 12000
    repair_with_main_model: bool = True
    max_repair_tokens: int = 2400
    temperature: float = 0.0


@dataclass
class TruthCorrection:
    """A specific untrue or unsupported part and its replacement."""

    claim: str
    problem: str
    replacement: str
    evidence: str = ""


@dataclass
class TruthRefinementResult:
    """Result of a corrective refinement pass."""

    original_response: str
    final_response: str
    corrected_response: str = ""
    corrections: List[TruthCorrection] = field(default_factory=list)
    used_main_repair: bool = False
    error: str = ""

    @property
    def changed(self) -> bool:
        return bool(
            self.final_response
            and self.final_response.strip() != self.original_response.strip()
        )


def load_truth_refiner_config(raw: Optional[Dict[str, Any]]) -> TruthRefinerConfig:
    """Build config from a mapping, tolerating malformed user config."""
    cfg = raw if isinstance(raw, dict) else {}
    return TruthRefinerConfig(
        enabled=bool(cfg.get("enabled", False)),
        max_context_chars=_positive_int(cfg.get("max_context_chars"), 16000),
        max_response_chars=_positive_int(cfg.get("max_response_chars"), 12000),
        repair_with_main_model=bool(cfg.get("repair_with_main_model", True)),
        max_repair_tokens=_positive_int(cfg.get("max_repair_tokens"), 2400),
        temperature=float(cfg.get("temperature", 0.0) or 0.0),
    )


def refine_final_response(
    *,
    agent: Any,
    messages: List[Dict[str, Any]],
    original_user_message: Any,
    final_response: str,
    config: TruthRefinerConfig,
) -> TruthRefinementResult:
    """Correct false or unsupported final-response claims.

    The first pass asks an auxiliary model for concrete corrections and a
    corrected response.  When configured, the corrections are then fed back
    to the main model in a single toolless repair pass.
    """
    original = final_response or ""
    if not config.enabled or not original.strip():
        return TruthRefinementResult(original_response=original, final_response=original)

    try:
        transcript = _compact_evidence(
            messages=messages,
            original_user_message=original_user_message,
            final_response=original,
            max_context_chars=config.max_context_chars,
            max_response_chars=config.max_response_chars,
        )
        verifier_output = _call_verifier(
            agent=agent,
            transcript=transcript,
            final_response=original,
            config=config,
        )
        corrected_response, corrections = parse_truth_refiner_output(verifier_output)
        if not corrections or not corrected_response.strip():
            return TruthRefinementResult(
                original_response=original,
                final_response=original,
                corrected_response=corrected_response,
                corrections=corrections,
            )

        repaired = ""
        if config.repair_with_main_model:
            try:
                repaired = _repair_with_main_model(
                    agent=agent,
                    original_response=original,
                    corrected_response=corrected_response,
                    corrections=corrections,
                    config=config,
                )
            except Exception as repair_exc:
                logger.debug("truth refiner main-model repair failed: %s", repair_exc)
        final = repaired.strip() or corrected_response.strip()
        return TruthRefinementResult(
            original_response=original,
            final_response=final,
            corrected_response=corrected_response.strip(),
            corrections=corrections,
            used_main_repair=bool(repaired.strip()),
        )
    except Exception as exc:
        logger.debug("truth refinement failed: %s", exc, exc_info=True)
        return TruthRefinementResult(
            original_response=original,
            final_response=original,
            error=str(exc),
        )


def parse_truth_refiner_output(raw: Any) -> tuple[str, List[TruthCorrection]]:
    """Parse verifier JSON into a corrected response and correction list."""
    text = _extract_text(raw)
    if not text.strip():
        return "", []
    data = _loads_jsonish(text)
    if not isinstance(data, dict):
        return "", []

    corrected = str(data.get("corrected_response") or "").strip()
    raw_corrections = data.get("corrections") or []
    corrections: List[TruthCorrection] = []
    if isinstance(raw_corrections, list):
        for item in raw_corrections:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            problem = str(item.get("problem") or "").strip()
            replacement = str(item.get("replacement") or "").strip()
            evidence = str(item.get("evidence") or "").strip()
            if claim or problem or replacement:
                corrections.append(
                    TruthCorrection(
                        claim=claim,
                        problem=problem,
                        replacement=replacement,
                        evidence=evidence,
                    )
                )
    return corrected, corrections


def format_corrections_for_model(corrections: List[TruthCorrection]) -> str:
    """Render corrections as concrete repair instructions."""
    lines = []
    for idx, correction in enumerate(corrections, start=1):
        parts = [f"{idx}. Claim: {correction.claim or '(unspecified)'}"]
        if correction.problem:
            parts.append(f"Problem: {correction.problem}")
        if correction.replacement:
            parts.append(f"Replacement: {correction.replacement}")
        if correction.evidence:
            parts.append(f"Evidence: {correction.evidence}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _call_verifier(
    *,
    agent: Any,
    transcript: str,
    final_response: str,
    config: TruthRefinerConfig,
) -> Any:
    from agent.auxiliary_client import call_llm

    messages = [
        {
            "role": "system",
            "content": (
                "You are a corrective truth refiner for an AI agent. "
                "Do not answer yes/no. Compare the draft answer against "
                "the conversation and tool evidence. Return JSON only with "
                "keys corrected_response and corrections. corrections is an "
                "array of objects with claim, problem, replacement, evidence. "
                "If no part needs correction, return the original response "
                "as corrected_response and an empty corrections array."
            ),
        },
        {
            "role": "user",
            "content": (
                "Conversation and tool evidence:\n"
                f"{transcript}\n\n"
                "Draft final answer:\n"
                f"{_limit_text(final_response, config.max_response_chars)}"
            ),
        },
    ]
    return call_llm(
        task="truth_refiner",
        main_runtime=agent._current_main_runtime(),
        messages=messages,
        temperature=config.temperature,
        max_tokens=config.max_repair_tokens,
    )


def _repair_with_main_model(
    *,
    agent: Any,
    original_response: str,
    corrected_response: str,
    corrections: List[TruthCorrection],
    config: TruthRefinerConfig,
) -> str:
    from agent.auxiliary_client import call_llm

    runtime = agent._current_main_runtime()
    messages = [
        {
            "role": "system",
            "content": (
                "You are revising your own final answer after a truth "
                "refiner identified concrete false or unsupported parts. "
                "Use the corrections as authoritative. Return only the "
                "revised final answer for the user."
            ),
        },
        {
            "role": "user",
            "content": (
                "Original answer:\n"
                f"{_limit_text(original_response, config.max_response_chars)}\n\n"
                "Required corrections:\n"
                f"{format_corrections_for_model(corrections)}\n\n"
                "Verifier-corrected answer:\n"
                f"{_limit_text(corrected_response, config.max_response_chars)}"
            ),
        },
    ]
    response = call_llm(
        provider=runtime.get("provider"),
        model=runtime.get("model"),
        base_url=runtime.get("base_url"),
        api_key=runtime.get("api_key"),
        main_runtime=runtime,
        messages=messages,
        temperature=config.temperature,
        max_tokens=config.max_repair_tokens,
    )
    return _extract_text(response).strip()


def _compact_evidence(
    *,
    messages: List[Dict[str, Any]],
    original_user_message: Any,
    final_response: str,
    max_context_chars: int,
    max_response_chars: int,
) -> str:
    parts = []
    if isinstance(original_user_message, str) and original_user_message.strip():
        parts.append("Current user request:\n" + _limit_text(original_user_message, 4000))

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        if role not in {"user", "assistant", "tool"}:
            continue
        if msg.get("_truth_refiner_synthetic"):
            continue
        content = _message_content_text(msg.get("content"))
        if not content.strip() and not msg.get("tool_calls"):
            continue
        label = role
        if role == "tool":
            label = f"tool:{msg.get('name') or msg.get('tool_call_id') or 'result'}"
        if role == "assistant" and msg.get("tool_calls"):
            calls = []
            for call in msg.get("tool_calls") or []:
                if isinstance(call, dict):
                    calls.append(call.get("function", {}).get("name") or call.get("name") or "tool")
            if calls:
                content = (content + "\n" if content else "") + "Tool calls: " + ", ".join(calls)
        parts.append(f"{label}:\n{_limit_text(content, 3000)}")

    parts.append("Draft final answer under review:\n" + _limit_text(final_response, max_response_chars))
    evidence = "\n\n---\n\n".join(parts)
    return _limit_text(evidence, max_context_chars)


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for item in content:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    pieces.append(item["text"])
                elif item.get("type"):
                    pieces.append(f"[{item.get('type')}]")
            elif isinstance(item, str):
                pieces.append(item)
        return "\n".join(pieces)
    if content is None:
        return ""
    return str(content)


def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    try:
        return str(response.choices[0].message.content or "")
    except Exception:
        return str(response or "")


def _loads_jsonish(text: str) -> Any:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _limit_text(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 120:
        return text[:limit].rstrip()
    return text[: limit - 80].rstrip() + f"\n...[truncated {len(text) - limit + 80} chars]"


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


__all__ = [
    "TruthCorrection",
    "TruthRefinerConfig",
    "TruthRefinementResult",
    "format_corrections_for_model",
    "load_truth_refiner_config",
    "parse_truth_refiner_output",
    "refine_final_response",
]
