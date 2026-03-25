"""Agent Runner with lifecycle management.

Orchestrates hooks, guardrails, permissions, skills, handoffs,
and session management around a Pydantic AI Agent.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import RunUsage

from agent_sdk.errors import AgentSDKError
from agent_sdk.guardrails import Guardrail, run_guardrails
from agent_sdk.hooks import Hook, HookToolset, _fire_hooks
from agent_sdk.types import HookEvent, OnErrorData, OnStartData, OnStopData, SDKMetrics

logger = logging.getLogger('agent_sdk.runner')

OutputT = TypeVar('OutputT')
DepsT = TypeVar('DepsT')


@dataclass
class RunResult(Generic[OutputT]):
    """Result of a Runner.run() call, extending Pydantic AI's result."""

    output: OutputT
    messages: list[ModelMessage]
    usage: RunUsage
    sdk_metrics: SDKMetrics
    session_id: str | None = None
    stop_reason: str | None = None


class Runner(Generic[DepsT, OutputT]):
    """Orchestrates the full agent lifecycle.

    Wraps a Pydantic AI Agent with hooks, guardrails, permissions,
    skills, handoffs, and session management.
    """

    def __init__(
        self,
        agent: Agent[Any, Any],
        *,
        hooks: list[Hook] | None = None,
        guardrails: list[Guardrail[Any]] | None = None,
        max_turns: int | None = None,
        max_budget_tokens: int | None = None,
        debug_callback: Any | None = None,
    ) -> None:
        self._agent = agent
        self._hooks = hooks or []
        self._guardrails = guardrails or []
        self._max_turns = max_turns
        self._max_budget_tokens = max_budget_tokens
        self._debug_callback = debug_callback
        self._running = False
        self._interrupt_event: asyncio.Event | None = None

    async def run(
        self,
        prompt: str | Sequence[Any],
        *,
        deps: Any = None,
        model: Any = None,
        model_settings: Any = None,
        message_history: list[ModelMessage] | None = None,
    ) -> RunResult[Any]:
        """Run the agent with full lifecycle management."""
        if isinstance(prompt, str) and not prompt.strip():
            raise ValueError('Prompt cannot be empty')

        if self._running:
            raise AgentSDKError('Runner is already running. Concurrent runs are not supported.')

        self._running = True
        self._interrupt_event = asyncio.Event()
        metrics = SDKMetrics()

        try:
            # 1. Fire OnStart hooks
            start_data = OnStartData(
                prompt=prompt if isinstance(prompt, str) else str(prompt),
                agent_name=self._agent.name,
            )
            await _fire_hooks(self._hooks, HookEvent.OnStart, start_data, None, metrics=metrics)
            self._debug('OnStart', {'prompt': str(prompt)[:100], 'agent': self._agent.name})

            # 2. Run INPUT guardrails (parallel, before model call)
            if self._guardrails:
                prompt_str = prompt if isinstance(prompt, str) else str(prompt)
                await run_guardrails(
                    self._guardrails, 'input', prompt_str, None, metrics=metrics
                )
                self._debug('InputGuardrails', {'count': len(self._guardrails)})

            # 3. Build run kwargs and execute agent
            run_kwargs: dict[str, Any] = {}
            if deps is not None:
                run_kwargs['deps'] = deps
            if model is not None:
                run_kwargs['model'] = model
            if model_settings is not None:
                run_kwargs['model_settings'] = model_settings
            if message_history is not None:
                run_kwargs['message_history'] = message_history

            if self._hooks:
                hook_toolset = HookToolset(
                    wrapped=self._agent._toolset,  # type: ignore[attr-defined]
                    hooks=self._hooks,
                    metrics=metrics,
                )
                run_kwargs['toolsets'] = [hook_toolset]

            pydantic_result = await self._agent.run(prompt, **run_kwargs)

            output = pydantic_result.output

            # 4. Run OUTPUT guardrails (parallel, after model response)
            if self._guardrails:
                output_str = str(output) if not isinstance(output, str) else output
                await run_guardrails(
                    self._guardrails, 'output', output_str, None, metrics=metrics
                )
                self._debug('OutputGuardrails', {'count': len(self._guardrails)})

            # 5. Build RunResult
            result: RunResult[Any] = RunResult(
                output=output,
                messages=list(pydantic_result.all_messages()),
                usage=pydantic_result.usage(),
                sdk_metrics=metrics,
            )

            # 6. Fire OnStop hooks
            stop_data = OnStopData(result=result.output, stop_reason=None)
            await _fire_hooks(self._hooks, HookEvent.OnStop, stop_data, None, metrics=metrics)
            self._debug('OnStop', {'stop_reason': result.stop_reason})

            return result

        except Exception as e:
            if not isinstance(e, AgentSDKError) or 'OnError' not in str(e):
                try:
                    error_data = OnErrorData(error=e, context='runner.run')
                    await _fire_hooks(
                        self._hooks, HookEvent.OnError, error_data, None, metrics=metrics
                    )
                except Exception:
                    logger.exception('OnError hook itself failed')
            raise

        finally:
            self._running = False
            self._interrupt_event = None

    def run_sync(
        self,
        prompt: str,
        *,
        deps: Any = None,
        **kwargs: Any,
    ) -> RunResult[Any]:
        """Synchronous wrapper around run()."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.run(prompt, deps=deps, **kwargs))
        finally:
            loop.close()

    async def interrupt(self) -> None:
        """Interrupt a running agent. No-op if not running."""
        if self._interrupt_event:
            self._interrupt_event.set()

    def _debug(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit a debug event if debug_callback is configured."""
        if self._debug_callback:
            self._debug_callback(event_type, data)
