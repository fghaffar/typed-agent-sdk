"""Simple agent with hooks — the MVP example."""

from pydantic_ai import Agent

from typed_agent_sdk import Hook, HookEvent, HookResult, Runner
from typed_agent_sdk.types import PreToolUseData

# Use any model — OpenAI, Anthropic, Google, Groq, etc.
agent = Agent('test', system_prompt='You are a helpful assistant.')


@agent.tool_plain
def calculate(expression: str) -> str:
    """Parse a Python literal expression with ast.literal_eval (safe)."""
    import ast

    try:
        return str(ast.literal_eval(expression))
    except (ValueError, SyntaxError) as exc:
        return f'Cannot parse {expression!r}: {exc}'


# Hook to log all tool calls
async def log_tools(event_data: PreToolUseData, ctx: object) -> HookResult:
    print(f'[Hook] Tool called: {event_data.tool_name}({event_data.tool_args})')
    return HookResult()


hook = Hook(event=HookEvent.PreToolUse, callback=log_tools)
runner = Runner(agent, hooks=[hook])

if __name__ == '__main__':
    result = runner.run_sync('What is 6 times 7?')
    print(f'Output: {result.output}')
    print(f'Hooks fired: {result.sdk_metrics.hook_invocations}')
