from agent.output_language import (
    build_output_language_system_block,
    load_output_language_policy,
)
from agent.prompt_sections import normalize_prompt_sections, render_prompt_sections


def test_fixed_output_language_policy_uses_display_name():
    policy = load_output_language_policy({
        "agent": {"output_language": {"mode": "fixed", "language": "zh-Hant"}}
    })

    block = build_output_language_system_block(policy)

    assert policy.language == "zh-hant"
    assert "Traditional Chinese" in block
    assert "Do not translate code" in block


def test_auto_output_language_policy_mentions_latest_user_language():
    policy = load_output_language_policy({"agent": {"output_language": {"mode": "auto"}}})

    block = build_output_language_system_block(policy)

    assert "same natural language as the user's latest message" in block


def test_prompt_sections_render_by_insertion():
    sections = normalize_prompt_sections([
        {"type": "character_description", "insertion": "identity_after", "content": "Raven coder"},
        {"type": "scenario", "insertion": "context", "content": "Raid the codebase"},
    ])

    identity = render_prompt_sections(sections, "identity_after")
    context = render_prompt_sections(sections, "context")

    assert "Character description" in identity
    assert "Raven coder" in identity
    assert "Scenario" in context
    assert "Raid the codebase" in context
