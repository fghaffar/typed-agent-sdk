"""Transport abstraction for agent_sdk.

Enables custom agent communication backends (in-process, HTTP, WebSocket).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Transport(Protocol):
    """Protocol for agent execution transports.

    Enables running agents remotely or in different execution contexts.
    """

    async def run(self, agent: Any, prompt: str, **kwargs: Any) -> Any: ...


class InProcessTransport:
    """Default transport that runs agents in the same process.

    Simply delegates to agent.run() — this is the passthrough case.
    """

    async def run(self, agent: Any, prompt: str, **kwargs: Any) -> Any:
        """Run the agent in-process."""
        return await agent.run(prompt, **kwargs)
