# TASK: Present-State Memory for Cross-Platform Conversations

## Invocation

Mythic Engineering mode was invoked for `hermes-agent` with the goal of making memory substantially better across platforms, including active present-state memory and automatic storage of key facts during conversations.

## Current Terrain

- Root orientation file present: `AGENTS.md`.
- `TODO.md`, `ARCHITECTURE.md`, `DOMAIN_MAP.md`, and ME-specific architecture docs were not present in the repository root.
- Core built-in memory lives in `tools/memory_tool.py`.
- Memory provider orchestration lives in `agent/memory_manager.py` and `agent/memory_provider.py`.
- Provider startup and tool injection live in `agent/agent_init.py`.
- Turn-level memory hooks live in `agent/conversation_loop.py`.
- System-prompt memory injection lives in `agent/system_prompt.py`.
- Built-in memory writes are bridged to external providers in `agent/tool_executor.py` and `agent/agent_runtime_helpers.py`.
- Config defaults and examples live in `hermes_cli/config.py` and `cli-config.yaml.example`.
- Existing memory-provider plugins live under `plugins/memory/`.
- Existing memory tests live mostly under `tests/agent/`, `tests/run_agent/`, `tests/plugins/memory/`, and `tests/honcho_plugin/`.

## What Exists Now

Hermes currently has two memory lanes:

1. Built-in curated memory:
   - `MEMORY.md` and `USER.md` under profile-scoped `HERMES_HOME/memories/`.
   - Cross-platform file locking is already handled with `fcntl` on Unix and `msvcrt` on Windows.
   - Writes are durable immediately.
   - The system prompt uses a frozen snapshot from session startup. Mid-session writes do not affect the live prompt until a rebuild or next session.
   - The store is intentionally small and curated.

2. External memory providers:
   - Activated by `memory.provider`.
   - Managed by `MemoryManager`.
   - Receive `on_turn_start`, `prefetch_all`, `sync_all`, `queue_prefetch_all`, `on_session_end`, `on_pre_compress`, `on_session_switch`, `on_memory_write`, and `on_delegation`.
   - Only one external provider can be active at a time.

## Problem Statement

The current architecture remembers durable facts, but it does not have a first-class live present-state layer that is visible during the same active conversation after facts are discovered or corrected.

This creates three practical gaps:

- Key facts saved mid-conversation are durable on disk but not reliably present in the active model context until a later session or system prompt rebuild.
- There is no compact, explicit “what is true right now in this conversation” state separate from permanent profile memory and full transcript history.
- Automatic fact capture depends heavily on the model choosing to call the memory tool or on external provider behavior, rather than on a core turn lifecycle that can extract, stage, and store important facts consistently across CLI, TUI, gateway, cron, and future platforms.

## Owning Domain

This belongs primarily to the memory domain, but it crosses three boundaries:

- Memory domain: state model, persistence, fact capture, provider bridge.
- Conversation execution domain: turn lifecycle, injection point, session switching, compression.
- Interface/config domain: tool schema, config defaults, documentation, test contracts.

## Target Outcome

Add a core present-state memory subsystem that:

- Maintains an active, compact, session-scoped state snapshot available during the current conversation.
- Persists the state under `HERMES_HOME` using cross-platform-safe file operations.
- Updates immediately when memory writes happen.
- Can receive extracted key facts after each completed conversation turn.
- Separates ephemeral present-state facts from durable long-term `MEMORY.md` and `USER.md`.
- Mirrors important state updates to external memory providers through existing `MemoryManager` hooks.
- Is platform-neutral: CLI, TUI, gateway, cron, and batch paths should all use the same agent lifecycle hooks where possible.
- Preserves existing memory provider APIs unless an additive optional hook is clearly needed.
- Preserves prompt-cache behavior by injecting live present-state context as a per-turn context block rather than rebuilding the stable system prompt on every turn.

## Constraints

- Do not remove existing built-in memory behavior.
- Do not remove existing provider behavior or tool names.
- Keep storage profile-scoped through `get_hermes_home()` / `HERMES_HOME`.
- Keep memory writes fault-tolerant; failures must log and continue.
- Avoid absolute paths in source.
- Keep Windows, Linux, macOS, Termux, and container use cases in view.
- Do not introduce network-only memory as the default.
- Do not hardcode user facts or environment facts in code.
- Keep new behavior configurable and conservative by default.
- Respect the existing one-external-provider rule.
- Use existing internal APIs for provider fan-out rather than mutating provider state directly.

## Proposed File-Level Work

- Add a new core module, likely `agent/present_state_memory.py`, for the present-state data model, storage, rendering, and merge rules.
- Extend `agent/memory_manager.py` only if a small additive fan-out hook is needed for present-state updates.
- Wire initialization in `agent/agent_init.py`.
- Inject live present-state context in `agent/conversation_loop.py` alongside existing external prefetch context.
- Update built-in memory write bridges in `agent/tool_executor.py` and `agent/agent_runtime_helpers.py` so explicit memory writes refresh present state immediately.
- Consider a compact tool/schema extension only if the model needs an explicit present-state command separate from long-term memory.
- Add config keys in `hermes_cli/config.py` and `cli-config.yaml.example`.
- Add tests under `tests/agent/` and `tests/run_agent/` for storage, injection, session switching, compression, and failure tolerance.
- Update relevant docs after implementation.

## Verification Plan

- Unit test present-state storage path resolution and atomic writes.
- Unit test merge and de-duplication behavior.
- Unit test system/context injection does not rebuild the cached system prompt.
- Unit test explicit memory writes update present state.
- Unit test failed present-state writes do not break the turn.
- Unit test session switch behavior.
- Run focused memory tests before broader test runs:
  - `tests/agent/test_memory_provider.py`
  - `tests/agent/test_memory_session_switch.py`
  - `tests/run_agent/test_memory_sync_interrupted.py`
  - new present-state tests

## Open Questions for Approval

- Should present-state memory be enabled by default when built-in memory is enabled, or behind a separate `memory.present_state_enabled` flag defaulting to true?
- Should automatic key-fact extraction use an auxiliary LLM pass, deterministic heuristics, or start with explicit memory/write events only?
- Should present-state persist per session only, or should the latest active state also have a profile-level “current facts” view shared across sessions and platforms?
- Should the first implementation include an explicit model-facing tool for present-state edits, or keep it internal and fed by existing memory writes plus post-turn extraction?

## Proposed First Implementation Slice

The safest first slice is:

- Add present-state storage and rendering.
- Enable it under the built-in memory config.
- Update it from explicit memory writes.
- Inject it as live per-turn context.
- Add tests proving same-session visibility and cross-platform path behavior.

Automatic post-turn key-fact extraction can then be added as a second slice once the state layer is stable.

## Implementation Notes

Implemented in one pass after approval:

- Added `agent/present_state_memory.py`.
- Added profile-scoped storage at `HERMES_HOME/memories/PRESENT_STATE.json`.
- Added live per-turn injection through the existing user-message context path.
- Added explicit memory-tool mirroring into present state.
- Added deterministic post-turn key-fact capture for obvious user preferences, remembered facts, current goals, and latest assistant outcomes.
- Added session lineage handling for compression, resume, branch, and new-session rotations.
- Added config keys under `memory.present_state_*`.
- Added focused tests in `tests/agent/test_present_state_memory.py`.
