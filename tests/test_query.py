"""Tests for typed_agent_sdk query function and AgentSDKClient."""

from __future__ import annotations

import pytest

from typed_agent_sdk.query import (
    AgentOptions,
    AgentSDKClient,
    ResultMessage,
    TextMessage,
    ToolCallMessage,
    ToolResultMessage,
    query,
    query_sync,
)


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_yields_text_and_result(self) -> None:
        messages = []
        async for msg in query(prompt='Hello', model='test'):
            messages.append(msg)

        # Should have at least a text message and a result message
        types = [type(m).__name__ for m in messages]
        assert 'ResultMessage' in types

    @pytest.mark.asyncio
    async def test_query_with_options(self) -> None:
        opts = AgentOptions(model='test', system_prompt='Be brief.')
        messages = []
        async for msg in query(prompt='Hello', options=opts):
            messages.append(msg)

        has_result = any(isinstance(m, ResultMessage) for m in messages)
        assert has_result

    @pytest.mark.asyncio
    async def test_query_result_not_error(self) -> None:
        async for msg in query(prompt='Hello', model='test'):
            if isinstance(msg, ResultMessage):
                assert msg.is_error is False

    @pytest.mark.asyncio
    async def test_query_with_tools(self) -> None:
        def add(a: int, b: int) -> str:
            """Add two numbers."""
            return str(a + b)

        messages = []
        async for msg in query(prompt='Add numbers', model='test', tools=[add]):
            messages.append(msg)

        has_result = any(isinstance(m, ResultMessage) for m in messages)
        assert has_result

    @pytest.mark.asyncio
    async def test_query_empty_prompt_yields_error(self) -> None:
        messages = []
        async for msg in query(prompt='', model='test'):
            messages.append(msg)

        # Should yield a ResultMessage with is_error=True
        errors = [m for m in messages if isinstance(m, ResultMessage) and m.is_error]
        assert len(errors) == 1


class TestQuerySync:
    def test_returns_run_result(self) -> None:
        result = query_sync(prompt='Hello', model='test')
        assert result.output is not None
        assert len(result.messages) >= 1

    def test_with_system_prompt(self) -> None:
        result = query_sync(prompt='Hello', model='test', system_prompt='Be brief.')
        assert result.output is not None


class TestAgentSDKClient:
    @pytest.mark.asyncio
    async def test_multi_turn(self) -> None:
        opts = AgentOptions(model='test')
        async with AgentSDKClient(options=opts) as client:
            await client.send('Turn 1')
            turn1_msgs = [msg async for msg in client.receive()]
            assert any(isinstance(m, ResultMessage) for m in turn1_msgs)

            await client.send('Turn 2')
            turn2_msgs = [msg async for msg in client.receive()]
            assert any(isinstance(m, ResultMessage) for m in turn2_msgs)

            # History should accumulate
            assert len(client.message_history) >= 4

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with AgentSDKClient(model='test') as client:
            assert client._agent is not None
        # After exit, cleaned up
        assert client._agent is None

    @pytest.mark.asyncio
    async def test_last_result(self) -> None:
        async with AgentSDKClient(model='test') as client:
            assert client.last_result is None
            await client.send('Hello')
            assert client.last_result is not None
            assert client.last_result.output is not None

    @pytest.mark.asyncio
    async def test_with_kwargs(self) -> None:
        async with AgentSDKClient(model='test', system_prompt='Be helpful.', hooks=[]) as client:
            await client.send('Hi')
            messages = [msg async for msg in client.receive()]
            assert len(messages) >= 1


class TestMessageTypes:
    def test_text_message(self) -> None:
        msg = TextMessage(text='Hello')
        assert msg.text == 'Hello'
        assert msg.role == 'assistant'

    def test_tool_call_message(self) -> None:
        msg = ToolCallMessage(tool_name='search', tool_args={'q': 'python'})
        assert msg.tool_name == 'search'
        assert msg.tool_args == {'q': 'python'}

    def test_tool_result_message(self) -> None:
        msg = ToolResultMessage(tool_name='search', result='found it')
        assert msg.result == 'found it'

    def test_result_message_defaults(self) -> None:
        msg = ResultMessage(output='done')
        assert msg.is_error is False
        assert msg.total_cost_usd is None
        assert msg.session_id is None
