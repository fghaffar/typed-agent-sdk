# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-07

### Added

- `ExecutionBackend` protocol (`exec`, `aclose`) — pluggable backend layer that lets `SystemTools.bash` run on a local subprocess, a remote sandbox (Modal, E2B, ...), or any user-supplied implementation without changing tool schemas
- `LocalBackend` — default in-process subprocess implementation
- `ExecResult` TypedDict — structured `{stdout, stderr, exit_code}` return type
- `SystemTools(backend=...)` keyword argument
- `examples/sandbox_backend.py` demonstrating the swap pattern with three backend variants

### Changed

- `SystemTools.bash` and the standalone `bash()` helper now route through `ExecutionBackend` instead of calling `asyncio.create_subprocess_shell` directly. Behavior is unchanged when no backend is supplied (defaults to `LocalBackend`).
- `bash()` now appends `[exit code: N]` to its output when the command exits non-zero, so models can distinguish failure from success without parsing stderr.
- Backend exceptions raised from `bash()` are now logged in full via the SDK logger but truncated to 200 chars in the model-visible output, to avoid leaking auth tokens or internal URLs that some backends embed in exception messages.

### Known limitations

- `Runner` does not yet call `ExecutionBackend.aclose()` automatically. Callers using a backend with remote resources must invoke it themselves in a `finally` block. Automatic lifecycle wiring is planned for Phase 2.

## [0.1.0] - 2026-04-11

### Added

- Core `Runner` orchestrator with hooks, guardrails, permissions, max turns, and budget control
- `query()` async iterator and `query_sync()` for one-shot interactions
- `AgentSDKClient` for stateful multi-turn conversations
- Hook system with 11 event types: PreToolUse, PostToolUse, PreModelCall, PostModelCall, PreHandoff, PostHandoff, OnError, OnStart, OnStop, PreCompact, Notification
- `HookMatcher` for pattern-based hook targeting
- Input/output guardrails with parallel execution and tripwire (fail-closed) support
- `@input_guardrail()` and `@output_guardrail()` decorator factories
- Composable `Skill` bundles (tools + instructions + hooks + guardrails)
- Markdown-based skill definitions with YAML frontmatter
- Multi-agent `Handoff` system with depth limiting
- `PermissionPolicy` with glob-pattern allow/block lists and approval callbacks
- `Session` persistence with `JSONSessionBackend`
- `SystemTools` with sandboxed bash, file_read, file_write, file_edit, glob, grep
- `Transport` protocol for custom execution backends
- `HookRecorder` and `GuardrailRecorder` test utilities
- 21-type exception hierarchy
- Full type safety with generics (`DepsT`, `OutputT`) and py.typed marker
