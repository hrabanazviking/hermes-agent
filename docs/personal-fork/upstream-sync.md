# Upstream Sync Strategy for Hrafnvíkingr Seiðr-Hermes

This document records the downstream maintenance strategy for the personal fork.

## Branches

- `upstream-main` mirrors or stands in for the latest known official Hermes Agent `main`.
- `personal-main` is the stable personal downstream branch.
- `integration/YYYY-MM` is a temporary branch for monthly upstream merge work.

## Sync order

1. Fetch official upstream when network access is available.
2. Update `upstream-main` to the official upstream commit.
3. Create a new `integration/YYYY-MM` branch from `personal-main`.
4. Merge `upstream-main` into the integration branch.
5. Resolve conflicts by preserving upstream fixes and local fork invariants.
6. Run focused tests for the affective nervous system and changed areas.
7. Merge the integration branch into `personal-main` only after review.

## Local nervous-system invariants

During upstream merges, preserve these invariants:

- `affective_nervous_system.enabled` remains opt-in by default.
- State remains profile-scoped under `HERMES_HOME`.
- Synthetic affective context is injected only at API-call time and should not mutate persisted conversation history.
- Interrupted turns should not update affective state.
- Rendered context and stored observations remain bounded.
- State loading remains fault-tolerant.
- State writes remain atomic and locked.
- Safety/control gauges remain first-class signals.
- User reset, shutdown, correction, and interruption remain absolute.

## Recommended focused checks

```bash
scripts/run_tests.sh tests/agent/test_affective_nervous_system.py -- -q
scripts/run_tests.sh tests/hermes_cli/test_skin_engine.py -- -q
git diff --check
```

If the local environment lacks test dependencies, record the limitation and run the checks again in a prepared environment before treating an upstream sync as stable.
