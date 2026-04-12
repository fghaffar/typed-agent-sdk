# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
