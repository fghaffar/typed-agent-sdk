"""Integration tests: SystemTools(backend=...) wired through a real Agent + Runner.

Proves the bash tool actually routes through a custom ExecutionBackend
when invoked by the agent loop (not just when called directly).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent

from tests.conftest import make_tool_call_model
from typed_agent_sdk import (
    ExecResult,
    Hook,
    HookEvent,
    HookResult,
    Runner,
    SystemTools,
)

if TYPE_CHECKING:
    from typed_agent_sdk.types import PreToolUseData


class _Backend:
    """Captures every call; returns deterministic output."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def exec(
        self,
        command: str,
        *,
        timeout: float = 120.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        self.calls.append(command)
        return ExecResult(stdout='ok-from-backend', stderr='', exit_code=0)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_runner_routes_bash_through_custom_backend() -> None:
    backend = _Backend()
    tools = SystemTools(allowed=['bash'], backend=backend)

    model = make_tool_call_model(tool_name='bash', tool_args={'command': 'whoami'})
    agent: Agent[Any, Any] = Agent(model, tools=tools.tools)

    runner: Runner[Any, Any] = Runner(agent)
    result = await runner.run('run whoami')

    assert backend.calls == ['whoami']
    assert 'Done' in str(result.output)


@pytest.mark.asyncio
async def test_hooks_observe_backend_routed_tool() -> None:
    backend = _Backend()
    tools = SystemTools(allowed=['bash'], backend=backend)

    seen: list[str] = []

    async def record(data: PreToolUseData, ctx: Any) -> HookResult:
        seen.append(data.tool_name)
        return HookResult()

    model = make_tool_call_model(tool_name='bash', tool_args={'command': 'date'})
    agent: Agent[Any, Any] = Agent(model, tools=tools.tools)

    runner: Runner[Any, Any] = Runner(
        agent,
        hooks=[Hook(event=HookEvent.PreToolUse, callback=record)],
    )
    await runner.run('what time is it')

    assert seen == ['bash']
    assert backend.calls == ['date']
