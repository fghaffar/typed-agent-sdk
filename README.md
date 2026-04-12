# typed-agent-sdk

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/typed-agent-sdk.svg)](https://pypi.org/project/typed-agent-sdk/)
[![CI](https://github.com/fghaffar/typed-agent-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/fghaffar/typed-agent-sdk/actions)

A lightweight, model-agnostic, type-safe agent SDK built on [Pydantic AI](https://ai.pydantic.dev).

**Use any LLM provider** (OpenAI, Anthropic, Google, Groq, Ollama, etc.) with production-grade hooks, guardrails, skills, handoffs, and permissions.

## Features

- **Model-agnostic** -- works with any LLM provider supported by Pydantic AI
- **Type-safe** -- full generic typing (`DepsT`, `OutputT`), strict mypy, py.typed
- **Hooks** -- lifecycle hooks for tool use, model calls, handoffs, errors, and more
- **Guardrails** -- input/output validation with parallel execution and tripwire support
- **Skills** -- composable bundles of tools + instructions + hooks + guardrails
- **Handoffs** -- multi-agent delegation with depth limiting
- **Permissions** -- glob-pattern access control with allow/block lists
- **Sessions** -- persistent conversation state with pluggable backends
- **Async-first** -- native async design with sync wrappers

## Installation

```bash
pip install typed-agent-sdk
```

## Quick Start

```python
from pydantic_ai import Agent
from typed_agent_sdk import Hook, HookEvent, HookResult, Runner
from typed_agent_sdk.types import PreToolUseData

# Use any model -- OpenAI, Anthropic, Google, Groq, etc.
agent = Agent('openai:gpt-4o', system_prompt='You are a helpful assistant.')

@agent.tool_plain
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"The weather in {city} is sunny, 22C."

# Hook to log all tool calls
async def log_tools(event_data: PreToolUseData, ctx: object) -> HookResult:
    print(f'Tool called: {event_data.tool_name}({event_data.tool_args})')
    return HookResult()

hook = Hook(event=HookEvent.PreToolUse, callback=log_tools)
runner = Runner(agent, hooks=[hook])

result = runner.run_sync("What's the weather in London?")
print(result.output)
```

## Guardrails

Block unsafe inputs before they reach the model:

```python
from typed_agent_sdk import Runner, GuardrailResult, input_guardrail

@input_guardrail('content-filter')
async def block_harmful(data: str, ctx: object) -> GuardrailResult:
    prohibited = ['harmful_content']
    if any(p in data.lower() for p in prohibited):
        return GuardrailResult(passed=False, tripwire=True, reason='Prohibited content')
    return GuardrailResult(passed=True)

runner = Runner(agent, guardrails=[block_harmful])
```

## One-Shot Query

For simple use cases, skip the Runner and use `query()` directly:

```python
from typed_agent_sdk import query, TextMessage, ResultMessage

async for message in query(prompt="What is 2+2?", model="openai:gpt-4o"):
    if isinstance(message, TextMessage):
        print(message.text)
    elif isinstance(message, ResultMessage):
        print(f"Done. Cost: {message.total_cost_usd}")
```

## Multi-Turn Conversations

```python
from typed_agent_sdk import AgentSDKClient, AgentOptions

async with AgentSDKClient(model="openai:gpt-4o") as client:
    await client.send("What is Python?")
    async for msg in client.receive():
        print(msg)

    await client.send("Tell me more about its type system")
    async for msg in client.receive():
        print(msg)
```

## Architecture

typed-agent-sdk is a thin orchestration layer on top of Pydantic AI:

```
Your Code
    |
typed-agent-sdk  (hooks, guardrails, skills, handoffs, permissions)
    |
Pydantic AI      (agent, tools, structured output)
    |
Any LLM Provider (OpenAI, Anthropic, Google, Groq, Ollama, ...)
```

## API Overview

| Module | Key Exports | Purpose |
|--------|-------------|---------|
| `typed_agent_sdk` | `Runner`, `RunResult` | Core agent orchestration |
| | `query`, `query_sync`, `AgentSDKClient` | One-shot and multi-turn APIs |
| | `Hook`, `HookEvent`, `HookMatcher` | Lifecycle hooks |
| | `Guardrail`, `input_guardrail`, `output_guardrail` | Input/output validation |
| | `Skill`, `load_skills` | Composable skill bundles |
| | `Handoff`, `HandoffResult` | Multi-agent delegation |
| | `PermissionPolicy`, `PermissionMode` | Access control |
| | `Session`, `JSONSessionBackend` | Conversation persistence |
| | `SystemTools` | Built-in tools (bash, file ops, glob, grep) |
| | `HookRecorder`, `GuardrailRecorder` | Test utilities |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint and format
ruff check . && ruff format .

# Type check
mypy --strict typed_agent_sdk/
```

## Acknowledgments

Built on [Pydantic AI](https://ai.pydantic.dev) by the [Pydantic](https://pydantic.dev) team. Thanks to Samuel Colvin and contributors for providing an excellent foundation for model-agnostic agent development.

## License

[MIT](LICENSE)
