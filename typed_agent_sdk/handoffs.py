"""Multi-agent handoff system for typed_agent_sdk.

Handoffs enable agents to delegate tasks to specialist agents.
Each handoff appears as a tool call to the LLM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from typed_agent_sdk.errors import HandoffDepthError, HandoffExecutionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.usage import RunUsage

logger = logging.getLogger('typed_agent_sdk.handoffs')

DepsT = TypeVar('DepsT')

HANDOFF_DEPTH_KEY = '_typed_agent_sdk_handoff_depth'


@dataclass
class HandoffResult:
    """Result from a handoff to a target agent."""

    output: Any
    agent_name: str
    depth: int
    usage: RunUsage


@dataclass
class Handoff(Generic[DepsT]):
    """A delegation target that appears as a tool to the LLM.

    Args:
        target: The Pydantic AI agent to delegate to.
        description: Description shown to the LLM for delegation decision.
        filter: Optional function — if returns False, handoff not offered.
        context_transformer: Optional function to transform messages before target.
        max_depth: Maximum handoff chain depth (prevents infinite loops).
    """

    target: Agent[Any, Any]
    description: str
    filter: Callable[..., bool] | None = None
    context_transformer: Callable[[list[ModelMessage]], list[ModelMessage]] | None = None
    max_depth: int = 10


def create_handoff_tool_func(
    handoff: Handoff[Any],
    current_depth: int = 0,
) -> Callable[..., Any]:
    """Create an async tool function that executes a handoff.

    The returned function, when called by the LLM via tool call,
    runs the target agent and returns its output.
    """

    async def handoff_tool(task: str) -> str:
        """Delegate a task to a specialist agent."""
        depth = current_depth + 1

        if depth > handoff.max_depth:
            raise HandoffDepthError(depth, handoff.max_depth)

        try:
            # Optionally transform context
            message_history = None
            if handoff.context_transformer:
                message_history = handoff.context_transformer([])

            result = await handoff.target.run(
                task,
                message_history=message_history,
            )

            return str(result.output)

        except HandoffDepthError:
            raise
        except Exception as e:
            target_name = handoff.target.name or 'unnamed_agent'
            raise HandoffExecutionError(target_name, e) from e

    # Set metadata for the tool
    handoff_tool.__name__ = f'delegate_to_{handoff.target.name or "agent"}'
    handoff_tool.__doc__ = handoff.description

    return handoff_tool
