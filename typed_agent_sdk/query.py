"""One-shot query function and streaming client for typed-agent-sdk.

Provides a simple developer experience:
  - query() for one-liner async iteration
  - AgentSDKClient for stateful multi-turn conversations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from typed_agent_sdk.errors import AgentSDKError
from typed_agent_sdk.permissions import PermissionPolicy
from typed_agent_sdk.runner import Runner, RunResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.messages import ModelMessage

    from typed_agent_sdk.guardrails import Guardrail
    from typed_agent_sdk.hooks import Hook
    from typed_agent_sdk.types import SDKMetrics

logger = logging.getLogger('typed_agent_sdk.query')


# ---------------------------------------------------------------------------
# Message types yielded during streaming
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextMessage:
    """A text message from the agent."""

    text: str
    role: str = 'assistant'


@dataclass(frozen=True)
class ToolCallMessage:
    """A tool call made by the agent."""

    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ToolResultMessage:
    """Result of a tool call."""

    tool_name: str
    result: Any
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ResultMessage:
    """Final result of the agent run."""

    output: Any
    usage: Any = None
    sdk_metrics: SDKMetrics | None = None
    is_error: bool = False
    total_cost_usd: float | None = None
    session_id: str | None = None


Message = TextMessage | ToolCallMessage | ToolResultMessage | ResultMessage


# ---------------------------------------------------------------------------
# Options dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentOptions:
    """Configuration for query() and AgentSDKClient.

    Works with any LLM provider supported by Pydantic AI.
    """

    model: str = 'test'
    system_prompt: str | None = None
    hooks: list[Hook] | None = None
    guardrails: list[Guardrail[Any]] | None = None
    permissions: PermissionPolicy | None = None
    allowed_tools: list[str] | None = None
    blocked_tools: list[str] | None = None
    max_turns: int | None = None
    max_budget_tokens: int | None = None
    tools: list[Any] | None = None


# ---------------------------------------------------------------------------
# query() — one-shot async iterator
# ---------------------------------------------------------------------------


async def query(
    *,
    prompt: str,
    options: AgentOptions | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    hooks: list[Hook] | None = None,
    guardrails: list[Guardrail[Any]] | None = None,
    tools: list[Any] | None = None,
) -> AsyncIterator[Message]:
    """One-shot query that yields messages as they're produced.

    This is the simplest way to use typed-agent-sdk.

    Usage:
        async for message in query(prompt="What is 2+2?", model="openai:gpt-4o"):
            if isinstance(message, TextMessage):
                print(message.text)
            elif isinstance(message, ResultMessage):
                print(f"Done. Cost: {message.total_cost_usd}")

    Args:
        prompt: The user prompt.
        options: Full AgentOptions configuration.
        model: Model name shortcut (overrides options.model).
        system_prompt: System prompt shortcut (overrides options.system_prompt).
        hooks: Hooks shortcut (overrides options.hooks).
        guardrails: Guardrails shortcut (overrides options.guardrails).
        tools: Tool functions to register on the agent.

    Yields:
        Message objects: TextMessage, ToolCallMessage, ToolResultMessage, ResultMessage.
    """
    opts = options or AgentOptions()

    effective_model = model or opts.model
    effective_system = system_prompt or opts.system_prompt
    effective_hooks = hooks or opts.hooks or []
    effective_guardrails = guardrails or opts.guardrails or []
    effective_tools = tools or opts.tools or []

    # Build permissions from options
    permissions = opts.permissions
    if not permissions and (opts.allowed_tools or opts.blocked_tools):
        permissions = PermissionPolicy(
            allowed_tools=opts.allowed_tools or [],
            blocked_tools=opts.blocked_tools or [],
        )

    # Create agent
    agent = Agent(
        effective_model,
        system_prompt=effective_system or '',
    )

    # Register tools on the agent
    for tool_func in effective_tools:
        agent.tool_plain(tool_func)

    # Create runner
    runner = Runner(
        agent,
        hooks=effective_hooks,
        guardrails=effective_guardrails,
        max_turns=opts.max_turns,
        max_budget_tokens=opts.max_budget_tokens,
    )

    # Wrap hooks to capture tool calls/results for streaming

    if effective_hooks:
        # The existing hooks handle this — tool events get captured via HookToolset
        pass

    # Run and yield messages
    try:
        result = await runner.run(prompt)

        # Yield text messages from the conversation
        for msg in result.messages:
            # Extract text and tool call parts from Pydantic AI messages
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    part_type = type(part).__name__
                    if part_type == 'TextPart':
                        yield TextMessage(text=part.content)
                    elif part_type == 'ToolCallPart':
                        yield ToolCallMessage(
                            tool_name=part.tool_name,
                            tool_args=part.args if isinstance(part.args, dict) else {},
                            tool_call_id=getattr(part, 'tool_call_id', None),
                        )
                    elif part_type == 'ToolReturnPart':
                        yield ToolResultMessage(
                            tool_name=part.tool_name,
                            result=part.content,
                            tool_call_id=getattr(part, 'tool_call_id', None),
                        )

        # Yield final result
        yield ResultMessage(
            output=result.output,
            usage=result.usage,
            sdk_metrics=result.sdk_metrics,
            session_id=result.session_id,
        )

    except Exception as e:
        yield ResultMessage(
            output=str(e),
            is_error=True,
        )


# ---------------------------------------------------------------------------
# query_sync() — synchronous one-liner
# ---------------------------------------------------------------------------


def query_sync(
    *,
    prompt: str,
    options: AgentOptions | None = None,
    **kwargs: Any,
) -> RunResult[Any]:
    """Synchronous one-shot query returning a complete RunResult.

    Usage:
        result = query_sync(prompt="What is 2+2?", model="openai:gpt-4o")
        print(result.output)
    """
    opts = options or AgentOptions()
    effective_model = kwargs.get('model') or opts.model
    effective_system = kwargs.get('system_prompt') or opts.system_prompt
    effective_hooks = kwargs.get('hooks') or opts.hooks or []
    effective_guardrails = kwargs.get('guardrails') or opts.guardrails or []
    effective_tools = kwargs.get('tools') or opts.tools or []

    agent = Agent(effective_model, system_prompt=effective_system or '')
    for tool_func in effective_tools:
        agent.tool_plain(tool_func)

    runner = Runner(
        agent,
        hooks=effective_hooks,
        guardrails=effective_guardrails,
        max_turns=opts.max_turns,
    )

    return runner.run_sync(prompt)


# ---------------------------------------------------------------------------
# AgentSDKClient — stateful multi-turn
# ---------------------------------------------------------------------------


class AgentSDKClient:
    """Stateful, multi-turn agent client.

    Works with any LLM provider supported by Pydantic AI.

    Usage:
        async with AgentSDKClient(options=options) as client:
            await client.send("What is Python?")
            async for msg in client.receive():
                print(msg)

            await client.send("Tell me more")
            async for msg in client.receive():
                print(msg)
    """

    def __init__(
        self,
        options: AgentOptions | None = None,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        hooks: list[Hook] | None = None,
        guardrails: list[Guardrail[Any]] | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        self._opts = options or AgentOptions()
        self._model = model or self._opts.model
        self._system = system_prompt or self._opts.system_prompt
        self._hooks = hooks or self._opts.hooks or []
        self._guardrails = guardrails or self._opts.guardrails or []
        self._tools = tools or self._opts.tools or []
        self._message_history: list[ModelMessage] = []
        self._agent: Agent[Any, Any] | None = None
        self._runner: Runner[Any, Any] | None = None
        self._last_result: RunResult[Any] | None = None

    async def __aenter__(self) -> AgentSDKClient:
        """Set up the agent and runner."""
        self._agent = Agent(self._model, system_prompt=self._system or '')
        for tool_func in self._tools:
            self._agent.tool_plain(tool_func)

        self._runner = Runner(
            self._agent,
            hooks=self._hooks,
            guardrails=self._guardrails,
            max_turns=self._opts.max_turns,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Clean up."""
        self._agent = None
        self._runner = None

    async def send(self, prompt: str) -> None:
        """Send a message and store the result.

        After calling send(), iterate with receive() to get messages.
        """
        if not self._runner:
            raise AgentSDKError(
                'Client not connected. Use `async with AgentSDKClient() as client:`'
            )

        self._last_result = await self._runner.run(
            prompt,
            message_history=self._message_history if self._message_history else None,
        )
        # Update history for next turn
        self._message_history = self._last_result.messages

    async def receive(self) -> AsyncIterator[Message]:
        """Yield messages from the last send() call."""
        if not self._last_result:
            return

        for msg in self._last_result.messages:
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    part_type = type(part).__name__
                    if part_type == 'TextPart':
                        yield TextMessage(text=part.content)
                    elif part_type == 'ToolCallPart':
                        yield ToolCallMessage(
                            tool_name=part.tool_name,
                            tool_args=part.args if isinstance(part.args, dict) else {},
                            tool_call_id=getattr(part, 'tool_call_id', None),
                        )
                    elif part_type == 'ToolReturnPart':
                        yield ToolResultMessage(
                            tool_name=part.tool_name,
                            result=part.content,
                            tool_call_id=getattr(part, 'tool_call_id', None),
                        )

        yield ResultMessage(
            output=self._last_result.output,
            usage=self._last_result.usage,
            sdk_metrics=self._last_result.sdk_metrics,
        )

    @property
    def message_history(self) -> list[ModelMessage]:
        """Get the current conversation history."""
        return self._message_history.copy()

    @property
    def last_result(self) -> RunResult[Any] | None:
        """Get the last run result."""
        return self._last_result
