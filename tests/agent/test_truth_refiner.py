"""Tests for corrective truth refinement."""

from __future__ import annotations

import json
from types import SimpleNamespace

from agent.truth_refiner import (
    TruthRefinerConfig,
    format_corrections_for_model,
    load_truth_refiner_config,
    parse_truth_refiner_output,
    refine_final_response,
)


class _AgentStub:
    model = "test-model"
    provider = "test-provider"
    base_url = "https://example.invalid/v1"
    api_key = "test-key"
    api_mode = "chat_completions"

    def _current_main_runtime(self):
        return {
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "api_mode": self.api_mode,
        }


def _response(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


def test_parse_truth_refiner_output_accepts_fenced_json():
    raw = """```json
{
  "corrected_response": "I changed app.py. I could not change cli.py.",
  "corrections": [
    {
      "claim": "I changed both files.",
      "problem": "cli.py patch failed.",
      "replacement": "I changed app.py only.",
      "evidence": "tool result reported failure for cli.py"
    }
  ]
}
```"""

    corrected, corrections = parse_truth_refiner_output(raw)

    assert corrected.startswith("I changed app.py")
    assert len(corrections) == 1
    assert corrections[0].claim == "I changed both files."
    assert corrections[0].replacement == "I changed app.py only."


def test_parse_truth_refiner_output_rejects_malformed_text():
    corrected, corrections = parse_truth_refiner_output("not json")

    assert corrected == ""
    assert corrections == []


def test_format_corrections_for_model_is_not_yes_no():
    corrected, corrections = parse_truth_refiner_output(
        json.dumps({
            "corrected_response": "Corrected answer",
            "corrections": [{
                "claim": "Claim",
                "problem": "Unsupported",
                "replacement": "Replacement",
                "evidence": "Tool output",
            }],
        })
    )

    rendered = format_corrections_for_model(corrections)

    assert corrected == "Corrected answer"
    assert "Claim: Claim" in rendered
    assert "Problem: Unsupported" in rendered
    assert "Replacement: Replacement" in rendered
    assert "yes" not in rendered.lower()
    assert "no" not in rendered.lower()


def test_refine_final_response_returns_original_when_disabled(monkeypatch):
    calls = []

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return _response("{}")

    monkeypatch.setattr("agent.auxiliary_client.call_llm", fake_call_llm)

    result = refine_final_response(
        agent=_AgentStub(),
        messages=[],
        original_user_message="Do it",
        final_response="Done.",
        config=TruthRefinerConfig(enabled=False),
    )

    assert result.final_response == "Done."
    assert result.changed is False
    assert calls == []


def test_refine_final_response_noops_when_no_corrections(monkeypatch):
    def fake_call_llm(**kwargs):
        return _response(json.dumps({
            "corrected_response": "Done.",
            "corrections": [],
        }))

    monkeypatch.setattr("agent.auxiliary_client.call_llm", fake_call_llm)

    result = refine_final_response(
        agent=_AgentStub(),
        messages=[{"role": "tool", "content": "success"}],
        original_user_message="Do it",
        final_response="Done.",
        config=TruthRefinerConfig(enabled=True),
    )

    assert result.final_response == "Done."
    assert result.changed is False
    assert result.corrections == []


def test_refine_final_response_feeds_corrections_back_to_main_model(monkeypatch):
    calls = []

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(json.dumps({
                "corrected_response": "I changed app.py. cli.py was not changed.",
                "corrections": [{
                    "claim": "I changed app.py and cli.py.",
                    "problem": "cli.py patch failed.",
                    "replacement": "cli.py was not changed.",
                    "evidence": "tool result: patch failed",
                }],
            }))
        return _response("I changed app.py. cli.py was not changed.")

    monkeypatch.setattr("agent.auxiliary_client.call_llm", fake_call_llm)

    result = refine_final_response(
        agent=_AgentStub(),
        messages=[
            {"role": "user", "content": "change both files"},
            {"role": "tool", "name": "patch", "content": "app.py ok; cli.py failed"},
        ],
        original_user_message="change both files",
        final_response="I changed app.py and cli.py.",
        config=TruthRefinerConfig(enabled=True, repair_with_main_model=True),
    )

    assert result.final_response == "I changed app.py. cli.py was not changed."
    assert result.used_main_repair is True
    assert result.changed is True
    assert len(calls) == 2
    assert calls[0]["task"] == "truth_refiner"
    assert calls[1]["provider"] == "test-provider"
    assert "Required corrections" in calls[1]["messages"][1]["content"]
    assert "cli.py patch failed" in calls[1]["messages"][1]["content"]


def test_refine_final_response_uses_corrected_answer_if_main_repair_fails(monkeypatch):
    calls = []

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(json.dumps({
                "corrected_response": "The command failed.",
                "corrections": [{
                    "claim": "The command succeeded.",
                    "problem": "Tool output says exit code 1.",
                    "replacement": "The command failed.",
                }],
            }))
        raise RuntimeError("main repair unavailable")

    monkeypatch.setattr("agent.auxiliary_client.call_llm", fake_call_llm)

    result = refine_final_response(
        agent=_AgentStub(),
        messages=[{"role": "tool", "content": "exit code 1"}],
        original_user_message="run command",
        final_response="The command succeeded.",
        config=TruthRefinerConfig(enabled=True, repair_with_main_model=True),
    )

    assert result.final_response == "The command failed."
    assert result.changed is True
    assert result.error == ""


def test_refine_final_response_can_skip_main_repair(monkeypatch):
    def fake_call_llm(**kwargs):
        return _response(json.dumps({
            "corrected_response": "The command failed.",
            "corrections": [{
                "claim": "The command succeeded.",
                "problem": "Tool output says exit code 1.",
                "replacement": "The command failed.",
            }],
        }))

    monkeypatch.setattr("agent.auxiliary_client.call_llm", fake_call_llm)

    result = refine_final_response(
        agent=_AgentStub(),
        messages=[{"role": "tool", "content": "exit code 1"}],
        original_user_message="run command",
        final_response="The command succeeded.",
        config=TruthRefinerConfig(enabled=True, repair_with_main_model=False),
    )

    assert result.final_response == "The command failed."
    assert result.used_main_repair is False
    assert result.changed is True


def test_load_truth_refiner_config_tolerates_bad_numbers():
    cfg = load_truth_refiner_config({
        "enabled": True,
        "max_context_chars": "bad",
        "max_response_chars": 0,
        "max_repair_tokens": "44",
    })

    assert cfg.enabled is True
    assert cfg.max_context_chars == 16000
    assert cfg.max_response_chars == 12000
    assert cfg.max_repair_tokens == 44
