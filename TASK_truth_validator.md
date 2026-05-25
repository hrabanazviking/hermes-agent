# TASK: Truth Refiner for Final Assistant Output

## Invocation

Mythic Engineering mode was invoked for the fork of `hermes-agent` with the goal of adding a truth validator for all output. The requested shape is not a yes/no classifier. The system should identify untrue parts, fix those parts, and feed the corrections back to the model so the model knows what was wrong.

## Current Terrain

- Root orientation file present: `AGENTS.md`.
- No root `TODO.md`, `ARCHITECTURE.md`, or `DOMAIN_MAP.md` is present.
- Final response handling lives in `agent/conversation_loop.py`.
- Existing post-output transformation happens through the `transform_llm_output` plugin hook in `agent/conversation_loop.py`.
- Post-turn persistence hooks happen through `post_llm_call` in `agent/conversation_loop.py`.
- Auxiliary LLM routing lives in `agent/auxiliary_client.py`.
- Config defaults and example config live in `hermes_cli/config.py` and `cli-config.yaml.example`.
- Streaming output can be previewed before final post-loop transforms, so any truth-refinement design must account for already-visible text.

## Problem Statement

Hermes can currently append a file-mutation verifier footer when a tool write fails, but there is no general final-output truth refiner that examines the assistant's claims against the available conversation/tool evidence and rewrites unsupported or false parts before the final answer is treated as truth.

A yes/no "is this true?" validator is insufficient because it leaves the model with only a gate result. The requested behavior is corrective:

- identify unsupported, contradicted, or overclaimed parts;
- produce a corrected answer;
- feed corrections back to the main model so the model revises the answer with knowledge of what was wrong;
- preserve the corrected answer as the final response for hooks, memory, and session persistence.

## Owning Domain

This belongs to the output verification domain, crossing:

- conversation execution: final-response lifecycle and retry/repair pass;
- auxiliary inference: verifier/refiner model call;
- config/interface: feature flags, task-specific auxiliary provider settings;
- tests: correction parsing, disabled/failure behavior, and final-response replacement.

## Target Outcome

Add a truth-refinement subsystem that:

- runs after the model produces a final answer and before post-turn persistence hooks;
- evaluates the answer against the current turn's conversation and tool evidence;
- asks for structured corrections and a corrected response, not a boolean verdict;
- feeds corrections back to the main model as an explicit repair message for one revision pass;
- falls back to the corrected response from the verifier if the main-model repair pass fails;
- does nothing when disabled, interrupted, empty, or when no correction is needed;
- is best-effort and must not block the turn if the verifier fails;
- avoids infinite repair loops with a fixed single-pass limit;
- keeps secrets and large context under control with configurable character budgets.

## Constraints

- Do not remove existing file-mutation verifier behavior.
- Do not replace plugin `transform_llm_output`; the truth refiner should fit near that phase.
- Do not expose a yes/no-only tool or API.
- Do not let verifier failure break normal response delivery.
- Do not call external services unless enabled by config.
- Do not feed raw unlimited transcript/tool output into an auxiliary call.
- Preserve session persistence semantics: the stored final assistant response should be the refined response when refinement runs.
- For streamed/previewed output, make sure the final corrected text is still visible somehow if the draft was already shown.

## Proposed File-Level Work

- Add `agent/truth_refiner.py` for prompts, transcript/evidence compaction, JSON parsing, and the orchestration contract.
- Add config defaults in `hermes_cli/config.py`:
  - `truth_refiner.enabled`
  - `truth_refiner.max_context_chars`
  - `truth_refiner.max_response_chars`
  - `truth_refiner.repair_with_main_model`
  - `truth_refiner.max_repair_tokens`
- Add auxiliary task config under `auxiliary.truth_refiner`.
- Wire `agent/conversation_loop.py` to call the refiner after file-mutation footer and plugin transform, before `post_llm_call`.
- Add a thin method on `AIAgent` in `run_agent.py` if needed to keep `conversation_loop.py` clean.
- Add focused tests under `tests/agent/` or `tests/run_agent/`.
- Update `cli-config.yaml.example`.

## Verification Plan

- Unit test parser behavior for JSON, fenced JSON, and malformed verifier output.
- Unit test no-op behavior when verifier reports no corrections.
- Unit test corrected response replacement when verifier returns corrections.
- Unit test main-model repair prompt construction without making network calls.
- Unit test verifier failure returns original response.
- Run focused conversation-loop/output tests and `ruff`.

## Proposed Implementation Slice

The first slice should implement the internal truth-refiner module, config, and conversation-loop integration as an opt-in feature disabled by default. Once the pipeline is stable, it can be enabled on the fork profile config.
