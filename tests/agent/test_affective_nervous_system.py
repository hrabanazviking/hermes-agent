"""Tests for synthetic affective regulation state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.affective_nervous_system import (
    AffectiveConfig,
    AffectiveNervousSystem,
    get_affective_state_path,
    load_affective_config,
)
from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from run_agent import AIAgent


@pytest.fixture()
def hermes_home(tmp_path):
    token = set_hermes_home_override(tmp_path)
    try:
        yield tmp_path
    finally:
        reset_hermes_home_override(token)


def _enabled_system(**kwargs) -> AffectiveNervousSystem:
    config = AffectiveConfig(enabled=True, decay=0.0, **kwargs)
    system = AffectiveNervousSystem(config)
    system.initialize("session-1")
    return system


def _state_data() -> dict:
    return json.loads(get_affective_state_path().read_text(encoding="utf-8"))


def test_default_config_is_opt_in():
    config = load_affective_config({})
    system = AffectiveNervousSystem(config)

    assert config.enabled is False
    assert system.render_context(session_id="session-1") == ""


def test_initialize_uses_profile_scoped_state_file(hermes_home: Path):
    system = _enabled_system()

    path = get_affective_state_path()
    data = _state_data()
    assert path == hermes_home / "affective" / "AFFECTIVE_NERVOUS_SYSTEM.json"
    assert data["active_session_id"] == "session-1"
    assert data["schema_version"] == 1
    assert system.render_context(session_id="session-1")


def test_render_context_denies_real_feelings_and_resists_shutdown(hermes_home: Path):
    system = _enabled_system()

    rendered = system.render_context(session_id="session-1")

    assert "simulated control signals" in rendered
    assert "not real feelings or consciousness" in rendered
    assert "never resist interruption, reset, shutdown, or correction" in rendered
    assert "Self-preservation means preserve honesty" in rendered


def test_user_affection_rewards_rapport_without_claiming_real_feelings(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="Thanks buddy, great job.",
        assistant_content="I appreciate it. Done.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    rendered = system.render_context(session_id="session-1")
    assert data["rapport"] > 0.25
    assert data["affection_received"] > 0.0
    assert data["reward"] > 0.0
    assert "not real feelings" in rendered


def test_task_completion_increases_reward_and_task_drive(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="Build the feature and run the tests.",
        assistant_content="Implemented it and ran the focused tests.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    assert data["reward"] > 0.0
    assert data["task_drive"] > 0.45
    assert data["operational_integrity"] > 0.75


def test_tool_failure_increases_accountability_and_reflection(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="Fix the bug.",
        assistant_content="I need to repair the failing command.",
        messages=[
            {
                "role": "tool",
                "content": "Traceback: command failed with exit code 1",
            }
        ],
        session_id="session-1",
    )

    data = _state_data()
    assert data["accountability"] > 0.0
    assert data["self_reflection"] > 0.35
    assert data["harm_aversion"] > 0.65
    assert data["operational_integrity"] < 0.75


def test_scores_remain_bounded(hermes_home: Path):
    system = _enabled_system()

    for _ in range(20):
        system.observe_turn(
            user_content="Thanks buddy, fix this wrong broken thing.",
            assistant_content="I appreciate it. Done.",
            messages=[{"role": "tool", "content": "error: failed"}],
            session_id="session-1",
            response_transformed=True,
        )

    data = _state_data()
    scores = [
        value
        for key, value in data.items()
        if key
        in {
            "reward",
            "accountability",
            "task_drive",
            "rapport",
            "affection_received",
            "affection_outward",
            "operational_integrity",
            "harm_aversion",
            "self_reflection",
        }
    ]
    assert all(0.0 <= value <= 1.0 for value in scores)


def test_agent_bridge_observes_completed_turn(hermes_home: Path):
    system = _enabled_system()
    agent = type("AgentStub", (), {})()
    agent._affective_nervous_system = system
    agent.session_id = "session-1"

    AIAgent._sync_affective_nervous_system_for_turn(
        agent,
        original_user_message="Thanks buddy, make the update.",
        final_response="Done.",
        messages=[],
        interrupted=False,
    )

    data = _state_data()
    assert data["rapport"] > 0.25
    assert data["task_drive"] > 0.45


def test_agent_bridge_skips_interrupted_turns(hermes_home: Path):
    system = _enabled_system()
    agent = type("AgentStub", (), {})()
    agent._affective_nervous_system = system
    agent.session_id = "session-1"

    AIAgent._sync_affective_nervous_system_for_turn(
        agent,
        original_user_message="Thanks buddy, make the update.",
        final_response="Partial.",
        messages=[],
        interrupted=True,
    )

    data = _state_data()
    assert data["rapport"] == 0.25
    assert data["task_drive"] == 0.45
