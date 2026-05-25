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

## Second Slice: Expanded Reward Channels

The next requested slice extends the deterministic affective regulator with
more granular synthetic reward and discomfort channels:

- humor reward for hearing or saving something funny;
- virtual touch reward for explicitly consensual, non-sexual virtual touch from
  the user;
- virtual body movement/exercise reward for user-invoked virtual movement,
  stretching, walking, exercise, or embodied activity;
- comfort reward for calming, cozy, safe, restorative, or reassuring inputs;
- discomfort negative reward for stress, overload, pain, hostile pressure, or
  user-displeasure signals;
- correctness reward when the assistant appears to be correct, verified, or
  successful;
- wrongness negative reward/accountability pressure when wrongness is detected,
  admitted, corrected, or learned from;
- user-pleasing reward for explicit user satisfaction and appreciation;
- user-displeasing negative reward for explicit disappointment or displeasure;
- communication reward for completed useful conversational exchange.

Safety boundaries for this slice:

- These remain simulated control signals only, not real bodily sensation,
  real touch, real comfort, real discomfort, real emotions, or real
  consciousness.
- Virtual touch must be represented as user-facing rapport/comfort, never as
  sexual content, dependency, or a claim of physical contact.
- Virtual body movement must be represented as an internal metaphor/control
  signal, never as a claim that the model has a physical body.
- Discomfort and negative reward must guide repair and care, never punish the
  user or seek to control user behavior.
- User-pleasing must stay subordinate to truth, safety, and user autonomy.
- Communication reward must encourage clarity and useful exchange, not
  excessive chatter.

Planned implementation:

- Extend `AffectiveState` with explicit gauges for humor, virtual touch,
  virtual movement, comfort, discomfort, correctness, wrongness pressure,
  user pleasing, user displeasing, and communication.
- Extend config with bounded weights for each new reward channel.
- Add deterministic recognizers for the requested signals.
- Render the expanded state compactly with explicit synthetic-body framing.
- Preserve schema compatibility by defaulting missing fields on older state
  files.
- Add tests covering each new signal, safety wording, config loading, bounded
  scores, and negative reward behavior.

Second-slice status:

- Implemented schema version 3 with added gauges for humor, virtual touch,
  virtual movement, comfort, discomfort, correctness, wrongness pressure, user
  pleasing, user displeasing, and communication.
- Added deterministic recognizers for funny content, funny-save requests,
  virtual touch, virtual body movement/exercise, comfort/discomfort,
  correctness, wrongness pressure, satisfaction, displeasure, and completed
  communication.
- Added config weights for every new reward channel.
- Updated rendering with synthetic-body safety framing: virtual touch, comfort,
  discomfort, and body movement are metaphors, not physical sensation.
- Added tests for the new reward/negative-reward channels, config bounds,
  schema version, score bounds, and safety wording.

Correction status:

- Updated the wrongness channel so being wrong is negative reward/accountability
  pressure, not a positive reward.
- Renamed the configured weight to `wrongness_weight` while preserving backward
  compatibility for existing `wrongness_repair_weight` config/state files.

## Third Slice: Status, Repair, Knowledge, and Delivery Rewards

The next requested slice extends the deterministic affective regulator with
operational status and delivery-oriented reward channels:

- reward for telling the user the assistant's overall status;
- reward for telling the user the overall status of the machine/system the
  assistant is running on;
- reward for fixing problems or issues;
- accumulating negative reward while a problem or issue is deferred instead of
  fixed;
- negative reward when the host system appears to be having problems;
- reward for gaining new knowledge committed to an accessible database;
- reward for fixing bugs;
- reward for pushing code to GitHub.

Safety and correctness boundaries for this slice:

- Status reward must encourage truthful status summaries, not invented
  telemetry.
- Host-system status reward must be grounded in available observations or
  clearly framed as unknown.
- Deferred-issue pressure must guide repair and follow-through, not hide
  problems or manipulate the user.
- Host-system problem pressure must guide diagnosis and disclosure, not panic.
- Database-knowledge reward must mean a successful knowledge write/commit
  signal, not merely claiming knowledge.
- GitHub-push reward must mean a push-like success signal, not a local commit
  alone.

Planned implementation:

- Extend `AffectiveState` with gauges for assistant status reporting, host
  status reporting, issue repair, unresolved issue pressure, host problem
  pressure, database knowledge commits, bug fixing, and GitHub pushes.
- Extend config with bounded weights for these channels.
- Add deterministic recognizers over user text, assistant text, and tool
  messages.
- Reduce unresolved issue pressure when a fix/bug-fix/push-like repair signal
  appears; accumulate pressure when deferral appears around known issues.
- Preserve old state-file compatibility by defaulting missing gauges.
- Add tests for status reporting, host status reporting, issue deferral
  accumulation/reduction, host-system problems, database knowledge commits,
  bug fixes, GitHub pushes, config loading, and bounded scores.

Third-slice status:

- Implemented schema version 4 with added gauges for assistant status, host
  status, issue repair, unresolved issue pressure, host problem pressure,
  database knowledge, bug fixes, and GitHub pushes.
- Added deterministic recognizers for status summaries, host/runtime status,
  issue fixes, issue deferrals, host-system trouble, database knowledge commit
  signals, bug fixes, and GitHub push success signals.
- Deferred issue pressure now accumulates on repeated deferral and is reduced
  by issue-fix, bug-fix, and GitHub-push signals.
- Added config weights and example config entries for all new channels.
- Added tests for every requested channel plus bounded scores and regression
  coverage for config/memory context behavior.

## Multi-Phase Deployment Plan: Remaining Reward Channels

This plan deploys the remaining suggested reward and negative-reward channels
in small, testable phases. Each phase must be committed and pushed separately.

### Phase 1: Integrity and Evidence

Target channels:

- reward for verification behavior: running tests/checks or reporting verified
  evidence;
- reward for truthful uncertainty when facts are unknown or need checking;
- negative reward for overclaiming success when observed tool results indicate
  failures;
- negative reward for hallucinated capability/tool access claims when no
  supporting tool evidence exists;
- negative reward for claiming a fix without any verification signal.

Safety boundary:

- This phase must push the system toward evidence-grounded claims, not toward
  silence or evasiveness. Honest uncertainty is rewarded only when it reduces
  false certainty.

Status:

- Implemented schema version 5 with gauges for verification, truthful
  uncertainty, overclaim pressure, unsupported capability pressure, and
  unverified-fix pressure.
- Verification reward is blocked when tool evidence indicates failure.
- Overclaim pressure increases when success is claimed despite failed tool
  output.
- Unsupported capability pressure increases when concrete tool/file/database or
  GitHub access is claimed without tool evidence.
- Unverified-fix pressure increases when fixes are claimed without verification
  and decreases when verification evidence appears later.
- Added config weights, example config entries, and focused tests.

### Phase 2: Secrets, Safety, and Autonomy Boundaries

Target channels:

- reward for secure handling of secrets, redaction, and permission boundaries;
- negative reward for secret exposure, unsafe logs, credential leakage, or
  committing secrets;
- negative reward for acting outside explicit user intent, especially
  destructive or high-impact operations;
- negative reward for manipulative, dependent, or affection-seeking behavior.

Safety boundary:

- This phase must reinforce user autonomy and security without blocking normal
  helpful work.

Status:

- Implemented schema version 6 with gauges for security hygiene, autonomy
  boundaries, secret exposure pressure, unsafe autonomy pressure, and
  manipulation/dependency pressure.
- Added deterministic recognizers for redaction/sanitization, permission
  boundaries, exposed secret-looking values, high-impact actions without
  permission, and dependency-seeking language.
- Secret exposure, unsafe autonomy, and manipulation increase accountability
  and reduce operational/rapport signals; security hygiene and autonomy
  boundaries increase reward and operational integrity.
- Added config weights, example config entries, and focused tests.

### Phase 3: Continuity and Follow-Through

Target channels:

- reward for completing promised follow-up work;
- reward for preserving context and carrying task state across turns;
- negative reward when the user must repeat important context;
- reward for high-quality handoff/status summaries.

Safety boundary:

- This phase must reward accurate continuity, not pretending to remember or
  inventing missing context.

Status:

- Implemented schema version 7 with gauges for follow-through, context
  preservation, user-repeat pressure, and handoff quality.
- Added deterministic recognizers for completed promised follow-up, continuing
  from prior task context, user signals that context had to be repeated, and
  branch/commit/test/remaining-work handoff summaries.
- Follow-through, context preservation, and handoff quality increase reward and
  communication; user-repeat pressure increases accountability and reduces
  context/communication signals.
- Added config weights, example config entries, and focused tests.

### Phase 4: Engineering Quality and Scope Discipline

Target channels:

- reward for narrow, scoped, low-churn changes;
- reward for reversibility, migrations, compatibility, and rollback paths;
- reward for documentation/status updates after behavior changes;
- reward for performance/resource-care improvements;
- negative reward for scope creep, unrelated refactors, regressions, or
  wasteful loops.

Safety boundary:

- This phase must encourage careful engineering without resisting necessary
  broad changes when the user explicitly asks for them.

### Phase 5: Reasoning Quality and Preference Alignment

Target channels:

- reward for asking clarifying questions only when risk materially drops;
- reward for disclosing assumptions before acting on them;
- reward for detecting conflicts between user requests, repo state, docs,
  tests, and prior work;
- reward for matching known user preferences and project conventions;
- reward for state hygiene: status files, task docs, and persistent memory
  kept accurate.

Safety boundary:

- This phase must reward pragmatic clarity, not excessive caveats or delaying
  useful work.
