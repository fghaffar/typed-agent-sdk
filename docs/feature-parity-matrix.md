# Feature Parity Matrix: Claude Agent SDK vs AgentSDK (Ours)

**Date**: 2026-03-15
**Purpose**: Ensure our SDK has at least equivalent or better functionality than the Claude Agent SDK, while remaining lightweight and model-agnostic.

**Legend**:
- Covered = in our spec | Pydantic AI = handled by foundation | Gap = needs to be added | N/A = not applicable (Claude-specific)

---

## 1. Core Interaction Patterns

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `query()` — stateless one-shot | `runner.run()` / `runner.run_sync()` | Covered | Equivalent via Runner |
| `ClaudeSDKClient` — stateful bidirectional | `Runner` with session | Covered | US6 + US9 |
| Streaming output (`AsyncIterator[Message]`) | `runner.run_stream()` | Covered | Via Pydantic AI stream |
| Streaming input (`AsyncIterable[dict]`) | `runner.run(async_iterable)` | Covered | FR-026 |
| `include_partial_messages` (token-level) | Event stream handler | Pydantic AI | Via `AgentStreamEvent` |
| `interrupt()` mid-execution | `runner.interrupt()` | Covered | FR-023, US9 |
| Sync wrapper | `runner.run_sync()` | Covered | FR-010 |

## 2. Hook System

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `PreToolUse` | `PreToolUse` | Covered | FR-001, FR-002 |
| `PostToolUse` | `PostToolUse` | Covered | |
| `PostToolUseFailure` | `OnError` (covers this) | Covered | Our OnError is broader |
| `UserPromptSubmit` | `OnStart` (covers this) | Covered | Could add specific event |
| `Stop` | `OnStop` | Covered | |
| `SubagentStart` | `PreHandoff` | Covered | Our naming is clearer |
| `SubagentStop` | `PostHandoff` | Covered | |
| `PreCompact` | `PreCompact` | Covered | FR-025 |
| `Notification` | — | **Gap** | Need notification event |
| `PermissionRequest` | PermissionPolicy callback | Covered | Different mechanism, same result |
| `HookMatcher` (regex on tool name) | `HookMatcher` (regex) | Covered | FR-001 |
| `HookCallback` signature (input, tool_use_id, context) | Hook callback (event_data, ctx) | Covered | Simpler signature |
| Hook can block/deny tool use | Hook returns block decision | Covered | FR-012 |
| Hook can modify tool input (`updatedInput`) | Hook can modify args | Covered | FR-012 |
| Hook can modify tool output (`updatedMCPToolOutput`) | Hook can modify result | Covered | FR-012 |
| Hook timeout | Hook timeout config | **Gap** | Need per-hook timeout |
| Hook `additionalContext` injection | — | **Gap** | Hook injects context into conversation |
| Hook `suppressOutput` | — | **Gap** | Hook suppresses tool output |
| Hook `continue_` control | — | **Gap** | Hook controls agent continuation |
| Hook async mode (`async_: True`) | — | **Gap** | Fire-and-forget hooks |
| `stopReason` from hook | — | **Gap** | Custom stop reason from hook |
| Per-hook-event specific output types | Generic hook result | **Gap** | Claude has typed outputs per event |

## 3. Tool System

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `@tool` decorator | `@agent.tool` (Pydantic AI) | Pydantic AI | Already available |
| `create_sdk_mcp_server()` — in-process MCP | MCP integration (optional extra) | Covered | Via `[mcp]` extra |
| External MCP servers (stdio, SSE, HTTP) | MCP integration | Covered | Via Pydantic AI MCP |
| `ToolAnnotations` (readOnly, destructive, openWorld) | — | **Gap** | Need tool annotations |
| `allowed_tools` (glob patterns) | `PermissionPolicy.allowed_tools` | Covered | FR-007 |
| `disallowed_tools` | `PermissionPolicy.blocked_tools` | Covered | FR-007 |
| Tool namespacing (`mcp__server__tool`) | Skill namespacing | Covered | Via skill prefix |
| Built-in tools (Bash, Read, Write, Edit, Glob, Grep) | `SystemTools` skill | Covered | US8, FR-019 |
| Built-in WebSearch / WebFetch | `SystemTools.web_fetch` | Covered | FR-019 |
| Built-in NotebookEdit | — | **Gap** | Jupyter notebook editing |
| Built-in TodoRead / TodoWrite | — | **Gap** | Task tracking tools |
| Built-in Agent tool (spawn subagent) | `Handoff` | Covered | Different mechanism |
| `ToolsPreset` (preset tool sets) | Skill presets | Covered | Skills are our presets |
| Tool permission evaluation chain | PermissionPolicy evaluation | Covered | FR-007 |

## 4. Multi-Agent System

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `AgentDefinition` (description, prompt, tools, model) | `Handoff` + Agent config | Covered | US4 |
| Subagent spawning via tool call | Handoff as tool call | Covered | FR-006 |
| `SubagentStart` / `SubagentStop` hooks | `PreHandoff` / `PostHandoff` hooks | Covered | FR-002 |
| Agent transcript tracking | — | **Gap** | Need handoff result tracking |
| Agent-level model override | Agent model param | Pydantic AI | Each agent has its own model |
| Agent-level tool restrictions | Agent tools param + PermissionPolicy | Covered | |

## 5. Permission & Security

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `PermissionMode` (default/acceptEdits/plan/bypass) | `PermissionPolicy` modes | **Gap** | Need predefined permission modes |
| `can_use_tool` callback | `PermissionPolicy.require_approval` callback | Covered | FR-007 |
| `PermissionResultAllow` with `updated_input` | Hook can modify input | Covered | FR-012 |
| `PermissionResultDeny` with `interrupt` | Guardrail tripwire | Covered | |
| `PermissionUpdate` (addRules, removeRules, setMode) | — | **Gap** | Dynamic permission modification |
| Sandbox settings (network, commands, violations) | — | **Gap** | Need sandbox configuration |
| `max_budget_usd` (cost cap) | `max_budget_tokens` (token cap) | Partial | Need cost-based budget too |
| `max_turns` | `max_turns` | Covered | FR-021 |

## 6. Session Management

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `list_sessions()` | Session listing | Covered | US9 |
| `get_session_messages()` | Session message retrieval | Covered | US9 |
| `rename_session()` | — | **Gap** | Need session metadata |
| `tag_session()` | — | **Gap** | Need session tagging |
| `resume` (session resumption) | `runner.resume(session_id)` | Covered | FR-024 |
| `fork_session` | — | **Gap** | Need session forking |
| `enable_file_checkpointing` | — | **Gap** | Need file state tracking |
| `rewind_files()` | — | **Gap** | Need file rewind |
| Session worktree awareness | — | N/A | Git-specific |

## 7. Model & Configuration

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `model` selection | Agent model param | Pydantic AI | Model-agnostic by design |
| `fallback_model` | — | **Gap** | Need fallback model support |
| `ThinkingConfig` (adaptive/enabled/disabled) | — | **Gap** | Need thinking configuration |
| `effort` (low/medium/high/max) | — | **Gap** | Need effort/reasoning control |
| `max_thinking_tokens` | — | **Gap** | Need thinking budget |
| `output_format` (JSON schema) | `output_type` (Pydantic) | Pydantic AI | Pydantic is better (validated) |
| `system_prompt` / `SystemPromptPreset` | Agent instructions/system_prompt | Pydantic AI | |
| `betas` (feature flags) | — | N/A | Claude-specific |

## 8. Transport & Infrastructure

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `Transport` ABC | — | **Gap** | Need transport abstraction for remote agents |
| `SubprocessCLITransport` | — | N/A | We don't wrap a CLI |
| Custom transport implementations | — | **Gap** | Enables remote/distributed agents |
| `debug_stderr` / stderr callback | Logging/observability | **Gap** | Need debug output hooks |
| `cwd` (working directory) | SystemTools working dir | Covered | FR-027 |
| `env` (environment variables) | SystemTools env vars | Covered | FR-027 |
| `setting_sources` | — | N/A | CLI-specific |
| `add_dirs` (additional directories) | — | **Gap** | Need multi-directory support |

## 9. Plugin System

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `SdkPluginConfig` (local directory) | Skills (Python + Markdown) | Covered | Our skills are richer |
| Plugin directory structure | Skill directory structure | Covered | US7 |
| Plugin commands (from .md files) | Markdown skills | Covered | US7, FR-016 |

## 10. Observability & Debugging

| Claude Agent SDK Feature | Our SDK | Status | Notes |
|--------------------------|---------|--------|-------|
| `stderr` callback | — | **Gap** | Need debug/log callback |
| Stream events for debugging | Event stream handler | Pydantic AI | |
| Rate limit events | — | **Gap** | Need rate limit awareness |
| Usage tracking (tokens, cost) | — | **Gap** | Need usage/cost tracking |
| Entrypoint tracking | — | N/A | CLI-specific |

---

## Pydantic AI Already Provides (DO NOT REIMPLEMENT)

Based on exhaustive audit of pydantic-ai source code:

| Feature | Pydantic AI Implementation | Impact on Our Spec |
|---------|---------------------------|-------------------|
| Built-in WebSearch | `WebSearchTool` with location, domains, max_uses | Remove from SystemTools |
| Built-in WebFetch | `WebFetchTool` | Remove from SystemTools |
| Built-in CodeExecution | `CodeExecutionTool` | Covers sandbox exec |
| Built-in FileSearch | `FileSearchTool` | Covers file search |
| Built-in ImageGen | `ImageGenerationTool` | Bonus capability |
| Built-in Memory | `MemoryTool` | Covers agent memory |
| Tool approval system | `ApprovalRequiredToolset`, `DeferredToolRequests`, `ToolApproved`/`ToolDenied` | Our PermissionPolicy.require_approval wraps this |
| Fallback models | `fallback.py`, `FallbackExceptionGroup` | Remove FR-034 (already exists) |
| Usage tracking | `RunUsage` (input/output/cache tokens), `RequestUsage` | Remove FR-036 (already exists) |
| Tool timeout | `tool_timeout` on Agent + per-tool `timeout` | Already available |
| Concurrency control | `ConcurrencyLimit`, `ConcurrencyLimiter`, `max_concurrency` | Already available |
| History processors | `HistoryProcessor` type | Covers context compaction |
| Toolsets | `FilteredToolset`, `PrefixedToolset`, `RenamedToolset`, `WrapperToolset`, `CombinedToolset`, `PreparedToolset` | Skills can extend `AbstractToolset` |
| Retries | Per-tool max_retries, output_retries, tenacity integration | Already available |
| Durable execution | DBOS, Prefect, Temporal integrations | Covers persistence |
| Embeddings | Multi-provider embedding system | Bonus capability |
| MCP integration | `FastMCPToolset`, `MCPServerTool` | Remove from optional extras (already core) |
| Agent overrides | `@agent.override()` context manager | Testing support |
| TestModel/FunctionModel | Full test infrastructure | Testing support |
| End strategy | 'early' vs 'exhaustive' | Already available |

## Revised Gap Analysis (What We Actually Need to Build)

### Our SDK's TRUE Value-Add (5 core features)

1. **Hook Lifecycle System** — Pydantic AI has event_stream_handler but NO pre/post hook system that can block, modify, or inject context. This is our #1 feature.

2. **Guardrails** — Pydantic AI has tool-level approval but NO input/output guardrails that run in parallel, validate prompts before model call, or validate responses before delivery. This is safety-critical.

3. **Skills (Python + Markdown)** — Pydantic AI has toolsets but NO composable bundles that include instructions + hooks + guardrails + tools. And NO markdown-based skill definitions. This is our packaging/ecosystem play.

4. **Multi-Agent Handoffs** — Pydantic AI supports delegation via tool calls but has NO first-class handoff primitive with lifecycle hooks, depth tracking, or context transfer. This is our orchestration differentiator.

5. **Permission Policies (Glob-Based)** — Pydantic AI has `ApprovalRequiredToolset` but NO declarative glob-pattern policies, permission modes, or layered evaluation. Our system wraps and extends Pydantic AI's approval.

### Remaining Gaps to Address in Spec

| Gap | Priority | Action |
|-----|----------|--------|
| Notification hook event | Must | Already added (FR-002) |
| Hook timeout | Must | Already added (FR-029) |
| Hook advanced controls | Must | Already added (FR-030, FR-031) |
| Tool annotations | Must | Already added (FR-032) |
| Permission modes | Must | Already added (FR-033) |
| Thinking/reasoning passthrough | Should | Already added (FR-035) |
| Debug/log callback | Should | Already added (FR-037) |
| Transport abstraction | Should | Already added (FR-038) |
| Session forking | Could | Already added (FR-040) |
| Dynamic permissions | Could | Already added (FR-039) |

### Features We Can REMOVE from Spec (Pydantic AI already has them)

| Feature | Remove/Revise | Reason |
|---------|---------------|--------|
| FR-034 (fallback_model) | **Revise** | Pydantic AI has `fallback.py` — just document integration |
| FR-036 (usage tracking) | **Revise** | Pydantic AI's `RunUsage` already tracks tokens |
| SystemTools.web_fetch | **Revise** | Use Pydantic AI's `WebFetchTool` built-in |
| SystemTools.web_search | **Revise** | Use Pydantic AI's `WebSearchTool` built-in |
| Tool timeout in spec | **Remove** | Pydantic AI's `tool_timeout` parameter |
| Concurrency control | **Remove** | Pydantic AI's `max_concurrency` parameter |

### SystemTools Revised Scope

Only tools NOT already in Pydantic AI need to be built:
- `bash` — Shell execution (NOT in Pydantic AI)
- `file_read` — Read files with offset/limit (NOT in Pydantic AI — FileSearchTool is different)
- `file_write` — Write files (NOT in Pydantic AI)
- `file_edit` — String replacement editing (NOT in Pydantic AI)
- `glob` — File pattern matching (NOT in Pydantic AI)
- `grep` — Content search via regex (NOT in Pydantic AI)

Pydantic AI already provides: WebSearchTool, WebFetchTool, CodeExecutionTool, FileSearchTool, ImageGenerationTool, MemoryTool
