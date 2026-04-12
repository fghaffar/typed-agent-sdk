# Quickstart: Agent SDK

## Installation

```bash
pip install agent-sdk
```

## 1. Simple Agent with Hooks (5 minutes)

```python
from pydantic_ai import Agent
from typed_agent_sdk import Runner, Hook, HookEvent, on_pre_tool_use

# Use any model — OpenAI, Anthropic, Google, Groq, etc.
agent = Agent('openai:gpt-4o', system_prompt='You are a helpful assistant.')

@agent.tool_plain
def calculate(expression: str) -> str:
    """Evaluate a math expression safely."""
    import ast
    return str(ast.literal_eval(expression))

# Add a hook to log tool calls
@on_pre_tool_use()
async def log_tools(event_data, ctx):
    print(f"Tool called: {event_data.tool_name}({event_data.tool_args})")
    return {}  # Allow the tool call

runner = Runner(agent, hooks=[log_tools])
result = runner.run_sync("What is 42 * 17?")
print(result.output)
```

## 2. Adding Guardrails (3 minutes)

```python
from typed_agent_sdk import Runner, input_guardrail, GuardrailResult

@input_guardrail("content-filter")
async def block_harmful(data, ctx):
    prohibited = ["harmful_phrase"]
    if any(p in data.lower() for p in prohibited):
        return GuardrailResult(passed=False, tripwire=True, reason="Prohibited content")
    return GuardrailResult(passed=True)

runner = Runner(agent, guardrails=[block_harmful])
```

## 3. Composing Skills (5 minutes)

```python
from typed_agent_sdk import Skill, SystemTools

# Built-in system tools
sys_tools = SystemTools(allowed=["file_read", "grep", "glob"])

# Custom skill with tools + instructions
research_skill = Skill(
    name="researcher",
    instructions="When researching, always cite sources.",
    tools=[my_search_tool, my_summarize_tool],
)

runner = Runner(agent, skills=[sys_tools, research_skill])
```

## 4. Markdown Skills (no Python needed)

Create `skills/code-reviewer.md`:

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: [file_read, grep]
---

You are an expert code reviewer. When asked to review code:
1. Read the files using file_read
2. Search for common issues with grep
3. Provide actionable feedback with line numbers

Focus on: security, performance, readability.
Arguments: $ARGUMENTS
```

Load it:

```python
from typed_agent_sdk import load_skills, Runner

skills = load_skills("./skills")
runner = Runner(agent, skills=skills)
```

## 5. Multi-Agent Handoffs (5 minutes)

```python
from pydantic_ai import Agent
from typed_agent_sdk import Runner, Handoff

coder = Agent('anthropic:claude-sonnet-4-20250514', system_prompt='You write Python code.')
reviewer = Agent('openai:gpt-4o', system_prompt='You review code for bugs.')

triage = Agent('openai:gpt-4o-mini', system_prompt='Route tasks to specialists.')

runner = Runner(
    triage,
    handoffs=[
        Handoff(coder, description="Delegate coding tasks to the Python specialist"),
        Handoff(reviewer, description="Delegate code review to the reviewer"),
    ],
)

result = runner.run_sync("Write a function to check if a number is prime, then review it.")
```

## 6. Permission Policies (2 minutes)

```python
from typed_agent_sdk import PermissionPolicy, PermissionMode

policy = PermissionPolicy(
    mode=PermissionMode.default,
    allowed_tools=["file_read", "grep", "glob", "calculate"],
    blocked_tools=["file_write", "bash"],
    require_approval=["web_*"],
)

runner = Runner(agent, permissions=policy, skills=[SystemTools()])
```

## Switching Models

The same agent code works with any provider:

```python
# OpenAI
runner.run_sync("Hello", model='openai:gpt-4o')

# Anthropic
runner.run_sync("Hello", model='anthropic:claude-sonnet-4-20250514')

# Google
runner.run_sync("Hello", model='google:gemini-2.5-flash')

# Groq
runner.run_sync("Hello", model='groq:llama-3.3-70b-versatile')

# Local via Ollama
runner.run_sync("Hello", model='ollama:llama3.2')
```

## Testing Without API Calls

```python
from pydantic_ai.models.test import TestModel
from typed_agent_sdk import Runner, HookRecorder

recorder = HookRecorder()
runner = Runner(
    Agent(TestModel(), system_prompt='Test agent'),
    hooks=[recorder.get_hook()],
)

result = runner.run_sync("test prompt")
recorder.assert_called(HookEvent.OnStart)
recorder.assert_called(HookEvent.OnStop)
```
