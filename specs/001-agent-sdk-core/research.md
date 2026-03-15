# Research: Agent SDK Core

**Phase 0 Output** | **Date**: 2026-03-15

## R1: How to Intercept Pydantic AI's Agent Loop for Hooks

**Decision**: Implement hooks via a custom `WrapperToolset` that intercepts tool calls, combined with `HistoryProcessor` for PreModelCall/PostModelCall, and `EventStreamHandler` for streaming events.

**Rationale**: Pydantic AI's `WrapperToolset` is designed exactly for cross-cutting concerns — it wraps any toolset and intercepts `call_tool()`. This gives us PreToolUse/PostToolUse without modifying Pydantic AI internals. For model-level hooks, `HistoryProcessor` transforms messages before sending to the model (PreModelCall), and `EventStreamHandler` captures responses (PostModelCall). OnStart/OnStop are trivially added around `agent.run()`.

**Alternatives considered**:
- Monkey-patching `Agent.run()`: Fragile, breaks with Pydantic AI updates. Rejected.
- Subclassing `Agent`: Violates Constitution V (Composition Over Inheritance). Rejected.
- Custom `Model` wrapper: Would intercept model calls but adds complexity and breaks the principle of not wrapping Pydantic AI. Rejected.
- Using `agent.iter()` for step-by-step control: Viable but couples to internal graph nodes. Too tight coupling. Rejected.

## R2: How to Run Guardrails in Parallel

**Decision**: Use `asyncio.gather()` (or `anyio.create_task_group()`) to run all guardrails concurrently. Guardrails receive a snapshot of the input/output, not a reference to mutable state.

**Rationale**: Guardrails are read-only validators — they inspect data and return pass/fail/tripwire. Running them in parallel is safe because they don't modify shared state. Using `asyncio.gather()` with `return_exceptions=True` ensures one guardrail failure doesn't cancel others. Timeout per guardrail is implemented via `asyncio.wait_for()`.

**Alternatives considered**:
- Sequential execution: Simpler but defeats the purpose — slow guardrails block fast ones. Rejected.
- Thread pool: Unnecessary overhead for async guardrails. Rejected.

## R3: Skill Architecture — AbstractToolset vs Custom

**Decision**: `Skill[DepsT]` extends Pydantic AI's `AbstractToolset[DepsT]`. This makes skills first-class toolsets that compose with Pydantic AI's existing `CombinedToolset`, `FilteredToolset`, `PrefixedToolset` ecosystem.

**Rationale**: By extending `AbstractToolset`, a Skill automatically works with `agent = Agent(toolsets=[skill1, skill2])`. The Skill adds hooks, guardrails, and instructions on top of the toolset's tool definitions. This is the most natural integration point — no wrapping, no adapters.

**Alternatives considered**:
- Standalone class that registers tools manually: Would duplicate Pydantic AI's tool registration logic. Rejected.
- Wrapper around `CombinedToolset`: Adds unnecessary indirection. Rejected.
- Plugin descriptor pattern (like Semantic Kernel): Too much ceremony for Python. Rejected.

## R4: Handoff Implementation via Pydantic AI Tools

**Decision**: Each `Handoff` registers as a Pydantic AI tool on the parent agent. The tool function runs the target agent via `target_agent.run()` and returns the result. PreHandoff/PostHandoff hooks fire before/after the tool execution.

**Rationale**: This is exactly how the OpenAI Agents SDK implements handoffs — as tool calls. The LLM sees a tool like `delegate_to_code_reviewer(task: str)` and decides when to use it. The tool function handles context transfer (passing message history or a summary to the target agent). Depth tracking uses a counter in `RunContext.metadata`.

**Alternatives considered**:
- Graph-based orchestration (LangGraph style): Over-engineered for most use cases. Violates Constitution VI (Progressive Complexity). Rejected.
- Message-bus routing (AutoGen style): Requires runtime infrastructure. Violates Constitution IV (Lightweight). Rejected.
- Custom handoff protocol: Would need its own serialization format. Unnecessary when tool calls work perfectly. Rejected.

## R5: Permission Policy Evaluation Strategy

**Decision**: Permissions are evaluated via a custom `PreparedToolset` that wraps the agent's toolsets. On each step, the `prepare` function filters tools based on the policy's glob patterns. `require_approval` tools use Pydantic AI's built-in `ApprovalRequiredToolset`.

**Rationale**: Pydantic AI's `PreparedToolset` runs a `prepare` function before each model call, returning the filtered tool list. This is the correct interception point for permissions — tools are filtered BEFORE the model sees them, not after the model calls them. For approval-required tools, Pydantic AI already has `ApprovalRequiredToolset` which we wrap rather than reimplement.

**Alternatives considered**:
- PreToolUse hook that blocks: Works but the model already wasted tokens generating the tool call. Filtering before the model call is more efficient. Rejected as primary mechanism (kept as fallback via hooks).
- Static tool list filtering at registration time: Doesn't support dynamic permissions (FR-039). Rejected as sole mechanism.

## R6: Markdown Skill Parsing

**Decision**: Use PyYAML for frontmatter parsing. The markdown file format is:
```yaml
---
name: skill-name
description: What this skill does
tools: [tool1, tool2]
handoffs:
  - label: Target Name
    agent: other-skill
    prompt: When to hand off
---
Instruction body with $ARGUMENTS placeholder
```

**Rationale**: YAML frontmatter is the standard for markdown metadata (used by Jekyll, Hugo, Obsidian, Claude commands). PyYAML is lightweight (157KB), well-maintained, and already a transitive dependency in many Python projects. The format matches Claude Agent SDK's `.claude/commands/*.md` pattern for familiarity.

**Alternatives considered**:
- TOML frontmatter: Less common in markdown. `tomllib` is stdlib in 3.11+ but TOML in frontmatter is non-standard. Rejected.
- JSON frontmatter: Harder to read/write for non-developers. Rejected.
- Python dataclass serialization: Defeats the purpose of code-free skill definition. Rejected.

## R7: SystemTools Implementation

**Decision**: Each system tool is a standalone async function registered via `@tool` decorator. The `SystemTools` skill bundles them into a `FilteredToolset` where users select which tools to enable.

| Tool | Implementation | Notes |
|------|---------------|-------|
| `bash` | `asyncio.create_subprocess_exec` | Configurable timeout, cwd, env. Integrates with PermissionPolicy. |
| `file_read` | `pathlib.Path.read_text()` with offset/limit | Returns content with line numbers. Binary detection via `is_binary_string` heuristic. |
| `file_write` | `pathlib.Path.write_text()` | Creates parent directories. Returns confirmation. |
| `file_edit` | String search-and-replace | Fails if `old_string` not found or not unique. Returns diff preview. |
| `glob` | `pathlib.Path.glob()` | Returns sorted file paths with modification time. |
| `grep` | `subprocess` calling `grep -rn` (or `rg` if available) | Falls back to Python `re` if no grep binary. Returns file:line:content. |

**Rationale**: Native OS tools (subprocess, pathlib) are battle-tested and fast. Using `asyncio.create_subprocess_exec` for bash ensures non-blocking execution. Wrapping `grep`/`rg` rather than reimplementing regex search leverages optimized C implementations.

**Alternatives considered**:
- Pure Python implementations: Slower for large codebases (grep over 10K files). Rejected for grep/bash.
- Direct ripgrep bindings (`rg` Python package): Adds a compiled dependency. Rejected for core; could be optional enhancement.

## R8: Session Persistence

**Decision**: Sessions are serialized as JSON files using Pydantic AI's `ModelMessagesTypeAdapter` for message serialization. A `SessionBackend` protocol allows custom backends (Redis, SQLite, etc.) via optional extras.

**Rationale**: JSON files are zero-dependency and human-readable for debugging. Pydantic AI already provides `ModelMessagesTypeAdapter` for serializing/deserializing message histories. The `SessionBackend` protocol keeps the door open for production backends without adding dependencies to core.

**Alternatives considered**:
- SQLite: Adds `sqlite3` complexity to core. Better as an optional extra. Rejected for default.
- Pickle: Security risk (arbitrary code execution on deserialization). Rejected.
- In-memory only: Insufficient for production (no resume across process restarts). Rejected as only option.

## R9: Transport Abstraction Design

**Decision**: Minimal `Transport` protocol with `send()` and `receive()` methods. Default `InProcessTransport` executes agents in the same process. HTTP and WebSocket transports are optional extras.

```python
class Transport(Protocol[DepsT, OutputT]):
    async def run(self, agent: Agent[DepsT, OutputT], prompt: str, **kwargs) -> RunResult[OutputT]: ...
    async def run_stream(self, agent: Agent[DepsT, OutputT], prompt: str, **kwargs) -> AsyncIterator[AgentStreamEvent]: ...
```

**Rationale**: The transport abstraction enables remote agent execution without changing agent or tool code. The protocol is minimal (2 methods) to keep it lightweight. InProcessTransport is just `agent.run()` passthrough.

**Alternatives considered**:
- gRPC-based transport: Too heavy for core. Good as optional extra. Rejected for core.
- Custom message format: Unnecessary when we can serialize Pydantic AI's message types directly. Rejected.

## R10: PyYAML as Additional Dependency

**Decision**: Add `PyYAML >= 6.0` as a core dependency for markdown skill frontmatter parsing.

**Rationale**: PyYAML is 157KB, pure Python, and the de facto standard for YAML in Python. It's already a transitive dependency of many projects (Docker, Kubernetes, Ansible, etc.). The alternative (stdlib `tomllib`) doesn't support YAML frontmatter, which is the industry standard for markdown metadata. The dependency cost is justified by the Dual Skill Definition principle (Constitution IX).

**Constitution IV check**: Adding PyYAML increases core dependencies from 3 to 4. This is within acceptable bounds — the constitution says "minimal dependencies" not "exactly 3". PyYAML enables a core principle (IX), so the trade-off is justified.
