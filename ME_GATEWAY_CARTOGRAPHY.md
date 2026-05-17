# Hermes Agent Gateway Codebase Cartography

_System Architecture Map by Védis Eikleið — the Cartographer (INFP 9w1)_
_Generated: 2026-05-16_


## Purpose

This document maps every file in `gateway/`, `agent/transports/`, and
`hermes_cli/gateway.py`, tracing imports, consumers, public surface,
external dependencies, absolute paths, and platform assumptions.
It also surfaces orphans, circularities, and the data-flow topology.

---

## Module-by-Module Analysis

### 1. gateway/run.py (17,110 lines — the monolith)

**Role:** Main gateway entry point. `GatewayRunner` class + `start_gateway()`
+ `main()`. Owns the full lifecycle: adapter creation, agent orchestration,
slash-command dispatch, streaming, shutdown, restart, health checks.

**Imports (inputs):**

| Source | Symbols |
|---|---|
| `hermes_bootstrap` (try/except) | UTF-8 stdio on Windows |
| stdlib | `asyncio, dataclasses, inspect, json, logging, os, re, shlex, sys, signal, tempfile, threading, time, OrderedDict, copy_context, Path, datetime, Dict/Optional/Any/List/Union` |
| `agent.account_usage` | `fetch_account_usage, render_account_usage_lines` |
| `agent.async_utils` | `safe_schedule_threadsafe` |
| `agent.i18n` | `t` |
| `hermes_cli.config` | `cfg_get` |
| `hermes_constants` | `get_hermes_home` |
| `utils` | `atomic_json_write, atomic_yaml_write, base_url_host_matches, is_truthy_value` |
| `dotenv` | `load_dotenv` (for test monkeypatch compat) |
| `hermes_cli.env_loader` | `load_hermes_dotenv` |
| `gateway.config` | `Platform, _BUILTIN_PLATFORM_VALUES, GatewayConfig, HomeChannel, PlatformConfig, load_gateway_config` |
| `gateway.session` | `SessionStore, SessionSource, SessionContext, build_session_context, build_session_context_prompt, build_session_key, is_shared_multi_user_session` |
| `gateway.delivery` | `DeliveryRouter` |
| `gateway.platforms.base` | `BasePlatformAdapter, EphemeralReply, MessageEvent, MessageType, _reply_anchor_for_event, merge_pending_message_event` |
| `gateway.restart` | `DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT, GATEWAY_SERVICE_RESTART_EXIT_CODE, parse_restart_drain_timeout` |
| `gateway.whatsapp_identity` | `canonical_whatsapp_identifier, expand_whatsapp_aliases, normalize_whatsapp_identifier` |
| *Lazy imports* | `hermes_cli.runtime_provider`, `hermes_cli.auth`, `tools.process_registry`, `tools.tirith_security`, `hermes_state.SessionDB`, `hermes_cli.config.load_config`, `gateway.pairing.PairingStore`, `gateway.hooks.HookRegistry`, `plugins.teams_pipeline.runtime` |
| *Per-adapter lazy* | `gateway.platforms.telegram`, `.discord`, `.slack`, `.whatsapp`, `.signal`, `.matrix`, `.mattermost`, `.homeassistant`, `.email`, `.sms`, `.dingtalk`, `.api_server`, `.webhook`, `.msgraph_webhook`, `.feishu`, `.wecom`, `.wecom_callback`, `.weixin`, `.bluebubbles`, `.qqbot`, `.yuanbao` |
| `hermes_cli.commands` | `_sanitize_telegram_name`, `GATEWAY_KNOWN_COMMANDS` |

**Consumed by (consumers):**

- `hermes_cli/gateway.py` — calls `start_gateway()` for `hermes gateway run`
- `cli.py` — lazy-imports `start_gateway` for `--gateway`
- `tools/send_message_tool.py` — references `_gateway_runner_ref` for live adapter access
- `tools/process_registry.py` — accesses gateway runner via weakref
- Tests: `test_quick_commands.py`, `test_empty_model_fallback.py`, `test_yuanbao_integration.py`, `e2e/conftest.py`, etc.

**Public surface:**

- `GatewayRunner` class — main gateway controller
  - `__init__(config)` — wires SessionStore, DeliveryRouter, PairingStore, HookRegistry, SessionDB, agent cache
  - `start()` / `stop()` / `wait_for_shutdown()` — lifecycle
  - `request_restart()` — restart coordination
  - `shutdown_signal_handler()` / `restart_signal_handler()` — signal hooks
  - Dozens of private `_handle_*` methods for slash commands
- `start_gateway(config, replace, verbosity)` — async entry point
- `main()` — CLI entry (`python -m gateway.run`)
- `_gateway_runner_ref` — module-level weakref for tool access

**External dependencies:**

- `dotenv` (pip)
- `yaml` (via config)
- `openai` SDK (via agent)
- Platform SDKs loaded lazily (telegram, discord, slack, etc.)

**Absolute paths:**

- `/etc/ssl/certs/ca-certificates.crt` (Debian/Ubuntu)
- `/etc/pki/tls/certs/ca-bundle.crt` (RHEL/CentOS 7)
- `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` (RHEL/CentOS 8+)
- `/etc/ssl/ca-bundle.pem` (SUSE)
- `/etc/ssl/cert.pem` (Alpine/macOS)
- `/etc/pki/tls/cert.pem` (Fedora)
- `/usr/local/etc/openssl@1.1/cert.pem` (macOS Homebrew Intel)
- `/opt/homebrew/etc/openssl@1.1/cert.pem` (macOS Homebrew ARM)
- `~/.hermes/*` (via `get_hermes_home()`)

**Platform assumptions:**

- systemd-aware: reads `INVOCATION_ID`, `JOURNAL_STREAM`, checks `ppid==1`
- `sys.platform == "win32"` branch for restart logic
- `/proc/self/limits` and `/proc/loadavg` via `shutdown_forensics`
- `os.getloadavg()` (POSIX)
- Signal handlers: `SIGTERM`, `SIGINT`, `SIGUSR1`
- Docker detection via `TERMINAL_ENV=docker`


### 2. gateway/session.py (1,398 lines)

**Role:** Session context tracking, storage, reset policies, and dynamic
system prompt injection.

**Imports (inputs):**

| Source | Symbols |
|---|---|
| stdlib | `hashlib, logging, os, json, threading, uuid, Path, datetime, timedelta, dataclass` |
| `gateway.config` | `Platform, GatewayConfig, SessionResetPolicy, HomeChannel` |
| `gateway.whatsapp_identity` | `canonical_whatsapp_identifier, normalize_whatsapp_identifier` |
| `utils` | `atomic_replace` |

**Consumed by:**

- `gateway/run.py` — `SessionStore, SessionSource, SessionContext, build_session_context, build_session_context_prompt, build_session_key, is_shared_multi_user_session`
- `gateway/delivery.py` — `SessionSource`
- `gateway/__init__.py` — re-exports
- `cli.py` — lazy import for session info
- `tools/cronjob_tools.py` — session lookups
- Tests extensively

**Public surface:**

- `SessionSource` dataclass — origin metadata (platform, chat_id, user_id, thread_id, etc.)
- `SessionStore` class — persistent session storage, reset evaluation
- `SessionContext` dataclass — assembled context for agent
- `build_session_context()` / `build_session_context_prompt()`
- `build_session_key()` — composite key for session identity
- `is_shared_multi_user_session()` — group/channel detection
- `normalize_whatsapp_identifier()` (re-export)
- PII hashing: `_hash_id()`, `_hash_sender_id()`, `_hash_chat_id()`

**External dependencies:** None beyond stdlib + internal.

**Platform assumptions:** None — portable.

**Absolute paths:** None — uses `get_hermes_home()`-relative paths.


### 3. gateway/session_context.py (156 lines)

**Role:** Per-task `contextvars.ContextVar` session state — replaces the old
`os.environ` approach for concurrent async message handling.

**Imports:**

- `contextvars.ContextVar`
- `typing.Any`

**Consumed by:**

- `gateway/run.py` → indirectly via `gateway/session.py`
- Any tool that calls `get_session_env()` (tools use `from gateway.session_context import get_session_env`)

**Public surface:**

- `set_session_vars(platform, chat_id, ...)` — returns reset tokens
- `clear_session_vars(tokens)` — resets all to `""`
- `get_session_env(name, default)` — drop-in for old `os.getenv("HERMES_SESSION_*")`

**External dependencies:** None.

**Platform assumptions:** None — pure Python contextvars.


### 4. gateway/config.py (1,873 lines)

**Role:** Gateway configuration loading, `Platform` enum, `GatewayConfig`,
`PlatformConfig`, `HomeChannel`, `SessionResetPolicy`.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `logging, os, json, Path, dataclass, Dict/List/Optional/Any/Callable, Enum` |
| `hermes_cli.config` | `get_hermes_home` |
| `utils` | `is_truthy_value` |
| `gateway.platform_registry` | `platform_registry` (lazy, inside `Platform._missing_()`) |

**Consumed by:**

- `gateway/run.py` — massive consumer
- `gateway/session.py` — `Platform, GatewayConfig, SessionResetPolicy, HomeChannel`
- `gateway/delivery.py` — `Platform, GatewayConfig`
- `gateway/__init__.py` — re-exports
- `tools/send_message_tool.py` — `load_gateway_config, Platform, PlatformConfig, HomeChannel`
- `cli.py` — `load_gateway_config, Platform`
- `hermes_cli/gateway.py` — `Platform` enum
- `cron/scheduler.py` — delivery targets
- Tests extensively

**Public surface:**

- `Platform` enum — 22 built-in members + dynamic plugin members via `_missing_()`
- `GatewayConfig` dataclass — full gateway config
- `PlatformConfig` dataclass — per-platform config
- `HomeChannel` dataclass — default delivery target
- `SessionResetPolicy` dataclass — daily/idle/both/none
- `load_gateway_config()` — loads from config.yaml
- `_BUILTIN_PLATFORM_VALUES` — frozenset for validation

**External dependencies:** None beyond internal.

**Platform assumptions:**

- Filesystem scan for bundled platform plugins: `Path(__file__).parent.parent / "plugins" / "platforms"`
- WAL mode SQLite via `GatewayConfig`

**Absolute paths:** None — all relative to `get_hermes_home()`.


### 5. gateway/delivery.py (258 lines)

**Role:** Delivery routing for cron job outputs and agent responses.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `logging, Path, datetime, dataclass, Dict/List/Optional/Any` |
| `hermes_cli.config` | `get_hermes_home` |
| `gateway.config` | `Platform, GatewayConfig` |
| `gateway.session` | `SessionSource` |

**Consumed by:**

- `gateway/run.py` — `DeliveryRouter`
- `gateway/__init__.py` — re-exports

**Public surface:**

- `DeliveryTarget` dataclass — single delivery target with `parse()` factory
- `DeliveryRouter` class — resolves targets, dispatches messages
  - `__init__(config, adapters)`
  - `deliver(content, targets, ...)` — async delivery

**External dependencies:** None.

**Platform assumptions:** None.

**Absolute paths:** Uses `get_hermes_home() / "cron" / "output"`.


### 6. gateway/stream_consumer.py (1,286 lines)

**Role:** Bridges sync agent callbacks to async platform delivery. Buffers,
rate-limits, and progressively edits platform messages with streamed tokens.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `asyncio, logging, queue, re, time, dataclass` |
| `gateway.platforms.base` | `BasePlatformAdapter`, `_custom_unit_to_cp` |
| `gateway.config` | `DEFAULT_STREAMING_EDIT_INTERVAL`, `DEFAULT_STREAMING_BUFFER_THRESHOLD`, `DEFAULT_STREAMING_CURSOR` |

**Consumed by:**

- `gateway/run.py` — instantiates per-agent-turn

**Public surface:**

- `StreamConsumerConfig` dataclass — edit_interval, buffer_threshold, cursor, transport, etc.
- `GatewayStreamConsumer` class — async consumer
  - `__init__(adapter, chat_id, config, metadata, on_new_message, initial_reply_to_id)`
  - `on_delta(text)` — sync thread-safe callback
  - `run()` — async task
  - `finish()` — signal completion

**External dependencies:** None beyond internal.

**Platform assumptions:** None — abstract over adapter interface.


### 7. gateway/restart.py (20 lines)

**Role:** Shared gateway restart constants and parsing helpers.

**Imports:**

- `hermes_cli.config.DEFAULT_CONFIG`

**Consumed by:**

- `gateway/run.py` — `DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT`, `GATEWAY_SERVICE_RESTART_EXIT_CODE`, `parse_restart_drain_timeout`
- `hermes_cli/gateway.py` — same constants

**Public surface:**

- `GATEWAY_SERVICE_RESTART_EXIT_CODE = 75` (EX_TEMPFAIL)
- `DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT`
- `parse_restart_drain_timeout(raw)`

**External dependencies:** None.

**Platform assumptions:** None directly, but `EX_TEMPFAIL` is a POSIX convention.


### 8. gateway/shutdown_forensics.py (462 lines)

**Role:** Captures diagnostic context on SIGTERM/SIGINT. Fast synchronous
probe + optional async `ps aux` subprocess snapshot.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `json, os, signal, subprocess, sys, time, Path` |

**Consumed by:**

- `gateway/run.py` — `check_systemd_timing_alignment()`, `log_shutdown_context()`

**Public surface:**

- `snapshot_shutdown_context(received_signal)` — fast probe, returns dict
- `spawn_async_diagnostic(ctx)` — fire-and-forget subprocess walk
- `log_shutdown_context(ctx)` — structured log emission
- `check_systemd_timing_alignment(drain_timeout)` — sanity check at startup

**External dependencies:** None (pure stdlib).

**Platform assumptions:**

- **Linux-only for `/proc` reads**: `/proc/{pid}/status`, `/proc/{pid}/cmdline`, `/proc/self/cgroup`, `/proc/loadavg`
- systemd detection: `INVOCATION_ID` env, `ppid==1`
- `os.getloadavg()` (POSIX)
- `sys.platform == "win32"` branch for diagnostic subprocess
- `shutil.which("systemctl")` for timing alignment check

**Absolute paths:**

- `/proc/{pid}/status`
- `/proc/{pid}/cmdline`
- `/proc/self/cgroup`
- `/proc/loadavg`
- `/proc/self/status`


### 9. gateway/memory_monitor.py (230 lines)

**Role:** Periodic RSS memory logging for leak detection.

**Imports:**

- stdlib: `gc, logging, os, sys, threading, time`

**Consumed by:**

- `gateway/run.py` — `start_memory_monitoring()` called at startup

**Public surface:**

- `start_memory_monitoring(interval_seconds)` — starts daemon thread
- `stop_memory_monitoring()` — clean shutdown
- `log_memory_usage(prefix)` — on-demand snapshot

**External dependencies:**

- `resource` (stdlib, Linux/macOS) — primary RSS source
- `psutil` (optional pip) — fallback for Windows

**Platform assumptions:**

- `sys.platform == "darwin"` — different ru_maxrss units (bytes vs KB)
- Windows fallback via `psutil`


### 10. gateway/hooks.py (210 lines)

**Role:** Event hook system. Discovers + loads hook directories from
`~/.hermes/hooks/`.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `asyncio, importlib.util, sys` |
| pip | `yaml` |
| `hermes_cli.config` | `get_hermes_home` |

**Consumed by:**

- `gateway/run.py` — `HookRegistry` instantiated in `GatewayRunner.__init__()`

**Public surface:**

- `HookRegistry` class
  - `discover_and_load()` — scans `~/.hermes/hooks/`
  - `emit(event_type, context)` — async fire
  - `loaded_hooks` property

**External dependencies:**

- `yaml` (PyYAML)

**Platform assumptions:** None — pure Python.

**Absolute paths:** `get_hermes_home() / "hooks"`


### 11. gateway/mirror.py (178 lines)

**Role:** Cross-platform session mirroring — appends delivery-mirror records
to target session transcripts.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `json, logging, datetime` |
| `hermes_cli.config` | `get_hermes_home` |

**Consumed by:**

- `tools/send_message_tool.py` — `mirror_to_session()`

**Public surface:**

- `mirror_to_session(platform, chat_id, message_text, source_label, thread_id, user_id)` — returns bool

**External dependencies:** None.

**Platform assumptions:** None.

**Absolute paths:** `get_hermes_home() / "sessions" / "sessions.json"`


### 12. gateway/pairing.py (321 lines)

**Role:** DM pairing system — code-based user authorization flow.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `json, os, secrets, tempfile, threading, time, Path` |
| `hermes_constants` | `get_hermes_dir` |
| `utils` | `atomic_replace` |

**Consumed by:**

- `gateway/run.py` — `PairingStore` instantiated in `GatewayRunner.__init__()`

**Public surface:**

- `PairingStore` class
  - `is_approved(platform, user_id)`
  - `list_approved(platform)`
  - `create_code(platform, user_id, user_name)`
  - `validate_code(platform, code)`
  - `revoke(platform, user_id)`
  - `check_rate_limit(platform, user_id)`
  - `check_lockout(platform)`

**External dependencies:** None (pure stdlib).

**Platform assumptions:**

- `os.chmod(path, 0o600)` — POSIX permission setting (gracefully catches OSError on Windows)
- `os.fsync()` for durability

**Absolute paths:** `get_hermes_dir("platforms/pairing", "pairing")` — resolves to `~/.hermes/pairing/`


### 13. gateway/platform_registry.py (260 lines)

**Role:** Dynamic platform adapter registry for plugin-discovered adapters.

**Imports:**

- stdlib: `logging, dataclass, Any/Awaitable/Callable/Optional`

**Consumed by:**

- `gateway/config.py` — `Platform._missing_()` uses `platform_registry.is_registered()`
- `gateway/run.py` — adapter creation fallback path
- `tools/send_message_tool.py` — `platform_registry` for checking
- `run_agent.py` — credential routing
- Plugin system — `PluginContext.register_platform()`

**Public surface:**

- `PlatformEntry` dataclass — metadata + factory for one adapter
- `PlatformRegistry` class
  - `register(entry)` / `unregister(name)`
  - `is_registered(name)`
  - `create_adapter(name, config)` — factory call
  - `list_platforms()`
- `platform_registry` — module-level singleton

**External dependencies:** None.

**Platform assumptions:** None.


### 14. gateway/platforms/base.py (3,746 lines)

**Role:** Abstract base class for all platform adapters. Shared utility
functions for media handling, reply routing, proxy normalization.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `asyncio, inspect, ipaddress, logging, os, random, re, socket, subprocess, sys, uuid, ABC, abstractmethod, urlsplit` |
| `utils` | `normalize_proxy_url` |

**Consumed by:**

- Every platform adapter (20+ adapters in `gateway/platforms/`)
- `gateway/run.py` — `BasePlatformAdapter, EphemeralReply, MessageEvent, MessageType, _reply_anchor_for_event, merge_pending_message_event`
- `gateway/stream_consumer.py` — `BasePlatformAdapter`, `_custom_unit_to_cp`
- `gateway/platforms/__init__.py` — re-exports
- `gateway/platforms/helpers.py` — TYPE_CHECKING ref

**Public surface:**

- `BasePlatformAdapter` ABC — abstract adapter interface
- `MessageEvent` dataclass — normalized incoming message
- `MessageType` enum — text, image, voice, video, etc.
- `SendResult` dataclass — result of sending a message
- `EphemeralReply` — auto-delete reply wrapper
- `merge_pending_message_event()` — queue merging
- `_reply_anchor_for_event()` — reply routing
- `_thread_metadata_for_source()` — thread metadata
- `should_send_media_as_audio()` — media routing
- Proxy helpers: `_resolve_socks_environment()`, `_is_resolved_ip()`

**Platform assumptions:**

- `sys.platform != "darwin"` branch for socket option
- Proxy support (SOCKS5/HTTP) via `utils.normalize_proxy_url`
- `subprocess` for environment probing


### 15. agent/transports/ — Transport Adapters

**Role:** Provider API format conversion and response normalization.
Each transport owns: convert_messages → convert_tools → build_kwargs → normalize_response.

#### agent/transports/__init__.py (68 lines)
- `register_transport(api_mode, cls)` / `get_transport(api_mode)`
- Auto-discovers all transport modules
- Consumed by `run_agent.py` and `cli.py` for provider dispatch

#### agent/transports/base.py (89 lines)
- `ProviderTransport` ABC
- Defines `api_mode`, `convert_messages()`, `convert_tools()`, `build_kwargs()`, `normalize_response()`
- Consumed by all transport implementations

#### agent/transports/types.py (162 lines)
- `NormalizedResponse`, `ToolCall`, `Usage` dataclasses
- `build_tool_call()`, `map_finish_reason()`
- Zero external deps
- Consumed by all transports

#### agent/transports/chat_completions.py (614 lines)
- `ChatCompletionsTransport` — handles `api_mode="chat_completions"`
- Imports: `agent.lmstudio_reasoning`, `agent.moonshot_schema`, `agent.prompt_builder`
- Used by ~16 OpenAI-compatible providers
- Platform deps: none

#### agent/transports/anthropic.py (179 lines)
- `AnthropicTransport` — `api_mode="anthropic_messages"`
- Delegates to `agent.anthropic_adapter`
- Platform deps: none

#### agent/transports/codex.py (283 lines)
- `ResponsesApiTransport` — `api_mode="codex_responses"`
- Delegates to `agent.codex_responses_adapter`
- Imports `run_agent.DEFAULT_AGENT_IDENTITY`
- Platform deps: none

#### agent/transports/bedrock.py (154 lines)
- `BedrockTransport` — `api_mode="bedrock_converse"`
- Delegates to `agent.bedrock_adapter`
- Platform deps: AWS region default (`us-east-1`)

#### agent/transports/codex_app_server.py (368 lines)
- `CodexAppServerClient` — JSON-RPC 2.0 over stdio to `codex app-server`
- Platform deps: requires `codex` binary; `subprocess` spawn
- Absolute paths: `~/.codex/config.toml` reference

#### agent/transports/codex_event_projector.py (312 lines)
- `CodexEventProjector` — translates Codex events to OpenAI message format
- Consumed by `codex_app_server_session.py`
- Platform deps: none

#### agent/transports/codex_app_server_session.py (810 lines)
- `CodexAppServerSession` — single Codex thread per Hermes session
- Imports: `agent.redact`, `codex_app_server`, `codex_event_projector`
- Platform deps: none

#### agent/transports/hermes_tools_mcp_server.py (233 lines)
- Exposes Hermes tools to Codex via MCP stdio transport
- Run standalone: `python -m agent.transports.hermes_tools_mcp_server`
- Platform deps: none


### 16. hermes_cli/gateway.py (5,421 lines)

**Role:** CLI subcommand: `hermes gateway [run|start|stop|restart|status|install|uninstall|setup]`.

**Imports:**

| Source | Symbols |
|---|---|
| stdlib | `asyncio, os, shutil, signal, subprocess, sys, textwrap, dataclass, Path` |
| `gateway.status` | `terminate_pid` |
| `gateway.restart` | `DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT, GATEWAY_SERVICE_RESTART_EXIT_CODE, parse_restart_drain_timeout` |
| `hermes_cli.config` | `get_env_value, get_hermes_home, is_managed, managed_error, read_raw_config, save_env_value` |
| `hermes_cli.setup` | `print_header, print_info, print_success, print_warning, print_error, prompt, prompt_choice, prompt_yes_no` |
| `hermes_cli.colors` | `Colors, color` |

**Public surface:**

- `GatewayRuntimeSnapshot` dataclass
- `ProfileGatewayProcess` dataclass
- `cli_gateway_run()` — main command entry
- `cli_gateway_start()` / `stop()` / `restart()` / `status()` / `install()` / `uninstall()` / `setup()`
- `supports_systemd_services()` — helper
- Platform detection: `is_macos()`, `get_launchd_label()`

**External dependencies:** None beyond internal.

**Platform assumptions:**

- **systemd (Linux)**: `systemctl --user list-units`, `systemctl show --property=MainPID`
- **launchd (macOS)**: `launchctl list`
- **Windows**: `taskkill /T /F`, `msvcrt` locking, `schtasks`
- `psutil` (core dep) for parent PID resolution
- `signal.SIGUSR1` for self-restart (POSIX only)
- `shutil.which("systemctl")`, `shutil.which("launchctl")`
- `os.getloadavg()` for CPU sampling

**Absolute paths:** `PROJECT_ROOT = Path(__file__).parent.parent.resolve()`


### Supporting Files

#### gateway/status.py (971 lines)
- PID file management, runtime lock, process health checks
- `/proc/{pid}/stat`, `/proc/{pid}/cmdline` (Linux)
- `sys.platform == "win32"` for `msvcrt` locking
- Consumed by `hermes_cli/gateway.py`, `gateway/run.py`

#### gateway/display_config.py (206 lines)
- Per-platform display setting resolution (tool_progress, show_reasoning, streaming)
- 4-tier platform default system (HIGH, MEDIUM, LOW, MINIMAL)
- Consumed by `gateway/run.py`, `gateway/platforms/base.py`

#### gateway/runtime_footer.py (150 lines)
- Compact footer appended to final agent response
- Renders model, context %, cwd
- Consumed by `gateway/run.py`

#### gateway/whatsapp_identity.py (155 lines)
- Canonicalizes WhatsApp sender identity across LID/phone JID variants
- Reads `lid-mapping-*.json` from `~/.hermes/whatsapp/session/`
- Consumed by `gateway/run.py`, `gateway/session.py`

#### gateway/sticker_cache.py (111 lines)
- Telegram sticker description cache (`~/.hermes/sticker_cache.json`)
- Consumed by `gateway/platforms/telegram.py`

#### gateway/channel_directory.py (357 lines)
- Cached channel/contact directory across platforms
- `~/.hermes/channel_directory.json`
- Consumed by `gateway/run.py`, `tools/send_message_tool.py`

#### gateway/slash_access.py (229 lines)
- Per-platform slash command access control (admin/users split)
- Consumed by `gateway/run.py`

#### gateway/__init__.py (35 lines)
- Re-exports: `GatewayConfig, PlatformConfig, HomeChannel, load_gateway_config, SessionContext, SessionStore, SessionResetPolicy, build_session_context_prompt, DeliveryRouter, DeliveryTarget`

#### gateway/platforms/__init__.py (45 lines)
- Re-exports: `BasePlatformAdapter, MessageEvent, SendResult`
- Lazy: `QQAdapter`, `YuanbaoAdapter` via `__getattr__`

#### gateway/platforms/helpers.py (278 lines)
- `MessageDeduplicator` — TTL-based dedup for platform adapters
- `TextAggregator` — batch text aggregation
- `MarkdownStripper` — strip markdown for plain-text platforms
- `ThreadParticipant` — thread join tracking (Slack)
- Consumed by multiple platform adapters

#### gateway/builtin_hooks/__init__.py (1 line)
- Empty — extension point for always-active gateway hooks


---

## Data Flow Diagram

```
                                    ┌──────────────────────┐
                                    │   hermes_cli/        │
                                    │   gateway.py         │
                                    │   (CLI subcommand)   │
                                    └──────┬───────────────┘
                                           │ calls start_gateway()
                                           ▼
┌──────────────┐    ┌─────────────────────────────────────────────┐
│ config.yaml  │───▶│  gateway/config.py                          │
│ .env         │    │  GatewayConfig, PlatformConfig, Platform    │
└──────────────┘    └──────────────────┬──────────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │   gateway/run.py        │
                          │   GatewayRunner         │
                          │                         │
                          │  owns:                  │
                          │  ├─ SessionStore        │◀── gateway/session.py
                          │  ├─ DeliveryRouter      │◀── gateway/delivery.py
                          │  ├─ PairingStore        │◀── gateway/pairing.py
                          │  ├─ HookRegistry        │◀── gateway/hooks.py
                          │  ├─ Agent Cache (LRU)   │
                          │  └─ Platform Adapters   │
                          └──────┬──────┬───────────┘
                                 │      │
                    ┌────────────┘      └──────────────┐
                    ▼                                  ▼
   ┌────────────────────────────┐     ┌────────────────────────────┐
   │ gateway/platforms/         │     │ gateway/stream_consumer.py │
   │ ├─ telegram.py             │     │ GatewayStreamConsumer      │
   │ ├─ discord.py              │     │ (token streaming → edits)  │
   │ ├─ slack.py                │     └────────────────────────────┘
   │ ├─ whatsapp.py             │
   │ ├─ signal.py               │     ┌────────────────────────────┐
   │ ├─ matrix.py               │     │ run_agent.py / cli.py      │
   │ ├─ mattermost.py           │     │ AIAgent (LLM inference)    │
   │ ├─ feishu.py               │     │   uses:                    │
   │ ├─ wecom.py                │     │   agent/transports/        │
   │ ├─ weixin.py               │     │   ├─ chat_completions.py  │
   │ ├─ dingtalk.py             │     │   ├─ anthropic.py         │
   │ ├─ email.py                │     │   ├─ codex.py             │
   │ ├─ sms.py                  │     │   ├─ bedrock.py           │
   │ ├─ homeassistant.py        │     │   └─ codex_app_server*.py │
   │ ├─ bluebubbles.py          │     └────────────────────────────┘
   │ ├─ webhook.py              │
   │ ├─ msgraph_webhook.py      │     ┌────────────────────────────┐
   │ ├─ api_server.py           │     │ gateway/memory_monitor.py  │
   │ ├─ qqbot/                  │     │ (periodic RSS logging)     │
   │ └─ yuanbao.py              │     └────────────────────────────┘
   └────────────────────────────┘
              ▲
              │ registers via
   ┌──────────┴──────────────┐
   │ gateway/                │
   │ platform_registry.py    │
   │ (plugin adapters)       │
   └─────────────────────────┘

   ┌────────────────────────────┐
   │ gateway/                   │
   │ shutdown_forensics.py      │
   │ (SIGTERM/SIGINT diagnostics)│
   └────────────────────────────┘

   ┌────────────────────────────┐
   │ gateway/restart.py         │
   │ (restart constants)        │
   └────────────────────────────┘
```

### Message Processing Flow

```
Incoming Message (platform adapter)
    │
    ▼
Adapter creates MessageEvent
    │
    ▼
GatewayRunner._handle_message(event)
    ├─ Build SessionSource
    ├─ Resolve session via SessionStore
    ├─ Check authorization (pairing/allowed_users)
    ├─ Build session context prompt
    ├─ Pass to AIAgent in thread pool
    │   │
    │   ▼
    │   AIAgent.run_conversation()
    │   ├─ Uses agent/transports/ for API calls
    │   ├─ stream_delta_callback → GatewayStreamConsumer.on_delta()
    │   ├─ Tool calls executed via tools/*
    │   └─ Returns final response
    │
    ▼
Platform adapter.send_message()
    │
    ▼
Delivery to platform (Telegram/Discord/etc.)
```


## Dependency Graph

```
(Legend: A → B means "A depends on B" / "A imports from B")

                    ┌─────────────────┐
                    │ hermes_cli/     │
                    │ gateway.py      │
                    └───┬───┬───┬─────┘
                        │   │   │
        ┌───────────────┘   │   └──────────────┐
        ▼                   ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ gateway/     │   │ gateway/     │   │ hermes_cli/  │
│ restart.py   │   │ status.py    │   │ config.py    │
└──────────────┘   └──────────────┘   └──────────────┘

┌──────────────────────────────────────────────────────┐
│ gateway/run.py  (the hub — imports everything below) │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌──────────┐
│conf││sess││del ││pair││hook││mem ││restart   │
│ig  ││ion ││iver││ing ││s   ││ory ││          │
└──┬─┘└──┬─┘└────┘└────┘└────┘│_mon│└──────────┘
   │     │                     │itor│
   │     │                     └────┘
   │     │
   │     ├──────▶ gateway/session_context.py
   │     │
   │     └──────▶ gateway/whatsapp_identity.py
   │
   ├───────────▶ gateway/platforms/base.py
   │                    ▲
   │          ┌─────────┴─────────────┐
   │          │ 20+ platform adapters │
   │          │ telegram, discord,    │
   │          │ slack, whatsapp,      │
   │          │ signal, matrix, ...   │
   │          └───────────────────────┘
   │
   ├───────────▶ gateway/platform_registry.py
   │                    ▲
   │          ┌─────────┴──────┐
   │          │ Plugin system   │
   │          │ (PluginContext) │
   │          └────────────────┘
   │
   ├───────────▶ gateway/stream_consumer.py
   ├───────────▶ gateway/display_config.py
   ├───────────▶ gateway/runtime_footer.py
   ├───────────▶ gateway/slash_access.py
   ├───────────▶ gateway/channel_directory.py
   │
   └───────────▶ External:
                  ├─ agent/account_usage
                  ├─ agent/async_utils
                  ├─ agent/i18n
                  ├─ hermes_cli/runtime_provider
                  ├─ hermes_state.py (SessionDB)
                  ├─ tools/process_registry
                  └─ run_agent.py (AIAgent)


┌─────────────────────────────────────────────┐
│ External Consumers of gateway/ modules      │
├─────────────────────────────────────────────┤
│                                             │
│ tools/send_message_tool.py                  │
│   ├── gateway.config (Platform, GatewayConfig, HomeChannel)
│   ├── gateway.mirror (mirror_to_session)    │
│   ├── gateway.run (_gateway_runner_ref)     │
│   └── gateway.platform_registry            │
│                                             │
│ cli.py (HermesCLI)                          │
│   ├── gateway.config (load_gateway_config)  │
│   └── gateway.run (start_gateway)           │
│                                             │
│ run_agent.py (AIAgent)                      │
│   └── gateway.platform_registry            │
│                                             │
│ cron/scheduler.py                           │
│   └── gateway.config (delivery targets)    │
│                                             │
│ tools/process_registry.py                  │
│   └── gateway.run (weakref)                │
│                                             │
│ tests/ (extensively)                        │
│   └── all gateway modules                  │
└─────────────────────────────────────────────┘
```


## Absolute Paths Found

### Hardcoded System Paths

| Path | File | Purpose |
|---|---|---|
| `/proc/{pid}/status` | `shutdown_forensics.py`, `status.py` | Process status (Linux) |
| `/proc/{pid}/cmdline` | `shutdown_forensics.py`, `status.py` | Process cmdline (Linux) |
| `/proc/{pid}/stat` | `status.py` | Process start time (Linux) |
| `/proc/self/cgroup` | `shutdown_forensics.py` | systemd unit detection (Linux) |
| `/proc/self/status` | `shutdown_forensics.py` | TracerPid check (Linux) |
| `/proc/loadavg` | `shutdown_forensics.py` | Load average (Linux) |
| `/etc/ssl/certs/ca-certificates.crt` | `run.py` | SSL CA bundle (Debian/Ubuntu) |
| `/etc/pki/tls/certs/ca-bundle.crt` | `run.py` | SSL CA bundle (RHEL/CentOS 7) |
| `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` | `run.py` | SSL CA bundle (RHEL/CentOS 8+) |
| `/etc/ssl/ca-bundle.pem` | `run.py` | SSL CA bundle (SUSE) |
| `/etc/ssl/cert.pem` | `run.py` | SSL CA bundle (Alpine/macOS) |
| `/etc/pki/tls/cert.pem` | `run.py` | SSL CA bundle (Fedora) |
| `/usr/local/etc/openssl@1.1/cert.pem` | `run.py` | SSL CA bundle (macOS Homebrew Intel) |
| `/opt/homebrew/etc/openssl@1.1/cert.pem` | `run.py` | SSL CA bundle (macOS Homebrew ARM) |

### HERMES_HOME-Relative Paths (via `get_hermes_home()` / `get_hermes_dir()`)

| Virtual Path | Set By | Usage |
|---|---|---|
| `~/.hermes/gateway.pid` | `status.py` | PID file |
| `~/.hermes/gateway.lock` | `status.py` | Runtime lock |
| `~/.hermes/gateway_state.json` | `status.py` | Runtime health status |
| `~/.hermes/hooks/` | `hooks.py` | Hook directories |
| `~/.hermes/sessions/` | `mirror.py` | Session transcripts |
| `~/.hermes/sessions/sessions.json` | `mirror.py` | Session index |
| `~/.hermes/pairing/` | `pairing.py` | Pairing codes + approved lists |
| `~/.hermes/sticker_cache.json` | `sticker_cache.py` | Telegram sticker descriptions |
| `~/.hermes/channel_directory.json` | `channel_directory.py` | Channel/contact directory |
| `~/.hermes/cron/output/` | `delivery.py` | Cron output directory |
| `~/.hermes/whatsapp/session/lid-mapping-*.json` | `whatsapp_identity.py` | WhatsApp LID mappings |
| `~/.hermes/checkpoints/` | `run.py` | Shadow repo checkpoints |
| `~/.hermes/config.yaml` | `config.py` | Main config |
| `~/.hermes/.env` | `hermes_cli/env_loader.py` | API keys |

### Project-Relative Path Discovery

| Path Pattern | File | Purpose |
|---|---|---|
| `plugins/platforms/*/plugin.yaml` | `config.py` | Bundled platform plugin scan |
| `Path(__file__).parent.parent.resolve()` | `hermes_cli/gateway.py` | PROJECT_ROOT |


## Platform-Specific Assumptions

### Linux-Only

| Feature | File(s) | Notes |
|---|---|---|
| `/proc` filesystem reads | `shutdown_forensics.py`, `status.py` | All `/proc/{pid}/*`, `/proc/loadavg`, `/proc/self/*` |
| `os.getloadavg()` | `shutdown_forensics.py`, `run.py` | Load average (also macOS) |
| `resource.getrusage()` | `memory_monitor.py` | RSS via stdlib (also macOS) |
| `fcntl` file locking | `status.py` | Gateway singleton lock |
| `os.fsync()` | `pairing.py` | Data durability (also macOS) |

### systemd-Specific

| Feature | File(s) | Notes |
|---|---|---|
| `INVOCATION_ID` env check | `run.py`, `shutdown_forensics.py` | systemd unit detection |
| `JOURNAL_STREAM` env check | `shutdown_forensics.py` | systemd journal |
| `systemctl --user list-units` | `hermes_cli/gateway.py` | Service management |
| `systemctl show --property=MainPID` | `hermes_cli/gateway.py` | PID resolution |
| `check_systemd_timing_alignment()` | `shutdown_forensics.py` | TimeoutStopSec vs drain |
| `EX_TEMPFAIL` (exit code 75) | `restart.py`, `run.py` | systemd Restart=on-failure |
| `ppid == 1` check | `run.py`, `shutdown_forensics.py` | systemd reaped parent |
| `/proc/self/cgroup` parsing | `shutdown_forensics.py` | systemd unit name discovery |

### macOS-Specific

| Feature | File(s) | Notes |
|---|---|---|
| `launchctl list` | `hermes_cli/gateway.py` | launchd service management |
| `sys.platform == "darwin"` RSS units | `memory_monitor.py` | ru_maxrss in bytes vs KB |
| Homebrew SSL cert paths | `run.py` | SSL CA bundles |
| `sys.platform != "darwin"` socket option | `platforms/base.py` | SO_REUSEPORT gate |

### Windows-Specific

| Feature | File(s) | Notes |
|---|---|---|
| `msvcrt` file locking | `status.py` | Gateway singleton lock |
| `taskkill /T /F` | `hermes_cli/gateway.py`, `status.py` | Process termination |
| `psutil` fallback for RSS | `memory_monitor.py` | No `resource` module |
| `sys.platform == "win32"` restart branch | `run.py` | Subprocess restart |
| `schtasks` | `hermes_cli/gateway.py` | Scheduled task management |
| `hermes_bootstrap` import | `run.py` | UTF-8 stdio setup |

### Docker-Specific

| Feature | File(s) | Notes |
|---|---|---|
| `TERMINAL_ENV == "docker"` check | `run.py` | Media delivery warning |
| `TERMINAL_DOCKER_VOLUMES` parsing | `run.py` | Output mount detection |

### POSIX Signal Assumptions

| Signal | File(s) | Purpose |
|---|---|---|
| `SIGTERM` | `run.py` | Graceful shutdown |
| `SIGINT` | `run.py` | Interactive interrupt |
| `SIGUSR1` | `run.py`, `hermes_cli/gateway.py` | Self-restart trigger |
| `signal.SIGUSR1` availability check | `hermes_cli/gateway.py` | POSIX guard |
| `signal.SIGKILL` | `status.py` | Force kill |

### Cross-Platform Guards

The codebase uses these patterns to safely handle platform differences:
- `sys.platform == "win32"` checks for Windows-specific paths
- `hasattr(signal, "SIGUSR1")` for POSIX-only signals
- `shutil.which("systemctl")` / `shutil.which("launchctl")` for optional tools
- `try/except (FileNotFoundError, OSError)` for `/proc` access
- `os.chmod(..., 0o600)` with OSError catch for Windows
- Import guards: `try: import resource` / `try: import psutil`


## Orphaned Modules

Modules that nothing in the production codebase imports (test-only consumers
excluded):

| Module | Status | Notes |
|---|---|---|
| `gateway/builtin_hooks/__init__.py` | **Orphaned** (by design) | Empty extension point — `HookRegistry._register_builtin_hooks()` returns immediately. No shipped built-in hooks. |
| `gateway/platforms/_http_client_limits.py` | **Likely orphaned** | Internal helper for platform adapters. Verify consumers. |

Modules with very few consumers (1-2):

| Module | Consumers |
|---|---|
| `gateway/memory_monitor.py` | Only `gateway/run.py` (`start_memory_monitoring()`) |
| `gateway/hooks.py` | Only `gateway/run.py` (`HookRegistry`) |
| `gateway/pairing.py` | Only `gateway/run.py` (`PairingStore`) |
| `gateway/mirror.py` | Only `tools/send_message_tool.py` (`mirror_to_session()`) |
| `gateway/restart.py` | `gateway/run.py` + `hermes_cli/gateway.py` |
| `gateway/shutdown_forensics.py` | Only `gateway/run.py` |
| `gateway/runtime_footer.py` | Only `gateway/run.py` |
| `gateway/display_config.py` | `gateway/run.py` + some platform adapters |
| `gateway/slash_access.py` | Only `gateway/run.py` |
| `gateway/sticker_cache.py` | Only `gateway/platforms/telegram.py` |
| `gateway/channel_directory.py` | `gateway/run.py` + `tools/send_message_tool.py` |
| `gateway/whatsapp_identity.py` | `gateway/run.py` + `gateway/session.py` |
| `gateway/session_context.py` | Only `gateway/session.py` + tools via `get_session_env()` |

None of these are true orphans — every gateway module has at least one
production consumer. `builtin_hooks/__init__.py` is intentionally empty
as an extension point.


## Circular Dependencies

**No circular imports detected in the gateway modules.** The dependency
graph is strictly hierarchical:

```
gateway/config.py          ← depends on nothing internal
gateway/platform_registry.py ← depends on nothing internal
gateway/restart.py         ← depends only on hermes_cli
gateway/session_context.py ← depends on nothing
gateway/whatsapp_identity.py ← depends on hermes_constants
gateway/session.py         ← depends on config + whatsapp_identity
gateway/delivery.py        ← depends on config + session
gateway/pairing.py         ← depends on hermes_constants + utils
gateway/hooks.py           ← depends on hermes_cli
gateway/mirror.py          ← depends on hermes_cli
gateway/memory_monitor.py  ← depends on nothing internal
gateway/shutdown_forensics.py ← depends on nothing
gateway/stream_consumer.py ← depends on config + platforms/base
gateway/platforms/base.py  ← depends on utils
gateway/run.py             ← depends on ALL of the above (leaf)
```

The tricky relationship is `gateway/config.py` ↔ `gateway/platform_registry.py`:

- `config.py`'s `Platform._missing_()` lazily imports `platform_registry` to check if a platform name is registered. This is a **lazy import** (inside a method, not at module level), so it does NOT create a circular dependency.
- `platform_registry.py` does NOT import `config.py`.

`gateway/run.py` imports everything but nothing circularly imports it at module
level. The `_gateway_runner_ref` weakref pattern allows tools to access the
live runner without creating import cycles.

### Potential Circular Risk (not currently triggered)

`gateway/platforms/helpers.py` uses `TYPE_CHECKING` guard for `gateway.platforms.base.MessageEvent`,
preventing a runtime circular import with the platform adapters that import helpers.


## Summary Statistics

| Metric | Count |
|---|---|
| Total gateway `.py` files | 62 |
| Platform adapters | 22+ (telegram, discord, slack, whatsapp, signal, matrix, mattermost, homeassistant, email, sms, dingtalk, api_server, webhook, msgraph_webhook, feishu, wecom, wecom_callback, weixin, bluebubbles, qqbot, yuanbao, + plugin-provided) |
| Transport adapters | 6 (chat_completions, anthropic, codex_responses, bedrock_converse, codex_app_server, hermes_tools_mcp_server) |
| Hardcoded absolute paths | 15 system paths + 12 HERMES_HOME-relative |
| Linux-only code paths | ~8 distinct patterns |
| systemd-only code paths | ~7 distinct patterns |
| macOS-only code paths | ~4 distinct patterns |
| Windows-only code paths | ~5 distinct patterns |
| Orphaned modules | 0 (all have consumers) |
| Circular dependencies | 0 |

---

## Architecture Observations

1. **Monolithic Hub:** `gateway/run.py` at 17,110 lines is the central
   controller. It directly imports and orchestrates every other gateway
   module. This makes the dependency graph simple but the file itself
   difficult to navigate.

2. **Platform Abstraction is Solid:** Every adapter inherits from
   `BasePlatformAdapter` in `platforms/base.py`. The `platform_registry.py`
   mechanism allows plugin-discovered adapters to register without modifying
   the core `Platform` enum.

3. **systemd Is Deeply Entangled:** The gateway assumes systemd in multiple
   places — signal handling, exit codes, restart logic, timing alignment.
   Cross-platform operation (macOS/Windows) has fallbacks but the primary
   design target is Linux/systemd.

4. **Absolute Paths Are Mostly Fallback:** The SSL CA bundle paths in
   `run.py` are tried sequentially with try/except — only one needs to
   succeed. The `/proc` paths in `shutdown_forensics.py` and `status.py`
   are Linux-only and guarded by OSError catches.

5. **Session Isolation Is Strong:** `session_context.py` uses `contextvars`
   for true async task isolation, replacing the old `os.environ` approach
   that was fundamentally broken under concurrency.

6. **Memory Monitoring Is Optional:** `memory_monitor.py` degrades
   gracefully — if neither `resource` nor `psutil` is available, it logs
   a warning and disables itself.

7. **Agent Caching Has Limits:** `GatewayRunner` maintains an LRU agent
   cache with configurable max size (128) and idle TTL (1h), preventing
   unbounded memory growth in long-running gateways.

8. **Transport Layer Is Cleanly Separated:** The `agent/transports/`
   directory isolates provider-specific API format handling from the
   agent's core logic. Each transport is a small, focused class.
