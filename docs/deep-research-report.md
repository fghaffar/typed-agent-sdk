# Deep Research Report: Agent SDK Landscape Analysis

**Date**: 2026-03-15
**Purpose**: Inform the design of a lightweight, model-agnostic, type-safe Agent SDK built on top of Pydantic AI

---

## 1. Executive Summary

This report analyzes six major agent SDK frameworks to identify the best architectural patterns for building a lightweight, model-agnostic, type-safe agent SDK. The key finding is that **Pydantic AI provides the ideal foundation** — it already delivers model-agnostic support, deep type safety via generics, and a FastAPI-like developer experience. The gap is in **orchestration-level features** (hooks lifecycle, guardrails, skills/plugins, multi-agent handoffs) that Anthropic's Claude Agent SDK and OpenAI's Agents SDK excel at. The proposed SDK bridges this gap by layering lightweight orchestration primitives on top of Pydantic AI's core.

---

## 2. Framework Analysis

### 2.1 Anthropic Claude Agent SDK

**Architecture**: Event-driven agent loop with hooks lifecycle system. The SDK wraps Claude as the execution engine, providing programmatic control over the agent's tool use, permissions, and subagent orchestration.

**Core Concepts**:
- **Query/Session model**: `query()` function sends prompts and streams responses. Sessions maintain conversation state.
- **Hooks system**: 10+ lifecycle events (`PreToolUse`, `PostToolUse`, `Stop`, `SubagentStart`, `SubagentStop`, `UserPromptSubmit`, `PreCompact`, `Notification`, `PermissionRequest`, `SessionStart`, `SessionEnd`, `Setup`, `ConfigChange`). Hooks use `HookMatcher` patterns (regex on tool names) to filter which hooks fire.
- **MCP-native tools**: Tools are defined as MCP servers via `create_sdk_mcp_server()`. The `@tool` decorator creates tool definitions with JSON schema. Tools are namespaced: `mcp__servername__toolname`.
- **Permissions**: `allowedTools` whitelist with glob patterns (`mcp__github__*`). Permission hooks for runtime decisions.
- **Subagents**: Full subagent lifecycle with `SubagentStart`/`SubagentStop` hooks, transcript tracking, and nested tool execution.
- **Streaming**: Async generator pattern for streaming responses.

**Strengths**:
- Rich hook lifecycle system — most comprehensive event model of any SDK
- MCP-native tool architecture — interoperable with the broader MCP ecosystem
- Fine-grained permissions model
- Subagent orchestration with lifecycle tracking

**Weaknesses**:
- Tightly coupled to Claude/Anthropic — not model-agnostic
- Heavy runtime (spawns actual Claude processes)
- MCP-only tool model adds overhead for simple tools
- No type-safe dependency injection pattern

**Key Patterns to Adopt**:
- Hook lifecycle event system (simplified)
- Permission/allowed tools model
- Subagent lifecycle tracking
- Tool namespacing

---

### 2.2 Pydantic AI

**Architecture**: Agent-centric framework with FastAPI-like ergonomics. Agents are generic classes parameterized by dependency type and output type, providing compile-time type safety.

**Core Concepts**:
- **Agent[DepsT, OutputT]**: Generic agent class. `DepsT` is the dependency injection type, `OutputT` is the structured output type validated by Pydantic.
- **Model abstraction**: `Model` protocol with implementations for OpenAI, Anthropic, Google, Groq, Mistral, Ollama, and a test model. Model-agnostic by design.
- **Tools**: Three registration patterns:
  1. `@agent.tool` — decorator with `RunContext[DepsT]` access
  2. `@agent.tool_plain` — decorator without context
  3. `Tool(func, ...)` — explicit tool definition
  Auto-generates JSON schema from type hints. Supports Pydantic models as parameters.
- **Dependency Injection**: `RunContext[DepsT]` carries typed dependencies through the entire execution. Dependencies are provided at `agent.run(deps=...)` time.
- **Structured Output**: `output_type` parameter validates LLM output against Pydantic models. Retries on validation failure.
- **Streaming**: `agent.run_stream()` with `AgentStreamEvent` types (`PartStartEvent`, `PartDeltaEvent`, `FunctionToolCallEvent`, `FunctionToolResultEvent`, `FinalResultEvent`).
- **Multi-agent**: Delegation via tool calls — one agent calls another inside a tool function. Shared dependencies via `RunContext`.
- **Toolsets**: `AbstractToolset` for grouping related tools. `toolsets` parameter on Agent.
- **History Processors**: Transform message history before sending to model (context windowing, summarization).
- **Event Stream Handler**: Async callback receiving `AsyncIterable[AgentStreamEvent]` for real-time event processing.

**Strengths**:
- Best-in-class type safety — generics for deps AND output
- Truly model-agnostic with clean Model protocol
- FastAPI-like developer experience (decorators, DI)
- Pydantic validation for tool args AND outputs
- Lightweight core with minimal dependencies
- Built-in test model for testing without API calls
- Toolsets for organized tool grouping

**Weaknesses**:
- No built-in hook/middleware lifecycle system
- Multi-agent is manual (delegation via tool calls, no handoff primitive)
- No guardrails concept
- No skills/plugin packaging system
- No permission model for tools
- Event streaming is output-focused, not lifecycle-focused

**Key Patterns to Adopt (as foundation)**:
- `Agent[DepsT, OutputT]` generic pattern
- `RunContext[DepsT]` dependency injection
- Model protocol for provider abstraction
- Decorator-based tool registration
- Pydantic output validation
- Toolset grouping
- Event stream architecture

---

### 2.3 OpenAI Agents SDK (formerly Swarm)

**Architecture**: Agent-as-configuration with a separate Runner execution engine. Handoffs are first-class primitives for multi-agent coordination.

**Core Concepts**:
- **Agent**: Dataclass with `name`, `instructions`, `model`, `tools`, `handoffs`, `output_type`, `model_settings`. Configuration only, no behavior.
- **Runner**: `Runner.run()`, `Runner.run_sync()`, `Runner.run_streamed()` — executes the agent loop.
- **Handoffs**: Listed in agent's `handoffs` field. The model invokes a handoff like a tool call, transferring control to another agent with full conversation context.
- **Guardrails**: Input and output guardrails run in parallel with the main agent. `GuardrailResult` with `tripwire_triggered`.
- **RunContext[T]**: Generic context for dependency injection into tools, guardrails, and dynamic instructions.

**Strengths**:
- Simplest mental model — agents are just config
- Handoffs are elegant (multi-agent as tool calls)
- Strong type safety with generics
- Guardrails as first-class concept
- Very lightweight (~15 core files)

**Weaknesses**:
- Model interface tightly coupled to OpenAI message format
- No hook/middleware system
- No persistence/checkpointing
- No parallel agent execution

**Key Patterns to Adopt**:
- Agent-as-configuration pattern
- Handoffs as tool calls
- Guardrails (input + output, parallel execution)
- Separation of config (Agent) from execution (Runner)

---

### 2.4 LangGraph

**Architecture**: Graph-based state machine for agent orchestration. Nodes are functions, edges define control flow, typed state flows through the graph.

**Core Concepts**:
- **StateGraph[State]**: Graph with typed state schema
- **Nodes**: Functions receiving state, returning state updates
- **Edges**: Static, conditional, or `END`
- **Checkpointer**: Pluggable persistence (memory, SQLite, Postgres)
- **Send()**: Fan-out for parallel execution

**Strengths**:
- Most flexible orchestration (any workflow topology)
- Best-in-class checkpointing and time-travel debugging
- Rich streaming at every level
- Human-in-the-loop interrupts

**Weaknesses**:
- Steep learning curve; over-engineered for simple cases
- Heavy LangChain dependency tree
- String-based node naming reduces type safety
- State reducer semantics are confusing

**Key Patterns to Adopt**:
- Optional checkpointing concept (simplified)
- Conditional routing for complex workflows
- Typed state management

---

### 2.5 AutoGen (Microsoft)

**Architecture**: Protocol-based agents communicating via a message bus runtime. Layered design with core primitives and high-level AgentChat convenience layer.

**Core Concepts**:
- **Agent protocol**: `on_messages()` method
- **AgentRuntime**: Message bus for routing
- **Teams**: RoundRobin, Selector, Swarm group chat patterns
- **Termination conditions**: Composable stopping criteria

**Strengths**:
- Most sophisticated multi-agent communication (pub/sub, distributed)
- Clean protocol-based design
- Layered architecture (choose your abstraction level)
- First-class code execution (Docker sandbox)

**Weaknesses**:
- Complex; steep learning curve
- Narrower model support than LiteLLM-based frameworks
- Two-layer design can be confusing

**Key Patterns to Adopt**:
- Protocol-based agent interface
- Composable termination conditions
- Layered architecture (core + convenience)

---

### 2.6 Semantic Kernel (Microsoft)

**Architecture**: Kernel as central DI container with a Plugin system for organizing functions. Cross-language design (C#, Python, Java).

**Core Concepts**:
- **Kernel**: Holds AI services, plugins, filters, memory
- **Plugin**: Collection of KernelFunctions (native code or prompt templates)
- **AI Service**: Clean provider abstraction with capability-based selection
- **Filters**: Pre/post execution middleware on function calls

**Strengths**:
- Most mature model-agnostic design
- Plugin system is powerful (native + prompt + OpenAPI)
- Filter/middleware pattern for hooks
- Cross-language support
- Enterprise-ready (OpenTelemetry, DI)

**Weaknesses**:
- Enterprise complexity — too much ceremony for simple cases
- Kernel as God object
- Python version less idiomatic than C#

**Key Patterns to Adopt**:
- AI Service abstraction with capability-based selection
- Plugin grouping pattern
- Filter/middleware hooks
- OpenAPI-to-tool import concept

---

## 3. Comparative Matrix

| Feature | Claude Agent SDK | Pydantic AI | OpenAI Agents | LangGraph | AutoGen | Semantic Kernel |
|---------|-----------------|-------------|---------------|-----------|---------|-----------------|
| **Model-agnostic** | No (Claude only) | Yes (protocol) | Partial (OpenAI-biased) | Yes (LangChain) | Partial | Yes (best) |
| **Type safety** | Low | High (generics) | High (generics) | Medium | Medium | High (C#), Medium (Py) |
| **Tool system** | MCP servers | Decorators + DI | Decorators | Decorators + ToolNode | FunctionTool | @kernel_function |
| **Hooks/Lifecycle** | 10+ events | None | None | None | None | Filters (pre/post) |
| **Guardrails** | Via hooks | None | First-class | None | None | Via filters |
| **Multi-agent** | Subagents | Manual delegation | Handoffs | Graph orchestration | Group chat | AgentGroupChat |
| **DI pattern** | None | RunContext[T] | RunContext[T] | State dict | Runtime | Kernel container |
| **Structured output** | None | Pydantic models | Pydantic models | TypedDict | Pydantic | Pydantic/TypedDict |
| **Streaming** | Async generator | Event stream | Streamed run | Multi-level | Async | Event-based |
| **Persistence** | None | None | None | Checkpointer | Runtime | Memory stores |
| **Weight** | Heavy | Light | Light | Medium-Heavy | Medium | Medium |
| **Skills/Plugins** | MCP servers | Toolsets | None | None | None | Plugins (best) |

---

## 4. Recommended Architecture

### 4.1 Foundation: Pydantic AI

Pydantic AI is the optimal foundation because:
1. **Already model-agnostic** — clean Model protocol with 7+ provider implementations
2. **Best type safety** — `Agent[DepsT, OutputT]` generics pattern
3. **FastAPI-like DX** — decorators, dependency injection, validation
4. **Lightweight** — minimal dependencies, focused core
5. **Pydantic-native** — first-class structured output validation
6. **Active development** — rapidly evolving with community support

### 4.2 Layers to Add on Top

```
┌─────────────────────────────────────────────────┐
│            Application Layer                     │
│  (User's agents, tools, skills, workflows)       │
├─────────────────────────────────────────────────┤
│         SDK Orchestration Layer                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  Hooks   │ │Guardrails│ │  Multi-Agent     │ │
│  │ Lifecycle│ │ (I/O)    │ │  (Handoffs +     │ │
│  │ System   │ │          │ │   Orchestration) │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  Skills  │ │Permissions│ │  State/Memory   │ │
│  │ /Plugins │ │  Model   │ │  (Optional)      │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│         Pydantic AI Core                         │
│  Agent[DepsT,OutputT] | Model Protocol |         │
│  RunContext[DepsT] | Tools | Streaming           │
├─────────────────────────────────────────────────┤
│         Model Providers (separate packages)      │
│  OpenAI | Anthropic | Google | Groq | Ollama     │
└─────────────────────────────────────────────────┘
```

### 4.3 Key Design Decisions

#### 4.3.1 Hook Lifecycle System (inspired by Claude Agent SDK, adapted for Pydantic AI)

```python
HookEvent = Literal[
    "PreToolUse",       # Before tool execution — can block, modify args
    "PostToolUse",      # After tool execution — can modify result
    "PreModelCall",     # Before sending to LLM — can modify messages
    "PostModelCall",    # After LLM response — can modify/filter output
    "PreHandoff",       # Before agent handoff — can block, redirect
    "PostHandoff",      # After handoff completes
    "OnError",          # On any error — recovery, logging
    "OnStart",          # Agent run starts
    "OnStop",           # Agent run completes
]
```

Hooks use `HookMatcher` pattern matching (regex on tool names, event metadata) from Claude Agent SDK but with Pydantic AI's `RunContext[DepsT]` for typed context access.

#### 4.3.2 Guardrails (inspired by OpenAI Agents SDK)

```python
class Guardrail(Generic[DepsT]):
    """Input or output guardrail that runs in parallel with the agent."""
    async def check(self, ctx: RunContext[DepsT], data: Any) -> GuardrailResult: ...

class GuardrailResult:
    passed: bool
    reason: str | None
    tripwire: bool  # If True, immediately halt execution
```

#### 4.3.3 Skills/Plugins (inspired by Semantic Kernel + Claude MCP)

A Skill is a packaged, reusable bundle of tools, instructions, and hooks:

```python
class Skill(Generic[DepsT]):
    name: str
    description: str
    tools: list[Tool[DepsT]]
    instructions: str | None  # Injected into system prompt
    hooks: dict[HookEvent, list[HookCallback]]
    guardrails: list[Guardrail[DepsT]]
```

Skills are composable and can be shared across agents. They serve as the plugin architecture.

#### 4.3.4 Multi-Agent Handoffs (inspired by OpenAI Agents SDK)

```python
class Handoff(Generic[DepsT]):
    target: Agent[DepsT, Any]
    description: str  # LLM sees this to decide when to handoff
    filter: Callable[[RunContext[DepsT]], bool] | None
```

Handoffs are registered as tools — the LLM decides when to delegate. This is simpler and more composable than graph-based orchestration.

#### 4.3.5 Permissions Model (inspired by Claude Agent SDK)

```python
class PermissionPolicy:
    allowed_tools: list[str]     # Glob patterns
    blocked_tools: list[str]     # Glob patterns (override allowed)
    require_approval: list[str]  # Tools requiring human approval

    async def check(self, tool_name: str, ctx: RunContext) -> PermissionResult: ...
```

---

## 5. Feature Mapping: What to Include

### 5.1 Core (Must Have — v1.0)

| Feature | Source Inspiration | Implementation Approach |
|---------|-------------------|------------------------|
| Model-agnostic agents | Pydantic AI | Use as-is (`Agent[DepsT, OutputT]`) |
| Typed dependency injection | Pydantic AI | Use as-is (`RunContext[DepsT]`) |
| Decorator-based tools | Pydantic AI | Use as-is (`@agent.tool`) |
| Structured output | Pydantic AI | Use as-is (`output_type`) |
| Streaming | Pydantic AI | Extend with hook events |
| Hook lifecycle | Claude Agent SDK | New: 9 event types with matchers |
| Guardrails | OpenAI Agents SDK | New: input/output guardrails |
| Skills/Plugins | Semantic Kernel + Claude MCP | New: composable skill bundles |
| Handoffs | OpenAI Agents SDK | New: handoff-as-tool pattern |
| Permissions | Claude Agent SDK | New: glob-based tool permissions |
| Agent Runner | OpenAI Agents SDK | New: separate config from execution |

### 5.2 Extended (Should Have — v1.x)

| Feature | Source Inspiration |
|---------|-------------------|
| Checkpointing/persistence | LangGraph |
| Conditional routing | LangGraph |
| OpenAPI tool import | Semantic Kernel |
| MCP server integration | Claude Agent SDK |
| Composable termination | AutoGen |
| Observability (OpenTelemetry) | Semantic Kernel |
| Test utilities | Pydantic AI |

### 5.3 Future (Could Have — v2.x)

| Feature | Source Inspiration |
|---------|-------------------|
| Graph-based orchestration | LangGraph |
| Distributed agent runtime | AutoGen |
| Agent teams/group chat | AutoGen |
| Built-in memory stores | Semantic Kernel |

---

## 6. Technical Decisions

### 6.1 Why Pydantic AI as Foundation (Not From Scratch)

| Consideration | Build from Scratch | Build on Pydantic AI |
|--------------|-------------------|---------------------|
| Model protocol | Must design + implement | Already done (7+ providers) |
| Type safety | Must design generics system | `Agent[DepsT, OutputT]` ready |
| Tool system | Must build schema gen + DI | Decorators + RunContext ready |
| Streaming | Must build event system | Event stream handler ready |
| Output validation | Must integrate Pydantic | Native Pydantic validation |
| Testing | Must build test model | TestModel included |
| Time to v1.0 | 6-12 months | 2-4 months |
| Maintenance | Full ownership | Community maintains core |

**Decision**: Build on Pydantic AI. The SDK adds an orchestration layer; Pydantic AI handles the agent-model interface.

### 6.2 Package Structure

```
agent-sdk/                     # Monorepo
├── agent_sdk/                 # Core package (pip install agent-sdk)
│   ├── __init__.py
│   ├── agent.py               # Extended Agent with hooks, guardrails, skills
│   ├── hooks.py               # Hook system
│   ├── guardrails.py          # Guardrail system
│   ├── skills.py              # Skill/Plugin system
│   ├── handoffs.py            # Multi-agent handoffs
│   ├── permissions.py         # Permission policies
│   ├── runner.py              # Agent runner with lifecycle management
│   ├── types.py               # Shared types and protocols
│   └── testing.py             # Test utilities
├── tests/
├── examples/
├── docs/
└── pyproject.toml
```

### 6.3 Dependencies

**Required** (minimal):
- `pydantic-ai` — core agent framework
- `pydantic` — already a pydantic-ai dependency
- `typing-extensions` — for advanced type features

**Optional** (extras):
- `opentelemetry-api` — for observability (`pip install agent-sdk[telemetry]`)
- Provider packages via pydantic-ai extras

**Explicitly Avoided**:
- LangChain ecosystem (too heavy)
- LiteLLM (Pydantic AI already handles model abstraction)
- Any database drivers in core (checkpointing is optional)

---

## 7. Conclusion

The proposed SDK occupies a unique position in the landscape:

- **Lighter than**: LangGraph, AutoGen, Semantic Kernel, CrewAI
- **More featured than**: Raw Pydantic AI, OpenAI Agents SDK
- **More portable than**: Claude Agent SDK (model-agnostic)
- **More type-safe than**: All except Pydantic AI (which it extends)

It achieves this by being a **thin orchestration layer** on top of Pydantic AI, adding exactly the features that production agent systems need (hooks, guardrails, skills, handoffs, permissions) without the weight of a full framework.
