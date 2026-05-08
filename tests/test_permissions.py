"""Tests for typed_agent_sdk permission policies."""

from __future__ import annotations

import pytest

from typed_agent_sdk.permissions import PermissionMode, PermissionPolicy


class TestPermissionPolicy:
    def test_default_allows_all(self) -> None:
        policy = PermissionPolicy()
        result = policy.check('any_tool')
        assert result.allowed is True

    def test_allowed_tools_filters(self) -> None:
        policy = PermissionPolicy(allowed_tools=['search_*', 'calculate'])
        assert policy.check('search_web').allowed is True
        assert policy.check('calculate').allowed is True
        assert policy.check('file_write').allowed is False

    def test_blocked_tools_excludes(self) -> None:
        policy = PermissionPolicy(blocked_tools=['file_delete'])
        assert policy.check('file_delete').allowed is False
        assert policy.check('file_read').allowed is True

    def test_blocked_overrides_allowed(self) -> None:
        policy = PermissionPolicy(
            allowed_tools=['file_*'],
            blocked_tools=['file_delete'],
        )
        assert policy.check('file_read').allowed is True
        assert policy.check('file_delete').allowed is False

    def test_require_approval_flag(self) -> None:
        policy = PermissionPolicy(require_approval=['execute_*'])
        result = policy.check('execute_code')
        assert result.allowed is True
        assert result.requires_approval is True

    def test_plan_only_mode_blocks_all(self) -> None:
        policy = PermissionPolicy(mode=PermissionMode.planOnly)
        result = policy.check('any_tool')
        assert result.allowed is False
        assert 'Plan-only' in (result.reason or '')

    def test_unrestricted_mode(self) -> None:
        policy = PermissionPolicy(mode=PermissionMode.unrestricted)
        assert policy.check('dangerous_tool').allowed is True

    def test_empty_patterns_allow_all(self) -> None:
        policy = PermissionPolicy(allowed_tools=[], blocked_tools=[])
        assert policy.check('anything').allowed is True

    def test_wildcard_block(self) -> None:
        policy = PermissionPolicy(blocked_tools=['*'])
        assert policy.check('anything').allowed is False

    def test_filter_tools(self) -> None:
        policy = PermissionPolicy(
            allowed_tools=['search_*', 'calculate'],
            blocked_tools=['search_private'],
        )
        tools = ['search_web', 'search_private', 'calculate', 'file_write']
        filtered = policy.filter_tools(tools)
        assert filtered == ['search_web', 'calculate']

    def test_add_rule(self) -> None:
        policy = PermissionPolicy()
        policy.add_rule('blocked', 'dangerous_*')
        assert policy.check('dangerous_tool').allowed is False

    def test_remove_rule(self) -> None:
        policy = PermissionPolicy(blocked_tools=['file_delete'])
        policy.remove_rule('blocked', 'file_delete')
        assert policy.check('file_delete').allowed is True

    def test_add_rule_invalid_type_raises(self) -> None:
        policy = PermissionPolicy()
        with pytest.raises(ValueError, match='Unknown rule type'):
            policy.add_rule('invalid', 'pattern')

    def test_result_has_reason(self) -> None:
        policy = PermissionPolicy(blocked_tools=['bash'])
        result = policy.check('bash')
        assert result.reason is not None
        assert 'blocked' in result.reason


class TestCheckWithHooks:
    @pytest.mark.asyncio
    async def test_no_approval_required_returns_immediately(self) -> None:
        policy = PermissionPolicy()
        result = await policy.check_with_hooks('safe_tool', {})
        assert result.allowed is True
        assert result.requires_approval is False

    @pytest.mark.asyncio
    async def test_blocked_tool_short_circuits(self) -> None:
        from typed_agent_sdk.hooks import on_permission_request

        called = False

        @on_permission_request()
        async def cb(data, ctx):  # type: ignore[no-untyped-def]
            nonlocal called
            called = True
            from typed_agent_sdk.hooks import HookResult

            return HookResult()

        policy = PermissionPolicy(blocked_tools=['bash'])
        result = await policy.check_with_hooks('bash', {}, hooks=[cb])
        assert result.allowed is False
        # Hook should NOT fire — tool was already blocked.
        assert called is False

    @pytest.mark.asyncio
    async def test_hook_can_approve(self) -> None:
        from typed_agent_sdk.hooks import HookResult, on_permission_request

        @on_permission_request()
        async def cb(data, ctx):  # type: ignore[no-untyped-def]
            return HookResult()

        policy = PermissionPolicy(require_approval=['risky_*'])
        result = await policy.check_with_hooks('risky_op', {}, hooks=[cb])
        assert result.allowed is True
        assert result.requires_approval is False

    @pytest.mark.asyncio
    async def test_hook_can_deny(self) -> None:
        from typed_agent_sdk.hooks import HookResult, on_permission_request

        @on_permission_request()
        async def cb(data, ctx):  # type: ignore[no-untyped-def]
            return HookResult(block=True, stop_reason='policy violation')

        policy = PermissionPolicy(require_approval=['risky_*'])
        result = await policy.check_with_hooks('risky_op', {}, hooks=[cb])
        assert result.allowed is False
        assert result.reason == 'policy violation'

    @pytest.mark.asyncio
    async def test_falls_back_to_approval_callback(self) -> None:
        async def approve_all(name: str, args: dict) -> bool:  # type: ignore[type-arg]
            return True

        policy = PermissionPolicy(
            require_approval=['risky_*'],
            approval_callback=approve_all,
        )
        # No hooks → callback is consulted.
        result = await policy.check_with_hooks('risky_op', {}, hooks=[])
        assert result.allowed is True
        assert result.requires_approval is False

    @pytest.mark.asyncio
    async def test_approval_callback_can_deny(self) -> None:
        async def deny_all(name: str, args: dict) -> bool:  # type: ignore[type-arg]
            return False

        policy = PermissionPolicy(
            require_approval=['risky_*'],
            approval_callback=deny_all,
        )
        result = await policy.check_with_hooks('risky_op', {})
        assert result.allowed is False
        assert result.reason is not None
        assert 'approval_callback' in result.reason

    @pytest.mark.asyncio
    async def test_no_hooks_no_callback_preserves_requires_approval(self) -> None:
        policy = PermissionPolicy(require_approval=['risky_*'])
        result = await policy.check_with_hooks('risky_op', {})
        assert result.allowed is True
        assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_hook_takes_precedence_over_callback(self) -> None:
        from typed_agent_sdk.hooks import HookResult, on_permission_request

        callback_called = False

        async def cb_fallback(name: str, args: dict) -> bool:  # type: ignore[type-arg]
            nonlocal callback_called
            callback_called = True
            return True

        @on_permission_request()
        async def hook_cb(data, ctx):  # type: ignore[no-untyped-def]
            return HookResult(block=True, stop_reason='blocked by hook')

        policy = PermissionPolicy(
            require_approval=['risky_*'],
            approval_callback=cb_fallback,
        )
        result = await policy.check_with_hooks('risky_op', {}, hooks=[hook_cb])
        assert result.allowed is False
        assert callback_called is False  # hook short-circuited

    @pytest.mark.asyncio
    async def test_hook_matcher_filters_by_tool_name(self) -> None:
        from typed_agent_sdk.hooks import HookResult, on_permission_request

        # Hook only fires for Bash; risky_op is approval-required but unmatched
        # → no hook responds, no callback set, so requires_approval is preserved.
        @on_permission_request(matcher=r'^Bash$')
        async def cb(data, ctx):  # type: ignore[no-untyped-def]
            return HookResult()

        policy = PermissionPolicy(require_approval=['risky_*', 'Bash'])
        result = await policy.check_with_hooks('risky_op', {}, hooks=[cb])
        assert result.requires_approval is True
