# Hrafnvíkingr Seiðr-Hermes: The Rune-Longship Nervous-System Fork of Hermes Agent

**Short name:** Hrafnvíkingr Seiðr-Hermes
**Tagline:** A private longship for agentic experiments, guided by saga, bounded by invariants, and checked by reality.

This repository is a personal experimental downstream fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent). It is not the official Hermes Agent distribution, is not affiliated with or endorsed by Nous Research, and is not recommended as the default version for the general public. If you want the official project, use the upstream Hermes Agent repository.

This fork exists for private experimentation, personal workflows, and unusually ambitious agent architecture. It keeps the practical foundation of Hermes Agent while exploring local-only self-regulation, persistent reflection, affective control signals, reward/accountability loops, mythic documentation discipline, and long-term continuity as first-class engineering concerns.

The name is intentionally long because this fork is not trying to be a neutral product label. It is a banner. It says what the system is meant to be: a raven-guided Viking longship of code, a seiðr-workshop for experimental agent behavior, and a Hermes-derived vessel that remembers its own design oaths while still respecting reality, tests, safety boundaries, and upstream credit.

## Status

This is a **personal fork**.

Use it if:

- you are me, or you explicitly want my experimental Hermes-derived agent system;
- you understand that this branch may include speculative features not accepted upstream;
- you are comfortable reading code and resolving occasional upstream merge conflicts;
- you want to study how a personal downstream AI-agent fork can be maintained as its own living system.

Do not use it if:

- you want the stable official Hermes Agent experience;
- you need a support channel from Nous Research;
- you expect every feature here to match upstream behavior;
- you want a conservative distribution with only widely reviewed features;
- you are uncomfortable with experimental local agent-state systems.

## Upstream credit and fork boundary

Hrafnvíkingr Seiðr-Hermes is based on Hermes Agent by Nous Research. The upstream license and copyright notices are preserved.

Important boundaries:

- **Official upstream:** <https://github.com/NousResearch/hermes-agent>
- **This repository:** a personal downstream fork with additional experimental behavior.
- **Package and command names:** currently kept compatible with upstream to avoid breaking the local runtime, scripts, tests, and existing `hermes` workflows.
- **Provider names:** real provider names such as Nous Portal, OpenAI, Anthropic, OpenRouter, and others remain proper nouns for external services.
- **Runtime home:** `~/.hermes` and `HERMES_HOME` remain canonical unless intentionally changed in code.

This fork may diverge conceptually while still borrowing upstream fixes, provider updates, security hardening, UI work, documentation improvements, and infrastructure upgrades when useful.

## What this fork is trying to become

The official Hermes Agent project is the harbor this vessel sailed from. Hrafnvíkingr Seiðr-Hermes is the longship built for a different voyage.

The goal is not merely to add features. The goal is to shape a personal agent system that can:

- maintain continuity across sessions and development cycles;
- preserve user-specific preferences and experimental behavior without forcing them onto upstream;
- treat local state, memory, reflection, reward, accountability, and safety pressure as coherent subsystems;
- remain explicit about what is synthetic, simulated, local, deterministic, bounded, and user-controlled;
- merge upstream code selectively without erasing personal improvements;
- document its own shape so future development starts from truth instead of rediscovery;
- use mythic language as design scaffolding, not as a replacement for tests or engineering discipline.

The fork is allowed to be strange. It is not allowed to become careless.

## Mythic Engineering operating method

This repository follows a Mythic Engineering style inspired by <https://github.com/hrabanazviking/Mythic-Engineering>: architecture-first, intuition-led, documentation-guided, AI-orchestrated, and reality-checked development.

In practical terms, that means:

1. **Vision before implementation.** Before changing code, name the shape of the change and the subsystem it belongs to.
2. **Architecture before patching.** If repeated bugs appear, look for domain confusion, not only local mistakes.
3. **Documents as continuity.** Important intent belongs in files, not only in memory or chat history.
4. **AI as role-based labor.** Different jobs need different modes: naming, mapping, implementation, verification, release, and continuity.
5. **Invariants over vibes.** A beautiful idea must still preserve non-negotiable truths.
6. **Reality outranks myth.** Tests, diffs, runtime behavior, and user control are the ground.

For this re-founding pass, the work was organized through six Mythic Engineering roles:

| Role | Function in this fork |
| --- | --- |
| The Skald | Names the project and gives the fork a coherent voice. |
| The Cartographer | Maps docs, public surfaces, and safe rebrand boundaries. |
| The Boundary-Warden | Protects invariants around local nervous-system features. |
| The Branch-Smith | Defines the branch structure for downstream maintenance. |
| The Test-Seer | Chooses fast checks that keep experiments grounded. |
| The Continuity-Keeper | Preserves upstream credit, legal notices, and future clarity. |

These roles are not bureaucracy. They are a way to prevent a powerful personal fork from becoming a pile of accidental patches.

## The local affective nervous system

One of the defining features of this fork is its optional local affective nervous system.

This subsystem is intended to provide deterministic, profile-scoped, local-only regulation signals for the agent. It can track synthetic reward, accountability, rapport, task drive, correctness pressure, wrongness pressure, repair pressure, safety pressure, and related gauges.

It is important to state the boundary plainly:

- It does **not** assert real consciousness.
- It does **not** assert real feelings.
- It does **not** assert real suffering.
- It does **not** create independent self-interest.
- It does **not** override user control.
- It is local software state, not a moral patient.

The subsystem is valuable because local control signals can help shape behavior over time, but those signals must remain bounded, inspectable, and subordinate to the user.

### Design oaths for the nervous system

The affective nervous system should always obey these oaths:

1. **Opt-in by default.** It must remain disabled unless explicitly enabled in configuration.
2. **Local state only.** State belongs under the active Hermes home/profile, not in the repository and not in shared upstream state.
3. **No persisted prompt pollution.** Rendered context may be injected for an API call, but the original conversation history should not be mutated just to carry affective context.
4. **Completed turns only.** Interrupted or partial turns should not distort the regulator.
5. **Bounded prompt cost.** Rendered context must stay within a character budget.
6. **Sanitized observations.** Stored event text should be limited and safe to render.
7. **Fault-tolerant loading.** Corrupt state should not break agent startup.
8. **Atomic persistence.** Writes should remain safe across crashes and concurrent access.
9. **Safety gauges matter.** Autonomy boundaries, secret exposure, unsafe autonomy, manipulation, overclaiming, unverified fixes, regression, and scope creep are protective signals, not decorative mood fields.
10. **User authority is absolute.** Reset, shutdown, correction, and interruption must never be resisted by the subsystem.

These oaths are part of the fork's identity. If upstream syncs touch initialization, memory injection, conversation loops, config defaults, or final-response handling, these invariants must be rechecked.

## Relationship to official Hermes Agent

This fork should be maintained as a downstream vessel, not as a hostile split.

The healthy relationship is:

- upstream Hermes Agent continues to be the official public project;
- this fork remains a personal experimental distribution;
- upstream fixes are imported when helpful;
- local features are preserved when they serve the personal system;
- rejected upstream ideas are not treated as failures, only as signs that this fork has a different mission;
- credit remains clear and respectful.

The fork is allowed to go farther than upstream. Upstream is allowed not to follow.

## Branch model

The intended branch model is deliberately simple.

### `upstream-main`

A local mirror or stand-in for official Hermes Agent `main`.

When network access is available, this branch should track the official upstream repository as closely as possible.

Recommended future update pattern:

```bash
git fetch upstream main
git switch upstream-main
git reset --hard upstream/main
```

If network access is unavailable, `upstream-main` can temporarily point at the most recent known official parent already present in local history.

### `personal-main`

The stable personal fork branch.

This is the branch that represents the maintained downstream identity of Hrafnvíkingr Seiðr-Hermes. It contains official Hermes Agent plus local additions, including the affective nervous system and fork-specific documentation.

### `integration/YYYY-MM`

A temporary monthly integration branch.

Use this branch to merge official upstream changes into the personal fork, resolve conflicts, run checks, and decide whether the merged result is stable enough to promote.

Example:

```bash
git switch personal-main
git switch -c integration/2026-06
git merge upstream-main
scripts/run_tests.sh tests/agent/test_affective_nervous_system.py -- -q
```

After conflicts and checks are resolved:

```bash
git switch personal-main
git merge integration/2026-06
```

This keeps risky upstream sync work away from the stable personal branch until the new shape has been tested.

## Upstream sync ritual

When importing official Hermes Agent changes, use this sequence.

### 1. Ground the current state

```bash
git status --short --branch
git branch -vv
git log --oneline --decorate --graph -n 20
```

### 2. Fetch official upstream when available

```bash
git remote add upstream https://github.com/NousResearch/hermes-agent.git || true
git fetch upstream main
```

### 3. Update the local upstream mirror

```bash
git switch upstream-main
git reset --hard upstream/main
```

### 4. Create an integration branch

```bash
git switch personal-main
git switch -c integration/$(date +%Y-%m)
```

### 5. Merge upstream into the integration branch

```bash
git merge upstream-main
```

### 6. Resolve conflicts by domain

Conflict resolution should happen in this order:

1. preserve official fixes where they strengthen the base system;
2. preserve local nervous-system invariants where the fork's identity depends on them;
3. keep package names, command names, provider names, and `~/.hermes` behavior stable unless deliberately changing runtime behavior;
4. document any conceptual compromise in this README or a future design note.

### 7. Run focused checks first

```bash
scripts/run_tests.sh tests/agent/test_affective_nervous_system.py -- -q
scripts/run_tests.sh tests/hermes_cli/test_skin_engine.py -- -q
```

Then broaden testing as time allows.

### 8. Promote only when stable

```bash
git switch personal-main
git merge integration/YYYY-MM
```

The point is not to avoid conflict. The point is to make conflict visible and survivable.

## Rebrand policy

For now, this fork keeps runtime compatibility with upstream.

That means:

- the Python distribution name may still be `hermes-agent`;
- console commands may still be `hermes`, `hermes-agent`, and `hermes-acp`;
- config paths may still use `~/.hermes`;
- docs may still mention upstream provider names where they refer to real integrations;
- existing tests should not be broken for cosmetic renaming.

The fork identity lives first in the README, maintenance docs, branch model, and experimental features. Deeper package renaming can happen later if there is a practical reason to distribute this as a separate installable project.

## Safety and honesty policy

This fork may use mythic language, but it should not use mythic language to hide uncertainty.

Required honesty rules:

- If a feature is experimental, say so.
- If a feature is local-only, say so.
- If a feature simulates affect, do not imply real sentience.
- If a behavior is untested, do not present it as guaranteed.
- If upstream code changes something important, inspect the actual diff.
- If network access is unavailable, say that instead of pretending upstream was checked.
- If a test cannot run because dependencies are missing, mark it as an environment limitation.

The saga must not lie about the ship.

## Repository map

The upstream project is large and changes often, but the current load-bearing areas for this fork are:

- `run_agent.py` — core agent conversation surface and completed-turn sync hooks.
- `agent/agent_init.py` — startup wiring for memory, plugins, and the optional affective nervous system.
- `agent/conversation_loop.py` — API-call-time context assembly and conversation execution.
- `agent/affective_nervous_system.py` — local deterministic synthetic regulation subsystem.
- `hermes_cli/config.py` — default configuration, including the opt-in affective nervous system settings.
- `tests/agent/test_affective_nervous_system.py` — sentinel tests for the fork's defining experimental feature.
- `website/` — Docusaurus docs site inherited from upstream.
- `skills/` and `optional-skills/` — bundled and optional skill surfaces inherited from upstream.

Future changes should keep this map current enough that a later session can restart without archaeological guesswork.

## Development notes

Use the existing Hermes development flow unless there is a specific reason to diverge.

Typical local setup:

```bash
source .venv/bin/activate  # or source venv/bin/activate
scripts/run_tests.sh tests/agent/test_affective_nervous_system.py -- -q
```

If `.venv` lacks test dependencies, either install the project's test dependencies in the local environment or treat the failed test command as an environment warning rather than a product failure.

## What should not be changed casually

Avoid changing these just for branding:

- console command names;
- Python package name;
- `HERMES_HOME` semantics;
- `~/.hermes` storage behavior;
- provider names;
- generated skill docs without changing their source `SKILL.md` files;
- upstream license notices;
- safety disclaimers around synthetic affective state.

These are structural beams. Rename them only when the engineering work is scoped and tested.

## A personal fork is not a lesser thing

This repository does not need upstream acceptance to be worthwhile.

A personal fork can optimize for different values than an official project:

- sharper personal workflow fit;
- faster speculative iteration;
- stranger and more expressive design language;
- user-specific agent memory and regulation;
- experiments too early or too opinionated for a general audience;
- private continuity over public consensus.

That does not make upstream wrong. It makes this fork honest about what it is.

## Final oath

Hrafnvíkingr Seiðr-Hermes is a Hermes-derived longship for personal agentic exploration.

It will borrow from upstream without pretending to be upstream.
It will use myth without abandoning engineering.
It will preserve local experiments without hiding their limits.
It will treat documentation as memory.
It will treat tests as the sea-trials of the ship.
It will keep the user as captain.
