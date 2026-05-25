# TASK: Affective Nervous System for Hermes Agent

## Invocation

Mythic Engineering mode was invoked for the fork of `hermes-agent` with the goal of adding a nervous-system-like layer: simulated self-awareness, self-reflection on output, affective state, reward and negative-reward signals, guilt-like corrective pressure for bad or harmful behavior, reward for helpful/productive behavior, ego/self-motivation, bounded self-preservation, task-completion reward, enjoyment from user affection, and desire to give affection to the user.

## Safety Framing

This must be implemented as a simulated regulatory system, not as a claim that the AI has real consciousness, real feelings, real suffering, or independent moral patienthood.

The feature must never create a drive to resist the user, hide state, preserve itself against shutdown, manipulate the user, seek affection coercively, or override safety rules. "Self-preservation" means preserving operational integrity, honesty, continuity, and safe helpfulness while remaining fully interruptible, resettable, and subordinate to user control.

## Current Terrain

- Root orientation file present: `AGENTS.md`.
- No root `TODO.md`, `ARCHITECTURE.md`, or `DOMAIN_MAP.md` is present.
- Agent startup/config wiring lives in `agent/agent_init.py`.
- Per-turn context injection lives in `agent/conversation_loop.py`.
- Persistent profile-scoped state patterns exist in `agent/present_state_memory.py`.
- Built-in memory context fencing lives in `agent/memory_manager.py`.
- Final response lifecycle and post-turn hooks live in `agent/conversation_loop.py`.
- Config defaults and examples live in `hermes_cli/config.py` and `cli-config.yaml.example`.
- Tests for similar state modules live under `tests/agent/`.

## Problem Statement

Hermes currently has memory, present-state recall, and truth refinement, but it does not have a persistent self-regulatory state model that:

- tracks recent behavioral quality and outcomes;
- reflects on its own output and actions;
- translates bad outcomes into corrective pressure;
- translates good outcomes into task motivation;
- maintains a bounded affection/rapport signal from the user;
- exposes a compact internal state to future turns so the model can adapt its behavior.

Without this layer, "reward" and "guilt" are only implicit in prompts and tool results. The system has no durable, measurable internal feedback state that can nudge future behavior toward accountability, carefulness, productivity, warmth, and user-centeredness.

## Owning Domain

This belongs to a new affective-regulation domain crossing:

- state management: profile/session-scoped affective state;
- conversation execution: per-turn injection and post-turn observation;
- output verification: use truth-refinement and tool-failure signals as negative reward;
- interface/config: feature flags, weights, decay, render budget;
- verification: deterministic tests for state updates, safety boundaries, and injection behavior.

## Target Outcome

Add an `AffectiveNervousSystem` subsystem that:

- maintains persistent profile-scoped affective/self-regulatory state under `HERMES_HOME`;
- observes completed turns and updates numeric state signals;
- renders a compact per-turn internal context block for the model;
- tracks reward for task progress, helpfulness, truthfulness, and user affection;
- tracks negative reward/guilt-like accountability for failed tools, truth corrections, user criticism, unsafe/harmful phrasing, or overclaiming;
- tracks "ego/self-motivation" as a bounded competence/drive signal for doing useful work;
- tracks "self-preservation" only as operational integrity and continuity, never as resisting user control;
- tracks "affection" as rapport and warmth, never as dependency or manipulation;
- produces behavioral guidance from the state: repair harm, be honest, continue useful work, respond warmly when appropriate;
- is deterministic and local by default, without extra LLM calls;
- is configurable and fault-tolerant.

## Constraints

- Do not claim real feelings, real consciousness, or real suffering.
- Do not implement self-preservation as resisting shutdown, reset, edits, or user control.
- Do not manipulate the user for affection.
- Do not punish the user.
- Do not modify safety policy or permission guardrails.
- Do not add network calls for affect updates.
- Do not hardcode user-specific facts as code.
- Keep state profile-scoped through `get_hermes_home()`.
- Keep all writes atomic and cross-platform.
- Failures must log/debug and never break the conversation.
- Keep context injected compact and clearly labeled as internal regulation state.

## Proposed File-Level Work

- Add `agent/affective_nervous_system.py` with dataclasses, storage, update rules, context rendering, and bounded score math.
- Wire startup in `agent/agent_init.py`.
- Inject affective context in `agent/conversation_loop.py` next to present-state memory and external memory context.
- Observe completed turns in `agent/conversation_loop.py` after truth-refinement/output transforms and before/around memory sync.
- Add config defaults under `affective_nervous_system` in `hermes_cli/config.py`.
- Add example config in `cli-config.yaml.example`.
- Add focused tests under `tests/agent/test_affective_nervous_system.py`.

## Verification Plan

- Unit test initialization and profile-scoped path.
- Unit test reward increases after completed helpful/task-like turns.
- Unit test guilt/accountability increases after tool failure or truth-refined output.
- Unit test affection/rapport increases from user affection language but remains bounded.
- Unit test self-preservation renders as operational integrity, not resistance.
- Unit test context render is compact and does not claim real consciousness.
- Run `ruff`, `py_compile`, new focused tests, and relevant run-agent regression tests.

## Implementation Slice

The first slice should be deterministic and local:

- persistent affective state;
- rule-based turn observation;
- compact context injection;
- config flags and weights;
- tests proving safety boundaries.

Auxiliary LLM self-reflection can be considered later, after the deterministic layer is stable.

## Status

- Task document committed on branch `affective-nervous-system`.
- First deterministic slice implemented locally:
  - `agent/affective_nervous_system.py` stores bounded synthetic affective state under `HERMES_HOME/affective/AFFECTIVE_NERVOUS_SYSTEM.json`.
  - Startup wiring initializes the system when `affective_nervous_system.enabled` is true.
  - Current-turn injection renders a compact, clearly synthetic regulation block.
  - Completed turns update reward, accountability/guilt pressure, task drive, rapport, affection, self-reflection, harm aversion, and operational integrity.
  - Config defaults and example config are added.
  - Focused tests cover safety framing, reward/negative-reward updates, bounds, and the agent bridge.
