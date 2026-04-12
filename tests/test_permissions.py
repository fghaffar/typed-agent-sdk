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
