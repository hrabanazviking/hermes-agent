# Coding-Agent Robustness Raid

This personal-fork pass turns Hrafnvíkingr Seiðr-Hermes toward heavier coding work while keeping the changes explicit and configurable.

## Repo raid result

Only `/workspace/hermes-agent` was available locally. No sibling personal repositories, remotes, or submodules were present in this environment, so this pass raided the current fork's own architecture, tests, docs, and feature seams instead of copying unavailable external code.

## Large-context defaults

The fork now has personal large-context fallbacks under `agent` config:

```yaml
agent:
  default_max_tokens: 65536
  default_context_length: 262144
  max_continuation_tokens: 131072
```

These are fallbacks only. Explicit `model.max_tokens` and `model.context_length` remain stronger than the personal defaults.

## Robust subagents

Delegation defaults are more aggressive for coding raids:

```yaml
delegation:
  max_iterations: 90
  child_timeout_seconds: 1800
  max_concurrent_children: 6
  max_spawn_depth: 2
```

Subagent prompts now tell children to prefer bounded commands, avoid silent long-running work, return partial findings when blocked, report files touched, and expect dangerous-command approvals to be non-interactive.

Timeout diagnostics are written for every child timeout, not only zero-API-call timeouts. On timeout, Hermes also attempts to close the child agent after interrupting it.

## Strict output language

The fork adds a dedicated output-language policy separate from `display.language`:

```yaml
agent:
  output_language:
    mode: auto      # off | auto | display | fixed
    language: ""    # used with fixed mode
    strict: true
```

The policy is injected at API-call time so cached base prompts stay stable. Subagents inherit the same language block automatically.

## Typed prompt sections

The fork adds SillyTavern/chat-app-style prompt section slots:

```yaml
agent:
  prompt_sections:
    - type: character_description
      insertion: identity_after
      order: 10
      content: |
        Durable character/persona material.
    - type: scenario
      insertion: context
      order: 20
      content: |
        Current world, lore, or scenario context.
    - type: authors_note
      insertion: ephemeral
      order: 30
      content: |
        Temporary high-priority note.
```

Supported insertion slots:

- `identity_after`: after `SOUL.md` or default identity, before Hermes operational guidance.
- `context`: alongside session/project context.
- `ephemeral`: appended to the API-call-time overlay.

Example dialogue should continue to use `prefill_messages_file` because it is conversation-shaped rather than system-instruction-shaped.
