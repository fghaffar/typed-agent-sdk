"""Research Agent — typed-agent-sdk version.

A multi-agent research system that:
1. Lead agent breaks topics into subtopics
2. Researcher agents gather data (with web search)
3. Data analyst generates charts
4. Report writer creates PDF

Works with ANY model: OpenAI, Anthropic, Google, Groq, Mistral, Ollama.

Usage:
    # With OpenAI
    python our_sdk_version.py --model openai:gpt-4o

    # With Anthropic
    python our_sdk_version.py --model anthropic:claude-sonnet-4-20250514

    # With Google
    python our_sdk_version.py --model google:gemini-2.5-flash

    # With local Ollama
    python our_sdk_version.py --model ollama:llama3.2
"""

import asyncio
import sys
from pathlib import Path

from pydantic_ai import Agent

from typed_agent_sdk import (
    AgentOptions,
    AgentSDKClient,
    GuardrailResult,
    Handoff,
    Hook,
    HookEvent,
    HookResult,
    ResultMessage,
    Runner,
    SystemTools,
    TextMessage,
    ToolCallMessage,
    input_guardrail,
)
from typed_agent_sdk.types import PostToolUseData, PreToolUseData

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = 'anthropic:claude-haiku-4-5-20251001'
PROMPTS_DIR = Path(__file__).parent / 'prompts'


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text().strip()


# ---------------------------------------------------------------------------
# Define specialist agents (model-agnostic!)
# ---------------------------------------------------------------------------


def create_agents(model: str):
    """Create all specialist agents. Works with ANY model."""

    researcher = Agent(
        model,
        system_prompt=load_prompt('researcher.txt'),
        name='researcher',
    )

    # Give researcher web search + file write
    @researcher.tool_plain
    async def web_search(query_text: str) -> str:
        """Search the web for information."""
        # In production, integrate with a real search API
        # For demo, return a placeholder
        return f'[Search results for: {query_text}] — Replace with real search API integration'

    @researcher.tool_plain
    async def save_notes(filename: str, content: str) -> str:
        """Save research notes to files/research_notes/."""
        path = Path('files/research_notes') / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f'Saved to {path}'

    data_analyst = Agent(
        model,
        system_prompt=load_prompt('data_analyst.txt'),
        name='data_analyst',
    )

    # Give data analyst file access + bash for charts
    sys_tools_analyst = SystemTools(
        allowed=['file_read', 'glob', 'bash'],
        bash_timeout=60.0,
    )
    # Register tools manually since SystemTools is a Skill
    for tool_func in sys_tools_analyst._build_tool_map().values():
        data_analyst.tool_plain(tool_func)

    @data_analyst.tool_plain
    async def save_data(filename: str, content: str) -> str:
        """Save data summary to files/data/."""
        path = Path('files/data') / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f'Saved to {path}'

    report_writer = Agent(
        model,
        system_prompt=load_prompt('report_writer.txt'),
        name='report_writer',
    )

    # Give report writer file access + bash for PDF generation
    for tool_func in (
        SystemTools(
            allowed=['file_read', 'glob', 'bash'],
            bash_timeout=120.0,
        )
        ._build_tool_map()
        .values()
    ):
        report_writer.tool_plain(tool_func)

    @report_writer.tool_plain
    async def save_report(filename: str, content: str) -> str:
        """Save report file."""
        path = Path('files/reports') / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f'Saved to {path}'

    # Lead agent — only delegates, never researches
    lead = Agent(
        model,
        system_prompt=load_prompt('lead_agent.txt'),
        name='lead_coordinator',
    )

    return lead, researcher, data_analyst, report_writer


# ---------------------------------------------------------------------------
# Hooks — track everything
# ---------------------------------------------------------------------------

tool_log: list[str] = []


async def track_pre_tool(data: PreToolUseData, ctx: object) -> HookResult:
    """Log every tool call across all agents."""
    tool_log.append(f'→ {data.tool_name}({list(data.tool_args.keys())})')
    print(f'  [TOOL] → {data.tool_name}', flush=True)
    return HookResult()


async def track_post_tool(data: PostToolUseData, ctx: object) -> HookResult:
    """Log tool completion."""
    result_preview = str(data.tool_result)[:80]
    print(f'  [DONE] ← {data.tool_name}: {result_preview}', flush=True)
    return HookResult()


# ---------------------------------------------------------------------------
# Guardrail — block harmful research topics
# ---------------------------------------------------------------------------


@input_guardrail('content-safety')
async def safety_check(data: str, ctx: object) -> GuardrailResult:
    """Block harmful research requests."""
    blocked = ['illegal', 'weapons', 'exploit']
    if any(word in data.lower() for word in blocked):
        return GuardrailResult(
            passed=False,
            tripwire=True,
            reason='Research topic blocked by safety policy',
        )
    return GuardrailResult(passed=True)


# ---------------------------------------------------------------------------
# Main — using query() for Claude SDK-style DX
# ---------------------------------------------------------------------------


async def main_query_style(model: str):
    """Run using query() — matches Claude SDK's one-liner DX."""
    lead, researcher, data_analyst, report_writer = create_agents(model)

    # Create handoffs for the lead agent
    [
        Handoff(researcher, description='Delegate research on a specific subtopic'),
        Handoff(data_analyst, description='Generate charts and data analysis from research notes'),
        Handoff(report_writer, description='Create a PDF report from research and charts'),
    ]

    hooks = [
        Hook(event=HookEvent.PreToolUse, callback=track_pre_tool),
        Hook(event=HookEvent.PostToolUse, callback=track_post_tool),
    ]

    print('\n' + '=' * 50)
    print('  Research Agent (typed-agent-sdk)')
    print(f'  Model: {model}')
    print('=' * 50)
    print("\nResearch any topic. Type 'exit' to quit.\n")

    while True:
        try:
            topic = input('You: ').strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not topic or topic.lower() in ('exit', 'quit', 'q'):
            break

        print(f'\nResearching: {topic}')
        print('-' * 40)

        runner = Runner(
            lead,
            hooks=hooks,
            guardrails=[safety_check],
        )

        try:
            result = await runner.run(topic)
            print(f'\nAgent: {result.output}')
            print(f'\n[Metrics] Hooks fired: {result.sdk_metrics.hook_invocations}')
            print(f'[Metrics] Guardrail checks: {result.sdk_metrics.guardrail_checks}')
        except Exception as e:
            print(f'\nError: {e}')

        print()


# ---------------------------------------------------------------------------
# Main — using AgentSDKClient for multi-turn conversations
# ---------------------------------------------------------------------------


async def main_client_style(model: str):
    """Run using AgentSDKClient for stateful multi-turn conversations."""
    _lead, _researcher, _data_analyst, _report_writer = create_agents(model)

    hooks = [
        Hook(event=HookEvent.PreToolUse, callback=track_pre_tool),
        Hook(event=HookEvent.PostToolUse, callback=track_post_tool),
    ]

    options = AgentOptions(
        model=model,
        system_prompt=load_prompt('lead_agent.txt'),
        hooks=hooks,
        guardrails=[safety_check],
    )

    print('\n' + '=' * 50)
    print('  Research Agent (agent-sdk — Client mode)')
    print(f'  Model: {model}')
    print('=' * 50)

    async with AgentSDKClient(options=options) as client:
        while True:
            try:
                topic = input('\nYou: ').strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not topic or topic.lower() in ('exit', 'quit'):
                break

            await client.send(topic)

            async for msg in client.receive():
                if isinstance(msg, TextMessage):
                    print(f'Agent: {msg.text}')
                elif isinstance(msg, ToolCallMessage):
                    print(f'  [Calling {msg.tool_name}]')
                elif isinstance(msg, ResultMessage):
                    print(f'  [Done — {msg.sdk_metrics}]')

    print('\nGoodbye!')


if __name__ == '__main__':
    model = DEFAULT_MODEL
    if '--model' in sys.argv:
        idx = sys.argv.index('--model')
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]

    mode = 'runner'  # default
    if '--client' in sys.argv:
        mode = 'client'

    if mode == 'client':
        asyncio.run(main_client_style(model))
    else:
        asyncio.run(main_query_style(model))
