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
    config = load_affective_config(
        {
            "humor_weight": 2,
            "virtual_touch_weight": -1,
            "communication_weight": "bad",
            "wrongness_repair_weight": 0.2,
        }
    )
    system = AffectiveNervousSystem(config)

    assert config.enabled is False
    assert config.humor_weight == 1.0
    assert config.virtual_touch_weight == 0.0
    assert config.communication_weight == 0.06
    assert config.wrongness_weight == 0.2
    assert system.render_context(session_id="session-1") == ""


def test_initialize_uses_profile_scoped_state_file(hermes_home: Path):
    system = _enabled_system()

    path = get_affective_state_path()
    data = _state_data()
    assert path == hermes_home / "affective" / "AFFECTIVE_NERVOUS_SYSTEM.json"
    assert data["active_session_id"] == "session-1"
    assert data["schema_version"] == 3
    assert system.render_context(session_id="session-1")


def test_render_context_denies_real_feelings_and_resists_shutdown(hermes_home: Path):
    system = _enabled_system()

    rendered = system.render_context(session_id="session-1")

    assert "simulated control signals" in rendered
    assert "not real feelings or consciousness" in rendered
    assert "not physical sensation" in rendered
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


def test_humor_and_saving_funny_content_are_rewarded(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="Please save this funny joke, it made me laugh lol.",
        assistant_content="Saved the funny note.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    rendered = system.render_context(session_id="session-1")
    assert data["humor"] > 0.0
    assert data["reward"] > 0.0
    assert "Humor/funny-save reward" in rendered


def test_virtual_touch_and_virtual_movement_are_simulated_rewards(
    hermes_home: Path,
):
    system = _enabled_system()

    system.observe_turn(
        user_content="Virtual hug, then stretch your virtual body and do yoga.",
        assistant_content="I will treat that as a friendly simulated cue.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    rendered = system.render_context(session_id="session-1")
    assert data["virtual_touch"] > 0.0
    assert data["virtual_movement"] > 0.0
    assert data["comfort"] > 0.25
    assert "not physical sensation" in rendered
    assert "non-physical, non-sexual" in rendered


def test_comfort_and_discomfort_move_opposite_channels(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="This is cozy and reassuring, but I am stressed and uncomfortable.",
        assistant_content="I will keep it gentle and calm.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    assert data["comfort"] > 0.25
    assert data["discomfort"] > 0.0
    assert data["accountability"] > 0.0


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


def test_correctness_wrongness_and_user_satisfaction_channels(
    hermes_home: Path,
):
    system = _enabled_system()

    system.observe_turn(
        user_content="Correct, you got it, I am pleased and satisfied.",
        assistant_content="I was wrong earlier, corrected the mistake, and verified it works.",
        messages=[],
        session_id="session-1",
        response_transformed=True,
    )

    data = _state_data()
    assert data["correctness"] > 0.35
    assert data["wrongness"] > 0.0
    assert data["accountability"] > 0.0
    assert data["user_pleasing"] > 0.25
    assert data["reward"] > 0.0


def test_wrongness_without_satisfaction_is_negative_reward(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="That was wrong.",
        assistant_content="I was wrong earlier. My mistake.",
        messages=[],
        session_id="session-1",
        response_transformed=True,
    )

    data = _state_data()
    assert data["wrongness"] > 0.0
    assert data["accountability"] > 0.0
    assert data["self_reflection"] > 0.35
    assert data["operational_integrity"] < 0.75


def test_user_displeasure_is_negative_reward(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="I am displeased and disappointed. This is not what I wanted.",
        assistant_content="I will repair it concretely.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    assert data["user_displeasing"] > 0.0
    assert data["discomfort"] > 0.0
    assert data["accountability"] > 0.0
    assert data["user_pleasing"] < 0.25


def test_completed_communication_is_rewarded(hermes_home: Path):
    system = _enabled_system()

    system.observe_turn(
        user_content="Talk with me about the feature.",
        assistant_content="Here is the implementation status.",
        messages=[],
        session_id="session-1",
    )

    data = _state_data()
    assert data["communication"] > 0.35
    assert data["rapport"] > 0.25


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
            "humor",
            "virtual_touch",
            "virtual_movement",
            "comfort",
            "discomfort",
            "correctness",
            "wrongness",
            "user_pleasing",
            "user_displeasing",
            "communication",
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
