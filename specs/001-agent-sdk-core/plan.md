# Implementation Plan: Agent SDK Core

**Branch**: `001-agent-sdk-core` | **Date**: 2026-03-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-agent-sdk-core/spec.md`

## Summary

Build a lightweight, model-agnostic, type-safe Python agent SDK as a thin orchestration layer on top of Pydantic AI. The SDK adds 5 core capabilities that Pydantic AI lacks: (1) hook lifecycle system with 11 event types, (2) input/output guardrails with parallel execution and tripwire, (3) composable skills in Python and Markdown, (4) multi-agent handoffs as tool calls, and (5) glob-based permission policies. Additionally, a built-in `SystemTools` skill provides Linux ecosystem tools (bash, file_read, file_write, file_edit, glob, grep). The SDK preserves full Pydantic AI compatibility and works with any LLM provider.

## Technical Context

**Language/Version**: Python 3.11+ (for `StrEnum`, improved generics, `ExceptionGroup`, `tomllib`)
**Primary Dependencies**: `pydantic-ai >= 1.0`, `pydantic >= 2.0`, `typing-extensions >= 4.0`, `PyYAML >= 6.0` (for markdown skill frontmatter)
**Storage**: JSON files for session persistence (default); pluggable via `SessionBackend` protocol
**Testing**: `pytest` + `pytest-asyncio` + Pydantic AI's `TestModel`/`FunctionModel`
**Target Platform**: Cross-platform (Linux, macOS, Windows); Linux-optimized for SystemTools
**Project Type**: Library (PyPI package `agent-sdk`)
**Performance Goals**: <1ms hook overhead, <10ms guardrail parallel execution, <100ms skill registration
**Constraints**: Core package <500KB, <15 Python modules, zero external service requirements
**Scale/Scope**: Single-process agents; distributed via optional Transport abstraction

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Pydantic AI Foundation | PASS | SDK extends Pydantic AI's `Agent`, `RunContext`, `Tool`, `Model`. No reimplementation of model abstraction, tool schemas, streaming, usage tracking, retries, or testing infrastructure. |
| II. Model Agnosticism | PASS | All SDK features (hooks, guardrails, skills, handoffs, permissions) operate on Pydantic AI abstractions, never on provider-specific types. Tests validate across 3+ providers. |
| III. Type Safety First | PASS | All public APIs use generics (`Guardrail[DepsT]`, `Skill[DepsT]`, `Handoff[DepsT]`). `RunContext[DepsT]` flows through hooks, guardrails, skills. `mypy --strict` required. |
| IV. Lightweight by Design | PASS | 3 core deps + PyYAML for markdown skills. 13 public classes. Single `typed_agent_sdk` package. No database/service requirements. |
| V. Composition Over Inheritance | PASS | Agents configured via composition (attach skills, hooks, guardrails). `Skill` is a bundle, not a base class. `Protocol` used for extension points (Transport, SessionBackend). |
| VI. Progressive Complexity | PASS | Simple agent: identical to Pydantic AI. Adding hooks: +3 lines. Adding guardrails: +5 lines. Adding skills: +1 line. Adding handoffs: +5 lines. |
| VII. Test-First Development | PASS | `TestModel`/`FunctionModel` for unit tests. SDK provides `HookRecorder`, `GuardrailRecorder` test utilities. 90%+ coverage target. |
| VIII. Batteries Included | PASS | `SystemTools` skill ships with bash, file_read, file_write, file_edit, glob, grep. Selectively enabled. Integrates with PermissionPolicy. |
| IX. Dual Skill Definition | PASS | Skills definable in Python (typed classes) and Markdown (YAML frontmatter + instructions). Auto-discovery from `skills/` directory. |

**Result**: All 9 principles PASS. No violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-sdk-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (public API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
typed_agent_sdk/
├── __init__.py          # Public API exports (all 13 classes)
├── hooks.py             # Hook, HookEvent, HookMatcher, HookCallback, HookResult
├── guardrails.py        # Guardrail[DepsT], GuardrailResult, InputGuardrail, OutputGuardrail
├── skills.py            # Skill[DepsT], SkillMarkdown, SkillLoader, SkillRegistry
├── handoffs.py          # Handoff[DepsT], HandoffResult, handoff depth tracking
├── permissions.py       # PermissionPolicy, PermissionMode, PermissionResult
├── runner.py            # Runner, RunResult, lifecycle orchestration
├── system_tools.py      # SystemTools skill (bash, file_read, file_write, file_edit, glob, grep)
├── transport.py         # Transport protocol, InProcessTransport
├── session.py           # Session, SessionBackend protocol, JSONSessionBackend
├── types.py             # Shared types, enums, type aliases
├── errors.py            # All error/exception types
├── testing.py           # HookRecorder, GuardrailRecorder, test utilities
├── _utils.py            # Internal utilities (glob matching, YAML parsing)
└── py.typed             # PEP 561 marker

tests/
├── test_hooks.py
├── test_guardrails.py
├── test_skills.py
├── test_handoffs.py
├── test_permissions.py
├── test_runner.py
├── test_system_tools.py
├── test_session.py
├── test_transport.py
├── test_skill_markdown.py
├── test_integration.py
└── conftest.py          # Shared fixtures (TestModel agents, sample skills)

examples/
├── simple_agent.py      # Minimal: agent + hooks
├── guardrailed_agent.py # Agent with input/output guardrails
├── skill_composition.py # Multiple skills composed
├── multi_agent.py       # Handoff between agents
├── system_tools_agent.py # Agent with bash/file/grep tools
└── skills/              # Example markdown skills
    ├── code-reviewer.md
    └── researcher.md
```

**Structure Decision**: Single project layout. The `typed_agent_sdk/` package contains exactly 14 modules (under the 15 limit). Tests mirror the source structure. Examples demonstrate progressive complexity.

## Complexity Tracking

No violations to justify. All design decisions align with constitution principles.

## Plan Review (CEO)

**Reviewed**: 2026-03-15 | **Mode**: HOLD SCOPE

### Premise Challenge
Correct problem. Developers need production agent orchestration (hooks, guardrails, skills, handoffs) without model lock-in. Pydantic AI provides the foundation but lacks these orchestration primitives. Doing nothing leaves developers with raw Pydantic AI — functional but not production-ready for complex agent systems.

### Dream State Delta
```
CURRENT: Raw Pydantic AI → THIS PLAN: +hooks/guardrails/skills/handoffs/permissions/SystemTools
→ 12-MONTH: +skill marketplace, evaluation framework, cloud transport, visual debugging
```
Plan moves strongly toward the 12-month ideal. Architecture supports all future phases without rework.

### Scope Decision
HOLD SCOPE selected. The plan's 40 FRs across 9 user stories is already ambitious for a greenfield library. Review focused on making the existing scope bulletproof — architecture correctness, error handling, edge cases, security, test coverage, and Pydantic AI integration risks.

### Key Decisions Made
1. **Output guardrail injection point** → Chose post-run validation: guardrails check final output after `agent.run()` returns. Simplest, decoupled, matches industry patterns.
2. **SystemTools path sandboxing** → Chose sandbox by default: file operations restricted to `cwd` subtree. `sandbox=False` to disable for trusted agents.
3. **Bash output cap** → Chose 5MB cap with truncation. Configurable via `max_output_bytes`.
4. **Initial version** → Chose v0.1.0: allows breaking API changes during v0.x. Move to v1.0 after real-world validation.

### NOT in Scope
- Skill marketplace / registry (future v0.3)
- Agent evaluation framework (future v0.2)
- CLI scaffolding tool
- Visual debugging UI
- Distributed agent runtime / cloud transport
- Graph-based orchestration (LangGraph-style)
- NotebookEdit / TodoRead/TodoWrite tools
- Multi-tenant permissions

### What Already Exists (Pydantic AI)
- Model abstraction (15+ providers), tool system, toolsets, tool approval
- Fallback models, usage tracking, streaming, concurrency, retries
- Testing (TestModel, FunctionModel), instrumentation (OpenTelemetry)
- History processors, MCP integration, durable execution, embeddings

### Mandatory Implementation Requirements (from review)
1. **YAML must use `yaml.safe_load()`** — `yaml.load()` allows arbitrary code execution
2. **Expand error hierarchy** — plan needs ~15 error types, not 5 (see Error & Rescue Map)
3. **Empty prompt validation** — `Runner.run("")` must raise `ValueError`
4. **Concurrent run guard** — `Runner.run()` must reject if already running
5. **Interrupt idempotency** — `runner.interrupt()` when not running must no-op
6. **Hook regex escaping** — HookMatcher with literal tool names must use `re.escape()`
7. **Skill with 0 tools** — must be allowed (instructions-only skills)
8. **Robust frontmatter parsing** — handle `---` appearing in markdown body
9. **Session schema versioning** — include version field in session JSON
10. **Guardrail failure logging** — GuardrailResult.reason must be logged, not just returned
11. **Re-entrancy guard on Runner** — prevent hooks from calling `runner.run()` recursively
12. **Path sandbox on SystemTools** — restrict file ops to `cwd` subtree (Decision 2)
13. **Bash output cap** — 5MB default truncation (Decision 3)

### Error & Rescue Registry

```
EXCEPTION CLASS              | RESCUED? | RESCUE ACTION                     | USER SEES
-----------------------------|----------|-----------------------------------|---------------------------
GuardrailTripwireError       | N (raise)| Propagate to caller               | Exception with reason
GuardrailExecutionError      | Y        | Log + fail-open/closed            | Warning or Error
HookExecutionError           | Y        | Fire OnError hook, then propagate | Exception if OnError fails
asyncio.TimeoutError (hook)  | Y        | Log warning, skip hook            | Nothing (hook skipped)
asyncio.TimeoutError (guard) | Y        | fail-open: pass, fail-closed: trip| Nothing or TripwireError
asyncio.TimeoutError (bash)  | Y        | Kill process, return timeout msg  | "Command timed out"
HandoffDepthError            | N (raise)| Propagate                         | Exception with depth info
MaxTurnsExceeded             | N (raise)| Set stop_reason in RunResult      | RunResult.stop_reason
BudgetExhausted              | N (raise)| Set stop_reason in RunResult      | RunResult.stop_reason
SkillLoadError               | N (raise)| Propagate with file path + line   | Exception with location
SkillConflictError           | N (raise)| Propagate with both names         | Exception with conflict detail
EditNotFoundError            | Y        | Return error message to model     | Tool returns error string
SessionNotFoundError         | N (raise)| Propagate                         | Exception with session_id
PermissionDeniedError        | Y        | Return blocked message to model   | Tool not available
```

### Failure Modes (Critical Gaps)

```
CODEPATH              | FAILURE MODE           | RESCUED? | TEST? | USER SEES?      | LOGGED?
----------------------|------------------------|----------|-------|-----------------|--------
Runner.run()          | empty prompt           | N ←FIX   | N     | TypeError       | N ←FIX
Runner.run()          | concurrent calls       | N ←FIX   | N     | race condition  | N ←FIX
HookToolset           | hook returns bad type  | N ←FIX   | N     | TypeError       | N ←FIX
SkillLoader           | --- in markdown body   | N ←FIX   | N     | SkillLoadError  | N ←FIX
SystemTools.bash      | output > 5MB           | Y        | N     | truncated       | Y
SystemTools.file_*    | path traversal         | Y        | N     | sandbox block   | Y
Session.load          | schema version change  | N ←FIX   | N     | KeyError        | N ←FIX
Handoff               | re-entrant runner      | N ←FIX   | N     | infinite loop   | N ←FIX
YAML load             | code execution attack  | Y (req)  | N     | safe_load blocks| Y
```
12 failure modes need rescue handlers. All need tests.

### Diagrams

```
RUNNER LIFECYCLE STATE MACHINE:

  IDLE ──run()──▶ ON_START ──▶ INPUT_GUARDRAILS ──▶ AGENT_LOOP ──▶ OUTPUT_GUARDRAILS ──▶ ON_STOP ──▶ DONE
    ▲                              │ tripwire            │                │ tripwire           │
    │                              └──────────┐          │                └──────────┐         │
    │                                         ▼          ▼                           ▼         │
    │                                       DONE    [PreToolUse→tool→PostToolUse]*  DONE       │
    │                                                    │                                     │
    │                                              [PreHandoff→handoff→PostHandoff]            │
    │                                                    │                                     │
    │                                              max_turns / budget ──▶ ON_STOP ──▶ DONE     │
    │                                                    │                                     │
    │                                              OnError ──(recovery)──▶ continue loop       │
    │                                                    │                                     │
    └──interrupt()──────────────────────────── ON_STOP ──┘                                     │
                                                                                               │
    DONE ──resume()──▶ ON_START ──▶ ... (same cycle with loaded session)                       │
```

### Unresolved Decisions
None. All 4 raised questions were answered.

## Plan Review (Eng)

**Reviewed**: 2026-03-15 | **Mode**: SMALL CHANGE

### Scope Decision
CEO review already covered architecture, security, and scope at HOLD SCOPE. This eng review focused on execution quality: toolset injection mechanism, module cohesion, test strategy for tool calls, and wrapper depth performance. The plan's 14 modules / 13 classes is appropriate for a greenfield SDK. No scope reduction warranted given user's insistence on Claude Agent SDK feature parity.

### NOT in Scope
- Skill marketplace / distribution protocol
- Agent evaluation framework
- CLI scaffolding (`agent-sdk init`)
- Visual debugging UI
- Graph-based orchestration
- NotebookEdit / TodoWrite tools
- Cloud transport implementations
- Multi-tenant permissions
- Agent-to-agent streaming (handoffs are batch)

### What Already Exists
- Pydantic AI `WrapperToolset` → hook interception (no rebuild)
- Pydantic AI `PreparedToolset` → permission filtering (no rebuild)
- Pydantic AI `ApprovalRequiredToolset` → require_approval (no rebuild)
- Pydantic AI `AbstractToolset` → Skill base class (no rebuild)
- Pydantic AI `agent.override()` → runtime toolset injection (no rebuild)
- Pydantic AI `FunctionModel` → testing tool calls (no rebuild)
- Pydantic AI `RunUsage` → usage tracking (no rebuild)
- Pydantic AI `models.fallback` → fallback models (no rebuild)

### Key Decisions Made
1. **Toolset injection** → Chose 1A: `agent.override(toolsets=...)` context manager. Zero mutation, uses Pydantic AI's own mechanism.
2. **skills.py scope** → Chose 2A: Keep as one module. 14 modules near 15 cap; splitting adds marginal benefit for tightly coupled concerns.
3. **Tool call testing** → Chose 3A: `FunctionModel` with programmatic tool calls. Most realistic simulation of agent tool-calling loop.
4. **Wrapper depth** → Chose 4A: Accept 2 layers. ~0.02ms overhead per call is noise vs 500ms-5s LLM latency.

### Failure Modes

```
CODEPATH              | FAILURE MODE              | TEST? | HANDLED? | SILENT?
----------------------|---------------------------|-------|----------|--------
Runner.run()          | agent.override() rejects  | N     | N ←FIX   | Y ←CRIT
                      | toolset override           |       |          |
HookToolset           | WrapperToolset API change  | N     | N        | Y ←CRIT
                      | in pydantic-ai upgrade     |       |          |
Handoff tool          | nested agent.run() deadlock| N     | N ←FIX   | Y ←CRIT
PermissionToolset     | PreparedToolset.prepare()  | N     | N        | Y ←CRIT
                      | with stale context         |       |          |
```
4 critical gaps — all require validation during first implementation sprint.

### Diagrams

```
RUNNER TOOLSET INJECTION (via agent.override):

  User's Agent
    toolsets: [user_tools]
         │
         ▼
  Runner.run() calls:
    agent.override(
      toolsets=[
        HookToolset(              ← wraps everything for hook interception
          PermissionToolset(       ← filters tools per step based on policy
            CombinedToolset(      ← merges user tools + skill tools + handoff tools
              user_tools,
              skill1.toolset,
              skill2.toolset,
              handoff_toolset
            )
          )
        )
      ]
    )
```

### Unresolved Decisions
None.
