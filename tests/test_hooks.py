"""Tests for typed_agent_sdk hooks system."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from typed_agent_sdk.errors import HookExecutionError
from typed_agent_sdk.hooks import (
    Hook,
    HookMatcher,
    HookResult,
    _fire_hooks,
    fire_permission_request,
    fire_user_prompt_submit,
    on_permission_request,
    on_post_tool_use_failure,
    on_subagent_start,
    on_subagent_stop,
    on_user_prompt_submit,
)
from typed_agent_sdk.types import (
    HookEvent,
    OnStartData,
    PreToolUseData,
    SDKMetrics,
)


class TestHookMatcher:
    def test_none_pattern_matches_all(self) -> None:
        m = HookMatcher(pattern=None)
        assert m.matches('anything') is True

    def test_regex_matches(self) -> None:
        m = HookMatcher(pattern='Write|Edit')
        assert m.matches('Write') is True
        assert m.matches('Edit') is True
        assert m.matches('Read') is False

    def test_exact_match(self) -> None:
        m = HookMatcher(pattern='^calculate$')
        assert m.matches('calculate') is True
        assert m.matches('calculate_v2') is False

    def test_invalid_regex_raises(self) -> None:
        with pytest.raises(ValueError, match='Invalid regex'):
            HookMatcher(pattern='[invalid')


class TestHookResult:
    def test_defaults(self) -> None:
        r = HookResult()
        assert r.block is False
        assert r.modified_args is None
        assert r.continue_ is True

    def test_block_result(self) -> None:
        r = HookResult(block=True, stop_reason='blocked by policy')
        assert r.block is True
        assert r.stop_reason == 'blocked by policy'


class TestFireHooks:
    @pytest.mark.asyncio
    async def test_hook_fires_for_matching_event(self) -> None:
        called = False

        async def callback(data: Any, ctx: Any) -> HookResult:
            nonlocal called
            called = True
            return HookResult()

        hooks = [Hook(event=HookEvent.OnStart, callback=callback)]
        data = OnStartData(prompt='hello')
        await _fire_hooks(hooks, HookEvent.OnStart, data, None)
        assert called is True

    @pytest.mark.asyncio
    async def test_hook_skipped_for_non_matching_event(self) -> None:
        called = False

        async def callback(data: Any, ctx: Any) -> HookResult:
            nonlocal called
            called = True
            return HookResult()

        hooks = [Hook(event=HookEvent.OnStop, callback=callback)]
        data = OnStartData(prompt='hello')
        await _fire_hooks(hooks, HookEvent.OnStart, data, None)
        assert called is False

    @pytest.mark.asyncio
    async def test_matcher_filters_by_target(self) -> None:
        called_for: list[str] = []

        async def callback(data: Any, ctx: Any) -> HookResult:
            if isinstance(data, PreToolUseData):
                called_for.append(data.tool_name)
            return HookResult()

        hooks = [
            Hook(
                event=HookEvent.PreToolUse,
                callback=callback,
                matcher=HookMatcher(pattern='Write|Edit'),
            )
        ]

        # Should fire for Write
        await _fire_hooks(
            hooks,
            HookEvent.PreToolUse,
            PreToolUseData(tool_name='Write', tool_args={}),
            None,
            target='Write',
        )
        # Should NOT fire for Read
        await _fire_hooks(
            hooks,
            HookEvent.PreToolUse,
            PreToolUseData(tool_name='Read', tool_args={}),
            None,
            target='Read',
        )

        assert called_for == ['Write']

    @pytest.mark.asyncio
    async def test_hooks_execute_in_priority_order(self) -> None:
        order: list[int] = []

        async def make_callback(priority: int):
            async def cb(data: Any, ctx: Any) -> HookResult:
                order.append(priority)
                return HookResult()

            return cb

        hooks = [
            Hook(event=HookEvent.OnStart, callback=await make_callback(3), priority=3),
            Hook(event=HookEvent.OnStart, callback=await make_callback(1), priority=1),
            Hook(event=HookEvent.OnStart, callback=await make_callback(2), priority=2),
        ]

        await _fire_hooks(hooks, HookEvent.OnStart, OnStartData(prompt='test'), None)
        assert order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_hook_blocks_returns_result(self) -> None:
        async def blocking_hook(data: Any, ctx: Any) -> HookResult:
            return HookResult(block=True, stop_reason='blocked')

        hooks = [Hook(event=HookEvent.PreToolUse, callback=blocking_hook)]
        result = await _fire_hooks(
            hooks,
            HookEvent.PreToolUse,
            PreToolUseData(tool_name='test', tool_args={}),
            None,
            target='test',
        )
        assert result is not None
        assert result.block is True

    @pytest.mark.asyncio
    async def test_hook_modifies_args(self) -> None:
        async def modifier(data: Any, ctx: Any) -> HookResult:
            return HookResult(modified_args={'x': 42})

        hooks = [Hook(event=HookEvent.PreToolUse, callback=modifier)]
        result = await _fire_hooks(
            hooks,
            HookEvent.PreToolUse,
            PreToolUseData(tool_name='test', tool_args={'x': 1}),
            None,
            target='test',
        )
        assert result is not None
        assert result.modified_args == {'x': 42}

    @pytest.mark.asyncio
    async def test_hook_timeout_skips(self) -> None:
        async def slow_hook(data: Any, ctx: Any) -> HookResult:
            await asyncio.sleep(10)
            return HookResult()

        hooks = [
            Hook(
                event=HookEvent.OnStart,
                callback=slow_hook,
                matcher=HookMatcher(timeout=0.01),
            )
        ]
        # Should not raise, just skip
        result = await _fire_hooks(hooks, HookEvent.OnStart, OnStartData(prompt='test'), None)
        assert result is None  # Timed out hook produces no result

    @pytest.mark.asyncio
    async def test_hook_exception_raises_hook_execution_error(self) -> None:
        async def bad_hook(data: Any, ctx: Any) -> HookResult:
            raise RuntimeError('hook broke')

        hooks = [Hook(event=HookEvent.OnStart, callback=bad_hook)]
        with pytest.raises(HookExecutionError, match='hook broke'):
            await _fire_hooks(hooks, HookEvent.OnStart, OnStartData(prompt='test'), None)

    @pytest.mark.asyncio
    async def test_hook_bad_return_type_raises(self) -> None:
        async def bad_return(data: Any, ctx: Any) -> Any:
            return 'not a HookResult'

        hooks = [Hook(event=HookEvent.OnStart, callback=bad_return)]
        with pytest.raises(TypeError, match='must return HookResult'):
            await _fire_hooks(hooks, HookEvent.OnStart, OnStartData(prompt='test'), None)

    @pytest.mark.asyncio
    async def test_empty_dict_return_accepted(self) -> None:
        async def empty_return(data: Any, ctx: Any) -> Any:
            return {}

        hooks = [Hook(event=HookEvent.OnStart, callback=empty_return)]
        # Should not raise
        result = await _fire_hooks(hooks, HookEvent.OnStart, OnStartData(prompt='test'), None)
        assert result is not None
        assert result.block is False

    @pytest.mark.asyncio
    async def test_metrics_tracked(self) -> None:
        async def hook(data: Any, ctx: Any) -> HookResult:
            return HookResult()

        metrics = SDKMetrics()
        hooks = [Hook(event=HookEvent.OnStart, callback=hook)]
        await _fire_hooks(
            hooks, HookEvent.OnStart, OnStartData(prompt='test'), None, metrics=metrics
        )
        assert metrics.hook_invocations == 1

    @pytest.mark.asyncio
    async def test_block_increments_hooks_blocked(self) -> None:
        async def blocker(data: Any, ctx: Any) -> HookResult:
            return HookResult(block=True)

        metrics = SDKMetrics()
        hooks = [Hook(event=HookEvent.PreToolUse, callback=blocker)]
        await _fire_hooks(
            hooks,
            HookEvent.PreToolUse,
            PreToolUseData(tool_name='t', tool_args={}),
            None,
            target='t',
            metrics=metrics,
        )
        assert metrics.hooks_blocked == 1

    @pytest.mark.asyncio
    async def test_fire_and_forget_does_not_block(self) -> None:
        executed = asyncio.Event()

        async def slow_hook(data: Any, ctx: Any) -> HookResult:
            await asyncio.sleep(0.1)
            executed.set()
            return HookResult()

        hooks = [Hook(event=HookEvent.OnStart, callback=slow_hook, fire_and_forget=True)]
        # Should return immediately
        await _fire_hooks(hooks, HookEvent.OnStart, OnStartData(prompt='test'), None)
        # Give background task time to complete
        await asyncio.sleep(0.2)
        assert executed.is_set()


class TestAnthropicSDKParityHooks:
    """Hooks added for Claude Agent SDK feature parity."""

    @pytest.mark.asyncio
    async def test_user_prompt_submit_fires(self) -> None:
        seen: list[str] = []

        @on_user_prompt_submit()
        async def cb(data: Any, ctx: Any) -> HookResult:
            seen.append(data.prompt)
            return HookResult()

        result = await fire_user_prompt_submit([cb], 'hello world', agent_name='a')
        assert seen == ['hello world']
        assert result is not None
        assert result.block is False

    @pytest.mark.asyncio
    async def test_user_prompt_submit_can_inject_context(self) -> None:
        @on_user_prompt_submit()
        async def cb(data: Any, ctx: Any) -> HookResult:
            return HookResult(additional_context='extra info')

        result = await fire_user_prompt_submit([cb], 'q')
        assert result is not None
        assert result.additional_context == 'extra info'

    @pytest.mark.asyncio
    async def test_user_prompt_submit_can_block(self) -> None:
        @on_user_prompt_submit()
        async def cb(data: Any, ctx: Any) -> HookResult:
            return HookResult(block=True, stop_reason='disallowed')

        result = await fire_user_prompt_submit([cb], 'q')
        assert result is not None
        assert result.block is True
        assert result.stop_reason == 'disallowed'

    @pytest.mark.asyncio
    async def test_permission_request_fires_with_tool_target(self) -> None:
        seen: list[str] = []

        @on_permission_request(matcher=r'^Bash$')
        async def cb(data: Any, ctx: Any) -> HookResult:
            seen.append(data.tool_name)
            return HookResult()

        # Matches Bash
        await fire_permission_request([cb], 'Bash', {'command': 'ls'})
        # Does not match Read
        await fire_permission_request([cb], 'Read', {'path': '/'})
        assert seen == ['Bash']

    @pytest.mark.asyncio
    async def test_permission_request_can_deny(self) -> None:
        @on_permission_request()
        async def cb(data: Any, ctx: Any) -> HookResult:
            return HookResult(block=True, stop_reason='denied')

        result = await fire_permission_request([cb], 'Bash', {'command': 'rm -rf /'})
        assert result is not None
        assert result.block is True

    @pytest.mark.asyncio
    async def test_post_tool_use_failure_decorator_creates_correct_hook(self) -> None:
        @on_post_tool_use_failure(matcher=r'.*')
        async def cb(data: Any, ctx: Any) -> HookResult:
            return HookResult()

        assert cb.event == HookEvent.PostToolUseFailure

    @pytest.mark.asyncio
    async def test_subagent_alias_decorators(self) -> None:
        @on_subagent_start()
        async def start_cb(data: Any, ctx: Any) -> HookResult:
            return HookResult()

        @on_subagent_stop()
        async def stop_cb(data: Any, ctx: Any) -> HookResult:
            return HookResult()

        assert start_cb.event == HookEvent.SubagentStart
        assert stop_cb.event == HookEvent.SubagentStop


class TestHookToolsetPermissionGate:
    """HookToolset.call_tool should consult an attached PermissionPolicy."""

    @pytest.mark.asyncio
    async def test_blocked_tool_returns_denial_string_without_invoking_wrapped(self) -> None:
        from typed_agent_sdk.hooks import HookToolset
        from typed_agent_sdk.permissions import PermissionPolicy

        invoked = False

        class FakeWrapped:
            async def call_tool(
                self, name: str, args: dict, ctx: Any, tool: Any
            ) -> Any:  # type: ignore[type-arg]
                nonlocal invoked
                invoked = True
                return 'should not run'

        ts: HookToolset[Any] = HookToolset(
            wrapped=FakeWrapped(),  # type: ignore[arg-type]
            hooks=[],
            policy=PermissionPolicy(blocked_tools=['Bash']),
        )
        result = await ts.call_tool('Bash', {'cmd': 'ls'}, ctx=object(), tool=object())
        assert isinstance(result, str)
        assert 'denied by permission policy' in result
        assert invoked is False

    @pytest.mark.asyncio
    async def test_allowed_tool_passes_through(self) -> None:
        from typed_agent_sdk.hooks import HookToolset
        from typed_agent_sdk.permissions import PermissionPolicy

        class FakeWrapped:
            async def call_tool(
                self, name: str, args: dict, ctx: Any, tool: Any
            ) -> Any:  # type: ignore[type-arg]
                return f'ran {name}'

        ts: HookToolset[Any] = HookToolset(
            wrapped=FakeWrapped(),  # type: ignore[arg-type]
            hooks=[],
            policy=PermissionPolicy(allowed_tools=['Read']),
        )
        result = await ts.call_tool('Read', {'path': '/'}, ctx=object(), tool=object())
        assert result == 'ran Read'

    @pytest.mark.asyncio
    async def test_permission_request_hook_can_deny_at_dispatch(self) -> None:
        from typed_agent_sdk.hooks import HookToolset, on_permission_request
        from typed_agent_sdk.permissions import PermissionPolicy

        class FakeWrapped:
            async def call_tool(
                self, name: str, args: dict, ctx: Any, tool: Any
            ) -> Any:  # type: ignore[type-arg]
                return 'ran'

        @on_permission_request()
        async def deny(data: Any, ctx: Any) -> HookResult:
            return HookResult(block=True, stop_reason='compliance')

        ts: HookToolset[Any] = HookToolset(
            wrapped=FakeWrapped(),  # type: ignore[arg-type]
            hooks=[deny],
            policy=PermissionPolicy(require_approval=['risky_*']),
        )
        result = await ts.call_tool('risky_op', {}, ctx=object(), tool=object())
        assert isinstance(result, str)
        assert 'compliance' in result
