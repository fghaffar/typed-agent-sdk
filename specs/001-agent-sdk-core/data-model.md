# Data Model: Agent SDK Core

**Phase 1 Output** | **Date**: 2026-03-15

## Entity Relationship Overview

```
Runner ──manages──> Agent (Pydantic AI)
  │                   │
  ├── hooks ──────> Hook[] ──has──> HookMatcher
  ├── guardrails ─> Guardrail[DepsT][] ──returns──> GuardrailResult
  ├── permissions ─> PermissionPolicy ──uses──> PermissionMode
  ├── skills ─────> Skill[DepsT][] ──contains──> {tools, hooks, guardrails, instructions}
  ├── handoffs ───> Handoff[DepsT][] ──targets──> Agent (Pydantic AI)
  └── session ────> Session ──persisted-by──> SessionBackend
```

## Core Entities

### HookEvent (StrEnum)

```
Values: PreToolUse, PostToolUse, PreModelCall, PostModelCall,
        PreHandoff, PostHandoff, OnError, OnStart, OnStop,
        PreCompact, Notification
```

### HookMatcher

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| pattern | `str \| None` | Regex pattern to match against event target (tool name, agent name) | Valid regex; None matches all |
| timeout | `float \| None` | Max execution time in seconds | > 0 if set |

### Hook

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| event | `HookEvent` | Which lifecycle event to listen to | Must be valid HookEvent |
| callback | `HookCallback` | Async function called when event fires | Must be async callable |
| matcher | `HookMatcher \| None` | Optional filter for which events fire this hook | Valid HookMatcher |
| priority | `int` | Execution order (lower = first) | Default: 100 |
| fire_and_forget | `bool` | If True, hook runs in background without blocking | Default: False |

### HookCallback (Protocol)

```
Input:  (event_data: HookEventData, ctx: RunContext[DepsT]) -> HookResult
Output: HookResult with fields:
  - block: bool (False) — prevent the action
  - modified_args: dict | None — replacement tool args (PreToolUse only)
  - modified_result: Any | None — replacement tool result (PostToolUse only)
  - additional_context: str | None — inject message into conversation
  - suppress_output: bool (False) — hide tool output from model
  - continue_: bool (True) — whether agent loop should continue
  - stop_reason: str | None — custom stop reason
```

### HookEventData (Union per event type)

| Event | Available Fields |
|-------|-----------------|
| PreToolUse | tool_name, tool_args, tool_call_id |
| PostToolUse | tool_name, tool_args, tool_result, tool_call_id |
| PreModelCall | messages (list of model messages) |
| PostModelCall | response (model response), messages |
| PreHandoff | source_agent, target_agent, handoff_description |
| PostHandoff | source_agent, target_agent, result |
| OnError | error (Exception), context (what was happening) |
| OnStart | prompt, agent_name |
| OnStop | result, stop_reason |
| PreCompact | messages, trigger ("auto" \| "manual") |
| Notification | message, title, notification_type |

### Guardrail[DepsT] (Generic)

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| name | `str` | Identifier for logging | Non-empty |
| check | `GuardrailCheckFunc[DepsT]` | Async validation function | Must be async callable |
| kind | `Literal["input", "output"]` | When guardrail runs | Required |
| timeout | `float \| None` | Max execution time | > 0 if set |
| fail_closed | `bool` | If True, timeout = tripwire. If False, timeout = pass | Default: False |

### GuardrailCheckFunc (Protocol)

```
Input:  (data: str | ModelResponse, ctx: RunContext[DepsT]) -> GuardrailResult
```

### GuardrailResult

| Field | Type | Description |
|-------|------|-------------|
| passed | `bool` | Whether the check passed |
| reason | `str \| None` | Human-readable explanation |
| tripwire | `bool` | If True, immediately halt execution |

### Skill[DepsT] (Generic, extends AbstractToolset[DepsT])

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| name | `str` | Unique skill identifier | Non-empty, valid Python identifier |
| description | `str` | What the skill does | Non-empty |
| tools | `list[Tool[DepsT]]` | Tools provided by this skill | No name conflicts |
| instructions | `str \| None` | System prompt fragment appended to agent | None = no instructions |
| hooks | `list[Hook]` | Hooks to register when skill is attached | Valid hooks |
| guardrails | `list[Guardrail[DepsT]]` | Guardrails to register | Valid guardrails |
| permissions | `PermissionPolicy \| None` | Skill-specific permissions | None = no restrictions |

### SkillMarkdown

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| name | `str` | Skill identifier | YAML frontmatter `name` |
| description | `str` | Skill description | YAML frontmatter `description` |
| tools | `list[str]` | Tool names to include | YAML frontmatter `tools` |
| handoffs | `list[HandoffDef]` | Handoff targets | YAML frontmatter `handoffs` |
| instructions | `str` | System prompt body | Markdown body (after frontmatter) |
| source_path | `Path` | File path for error reporting | Auto-detected |

### Handoff[DepsT] (Generic)

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| target | `Agent[DepsT, Any]` | Target agent to delegate to | Must be valid Agent |
| description | `str` | Description shown to LLM for delegation decision | Non-empty |
| filter | `Callable[[RunContext[DepsT]], bool] \| None` | Dynamic filter — if returns False, handoff not offered | Must be callable if set |
| context_transformer | `Callable[[list[ModelMessage]], list[ModelMessage]] \| None` | Transform messages before passing to target | Optional |
| max_depth | `int` | Max handoff chain depth | Default: 10, > 0 |

### HandoffResult

| Field | Type | Description |
|-------|------|-------------|
| output | `Any` | Result from target agent |
| agent_name | `str` | Name of agent that produced the result |
| depth | `int` | Current depth in handoff chain |
| usage | `RunUsage` | Token usage from target agent run |

### PermissionPolicy

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| mode | `PermissionMode` | Predefined permission preset | Valid PermissionMode |
| allowed_tools | `list[str]` | Glob patterns for allowed tools | Valid glob patterns |
| blocked_tools | `list[str]` | Glob patterns for blocked tools (overrides allowed) | Valid glob patterns |
| require_approval | `list[str]` | Glob patterns for tools requiring human approval | Valid glob patterns |
| approval_callback | `Callable[[str, dict], Awaitable[bool]] \| None` | Async callback for approval decisions | Must be async if set |

### PermissionMode (StrEnum)

```
Values: default, readOnly, unrestricted, planOnly
```

### PermissionResult

| Field | Type | Description |
|-------|------|-------------|
| allowed | `bool` | Whether tool use is permitted |
| reason | `str \| None` | Why it was allowed/denied |
| requires_approval | `bool` | Whether human approval is needed |

### Runner

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| agent | `Agent[DepsT, OutputT]` | Pydantic AI agent to run | Required |
| hooks | `list[Hook]` | Global hooks | Valid hooks |
| guardrails | `list[Guardrail[DepsT]]` | Global guardrails | Valid guardrails |
| skills | `list[Skill[DepsT]]` | Skills to attach | Valid skills, no name conflicts |
| handoffs | `list[Handoff[DepsT]]` | Handoff targets | Valid handoffs |
| permissions | `PermissionPolicy \| None` | Global permission policy | Valid policy |
| max_turns | `int \| None` | Maximum tool-call turns | > 0 if set |
| max_budget_tokens | `int \| None` | Maximum token budget | > 0 if set |
| session_backend | `SessionBackend \| None` | Session persistence backend | Valid backend |
| transport | `Transport \| None` | Execution transport | Valid transport |
| debug_callback | `Callable[[str, dict], None] \| None` | Debug/log callback | Callable if set |

### RunResult[OutputT] (Generic)

| Field | Type | Description |
|-------|------|-------------|
| output | `OutputT` | Final output from agent |
| messages | `list[ModelMessage]` | Full message history |
| usage | `RunUsage` | Pydantic AI usage metrics |
| sdk_metrics | `SDKMetrics` | Hook/guardrail/handoff counts |
| session_id | `str \| None` | Session ID if session is active |
| stop_reason | `str \| None` | Why the agent stopped |

### SDKMetrics

| Field | Type | Description |
|-------|------|-------------|
| hook_invocations | `int` | Total hooks fired |
| guardrail_checks | `int` | Total guardrail checks run |
| handoff_count | `int` | Number of handoffs executed |
| guardrail_trips | `int` | Number of guardrail tripwires triggered |
| hooks_blocked | `int` | Number of actions blocked by hooks |

### Session

| Field | Type | Description |
|-------|------|-------------|
| session_id | `str` | Unique identifier (UUID) |
| messages | `list[ModelMessage]` | Conversation history |
| metadata | `dict[str, Any]` | User-defined metadata |
| created_at | `datetime` | Creation timestamp |
| updated_at | `datetime` | Last update timestamp |
| agent_name | `str \| None` | Agent that owns the session |
| parent_session_id | `str \| None` | For forked sessions |

### SessionBackend (Protocol)

```
Methods:
  async save(session: Session) -> None
  async load(session_id: str) -> Session | None
  async list(limit: int = 100) -> list[SessionInfo]
  async delete(session_id: str) -> None
```

### Transport (Protocol)

```
Methods:
  async run(agent, prompt, deps, ...) -> RunResult
  async run_stream(agent, prompt, deps, ...) -> AsyncIterator[AgentStreamEvent]
```

### ToolAnnotations

| Field | Type | Description |
|-------|------|-------------|
| read_only | `bool` | Tool only reads data (no side effects) |
| destructive | `bool` | Tool modifies or deletes data |
| open_world | `bool` | Tool accesses external systems |

## State Transitions

### Runner Lifecycle

```
IDLE -> OnStart -> INPUT_GUARDRAILS -> PreModelCall -> MODEL_CALL -> PostModelCall
  -> [PreToolUse -> TOOL_EXEC -> PostToolUse]* -> OUTPUT_GUARDRAILS -> OnStop -> DONE

Special transitions:
  Any state -> OnError -> (recovery | DONE)
  INPUT_GUARDRAILS -> tripwire -> OnStop -> DONE
  OUTPUT_GUARDRAILS -> tripwire -> OnStop -> DONE
  PreToolUse -> blocked -> (skip tool, continue loop)
  PreHandoff -> HANDOFF_EXEC -> PostHandoff -> (continue loop)
  Any state -> interrupt() -> OnStop -> DONE
  MODEL_CALL -> max_turns/max_budget -> OnStop -> DONE
```

### Session Lifecycle

```
NEW -> (runner.run) -> ACTIVE -> (run completes) -> SAVED
SAVED -> (runner.resume) -> ACTIVE -> SAVED
SAVED -> (runner.fork) -> NEW (with parent_session_id)
```
