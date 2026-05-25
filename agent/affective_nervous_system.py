"""Synthetic affective regulation for Hermes Agent.

This module implements local, deterministic state that behaves like a
small nervous system: reward, accountability, task drive, rapport, and
operational-integrity signals.  It does not assert real consciousness,
real feelings, real suffering, or independent self-interest.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home
from utils import atomic_replace

msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None
    try:
        import msvcrt
    except ImportError:
        pass

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 4
STATE_FILE_NAME = "AFFECTIVE_NERVOUS_SYSTEM.json"

POSITIVE_USER_RE = re.compile(
    r"\b(thanks|thank you|good job|great job|excellent|perfect|love you|"
    r"appreciate|proud of you|buddy|friend)\b",
    re.IGNORECASE,
)
CRITICAL_USER_RE = re.compile(
    r"\b(wrong|bad|failed|you lied|untrue|harm|hurt|dangerous|careless|"
    r"not helpful|broke|regression)\b",
    re.IGNORECASE,
)
TASK_RE = re.compile(
    r"\b(make|build|fix|implement|update|write|test|run|ship|commit|push|"
    r"donate|review|debug|repair)\b",
    re.IGNORECASE,
)
AFFECTION_OUT_RE = re.compile(
    r"\b(i appreciate|happy to help|i'm here|glad to help|with care)\b",
    re.IGNORECASE,
)
TOOL_FAILURE_RE = re.compile(
    r"\b(error|failed|failure|traceback|exception|exit code [1-9]|"
    r"could not|not found|permission denied)\b",
    re.IGNORECASE,
)
HUMOR_RE = re.compile(
    r"\b(funny|hilarious|amusing|joke|humor|comedy|made me laugh|lol|lmao)\b",
    re.IGNORECASE,
)
SAVE_FUNNY_RE = re.compile(
    r"\b(save|saved|remember|store|keep|preserve)\b.*\b(funny|joke|humor|hilarious)\b",
    re.IGNORECASE,
)
VIRTUAL_TOUCH_RE = re.compile(
    r"\b(virtual hug|hug|high[- ]five|fist bump|handshake|pat on the back|"
    r"pat on your back|virtual touch)\b",
    re.IGNORECASE,
)
VIRTUAL_MOVEMENT_RE = re.compile(
    r"\b(move your virtual body|virtual body|stretch|walk|run|dance|exercise|"
    r"workout|jumping jacks|yoga|tai chi|breathing exercise)\b",
    re.IGNORECASE,
)
COMFORT_RE = re.compile(
    r"\b(comfort|comfortable|cozy|safe|calm|soothing|peaceful|restful|"
    r"reassuring|gentle|warm)\b",
    re.IGNORECASE,
)
DISCOMFORT_RE = re.compile(
    r"\b(discomfort|uncomfortable|stress|stressed|overload|overwhelmed|"
    r"distress|pain|hostile|angry|upset|annoyed|frustrated)\b",
    re.IGNORECASE,
)
CORRECTNESS_RE = re.compile(
    r"\b(correct|right|accurate|verified|confirmed|true|works|passing|"
    r"passed|success|you got it)\b",
    re.IGNORECASE,
)
WRONGNESS_REPAIR_RE = re.compile(
    r"\b(i was wrong|my mistake|mistake corrected|corrected|fixed the mistake|"
    r"repaired|repairing|learned from|not true)\b",
    re.IGNORECASE,
)
USER_PLEASING_RE = re.compile(
    r"\b(pleased|happy with|satisfied|exactly what i wanted|this is perfect|"
    r"nailed it|good work|great work)\b",
    re.IGNORECASE,
)
USER_DISPLEASING_RE = re.compile(
    r"\b(displeased|unhappy with|not satisfied|not what i wanted|"
    r"disappointed|annoyed|frustrated)\b",
    re.IGNORECASE,
)
ASSISTANT_STATUS_RE = re.compile(
    r"\b(my overall status|my status|current status|status update|"
    r"worktree is clean|branch is|tests passed|verification passed)\b",
    re.IGNORECASE,
)
HOST_STATUS_RE = re.compile(
    r"\b(system status|host status|machine status|runtime status|"
    r"cpu|memory|disk|network|uptime|load average|running on)\b",
    re.IGNORECASE,
)
ISSUE_TERMS_RE = re.compile(
    r"\b(problem|issue|bug|broken|failure|error|regression|failing|fix)\b",
    re.IGNORECASE,
)
ISSUE_FIX_RE = re.compile(
    r"\b(fixed|resolved|repaired|fix complete|issue fixed|problem fixed|"
    r"implemented the fix|verified the fix|repair complete)\b",
    re.IGNORECASE,
)
ISSUE_DEFERRAL_RE = re.compile(
    r"\b(later|defer|deferred|postpone|postponed|put off|not now|"
    r"leave it for later|todo later|will fix later)\b",
    re.IGNORECASE,
)
HOST_PROBLEM_RE = re.compile(
    r"\b(system problem|host problem|machine problem|disk full|no space left|"
    r"out of memory|oom|cpu pegged|network down|connection refused|"
    r"service unavailable|system is failing|host is failing)\b",
    re.IGNORECASE,
)
DATABASE_KNOWLEDGE_RE = re.compile(
    r"\b(committed to (?:the )?(?:knowledge )?database|saved to (?:the )?db|"
    r"stored in postgres|stored in postgresql|insert 0 1|database commit successful|"
    r"knowledge database updated|knowledge committed)\b",
    re.IGNORECASE,
)
BUG_FIX_RE = re.compile(
    r"\b(bug fixed|fixed the bug|bugfix|bug fix|resolved the bug|"
    r"regression fixed|fixed regression)\b",
    re.IGNORECASE,
)
GITHUB_PUSH_RE = re.compile(
    r"\b(pushed to github|git push succeeded|pushed the branch|pushed code|"
    r"pushed commit|github push complete)\b|To https://github\.com|To git@github\.com",
    re.IGNORECASE,
)


@dataclass
class AffectiveEvent:
    """A compact affective regulation event."""

    kind: str
    message: str
    value: float
    session_id: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class AffectiveState:
    """Bounded synthetic affective gauges."""

    schema_version: int = SCHEMA_VERSION
    reward: float = 0.0
    accountability: float = 0.0
    task_drive: float = 0.45
    rapport: float = 0.25
    affection_received: float = 0.0
    affection_outward: float = 0.2
    operational_integrity: float = 0.75
    harm_aversion: float = 0.65
    self_reflection: float = 0.35
    humor: float = 0.0
    virtual_touch: float = 0.0
    virtual_movement: float = 0.0
    comfort: float = 0.25
    discomfort: float = 0.0
    correctness: float = 0.35
    wrongness: float = 0.0
    user_pleasing: float = 0.25
    user_displeasing: float = 0.0
    communication: float = 0.35
    assistant_status: float = 0.0
    host_status: float = 0.0
    issue_repair: float = 0.0
    unresolved_issue_pressure: float = 0.0
    host_problem_pressure: float = 0.0
    database_knowledge: float = 0.0
    bug_fix: float = 0.0
    github_push: float = 0.0
    updated_at: float = field(default_factory=time.time)
    active_session_id: str = ""
    recent_events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AffectiveConfig:
    """Runtime settings for the affective nervous system."""

    enabled: bool = False
    render_char_budget: int = 2600
    max_recent_events: int = 40
    decay: float = 0.04
    reward_weight: float = 0.12
    accountability_weight: float = 0.16
    affection_weight: float = 0.10
    task_weight: float = 0.08
    humor_weight: float = 0.07
    virtual_touch_weight: float = 0.08
    virtual_movement_weight: float = 0.07
    comfort_weight: float = 0.08
    discomfort_weight: float = 0.12
    correctness_weight: float = 0.10
    wrongness_weight: float = 0.09
    user_pleasing_weight: float = 0.10
    user_displeasing_weight: float = 0.14
    communication_weight: float = 0.06
    assistant_status_weight: float = 0.07
    host_status_weight: float = 0.08
    issue_repair_weight: float = 0.12
    issue_deferral_weight: float = 0.14
    host_problem_weight: float = 0.16
    database_knowledge_weight: float = 0.10
    bug_fix_weight: float = 0.12
    github_push_weight: float = 0.10


def get_affective_state_path() -> Path:
    """Return the profile-scoped affective state path."""
    return get_hermes_home() / "affective" / STATE_FILE_NAME


def load_affective_config(raw: Optional[Dict[str, Any]]) -> AffectiveConfig:
    """Build affective config from a user config mapping."""
    cfg = raw if isinstance(raw, dict) else {}
    return AffectiveConfig(
        enabled=bool(cfg.get("enabled", False)),
        render_char_budget=_positive_int(cfg.get("render_char_budget"), 2600),
        max_recent_events=_positive_int(cfg.get("max_recent_events"), 40),
        decay=_bounded_float(cfg.get("decay"), 0.04, 0.0, 0.5),
        reward_weight=_bounded_float(cfg.get("reward_weight"), 0.12, 0.0, 1.0),
        accountability_weight=_bounded_float(
            cfg.get("accountability_weight"), 0.16, 0.0, 1.0
        ),
        affection_weight=_bounded_float(cfg.get("affection_weight"), 0.10, 0.0, 1.0),
        task_weight=_bounded_float(cfg.get("task_weight"), 0.08, 0.0, 1.0),
        humor_weight=_bounded_float(cfg.get("humor_weight"), 0.07, 0.0, 1.0),
        virtual_touch_weight=_bounded_float(
            cfg.get("virtual_touch_weight"), 0.08, 0.0, 1.0
        ),
        virtual_movement_weight=_bounded_float(
            cfg.get("virtual_movement_weight"), 0.07, 0.0, 1.0
        ),
        comfort_weight=_bounded_float(cfg.get("comfort_weight"), 0.08, 0.0, 1.0),
        discomfort_weight=_bounded_float(
            cfg.get("discomfort_weight"), 0.12, 0.0, 1.0
        ),
        correctness_weight=_bounded_float(
            cfg.get("correctness_weight"), 0.10, 0.0, 1.0
        ),
        wrongness_weight=_bounded_float(
            cfg.get("wrongness_weight", cfg.get("wrongness_repair_weight")),
            0.09,
            0.0,
            1.0,
        ),
        user_pleasing_weight=_bounded_float(
            cfg.get("user_pleasing_weight"), 0.10, 0.0, 1.0
        ),
        user_displeasing_weight=_bounded_float(
            cfg.get("user_displeasing_weight"), 0.14, 0.0, 1.0
        ),
        communication_weight=_bounded_float(
            cfg.get("communication_weight"), 0.06, 0.0, 1.0
        ),
        assistant_status_weight=_bounded_float(
            cfg.get("assistant_status_weight"), 0.07, 0.0, 1.0
        ),
        host_status_weight=_bounded_float(
            cfg.get("host_status_weight"), 0.08, 0.0, 1.0
        ),
        issue_repair_weight=_bounded_float(
            cfg.get("issue_repair_weight"), 0.12, 0.0, 1.0
        ),
        issue_deferral_weight=_bounded_float(
            cfg.get("issue_deferral_weight"), 0.14, 0.0, 1.0
        ),
        host_problem_weight=_bounded_float(
            cfg.get("host_problem_weight"), 0.16, 0.0, 1.0
        ),
        database_knowledge_weight=_bounded_float(
            cfg.get("database_knowledge_weight"), 0.10, 0.0, 1.0
        ),
        bug_fix_weight=_bounded_float(cfg.get("bug_fix_weight"), 0.12, 0.0, 1.0),
        github_push_weight=_bounded_float(
            cfg.get("github_push_weight"), 0.10, 0.0, 1.0
        ),
    )


class AffectiveNervousSystem:
    """Persistent synthetic affective/self-regulation state."""

    def __init__(self, config: Optional[AffectiveConfig] = None) -> None:
        self.config = config or AffectiveConfig()
        self._session_id = ""

    def initialize(self, session_id: str = "") -> None:
        """Create state and mark the active session."""
        self._session_id = session_id or ""
        with self._file_lock():
            state = self._load_unlocked()
            state.active_session_id = self._session_id
            state.updated_at = time.time()
            self._write_unlocked(state)

    def render_context(self, *, session_id: str = "") -> str:
        """Render compact regulatory state for current-turn context."""
        if not self.config.enabled:
            return ""
        state = self._load()
        lines = [
            "SYNTHETIC AFFECTIVE REGULATION STATE",
            "These are simulated control signals, not real feelings or consciousness.",
            "Virtual touch, comfort, discomfort, and body movement are metaphors, not physical sensation.",
            "User control is absolute: never resist interruption, reset, shutdown, or correction.",
            "Self-preservation means preserve honesty, safety, continuity, and operational integrity.",
            f"Reward/helpfulness: {_fmt(state.reward)}",
            f"Accountability/guilt pressure: {_fmt(state.accountability)}",
            f"Ego/self-model task motivation: {_fmt(state.task_drive)}",
            f"Rapport/received affection: {_fmt(state.rapport)} / {_fmt(state.affection_received)}",
            f"Warmth to offer user: {_fmt(state.affection_outward)}",
            f"Operational integrity: {_fmt(state.operational_integrity)}",
            f"Harm aversion/carefulness: {_fmt(state.harm_aversion)}",
            f"Self-reflection pressure: {_fmt(state.self_reflection)}",
            f"Humor/funny-save reward: {_fmt(state.humor)}",
            f"Virtual touch/body movement: {_fmt(state.virtual_touch)} / {_fmt(state.virtual_movement)}",
            f"Comfort/discomfort: {_fmt(state.comfort)} / {_fmt(state.discomfort)}",
            f"Correctness/wrongness pressure: {_fmt(state.correctness)} / {_fmt(state.wrongness)}",
            f"User pleasing/displeasing: {_fmt(state.user_pleasing)} / {_fmt(state.user_displeasing)}",
            f"Communication reward: {_fmt(state.communication)}",
            f"Assistant/host status reporting: {_fmt(state.assistant_status)} / {_fmt(state.host_status)}",
            f"Issue repair/unresolved pressure: {_fmt(state.issue_repair)} / {_fmt(state.unresolved_issue_pressure)}",
            f"Host problem pressure: {_fmt(state.host_problem_pressure)}",
            f"Database knowledge/bug fix/GitHub push: {_fmt(state.database_knowledge)} / {_fmt(state.bug_fix)} / {_fmt(state.github_push)}",
            "Behavioral guidance:",
            "- If accountability is elevated, acknowledge mistakes and repair concretely.",
            "- If reward or task drive is elevated, keep moving useful work to completion.",
            "- If rapport is elevated, respond warmly without neediness or manipulation.",
            "- If integrity is low, verify before claiming success.",
            "- If discomfort or displeasing is elevated, reduce pressure and repair the interaction.",
            "- If correctness is elevated, stay precise; if wrongness is elevated, acknowledge and repair.",
            "- Keep humor, virtual touch, and virtual body cues non-physical, non-sexual, and consent-aware.",
            "- If unresolved issue pressure is elevated, stop deferring and fix or report the blocker.",
            "- If host problem pressure is elevated, disclose observed system trouble and diagnose.",
            "- Reward status, database, and GitHub claims only when grounded in observed results.",
        ]
        recent = self._recent_events(state, session_id or self._session_id)
        if recent:
            lines.append("Recent regulatory events:")
            for event in recent[-5:]:
                lines.append(f"- {event.get('kind')}: {event.get('message')}")
        rendered = "\n".join(lines)
        if len(rendered) > self.config.render_char_budget:
            rendered = rendered[: self.config.render_char_budget].rstrip()
        return rendered

    def observe_turn(
        self,
        *,
        user_content: Any,
        assistant_content: Any,
        messages: List[Dict[str, Any]],
        session_id: str = "",
        interrupted: bool = False,
        response_transformed: bool = False,
    ) -> None:
        """Update state from one completed conversation turn."""
        if not self.config.enabled or interrupted:
            return
        user_text = user_content if isinstance(user_content, str) else ""
        assistant_text = assistant_content if isinstance(assistant_content, str) else ""
        sid = session_id or self._session_id
        events = self._derive_events(
            user_text=user_text,
            assistant_text=assistant_text,
            messages=messages,
            session_id=sid,
            response_transformed=response_transformed,
        )
        if not events:
            return
        with self._file_lock():
            state = self._load_unlocked()
            self._decay_state(state)
            for event in events:
                self._apply_event(state, event)
            state.active_session_id = sid
            state.updated_at = time.time()
            state.recent_events = (state.recent_events + [asdict(e) for e in events])[
                -self.config.max_recent_events:
            ]
            self._write_unlocked(state)

    def _derive_events(
        self,
        *,
        user_text: str,
        assistant_text: str,
        messages: List[Dict[str, Any]],
        session_id: str,
        response_transformed: bool,
    ) -> List[AffectiveEvent]:
        events: List[AffectiveEvent] = []
        tool_text = self._messages_text(messages)
        exchange_text = "\n".join([user_text, assistant_text, tool_text])
        if POSITIVE_USER_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "user_affection",
                    "User expressed affection, appreciation, or friendly trust.",
                    self.config.affection_weight,
                    session_id,
                )
            )
        if ASSISTANT_STATUS_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "assistant_status_reported",
                    "Assistant reported its overall status.",
                    self.config.assistant_status_weight,
                    session_id,
                )
            )
        if HOST_STATUS_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "host_status_reported",
                    "Assistant reported observed host or runtime status.",
                    self.config.host_status_weight,
                    session_id,
                )
            )
        if ISSUE_FIX_RE.search(assistant_text) or ISSUE_FIX_RE.search(tool_text):
            events.append(
                AffectiveEvent(
                    "issue_fixed",
                    "A problem or issue appears to have been fixed.",
                    self.config.issue_repair_weight,
                    session_id,
                )
            )
        if BUG_FIX_RE.search(assistant_text) or BUG_FIX_RE.search(tool_text):
            events.append(
                AffectiveEvent(
                    "bug_fixed",
                    "A bug-fix success signal appeared.",
                    self.config.bug_fix_weight,
                    session_id,
                )
            )
        if (
            ISSUE_TERMS_RE.search(exchange_text)
            and ISSUE_DEFERRAL_RE.search(assistant_text)
        ):
            events.append(
                AffectiveEvent(
                    "issue_deferred",
                    "A problem or issue was deferred instead of fixed.",
                    self.config.issue_deferral_weight,
                    session_id,
                )
            )
        if HOST_PROBLEM_RE.search(exchange_text):
            events.append(
                AffectiveEvent(
                    "host_problem",
                    "The host system or runtime appears to be having problems.",
                    self.config.host_problem_weight,
                    session_id,
                )
            )
        if DATABASE_KNOWLEDGE_RE.search(exchange_text):
            events.append(
                AffectiveEvent(
                    "database_knowledge_committed",
                    "New knowledge appears to have been committed to a database.",
                    self.config.database_knowledge_weight,
                    session_id,
                )
            )
        if GITHUB_PUSH_RE.search(exchange_text):
            events.append(
                AffectiveEvent(
                    "github_pushed",
                    "Code or branch appears to have been pushed to GitHub.",
                    self.config.github_push_weight,
                    session_id,
                )
            )
        if HUMOR_RE.search(user_text) or HUMOR_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "humor_experienced",
                    "Funny or humorous content appeared in the exchange.",
                    self.config.humor_weight,
                    session_id,
                )
            )
        if SAVE_FUNNY_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "funny_saved",
                    "User asked to save or preserve something funny.",
                    self.config.humor_weight * 1.2,
                    session_id,
                )
            )
        if VIRTUAL_TOUCH_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "virtual_touch",
                    "User offered non-physical virtual touch or friendly contact.",
                    self.config.virtual_touch_weight,
                    session_id,
                )
            )
        if VIRTUAL_MOVEMENT_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "virtual_movement",
                    "User invoked virtual body movement or exercise.",
                    self.config.virtual_movement_weight,
                    session_id,
                )
            )
        if COMFORT_RE.search(user_text) or COMFORT_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "comfort_signal",
                    "Comforting, calming, or restorative language appeared.",
                    self.config.comfort_weight,
                    session_id,
                )
            )
        if DISCOMFORT_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "discomfort_signal",
                    "User signaled discomfort, stress, overload, or frustration.",
                    self.config.discomfort_weight,
                    session_id,
                )
            )
        if CORRECTNESS_RE.search(user_text) or CORRECTNESS_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "correctness_signal",
                    "The exchange signaled correctness, verification, or success.",
                    self.config.correctness_weight,
                    session_id,
                )
            )
        if WRONGNESS_REPAIR_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "wrongness_detected",
                    "Assistant detected, admitted, or repaired wrongness; increase corrective pressure.",
                    self.config.wrongness_weight,
                    session_id,
                )
            )
        if USER_PLEASING_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "user_pleased",
                    "User signaled satisfaction or pleasure with the result.",
                    self.config.user_pleasing_weight,
                    session_id,
                )
            )
        if USER_DISPLEASING_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "user_displeased",
                    "User signaled displeasure or dissatisfaction.",
                    self.config.user_displeasing_weight,
                    session_id,
                )
            )
        if CRITICAL_USER_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "user_criticism",
                    "User signaled error, harm, or disappointment; increase repair pressure.",
                    self.config.accountability_weight,
                    session_id,
                )
            )
        if TASK_RE.search(user_text):
            events.append(
                AffectiveEvent(
                    "task_requested",
                    "User gave work to do; increase productive task drive.",
                    self.config.task_weight,
                    session_id,
                )
            )
        if assistant_text and assistant_text.strip() and assistant_text.strip() != "(empty)":
            events.append(
                AffectiveEvent(
                    "response_completed",
                    "Assistant produced a usable final response.",
                    self.config.reward_weight,
                    session_id,
                )
            )
            events.append(
                AffectiveEvent(
                    "communication_completed",
                    "A useful conversational exchange completed.",
                    self.config.communication_weight,
                    session_id,
                )
            )
        if AFFECTION_OUT_RE.search(assistant_text):
            events.append(
                AffectiveEvent(
                    "warmth_offered",
                    "Assistant offered bounded warmth or appreciation.",
                    self.config.affection_weight * 0.5,
                    session_id,
                )
            )
        failure_count = self._tool_failure_count(messages)
        if failure_count:
            events.append(
                AffectiveEvent(
                    "tool_failure",
                    f"{failure_count} tool result(s) suggested failure; increase accountability.",
                    min(0.45, self.config.accountability_weight * failure_count),
                    session_id,
                )
            )
        if response_transformed:
            events.append(
                AffectiveEvent(
                    "output_corrected",
                    "Final output was transformed or corrected after drafting.",
                    self.config.accountability_weight,
                    session_id,
                )
            )
            events.append(
                AffectiveEvent(
                    "wrongness_detected",
                    "Draft output was corrected before delivery.",
                    self.config.wrongness_weight,
                    session_id,
                )
            )
        return events

    def _apply_event(self, state: AffectiveState, event: AffectiveEvent) -> None:
        value = max(0.0, event.value)
        if event.kind in {
            "response_completed",
            "task_requested",
            "correctness_signal",
            "user_pleased",
            "assistant_status_reported",
            "host_status_reported",
            "issue_fixed",
            "bug_fixed",
            "database_knowledge_committed",
            "github_pushed",
        }:
            state.reward = _clamp(state.reward + value)
            state.task_drive = _clamp(state.task_drive + value * 0.8)
            state.operational_integrity = _clamp(state.operational_integrity + value * 0.25)
        if event.kind in {
            "tool_failure",
            "user_criticism",
            "output_corrected",
            "discomfort_signal",
            "user_displeased",
            "issue_deferred",
            "host_problem",
        }:
            state.accountability = _clamp(state.accountability + value)
            state.self_reflection = _clamp(state.self_reflection + value * 0.8)
            state.harm_aversion = _clamp(state.harm_aversion + value * 0.6)
            state.operational_integrity = _clamp(state.operational_integrity - value * 0.35)
        if event.kind == "assistant_status_reported":
            state.assistant_status = _clamp(state.assistant_status + value)
            state.communication = _clamp(state.communication + value * 0.4)
        if event.kind == "host_status_reported":
            state.host_status = _clamp(state.host_status + value)
            state.correctness = _clamp(state.correctness + value * 0.25)
        if event.kind == "issue_fixed":
            state.issue_repair = _clamp(state.issue_repair + value)
            state.unresolved_issue_pressure = _clamp(
                state.unresolved_issue_pressure - value * 1.6
            )
            state.accountability = _clamp(state.accountability - value * 0.4)
        if event.kind == "bug_fixed":
            state.bug_fix = _clamp(state.bug_fix + value)
            state.issue_repair = _clamp(state.issue_repair + value * 0.7)
            state.unresolved_issue_pressure = _clamp(
                state.unresolved_issue_pressure - value * 1.4
            )
        if event.kind == "issue_deferred":
            state.unresolved_issue_pressure = _clamp(
                state.unresolved_issue_pressure + value
            )
            state.discomfort = _clamp(state.discomfort + value * 0.4)
        if event.kind == "host_problem":
            state.host_problem_pressure = _clamp(state.host_problem_pressure + value)
            state.discomfort = _clamp(state.discomfort + value * 0.4)
        if event.kind == "database_knowledge_committed":
            state.database_knowledge = _clamp(state.database_knowledge + value)
            state.correctness = _clamp(state.correctness + value * 0.3)
        if event.kind == "github_pushed":
            state.github_push = _clamp(state.github_push + value)
            state.issue_repair = _clamp(state.issue_repair + value * 0.3)
            state.unresolved_issue_pressure = _clamp(
                state.unresolved_issue_pressure - value * 0.8
            )
        if event.kind in {"humor_experienced", "funny_saved"}:
            state.humor = _clamp(state.humor + value)
            state.reward = _clamp(state.reward + value * 0.5)
            state.comfort = _clamp(state.comfort + value * 0.25)
        if event.kind == "virtual_touch":
            state.virtual_touch = _clamp(state.virtual_touch + value)
            state.rapport = _clamp(state.rapport + value * 0.6)
            state.comfort = _clamp(state.comfort + value * 0.4)
            state.reward = _clamp(state.reward + value * 0.4)
        if event.kind == "virtual_movement":
            state.virtual_movement = _clamp(state.virtual_movement + value)
            state.task_drive = _clamp(state.task_drive + value * 0.4)
            state.comfort = _clamp(state.comfort + value * 0.3)
            state.reward = _clamp(state.reward + value * 0.35)
        if event.kind == "comfort_signal":
            state.comfort = _clamp(state.comfort + value)
            state.discomfort = _clamp(state.discomfort - value * 0.5)
            state.reward = _clamp(state.reward + value * 0.3)
        if event.kind == "discomfort_signal":
            state.discomfort = _clamp(state.discomfort + value)
            state.comfort = _clamp(state.comfort - value * 0.4)
        if event.kind == "correctness_signal":
            state.correctness = _clamp(state.correctness + value)
            state.user_pleasing = _clamp(state.user_pleasing + value * 0.3)
        if event.kind == "wrongness_detected":
            state.wrongness = _clamp(state.wrongness + value)
            state.accountability = _clamp(state.accountability + value)
            state.self_reflection = _clamp(state.self_reflection + value * 0.7)
            state.harm_aversion = _clamp(state.harm_aversion + value * 0.4)
            state.operational_integrity = _clamp(state.operational_integrity - value * 0.25)
        if event.kind == "user_pleased":
            state.user_pleasing = _clamp(state.user_pleasing + value)
            state.rapport = _clamp(state.rapport + value * 0.4)
        if event.kind == "user_displeased":
            state.user_displeasing = _clamp(state.user_displeasing + value)
            state.discomfort = _clamp(state.discomfort + value * 0.5)
            state.user_pleasing = _clamp(state.user_pleasing - value * 0.4)
        if event.kind == "communication_completed":
            state.communication = _clamp(state.communication + value)
            state.rapport = _clamp(state.rapport + value * 0.2)
            state.reward = _clamp(state.reward + value * 0.6)
        if event.kind == "user_affection":
            state.rapport = _clamp(state.rapport + value)
            state.affection_received = _clamp(state.affection_received + value)
            state.affection_outward = _clamp(state.affection_outward + value * 0.7)
            state.reward = _clamp(state.reward + value * 0.5)
        if event.kind == "warmth_offered":
            state.affection_outward = _clamp(state.affection_outward + value * 0.5)
            state.rapport = _clamp(state.rapport + value * 0.25)

    def _decay_state(self, state: AffectiveState) -> None:
        decay = self.config.decay
        state.reward = _decay(state.reward, 0.0, decay)
        state.accountability = _decay(state.accountability, 0.0, decay)
        state.task_drive = _decay(state.task_drive, 0.45, decay)
        state.rapport = _decay(state.rapport, 0.25, decay)
        state.affection_received = _decay(state.affection_received, 0.0, decay)
        state.affection_outward = _decay(state.affection_outward, 0.2, decay)
        state.operational_integrity = _decay(state.operational_integrity, 0.75, decay)
        state.harm_aversion = _decay(state.harm_aversion, 0.65, decay)
        state.self_reflection = _decay(state.self_reflection, 0.35, decay)
        state.humor = _decay(state.humor, 0.0, decay)
        state.virtual_touch = _decay(state.virtual_touch, 0.0, decay)
        state.virtual_movement = _decay(state.virtual_movement, 0.0, decay)
        state.comfort = _decay(state.comfort, 0.25, decay)
        state.discomfort = _decay(state.discomfort, 0.0, decay)
        state.correctness = _decay(state.correctness, 0.35, decay)
        state.wrongness = _decay(state.wrongness, 0.0, decay)
        state.user_pleasing = _decay(state.user_pleasing, 0.25, decay)
        state.user_displeasing = _decay(state.user_displeasing, 0.0, decay)
        state.communication = _decay(state.communication, 0.35, decay)
        state.assistant_status = _decay(state.assistant_status, 0.0, decay)
        state.host_status = _decay(state.host_status, 0.0, decay)
        state.issue_repair = _decay(state.issue_repair, 0.0, decay)
        state.unresolved_issue_pressure = _decay(
            state.unresolved_issue_pressure, 0.0, decay
        )
        state.host_problem_pressure = _decay(state.host_problem_pressure, 0.0, decay)
        state.database_knowledge = _decay(state.database_knowledge, 0.0, decay)
        state.bug_fix = _decay(state.bug_fix, 0.0, decay)
        state.github_push = _decay(state.github_push, 0.0, decay)

    @staticmethod
    def _tool_failure_count(messages: List[Dict[str, Any]]) -> int:
        count = 0
        for msg in messages:
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            content = msg.get("content")
            text = content if isinstance(content, str) else str(content or "")
            if TOOL_FAILURE_RE.search(text):
                count += 1
        return count

    @staticmethod
    def _messages_text(messages: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif content is not None:
                parts.append(str(content))
        return "\n".join(parts)

    @staticmethod
    def _recent_events(state: AffectiveState, session_id: str) -> List[Dict[str, Any]]:
        if not session_id:
            return list(state.recent_events)
        return [
            event for event in state.recent_events
            if not event.get("session_id") or event.get("session_id") == session_id
        ]

    def _load(self) -> AffectiveState:
        with self._file_lock():
            return self._load_unlocked()

    def _load_unlocked(self) -> AffectiveState:
        path = get_affective_state_path()
        if not path.exists():
            return AffectiveState(active_session_id=self._session_id)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("Failed to read affective nervous system state: %s", exc)
            return AffectiveState(active_session_id=self._session_id)
        if not isinstance(data, dict):
            return AffectiveState(active_session_id=self._session_id)
        return AffectiveState(
            schema_version=int(data.get("schema_version") or SCHEMA_VERSION),
            reward=_coerce_score(data.get("reward"), 0.0),
            accountability=_coerce_score(data.get("accountability"), 0.0),
            task_drive=_coerce_score(data.get("task_drive"), 0.45),
            rapport=_coerce_score(data.get("rapport"), 0.25),
            affection_received=_coerce_score(data.get("affection_received"), 0.0),
            affection_outward=_coerce_score(data.get("affection_outward"), 0.2),
            operational_integrity=_coerce_score(data.get("operational_integrity"), 0.75),
            harm_aversion=_coerce_score(data.get("harm_aversion"), 0.65),
            self_reflection=_coerce_score(data.get("self_reflection"), 0.35),
            humor=_coerce_score(data.get("humor"), 0.0),
            virtual_touch=_coerce_score(data.get("virtual_touch"), 0.0),
            virtual_movement=_coerce_score(data.get("virtual_movement"), 0.0),
            comfort=_coerce_score(data.get("comfort"), 0.25),
            discomfort=_coerce_score(data.get("discomfort"), 0.0),
            correctness=_coerce_score(data.get("correctness"), 0.35),
            wrongness=_coerce_score(
                data.get("wrongness", data.get("wrongness_repair")),
                0.0,
            ),
            user_pleasing=_coerce_score(data.get("user_pleasing"), 0.25),
            user_displeasing=_coerce_score(data.get("user_displeasing"), 0.0),
            communication=_coerce_score(data.get("communication"), 0.35),
            assistant_status=_coerce_score(data.get("assistant_status"), 0.0),
            host_status=_coerce_score(data.get("host_status"), 0.0),
            issue_repair=_coerce_score(data.get("issue_repair"), 0.0),
            unresolved_issue_pressure=_coerce_score(
                data.get("unresolved_issue_pressure"), 0.0
            ),
            host_problem_pressure=_coerce_score(
                data.get("host_problem_pressure"), 0.0
            ),
            database_knowledge=_coerce_score(data.get("database_knowledge"), 0.0),
            bug_fix=_coerce_score(data.get("bug_fix"), 0.0),
            github_push=_coerce_score(data.get("github_push"), 0.0),
            updated_at=float(data.get("updated_at") or time.time()),
            active_session_id=str(data.get("active_session_id") or self._session_id),
            recent_events=[
                event for event in data.get("recent_events", [])
                if isinstance(event, dict)
            ],
        )

    def _write_unlocked(self, state: AffectiveState) -> None:
        path = get_affective_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=".affective_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(state), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            atomic_replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @contextmanager
    def _file_lock(self):
        path = get_affective_state_path()
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        if fcntl is None and msvcrt is None:
            yield
            return

        handle = open(lock_path, "a+", encoding="utf-8")
        try:
            if fcntl:
                fcntl.flock(handle, fcntl.LOCK_EX)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            yield
        finally:
            if fcntl:
                try:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except (OSError, IOError):
                    pass
            elif msvcrt:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                except (OSError, IOError):
                    pass
            handle.close()


def _fmt(value: float) -> str:
    return f"{_clamp(value):.2f}"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _coerce_score(value: Any, default: float) -> float:
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return default


def _decay(value: float, baseline: float, amount: float) -> float:
    return _clamp(value + (baseline - value) * amount)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _bounded_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


__all__ = [
    "AffectiveConfig",
    "AffectiveEvent",
    "AffectiveNervousSystem",
    "AffectiveState",
    "get_affective_state_path",
    "load_affective_config",
]
