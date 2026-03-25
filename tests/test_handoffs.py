"""Tests for agent_sdk handoff system."""

from __future__ import annotations

from typing import Any

import pytest

from agent_sdk.errors import HandoffDepthError, HandoffExecutionError
from agent_sdk.handoffs import Handoff, create_handoff_tool_func


class TestHandoff:
    def test_handoff_creation(self) -> None:
        from pydantic_ai import Agent

        target = Agent('test', name='specialist')
        h = Handoff(target=target, description='Delegate coding tasks')
        assert h.description == 'Delegate coding tasks'
        assert h.max_depth == 10

    def test_handoff_custom_depth(self) -> None:
        from pydantic_ai import Agent

        target = Agent('test', name='specialist')
        h = Handoff(target=target, description='test', max_depth=5)
        assert h.max_depth == 5


class TestHandoffToolFunc:
    @pytest.mark.asyncio
    async def test_depth_exceeded_raises(self) -> None:
        from pydantic_ai import Agent

        target = Agent('test', name='deep')
        h = Handoff(target=target, description='test', max_depth=3)
        func = create_handoff_tool_func(h, current_depth=3)

        with pytest.raises(HandoffDepthError, match='exceeds maximum 3'):
            await func('do something')

    def test_tool_func_has_correct_name(self) -> None:
        from pydantic_ai import Agent

        target = Agent('test', name='reviewer')
        h = Handoff(target=target, description='Review code')
        func = create_handoff_tool_func(h)
        assert func.__name__ == 'delegate_to_reviewer'

    def test_tool_func_has_description(self) -> None:
        from pydantic_ai import Agent

        target = Agent('test', name='coder')
        h = Handoff(target=target, description='Write Python code')
        func = create_handoff_tool_func(h)
        assert func.__doc__ == 'Write Python code'
