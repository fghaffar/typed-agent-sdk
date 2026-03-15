# Feature Specification: Agent SDK Core

**Feature Branch**: `001-agent-sdk-core`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "A lightweight, model-agnostic, type-safe Python agent SDK built on top of Pydantic AI with hooks, guardrails, skills, handoffs, and permissions"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single Agent with Hooks (Priority: P1)

A developer creates an agent with custom lifecycle hooks to log, validate, or modify tool usage. They register hooks for specific events (e.g., PreToolUse, PostToolUse) with optional matcher patterns, and the hooks fire automatically during agent execution.

**Why this priority**: Hooks are the foundational orchestration feature. Every other feature (guardrails, skills, permissions) builds on or interacts with the hook lifecycle. Without hooks, the SDK offers nothing beyond raw Pydantic AI.

**Independent Test**: Can be fully tested by creating an agent with a PreToolUse hook that logs tool calls, running the agent with Pydantic AI's TestModel, and asserting the hook was called with correct event data.

**Acceptance Scenarios**:

1. **Given** an agent with a PreToolUse hook registered, **When** the agent calls a tool, **Then** the hook fires before tool execution with tool name, arguments, and RunContext accessible.
2. **Given** a PreToolUse hook that returns a block decision, **When** the hook blocks, **Then** the tool is not executed and the agent receives a blocked message.
3. **Given** a PostToolUse hook with a HookMatcher pattern `"Write|Edit"`, **When** the agent calls a "Read" tool, **Then** the hook does NOT fire. **When** the agent calls a "Write" tool, **Then** the hook fires.
4. **Given** multiple hooks registered for the same event, **When** the event fires, **Then** all hooks execute in registration order.
5. **Given** an OnError hook, **When** a tool raises an exception, **Then** the hook fires with error details and can provide recovery instructions.

---

### User Story 2 - Guardrails for Input/Output Safety (Priority: P1)

A developer adds input and output guardrails to an agent to enforce safety policies. Input guardrails validate user prompts before they reach the model. Output guardrails validate model responses before they reach the user. Guardrails run in parallel with the main agent loop and can halt execution via tripwire.

**Why this priority**: Guardrails are essential for production safety. They run independently of hooks and represent a distinct concern (safety vs. observability/control).

**Independent Test**: Can be tested by creating a guardrail that blocks prohibited content, running the agent with prohibited input via TestModel, and asserting the guardrail trips.

**Acceptance Scenarios**:

1. **Given** an input guardrail that checks for prohibited content, **When** a user prompt contains prohibited content, **Then** the guardrail returns `tripwire=True` and execution halts before the model is called.
2. **Given** an output guardrail that checks for PII in responses, **When** the model response contains PII, **Then** the guardrail returns `tripwire=True` and the response is not delivered to the user.
3. **Given** multiple guardrails, **When** input is submitted, **Then** all guardrails run in parallel (not sequentially).
4. **Given** a guardrail that returns `passed=False` without `tripwire=True`, **When** it fails, **Then** the failure is logged but execution continues.
5. **Given** guardrails with typed dependencies `RunContext[DepsT]`, **When** the guardrail executes, **Then** it has access to the same dependencies as the agent.

---

### User Story 3 - Composable Skills/Plugins (Priority: P2)

A developer packages related tools, instructions, hooks, and guardrails into a reusable Skill. They attach skills to agents at configuration time. Skills from different sources (internal, third-party) compose cleanly without conflicts.

**Why this priority**: Skills are the packaging/reuse mechanism. They depend on hooks and guardrails being implemented but add significant value for real-world usage and ecosystem building.

**Independent Test**: Can be tested by creating a "web-search" skill with tools, a system prompt fragment, and a PreToolUse hook, attaching it to an agent, and verifying all components register correctly.

**Acceptance Scenarios**:

1. **Given** a Skill with tools, instructions, and hooks, **When** attached to an agent, **Then** all tools are registered, instructions are appended to the system prompt, and hooks are active.
2. **Given** two Skills with different tools, **When** both are attached to the same agent, **Then** all tools from both skills are available without naming conflicts.
3. **Given** a Skill with a guardrail, **When** the skill is attached, **Then** the guardrail runs alongside the agent's own guardrails.
4. **Given** a Skill created with `deps_type=MyDeps`, **When** attached to an agent with the same `deps_type`, **Then** the skill's tools and hooks receive the correct typed dependencies.
5. **Given** a Skill, **When** shared across multiple agents, **Then** each agent gets its own instance of the skill's state (no shared mutable state).

---

### User Story 4 - Multi-Agent Handoffs (Priority: P2)

A developer creates a multi-agent system where a primary agent can delegate tasks to specialist agents. Handoffs appear as tool calls to the LLM — the model decides when to delegate based on the handoff description. Conversation context transfers to the target agent.

**Why this priority**: Multi-agent is a key differentiator but requires hooks and guardrails as building blocks. Many users will start with single-agent and add multi-agent later.

**Independent Test**: Can be tested by creating a triage agent with a handoff to a specialist agent, providing a prompt that triggers delegation, and verifying the specialist agent handles it and returns a result.

**Acceptance Scenarios**:

1. **Given** an agent with a Handoff to a specialist agent, **When** the LLM decides to delegate, **Then** the specialist agent receives the conversation context and runs to completion.
2. **Given** a handoff with a `description`, **When** the agent's tools are listed, **Then** the handoff appears as a callable tool with the description visible to the LLM.
3. **Given** a handoff from agent A (deps_type=SharedDeps) to agent B (deps_type=SharedDeps), **When** the handoff occurs, **Then** agent B receives the same dependency instance as agent A.
4. **Given** a PreHandoff hook, **When** a handoff is triggered, **Then** the hook fires before the handoff executes, and can block or redirect the handoff.
5. **Given** a chain of handoffs (A -> B -> C), **When** the chain completes, **Then** the result propagates back to agent A.
6. **Given** a handoff with an optional `filter` function, **When** the filter returns `False`, **Then** the handoff tool is not presented to the LLM for that run.

---

### User Story 5 - Permission Policies (Priority: P3)

A developer configures permission policies to control which tools an agent can use. Policies use glob patterns for allow/block lists and can require human approval for sensitive tools.

**Why this priority**: Permissions are important for production safety but are a refinement on top of the core hook system. Most early adopters will rely on hooks for access control before needing a dedicated permission model.

**Independent Test**: Can be tested by creating a permission policy that blocks `"file_*"` tools, attaching it to an agent, and verifying file tools are excluded from the tool list sent to the model.

**Acceptance Scenarios**:

1. **Given** a PermissionPolicy with `allowed_tools=["search_*", "calculate"]`, **When** the agent runs, **Then** only tools matching those patterns are available to the LLM.
2. **Given** a PermissionPolicy with `blocked_tools=["file_delete"]`, **When** the agent runs, **Then** the `file_delete` tool is excluded even if otherwise allowed.
3. **Given** a PermissionPolicy with `require_approval=["execute_*"]`, **When** the LLM calls an `execute_code` tool, **Then** execution pauses and an approval callback is invoked.
4. **Given** conflicting allow and block rules, **When** resolved, **Then** block rules take precedence over allow rules.
5. **Given** a PermissionPolicy attached via a Skill, **When** the skill is active, **Then** the policy applies to all tools (not just the skill's tools).

---

### User Story 6 - Agent Runner with Lifecycle Management (Priority: P3)

A developer uses the Runner to execute agents with full lifecycle management — starting the agent, processing the hook/guardrail pipeline, managing handoffs, and collecting results. The Runner separates agent configuration from execution concerns.

**Why this priority**: The Runner is the integration point that ties all features together. It depends on all other features being implemented. However, a basic runner (without full lifecycle) is needed from P1 for hooks to work.

**Independent Test**: Can be tested by configuring a Runner with hooks, guardrails, and a permission policy, running an agent through it, and asserting the full lifecycle executed correctly.

**Acceptance Scenarios**:

1. **Given** a Runner with an agent, hooks, and guardrails, **When** `runner.run(prompt)` is called, **Then** the full lifecycle executes: OnStart -> input guardrails -> PreModelCall -> model -> PostModelCall -> [PreToolUse -> tool -> PostToolUse]* -> output guardrails -> OnStop.
2. **Given** a Runner in streaming mode, **When** `runner.run_stream(prompt)` is called, **Then** events stream in real-time through the event handler while hooks still fire at appropriate points.
3. **Given** a Runner managing a multi-agent handoff, **When** agent A hands off to agent B, **Then** the Runner tracks both agents' lifecycles and hooks fire for both.
4. **Given** a Runner with `runner.run_sync(prompt)`, **Then** a synchronous wrapper is available for non-async contexts.

---

### User Story 7 - Markdown-Based Skill Definitions (Priority: P1)

A developer or non-technical user defines skills as markdown files in a `skills/` directory. Each markdown file contains frontmatter (name, description, tools, handoffs) and a body that serves as the skill's system prompt / instructions. The SDK automatically discovers and loads these skill files, making them available to agents without writing Python code.

**Why this priority**: This is a core differentiator of the Claude Agent SDK's developer experience — skills as `.md` files in `.claude/commands/` are what make the system accessible to prompt engineers, not just Python developers. Treating skills as code-only would exclude a major user segment.

**Independent Test**: Can be tested by creating a `skills/web-researcher.md` file with frontmatter and instructions, loading the SDK's skill discovery, and asserting the skill is available with correct tools, instructions, and handoff targets.

**Acceptance Scenarios**:

1. **Given** a markdown file in the `skills/` directory with YAML frontmatter (`name`, `description`, `tools`, `handoffs`), **When** the SDK starts, **Then** the skill is auto-discovered and loadable by name.
2. **Given** a skill markdown file with a body containing instructions and `$ARGUMENTS` placeholder, **When** the skill is invoked with arguments, **Then** the placeholder is replaced with the actual arguments in the system prompt.
3. **Given** a skill markdown with `handoffs` frontmatter listing other skill names, **When** the skill is attached to an agent, **Then** the agent can delegate to those handoff targets.
4. **Given** a skill defined in markdown AND a skill defined in Python with the same name, **When** both are loaded, **Then** the Python skill takes precedence with a warning logged.
5. **Given** a nested directory structure (`skills/category/skill.md`), **When** the SDK discovers skills, **Then** skills are namespaced by directory (e.g., `category.skill`).
6. **Given** a skill markdown file with invalid frontmatter, **When** the SDK loads it, **Then** a clear validation error is raised specifying the file and the issue.

---

### User Story 8 - Built-in System Tools (Linux Ecosystem) (Priority: P1)

A developer equips an agent with built-in system tools that wrap the Linux/OS ecosystem — shell execution, file operations, content search, and web access. These tools are provided as a built-in skill/toolset that can be selectively enabled, giving agents real-world capabilities out of the box.

**Why this priority**: Without built-in system tools, agents cannot interact with the file system, run commands, or search code — the most common agent use cases. The Claude Agent SDK's power comes from its built-in Bash/Read/Write/Edit/Glob/Grep tools. Our SDK must provide equivalent capabilities as a first-class, model-agnostic toolset.

**Independent Test**: Can be tested by creating an agent with the system tools skill enabled, running a prompt that requires file reading and shell execution via TestModel with pre-programmed tool calls, and asserting correct tool execution.

**Acceptance Scenarios**:

1. **Given** an agent with the `SystemTools` skill enabled, **When** the agent's tools are listed, **Then** tools for shell execution (`bash`), file read/write/edit, file search (`glob`), and content search (`grep`) are available. Web search and web fetch are provided separately via Pydantic AI's built-in `WebSearchTool` and `WebFetchTool`.
2. **Given** the `bash` tool, **When** invoked with a shell command, **Then** the command executes in the specified working directory with configurable timeout, and stdout/stderr are returned.
3. **Given** the `file_read` tool, **When** invoked with a file path, **Then** the file contents are returned with optional offset/limit for large files.
4. **Given** the `file_write` tool, **When** invoked with a path and content, **Then** the file is created or overwritten at that path.
5. **Given** the `file_edit` tool, **When** invoked with a path, old_string, and new_string, **Then** the exact string replacement is performed in the file.
6. **Given** the `glob` tool, **When** invoked with a pattern like `"**/*.py"`, **Then** matching file paths are returned.
7. **Given** the `grep` tool, **When** invoked with a regex pattern, **Then** matching file paths and line content are returned (wrapping ripgrep/grep).
8. **Given** a `SystemTools` skill configured with `allowed=["file_read", "grep"]`, **When** attached to an agent, **Then** only those specific system tools are enabled (not all).
10. **Given** the `bash` tool with sandboxing enabled, **When** a dangerous command is attempted, **Then** the command is blocked by the permission policy.

---

### User Story 9 - Session Management and Conversation Control (Priority: P2)

A developer manages long-running conversations with session persistence, resumption, budget limits, and interrupts. The SDK provides both stateless (single query) and stateful (multi-turn session) interaction modes.

**Why this priority**: Session management is essential for production agents that maintain state across interactions. It depends on the core Runner being implemented but adds critical production capabilities.

**Independent Test**: Can be tested by creating a session, running multiple queries, saving the session, resuming it in a new Runner instance, and asserting conversation continuity.

**Acceptance Scenarios**:

1. **Given** a Runner configured with `max_turns=5`, **When** the agent exceeds 5 tool-call turns, **Then** execution stops gracefully with a `MaxTurnsReached` result.
2. **Given** a Runner configured with `max_budget_tokens=10000`, **When** token usage approaches the budget, **Then** execution stops with a `BudgetExhausted` result.
3. **Given** a running agent, **When** `runner.interrupt()` is called, **Then** the current execution stops gracefully and partial results are available.
4. **Given** a completed session, **When** `runner.resume(session_id)` is called with a new prompt, **Then** the conversation continues with full prior context.
5. **Given** a PreCompact hook registered, **When** the conversation context approaches model limits, **Then** the hook fires before context compaction, allowing custom summarization logic.
6. **Given** streaming input via an async iterable of messages, **When** passed to `runner.run()`, **Then** messages are processed as they arrive (not buffered).

---

### Edge Cases

- What happens when a hook raises an unhandled exception? The OnError hook fires; if OnError itself fails, the exception propagates to the caller.
- What happens when two skills register tools with the same name? A `SkillConflictError` is raised at registration time with clear guidance on resolution (skill namespacing).
- What happens when a guardrail times out? The guardrail is treated as `passed=True` with a warning logged (fail-open by default, configurable to fail-closed).
- What happens when a handoff target agent is not properly configured? A `HandoffConfigError` is raised at registration time, not at runtime.
- What happens when a circular handoff chain is detected (A -> B -> A)? A configurable max handoff depth (default: 10) prevents infinite loops; `HandoffDepthError` is raised.
- What happens when all models fail in a multi-model setup? The OnError hook fires with details; no silent fallback to a different model unless explicitly configured.
- What happens when a skill markdown file has syntax errors in frontmatter? A `SkillLoadError` is raised with file path, line number, and a human-readable message.
- What happens when `bash` tool runs a command that hangs? Configurable timeout (default: 120s) kills the process and returns a timeout error.
- What happens when `file_read` is called on a binary file? The tool detects binary content and returns metadata (size, MIME type) instead of raw bytes.
- What happens when `runner.interrupt()` is called during a tool execution? The tool execution is cancelled via asyncio cancellation, and a partial result is returned.
- What happens when session storage is unavailable for `resume()`? A `SessionNotFoundError` is raised with the session ID and storage backend details.
- What happens when a skill markdown references a handoff target that doesn't exist? A warning is logged at load time (not an error), and the handoff is omitted. Error occurs only if the handoff is invoked at runtime.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `Hook` class that accepts a `HookEvent` type, an async callback function, and an optional `HookMatcher` with regex pattern matching on tool names.
- **FR-002**: System MUST support 11 hook event types: `PreToolUse`, `PostToolUse`, `PreModelCall`, `PostModelCall`, `PreHandoff`, `PostHandoff`, `OnError`, `OnStart`, `OnStop`, `PreCompact`, `Notification`.
- **FR-003**: System MUST provide a `Guardrail` generic class parameterized by `DepsT` with an async `check` method returning `GuardrailResult`.
- **FR-004**: System MUST execute input guardrails in parallel before the model call and output guardrails in parallel after the model response.
- **FR-005**: System MUST provide a `Skill` generic class that bundles tools, instructions, hooks, and guardrails into a composable, reusable unit.
- **FR-006**: System MUST provide a `Handoff` generic class that registers target agents as tool calls, enabling model-driven delegation.
- **FR-007**: System MUST provide a `PermissionPolicy` class with glob-pattern-based `allowed_tools`, `blocked_tools`, and `require_approval` lists.
- **FR-008**: System MUST provide a `Runner` class that orchestrates the full agent lifecycle including hooks, guardrails, permissions, and handoffs.
- **FR-009**: System MUST preserve full compatibility with Pydantic AI's `Agent`, `RunContext`, `Tool`, `Model`, streaming, and `TestModel` APIs.
- **FR-010**: System MUST support synchronous (`run_sync`), asynchronous (`run`), and streaming (`run_stream`) execution modes.
- **FR-011**: System MUST provide clear error types: `SkillConflictError`, `HandoffConfigError`, `HandoffDepthError`, `GuardrailTripwireError`, `PermissionDeniedError`.
- **FR-012**: System MUST allow hooks to modify tool arguments (PreToolUse), modify tool results (PostToolUse), modify model messages (PreModelCall), and block execution.
- **FR-013**: System MUST allow guardrails to access typed dependencies via `RunContext[DepsT]`.
- **FR-014**: System MUST detect and prevent tool name conflicts across skills at registration time.
- **FR-015**: System MUST enforce a configurable maximum handoff depth to prevent circular delegation.
- **FR-016**: System MUST support skill definitions as markdown files with YAML frontmatter (`name`, `description`, `tools`, `handoffs`) and a body serving as the skill's instructions/system prompt.
- **FR-017**: System MUST auto-discover skill markdown files from a configurable `skills/` directory, supporting nested directories for namespacing.
- **FR-018**: System MUST support `$ARGUMENTS` placeholder substitution in skill markdown bodies when the skill is invoked with arguments.
- **FR-019**: System MUST provide a built-in `SystemTools` skill containing: `bash` (shell execution with timeout), `file_read` (read with offset/limit), `file_write` (create/overwrite), `file_edit` (string replacement), `glob` (file pattern matching), and `grep` (content search via regex). Web search and web fetch are NOT included — Pydantic AI's built-in `WebSearchTool` and `WebFetchTool` MUST be used instead. The `SystemTools` skill SHOULD integrate Pydantic AI's `CodeExecutionTool` as an optional sub-tool.
- **FR-020**: System MUST allow selective enabling of individual system tools (e.g., read-only agents get `file_read` and `grep` but not `bash` or `file_write`).
- **FR-021**: System MUST support `max_turns` configuration to limit the number of tool-call turns per agent run.
- **FR-022**: System MUST support `max_budget_tokens` configuration to limit total token consumption per agent run.
- **FR-023**: System MUST support `runner.interrupt()` to cancel a running agent and return partial results.
- **FR-024**: System MUST support session persistence and `runner.resume(session_id)` for multi-turn conversation continuity.
- **FR-025**: System MUST support a `PreCompact` hook event that fires before conversation context is compacted due to model context limits.
- **FR-026**: System MUST support streaming input via async iterables, not just string prompts.
- **FR-027**: The `bash` system tool MUST support configurable timeout, working directory, and environment variables per invocation.
- **FR-028**: The `bash` system tool MUST integrate with the PermissionPolicy system — dangerous commands can be blocked or require approval.
- **FR-029**: Hooks MUST support configurable per-hook timeout to prevent runaway hook execution.
- **FR-030**: Hooks MUST support advanced control outputs: `additionalContext` (inject context into conversation), `suppressOutput` (hide tool output from model), `continue_` (control whether agent loop continues), and custom `stopReason`.
- **FR-031**: Hooks MUST support fire-and-forget async mode for non-blocking logging/telemetry hooks.
- **FR-032**: Tools MUST support annotations metadata: `readOnly` (tool only reads data), `destructive` (tool modifies/deletes data), `openWorld` (tool accesses external systems). Annotations inform permission decisions and UI.
- **FR-033**: System MUST support predefined `PermissionMode` presets: `default` (prompt for dangerous ops), `readOnly` (only read tools allowed), `unrestricted` (all tools auto-approved), `planOnly` (no execution, planning only).
- **FR-034**: System MUST integrate with Pydantic AI's built-in fallback model system (`models.fallback`) — documenting how to configure auto-fallback to a secondary model when the primary model fails or is rate-limited.
- **FR-035**: System MUST support model-specific thinking/reasoning configuration passthrough: adaptive thinking, thinking budget tokens, and effort level (low/medium/high/max) for models that support extended reasoning.
- **FR-036**: System MUST expose Pydantic AI's built-in `RunUsage` metrics (input_tokens, output_tokens, cache_tokens) through the Runner result, and MUST additionally track number of hook invocations, guardrail checks, and handoff count per run as SDK-level metrics.
- **FR-037**: System MUST provide a configurable debug/log callback for internal SDK events, replacing stderr-based debugging with structured log output.
- **FR-038**: System MUST provide a `Transport` protocol/ABC enabling custom agent communication backends (in-process, subprocess, HTTP, WebSocket) for remote/distributed agent execution.
- **FR-039**: System MUST support dynamic permission modification at runtime — adding, removing, or replacing permission rules during an agent run via hooks or API.
- **FR-040**: System MUST support session forking — creating a new conversation branch from an existing session's state.

### Key Entities

- **Hook**: A lifecycle callback bound to a specific event type with optional matcher filtering. Attributes: event type, callback, matcher pattern, priority.
- **HookMatcher**: A filter that determines whether a hook fires for a given event. Uses regex patterns on event targets (tool names, agent names).
- **Guardrail**: A safety check that runs in parallel with the agent. Types: input guardrail (validates prompts), output guardrail (validates responses). Returns pass/fail/tripwire.
- **Skill**: A composable package of agent capabilities. Can be defined in Python (class-based) OR as markdown files (declarative). Contains: tools, system prompt instructions, hooks, guardrails. Skills are the unit of reuse and distribution.
- **SkillMarkdown**: A skill defined as a `.md` file with YAML frontmatter (name, description, tools, handoffs) and a body providing instructions. Supports `$ARGUMENTS` placeholder and directory-based namespacing.
- **SystemTools**: A built-in skill providing OS/system interaction tools: bash, file_read, file_write, file_edit, glob, grep. Selectively enableable per agent. Web search/fetch/code execution use Pydantic AI's built-in tools.
- **Handoff**: A delegation target that appears as a tool to the LLM. Contains: target agent, description (for LLM), optional filter function, optional context transformer.
- **PermissionPolicy**: A declarative access control policy for tools. Uses glob patterns for allow/block/approval lists. Evaluated before tool execution.
- **Runner**: The execution engine that manages the agent lifecycle. Coordinates hooks, guardrails, permissions, handoffs, sessions, budgets, and interrupts. Separates configuration from execution.
- **Session**: A persistent conversation state that can be saved, resumed, and forked. Contains: message history, agent configuration snapshot, metadata.
- **GuardrailResult**: The outcome of a guardrail check. Contains: passed (bool), reason (optional message), tripwire (bool, halts execution if true).
- **ToolAnnotations**: Metadata about a tool's behavior. Contains: readOnly (bool), destructive (bool), openWorld (bool). Used by permission system and UI.
- **PermissionMode**: A predefined permission preset. Options: default (prompt for dangerous), readOnly (read-only tools only), unrestricted (all auto-approved), planOnly (no execution).
- **Transport**: An abstract communication backend for agent execution. Enables in-process, subprocess, HTTP, and WebSocket transports for distributed agent architectures.
- **UsageMetrics**: Per-run usage tracking. Extends Pydantic AI's `RunUsage` (input_tokens, output_tokens, cache_tokens) with SDK-level metrics: hook_invocations, guardrail_checks, handoff_count. Available on RunResult.

### Pydantic AI Features to Leverage (NOT reimplement)

The SDK MUST integrate with, not reimplement, these Pydantic AI capabilities:

- **Model abstraction**: `Model` protocol with 15+ providers (OpenAI, Anthropic, Google, Groq, Mistral, Cohere, xAI, Bedrock, HuggingFace, OpenRouter, etc.)
- **Agent generics**: `Agent[DepsT, OutputT]` for typed dependency injection and structured output
- **Tool system**: `@agent.tool()`, `@agent.tool_plain()`, `Tool.from_schema()`, auto JSON schema from type hints
- **Toolsets**: `AbstractToolset`, `FilteredToolset`, `PrefixedToolset`, `WrapperToolset`, `CombinedToolset`, `ApprovalRequiredToolset`, `FastMCPToolset`
- **Built-in tools**: `WebSearchTool`, `WebFetchTool`, `CodeExecutionTool`, `FileSearchTool`, `ImageGenerationTool`, `MemoryTool`
- **Common tools**: DuckDuckGo, Exa, Tavily search integrations
- **Tool approval**: `DeferredToolRequests`, `ToolApproved`, `ToolDenied`, `ApprovalRequired` exception
- **Fallback models**: `models.fallback` for automatic model failover
- **Usage tracking**: `RunUsage` with input/output/cache token counts
- **Streaming**: `run_stream()`, `AgentStreamEvent`, `EventStreamHandler`
- **Concurrency**: `ConcurrencyLimit`, `ConcurrencyLimiter`, `max_concurrency`
- **Retries**: Per-tool `max_retries`, `output_retries`, tenacity integration
- **History processors**: `HistoryProcessor` for context management
- **Testing**: `TestModel`, `FunctionModel`, `@agent.override()`
- **Instrumentation**: OpenTelemetry via `instrument` parameter, Logfire integration
- **Durable execution**: DBOS, Prefect, Temporal workflow integrations
- **Embeddings**: Multi-provider embedding system
- **MCP**: `FastMCPToolset` for Model Context Protocol servers
- **Output validation**: Pydantic model validation, `output_type`, `@output_validator()`
- **End strategy**: `'early'` vs `'exhaustive'` for tool call handling

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can create a single agent with tools and hooks in under 20 lines of code (excluding imports).
- **SC-002**: A developer can add guardrails to an existing Pydantic AI agent by adding 5 or fewer lines of code.
- **SC-003**: A developer can create and attach a reusable Skill in under 15 lines of code.
- **SC-004**: A developer can set up a two-agent handoff system in under 30 lines of code.
- **SC-005**: All SDK features work identically across at least 3 different model providers (verified by test suite).
- **SC-006**: The SDK adds less than 500KB to the installed package size (excluding pydantic-ai).
- **SC-007**: Hook execution overhead is less than 1ms per hook invocation (measured via benchmark).
- **SC-008**: 90% of test suite runs without any real LLM API calls (using TestModel/FunctionModel).
- **SC-009**: The SDK passes `mypy --strict` with zero errors.
- **SC-010**: A developer can migrate from raw Pydantic AI to the SDK by changing fewer than 10 lines in a typical single-agent application.
- **SC-011**: A non-developer can create a functional skill by writing only a markdown file — no Python code required.
- **SC-012**: An agent with `SystemTools` enabled can read files, search code, and execute shell commands on the local system.
- **SC-013**: An agent can be interrupted mid-execution and return partial results within 1 second.
- **SC-014**: A session can be saved and resumed across process restarts, maintaining full conversation context.
- **SC-015**: Usage metrics (tokens, tool calls, estimated cost) are available after every agent run.
- **SC-016**: The SDK automatically falls back to a secondary model when the primary model is unavailable.
- **SC-017**: A developer can run an agent remotely via a custom Transport implementation (e.g., HTTP) without changing agent or tool code.
