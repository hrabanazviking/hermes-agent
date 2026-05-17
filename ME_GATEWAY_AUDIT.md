# Hermes Agent Gateway — Forensic Audit

**Auditor:** Sólrún Hvítmynd (INTJ 1w9)
**Date:** 2026-05-16
**Scope:** `gateway/`, `agent/transports/`, `hermes_cli/gateway.py`
**Profile:** Raspberry Pi Linux, systemd user service, 520MB RSS peaks, 102s shutdown timeout

---

## Executive Summary

The gateway is a ~30,000-line async Python runtime (gateway/run.py alone is 17,110 lines / 806KB)
that bridges 25+ messaging platforms to an AI agent. The code shows evidence of many bug fixes
layered on — each finding below has a corresponding fix-but-not-prevention pattern. The
architecture is **reactive-patched** rather than **proactive-designed** for resilience. Several
findings are P0 (cause crashes or data loss in the field).

**Total findings:** 34
- **P0 (crashes/data loss):** 8
- **P1 (degrades reliability):** 16
- **P2 (code smell/tech debt):** 10

---

## 1. ERROR HANDLING PATTERNS

### P0-01: No `error_classifier.py` — No Error Taxonomy
**Location:** Searched entire codebase; `error_classifier.py` does not exist.
**Finding:** There is no centralized error classification module. Each of the 25+ platform
adapters and the runner independently handle errors with ad-hoc string matching and
`except Exception as e:` catch-all blocks. The `_normalize_empty_agent_response()` in
`run.py:1077` does pattern-matching on error strings (`"context"`, `"token"`, `"400"`)
inline — fragile and incomplete. Moonshot schema HTTP 400 cascade was "partially fixed"
but no systemic classifier prevents recurrence with other providers.
**Risk:** Error handling decisions are made in 30+ separate locations with no shared taxonomy.
A new provider returning a novel error format will not be classified correctly anywhere.

### P0-02: Bare `except:` Swallowed Exceptions
**Location:** `gateway/platforms/base.py:1440` — comment says "A persistently failing status
dir used to be silent (`except: pass`)" but the comment itself indicates the pattern existed.
**Finding:** While the literal `except: pass` pattern has been cleaned from most active paths,
the codebase still contains 442 instances of `except Exception:` across gateway files, many of
which silently swallow with only `logger.debug()` — invisible in WARNING+ log levels.
**Risk:** During a production incident, critical failures are invisible because they log at
DEBUG level. Operators running default log levels will never see them.

### P0-03: `except Exception: pass` Still Present
**Location:** Multiple locations found:
- `gateway/session.py:847-849` — `except Exception: pass  # fall through to heuristic`
- `gateway/run.py:1011-1012` — `except Exception: pass`
- `gateway/run.py:16391-16393` — background delivery callbacks: `except Exception: pass`
- `gateway/run.py:16549-16550` — temp bubble deletion: `except Exception: pass`
- `gateway/run.py:12124` — `except Exception: pass` (multiple instances in agent run path)

**Finding:** 13+ instances of bare `except Exception: pass` found in the gateway alone.
Several suppress errors from background callback delivery — meaning if a callback is
misconfigured and raises, the agent silently never delivers the user's result.
**Risk:** Silent data loss when callbacks fail. The user sends a message, the agent
processes it, but the response is swallowed because the post-delivery callback raised.

### P1-04: `except Exception:` Without Context
**Location:** 442 total `except Exception:` blocks across gateway/.
**Finding:** The vast majority catch `Exception` (too broad) rather than specific
exception types. This masks bugs — a `NameError` from a typo in a try-block is caught
identically to a legitimate `ConnectionError`. The Python community consensus (PEP 8,
Google style guide) recommends catching the narrowest exception type possible.
**Risk:** Genuine code bugs (typos, attribute errors) are silently suppressed inside these
broad handlers, making them effectively impossible to detect in production.

### P1-05: Platform Reconnection — No Circuit Breaker, Just Pause
**Location:** `gateway/run.py:4820-4953` — `_retry_failed_platforms()`
**Finding:** The "circuit breaker" is a manual pause after `_PAUSE_AFTER_FAILURES = 10`
consecutive failures. It does not auto-resume — the user must run `/platform resume`.
The backoff cap is 300s (5 min). This means:
1. A transient DNS failure lasting 6 minutes causes the platform to pause permanently
   until manual intervention.
2. No "half-open" state to test if the service has recovered.
3. No auto-resume on gateway restart (restart resets the retry counter entirely,
   which is both a feature and a bug — it can restart the failure loop from zero).
**Risk:** After a prolonged outage, platforms silently pause and stop retrying. Users
must manually discover and resume them via slash commands they may not know about.

### P2-06: `except BaseException` in Session Save
**Location:** `gateway/session.py:737`
**Finding:** Catches `BaseException` (which includes `KeyboardInterrupt` and `SystemExit`)
during session JSON persistence. This is deliberate to clean up temp files, but the
`raise` on line 742 re-raises the original exception, losing the traceback chain.
**Risk:** Minor — temp file cleanup logic is correct, but the bare re-raise loses
exception chaining information.

---

## 2. CRASH RECOVERY

### P0-07: No OOM Handler — Process Killed Without State Persistence
**Location:** Entire codebase. No `setrlimit`, no `memory.high` cgroup watcher, no
graceful OOM path.
**Finding:** When the gateway hits OOM (documented: 520MB RSS peaks), the kernel's OOM
killer sends SIGKILL. The gateway has no SIGKILL handler (impossible by definition),
so it cannot: drain active agents, notify users, persist state, clean temp files, or
set `.clean_shutdown`. On restart, `suspend_recently_active()` fires, but any
mid-flight conversations are lost: the agent's partial work, tool results in progress,
and MCP server states are all discarded.
**Risk:** At 520MB peak RSS, a Pi with 1GB RAM is at constant OOM risk. Every OOM kill
loses all in-progress agent conversations with zero recovery.

### P1-08: restart.py Is Minimal — No Actual Restart Logic
**Location:** `gateway/restart.py` (20 lines)
**Finding:** `restart.py` only defines `GATEWAY_SERVICE_RESTART_EXIT_CODE = 75` and a
timeout parser. The actual restart logic is split between:
- `gateway/run.py` — `restart_signal_handler()`, `request_restart()`, `_launch_detached_restart_command()`
- `hermes_cli/gateway.py` — 5400 lines of CLI subcommand management
- `gateway/status.py` — takeover/planned-stop marker management

The restart flow is fragmented across 3 modules. The `restart.py` module name is misleading —
it should be called `restart_constants.py`.
**Risk:** New developers reading `restart.py` will not find the restart implementation.
The split makes the shutdown/restart logic hard to audit end-to-end.

### P1-09: State Persistence Across Crashes — Partial
**Location:** `gateway/run.py:5213-5239`, `gateway/session.py:680-718`
**Finding:** State persistence uses a combination of:
1. `.clean_shutdown` sentinel file (gateway/run.py:5221) — created on clean stop
2. `resume_pending` marks on session entries (session.py)
3. `restart_failure_counts` for stuck-loop detection
4. `gateway_state.json` for runtime status

But: the `.clean_shutdown` file is only created when `stop()` completes gracefully
and drain didn't time out. On SIGKILL (OOM, systemd escalation), none of this runs.
The JSONL session backup only triggers on explicit saves — in-memory session entries
modified since the last save are lost.
**Risk:** Crash recovery works for graceful SIGTERM but fails for SIGKILL. Since the
known 102s systemd timeout means SIGKILL is the terminal state for many shutdowns,
this means the nominal recovery path often doesn't execute.

### P1-10: Graceful Degradation — None
**Location:** `gateway/run.py:1706-1710` — `start_gateway()` returns `False` on any
platform connection failure.
**Finding:** When a single sub-service fails to connect (e.g., Discord DNS timeout),
the entire gateway exits with failure. There is no partial-start mode where working
platforms stay up. Instead, `start_gateway()` returns `False`, systemd restarts,
and the cycle repeats. The `_failed_platforms` retry queue exists but is only used
for post-startup failures, not initial connect failures.
**Risk:** A single misconfigured platform blocks the entire gateway. The user may
not be able to use Telegram because Discord is down.

### P1-11: Shutdown Forensics — Good But Late
**Location:** `gateway/shutdown_forensics.py` (462 lines)
**Finding:** The shutdown forensics module is well-designed: fast (<10ms) synchronous
probe, async diagnostic subprocess, takeover/planned-stop marker detection, systemd
timing alignment check. However, it only runs when a signal is *received*. It cannot
diagnose SIGKILL deaths (OOM, systemd escalation) since those bypass signal handlers.
**Risk:** The most interesting crash (OOM SIGKILL) produces zero forensics.

---

## 3. RESILIENCE PATTERNS

### P1-12: No Circuit Breaker Pattern
**Location:** Gateway-wide.
**Finding:** Despite 28 files referencing "retry" or "backoff", there is no reusable
circuit breaker. The platform reconnection logic has a manual pause mechanism
(`_PAUSE_AFTER_FAILURES = 10`) but no:
- Half-open state (test one request before full recovery)
- Recovery time window (pause is permanent until `/platform resume`)
- Health check integration
- Statistical failure tracking (all failures are treated equally)

### P1-13: Retry With Backoff — Inconsistent
**Location:** Multiple locations.
**Finding:** Exponential backoff exists for platform reconnection (`30 * 2^(attempt-1)`,
capped at 300s). But other retry paths (HTTP calls inside adapters) may use different
strategies or no backoff. The `_http_client_limits.py` module exists for HTTP-level
limits, but retry strategy is adapter-specific.
**Risk:** Inconsistent retry behavior across platforms means some recover gracefully
while others hammer the remote service.

### P1-14: No Dead Man's Switch
**Location:** Gateway-wide. No implementation found.
**Finding:** If the gateway event loop hangs (e.g., due to a blocking synchronous
operation in an async context, or a deadlocked thread), there is no external watchdog
that detects the hang and kills/restarts the process. systemd's `WatchdogSec` could
theoretically be used but the unit file would need `sd_notify` calls — none are present.
**Risk:** A hung gateway stays hung until the kernel OOM killer intervenes or an
operator notices. Could be hours of silent downtime.

### P1-15: Health Checks — Ad-Hoc
**Location:** `gateway/status.py` — `write_runtime_status()` / `read_runtime_status()`
**Finding:** `gateway_state.json` provides a snapshot of gateway health, but it's
write-only from the gateway's perspective — nobody reads it except `hermes gateway status`.
There's no health check endpoint for external monitoring (the API server could serve one
but doesn't). The status file isn't integrated with systemd's `WatchdogSec`.
**Risk:** Monitoring tools cannot detect gateway health without shelling out to
`hermes gateway status`. No Prometheus/OpenMetrics endpoint, no `/healthz`.

### P2-16: Sub-Process Health Checks — Manual Only
**Location:** `gateway/run.py:16572-16664` — `_start_cron_ticker()`
**Finding:** The cron ticker background thread runs independently but its health is
never verified. If the thread dies, cron jobs silently stop firing. The same applies
to the memory monitor thread and any adapter-internal poll loops.
**Risk:** Background service threads can die without detection. The gateway appears
healthy but cron delivery stops.

---

## 4. RESOURCE MANAGEMENT

### P0-19: Memory Leak — No Proactive GC or Leak Prevention
**Location:** `gateway/memory_monitor.py`, `gateway/run.py:62-66`
**Finding:** The memory monitor is **observational only** — it logs RSS every 5 minutes
but takes no action when RSS exceeds thresholds. With `_AGENT_CACHE_MAX_SIZE = 128` and
`_AGENT_CACHE_IDLE_TTL_SECS = 3600`, up to 128 AIAgent instances can be cached, each
holding LLM clients, tool schemas, MCP connections, and memory providers. At 520MB
observed peak, a single runaway session can push the Pi into OOM.
**Risk:** The memory monitor writes `"rss=520MB"` to the log and does nothing else.
There is no: GC trigger, agent cache eviction on high RSS, tool schema cache clearing,
MCP connection pruning, or warning to connected users.

### P0-20: File Descriptor Leaks — No Monitoring
**Location:** `gateway/run.py:5178-5189` — `shutdown_cached_clients()` comment
**Finding:** The comment at line 5178-5184 explicitly documents that "long-running
gateways accumulate async httpx transports until they hit EMFILE on macOS's default
RLIMIT_NOFILE=256." This was fixed by adding cleanup at shutdown, but:
1. There is no runtime FD monitoring (no `len(os.listdir('/proc/self/fd'))` check)
2. The `_AGENT_CACHE_MAX_SIZE = 128` agent cache can hold many httpx clients
3. Platform adapters each hold at least one persistent HTTP session
**Risk:** On a long-running gateway (weeks+), FD exhaustion is possible even with
the shutdown cleanup — a slow leak of 1 FD/hour reaches EMFILE in 10 days.

### P1-21: Subprocess Lifecycle — Best-Effort Kill, No Guarantee
**Location:** `gateway/run.py:4972-5004` — `_kill_tool_subprocesses()`
**Finding:** The shutdown path calls `process_registry.kill_all()` twice (post-interrupt
and final-cleanup), but this is documented as "best-effort." If a subprocess is in
uninterruptible sleep (D-state in /proc), the kill is queued but the process won't die
until the syscall completes. Under systemd, the 102s timeout escalates to cgroup-level
SIGKILL before the cleanups can finish.
**Risk:** Zombie processes left behind after gateway shutdown, consuming memory and
potentially holding file locks.

### P1-22: Connection Pooling — Ad-Hoc Per Adapter
**Location:** Each platform adapter manages its own HTTP sessions.
**Finding:** There is no shared connection pool. The `_http_client_limits.py` module
provides limits (max connections, timeouts) but each adapter instantiates its own
aiohttp.ClientSession or httpx.AsyncClient. This means:
1. Total open connections = sum of all adapter sessions
2. No shared DNS cache
3. No shared connection reuse across platforms
**Risk:** With 10+ platforms connected, the gateway can have 50-200 open TCP connections.
On a Pi with limited kernel socket buffers, this increases OOM risk.

### P2-23: `cleanup_image_cache` Runs Hourly But Is Blocking
**Location:** `gateway/run.py:16623-16635` — inside cron ticker
**Finding:** Image/document cache cleanup runs synchronously in the cron ticker thread.
If the cache directory is large (NFS, many files), this blocks the cron ticker for
seconds. The cron ticker also handles channel directory refresh and paste sweeping —
all serialized in a single thread.
**Risk:** A large cache can delay cron delivery by minutes during cleanup windows.

---

## 5. CROSS-PLATFORM ISSUES

### P1-24: Linux-Specific `/proc` Assumptions
**Location:** `gateway/shutdown_forensics.py:48-101` — `_read_proc_field()`, `_read_proc_cmdline()`
`gateway/status.py:111-118`, `647-655` — `/proc/<pid>/stat`, `/proc/<pid>/status`
**Finding:** The shutdown forensics and status modules make extensive use of `/proc`
filesystem reads. On macOS, these paths don't exist. The code handles this with
try/except FileNotFoundError, falling back to `psutil` or `None`. However, the
fallback path loses:
- Process start time (used for PID reuse detection in takeover markers)
- Process state inspection (stopped/Ctrl+Z detection for lock staleness)
- Parent process details

This means the gateway runs on macOS but with degraded takeover detection and
lock staleness handling.
**Risk:** On macOS, PID-reuse race conditions in takeover markers are more likely.
Two concurrent `--replace` invocations could both think they own the lock.

### P1-25: systemd-Specific Code Leaks Into Generic Paths
**Location:** `gateway/shutdown_forensics.py:322-406` — `check_systemd_timing_alignment()`
`gateway/run.py:16849` — `_signal_initiated_shutdown` logic
**Finding:** The shutdown signal handler differentiates SIGINT (planned stop) from
SIGTERM (might be systemd kill), and uses systemd `INVOCATION_ID` / `JOURNAL_STREAM`
environment variables. On macOS (launchd), none of these exist — SIGTERM is always
treated as a planned stop from `launchctl`.
**Risk:** On macOS, an external SIGTERM (e.g., from Activity Monitor) would NOT trigger
the `_signal_initiated_shutdown` flag, meaning launchd's equivalent of
`Restart=on-failure` would not revive the process.

### P1-26: Absolute Paths — SSL Certs Only
**Location:** `gateway/run.py:330-341`
**Finding:** Hardcoded absolute paths exist for SSL certificate discovery, but these
are documented with platform-specific comments (Debian, RHEL, Alpine, macOS) and are
appropriate for their purpose. The only other absolute path is a log message example
(`/home/user/.hermes/cache/documents:/output`).
**Risk:** Low — SSL cert paths are well-scoped and appropriate. No hardcoded `/home/pi/`
paths found.

### P2-27: `sys.platform == "win32"` Guards Are Sparse
**Location:** `gateway/status.py:363-401` — `_pid_exists()`, `gateway/shutdown_forensics.py:226-227`
**Finding:** Windows support is present but minimal. The `_pid_exists()` function has a
detailed (and correct) Windows implementation using ctypes to avoid the `os.kill(pid, 0)`
= `CTRL_C_EVENT` bug. However, many other paths assume POSIX:
- Signal handlers use `loop.add_signal_handler()` which raises `NotImplementedError` on Windows (caught, but silently skips)
- `/proc` reads have no Windows alternative beyond psutil
- `spawn_async_diagnostic()` returns `None` on Windows (no `ps` command)
**Risk:** The gateway reports it starts on Windows but has degraded functionality
(no shutdown diagnostics, no signal handling). This is acceptable but undocumented.

### P2-28: macOS Resource Reporting Bug Potential
**Location:** `gateway/memory_monitor.py:66-67`
**Finding:** `ru_maxrss` is in KB on Linux but in bytes on macOS. The code correctly
branches on `sys.platform == "darwin"`, but uses integer division which silently
truncates. More importantly, `resource.getrusage()` returns the high-water mark,
not current RSS — so the "memory leak detection" is actually measuring "peak memory
since process start," which never goes down.
**Risk:** The memory monitor cannot detect memory *reclamation* — once 520MB is hit,
the log forever shows 520MB even if GC reduced actual RSS to 200MB. Operators see
false-positive "non-decreasing" memory patterns.

---

## 6. DESIGN ANTI-PATTERNS

### P0-29: God Object — `GatewayRunner` (12,000+ lines)
**Location:** `gateway/run.py:1175-17110` — `class GatewayRunner`
**Finding:** The `GatewayRunner` class spans ~15,000 lines (lines 1175 through the end
of the 17,110-line file). It handles:
- Agent lifecycle (creation, caching, eviction, model resolution)
- Message routing (interrupt, queue, drain, redirect)
- Platform management (connect, disconnect, retry, pause)
- Session management (create, reset, expire, suspend)
- Voice mode state
- Slash command dispatch (30+ commands)
- Streaming/progress callbacks
- Proxy mode
- Shutdown orchestration
- Cron ticker management
- System prompt construction
- And ~50 more responsibilities

**Risk:** This is the textbook definition of a God Object. Any change to any
subsystem risks breaking an unrelated subsystem. The class cannot be unit-tested
effectively — tests must mock dozens of dependencies. The cognitive load of
understanding this class is prohibitive for new contributors.

### P0-30: Deep Call Stack With Nested Async Closures
**Location:** `gateway/run.py:14519-16569` — `_run_agent()` method
**Finding:** The `_run_agent()` method contains:
- 5 nested closures (`_run_still_current`, `progress_callback`, thread target, etc.)
- 4 mutable-list holders (`last_tool`, `last_progress_msg`, `repeat_count`, `long_tool_hint_fired`)
- Thread pool submission with result queues
- asyncio.create_task for stream consumer, progress sender, interrupt monitor
- Non-local variable modification across closure boundaries

**Risk:** The mutable-list "holders" pattern (`last_tool = [None]`) is a well-known
Python anti-pattern for working around closure scoping rules. It's error-prone and
makes the code resistant to static analysis.

### P1-31: Circular Dependency Risk — `gateway.run` ↔ `hermes_cli.gateway`
**Location:** `gateway/run.py:50-56` — imports from `agent.*` and `hermes_cli.*`
`hermes_cli/gateway.py:19-24` — imports from `gateway.status` and `gateway.restart`
**Finding:** The `hermes_cli/gateway.py` module (5400 lines) imports from `gateway.*`,
and `gateway/run.py` imports from `hermes_cli.*`. This bidirectional dependency
between packages is fragile:
- `run.py` depends on `hermes_cli.config` for config loading
- `hermes_cli/gateway.py` depends on `gateway.status` for PID management
- `run.py` depends on `hermes_cli.commands` for slash command dispatch

**Risk:** Circular imports are avoided through lazy imports (inside function bodies),
but this makes the dependency graph implicit and undiscoverable. Moving either module
risks import errors.

### P1-32: Global Mutable State — Module-Level Variables
**Location:** Multiple files:
- `gateway/memory_monitor.py:45-49` — `_monitor_thread`, `_stop_event`, `_start_time`, `_interval_seconds`, `_lock`
- `gateway/run.py:1074` — `_gateway_runner_ref` (weakref to global singleton)
- `gateway/run.py:1185-1196` — class-level defaults on `GatewayRunner` (mutable dicts!)
- `gateway/status.py:37` — `_gateway_lock_handle`

**Finding:** Module-level mutable state is common. The `GatewayRunner` class defines
mutable dicts as class-level defaults (`_running_agents_ts: Dict[str, float] = {}`,
`_session_model_overrides: Dict[str, Dict[str, str]] = {}`). If two `GatewayRunner`
instances were ever created in the same process, they'd share these dicts.
**Risk:** While only one GatewayRunner exists per process, the pattern is a ticking
time bomb for any future feature that creates multiple runners (multi-profile, tests).

### P1-33: Tight Coupling — Agent Creation in Gateway Runner
**Location:** `gateway/run.py:1816-1898` — `_resolve_session_agent_runtime()`
The GatewayRunner directly instantiates `AIAgent` objects from `run_agent.py`. This
couples the gateway to the agent's constructor interface (~60 parameters). Any change
to `AIAgent.__init__` signature potentially breaks the gateway at runtime (not import
time, since the import is lazy).
**Risk:** Agent constructor changes are a common source of gateway regressions.
The gateway should interact with the agent through a factory/facade, not direct
instantiation.

### P2-34: Deep Inheritance Chain — `BasePlatformAdapter` → 25+ subclasses
**Location:** `gateway/platforms/base.py` → 25+ adapter files
**Finding:** The `BasePlatformAdapter` is an ABC with 3,746 lines and ~50 methods.
Each of the 25+ platform adapters overrides a subset. Some adapters override the
entire `send()` method rather than using template method pattern, causing behavioral
divergence.
**Risk:** Adding a feature to all platforms requires touching 25+ files. The abstract
base class is too large to evolve safely.

### P2-35: `_hermes_home` Module Variable Re-Assignment
**Location:** `gateway/run.py:381` — `_hermes_home = get_hermes_home()`
**Finding:** Module-level `_hermes_home` is set once at import time and used throughout
the module. If someone changes `HERMES_HOME` during runtime (unlikely but possible in
a long-lived process), the stale value persists.
**Risk:** Minor — `HERMES_HOME` changes almost never happen mid-process, but the pattern
is a code smell.

---

## Summary of P0 Findings

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| P0-01 | No error classifier module | Global | Unpredictable error handling across 25+ platforms |
| P0-02 | Bare `except Exception` (442 instances) | gateway/ | Silent failure swallowing, invisible to operators |
| P0-03 | `except Exception: pass` (13+ instances) | Multiple | Silent data loss in callback delivery |
| P0-07 | No OOM handler | Global | SIGKILL loses all in-progress agent work |
| P0-19 | Memory monitor is observational only | memory_monitor.py | Knows about 520MB peak, takes no action |
| P0-20 | No FD leak monitoring | run.py | Slow FD exhaustion kills gateway after weeks |
| P0-29 | God Object (GatewayRunner, 15K lines) | run.py:1175+ | Unmaintainable, untestable, fragile |
| P0-30 | Deep nested closures with mutable holders | run.py:_run_agent | Error-prone, resistant to static analysis |

---

## Recommendations (Priority Order)

1. **Implement OOM guard:** Set `RLIMIT_AS` via `resource.setrlimit()` to trigger
   `MemoryError` before SIGKILL, or use cgroup memory.high notifications.
2. **Promote memory monitor to active:** When RSS exceeds 80% of system RAM, evict
   idle agent caches, force GC, and warn connected users.
3. **Add dead man's switch:** Integrate `sd_notify` with systemd `WatchdogSec`.
4. **Create `ErrorClassifier`:** Centralized taxonomy that all catch blocks route through
   for consistent logging, classification, and auto-recovery decisions.
5. **Split `GatewayRunner`:** Extract agent lifecycle, platform management, session
   management, and slash command dispatch into separate collaborating objects.
6. **Add FD monitoring:** Periodic check of `/proc/self/fd` count with warning at 80%
   of `RLIMIT_NOFILE`.
7. **Implement proper circuit breaker:** Half-open state, auto-recovery window,
   statistical failure rate tracking.
8. **Add health check endpoint:** `/healthz` on the API server returning JSON status
   of all connected platforms.
9. **Fix all `except Exception: pass`:** Replace with at minimum `logger.warning()`
   and structured error metadata.
10. **Add `.clean_shutdown` equivalent for SIGKILL:** Periodic state file writes
    (every ~30s during agent turns) so that at most 30s of work is lost on crash.
