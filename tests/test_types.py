"""Tests for agent_sdk.types."""

from __future__ import annotations

from agent_sdk.types import (
    HookEvent,
    NotificationData,
    OnErrorData,
    OnStartData,
    OnStopData,
    PostToolUseData,
    PreToolUseData,
    SDKMetrics,
    ToolAnnotations,
)


class TestHookEvent:
    def test_all_11_events_exist(self) -> None:
        events = list(HookEvent)
        assert len(events) == 11

    def test_event_values(self) -> None:
        assert HookEvent.PreToolUse == 'PreToolUse'
        assert HookEvent.PostToolUse == 'PostToolUse'
        assert HookEvent.PreModelCall == 'PreModelCall'
        assert HookEvent.PostModelCall == 'PostModelCall'
        assert HookEvent.PreHandoff == 'PreHandoff'
        assert HookEvent.PostHandoff == 'PostHandoff'
        assert HookEvent.OnError == 'OnError'
        assert HookEvent.OnStart == 'OnStart'
        assert HookEvent.OnStop == 'OnStop'
        assert HookEvent.PreCompact == 'PreCompact'
        assert HookEvent.Notification == 'Notification'

    def test_event_is_str_enum(self) -> None:
        assert isinstance(HookEvent.PreToolUse, str)
        assert HookEvent.PreToolUse == 'PreToolUse'


class TestHookEventData:
    def test_pre_tool_use_data(self) -> None:
        data = PreToolUseData(tool_name='calc', tool_args={'x': 1}, tool_call_id='tc1')
        assert data.tool_name == 'calc'
        assert data.tool_args == {'x': 1}
        assert data.tool_call_id == 'tc1'

    def test_post_tool_use_data(self) -> None:
        data = PostToolUseData(
            tool_name='calc', tool_args={'x': 1}, tool_result='42', tool_call_id='tc1'
        )
        assert data.tool_result == '42'

    def test_on_error_data(self) -> None:
        err = ValueError('test')
        data = OnErrorData(error=err, context='tool execution')
        assert data.error is err
        assert data.context == 'tool execution'

    def test_on_start_data_defaults(self) -> None:
        data = OnStartData(prompt='hello')
        assert data.agent_name is None

    def test_on_stop_data_defaults(self) -> None:
        data = OnStopData()
        assert data.result is None
        assert data.stop_reason is None

    def test_notification_data_defaults(self) -> None:
        data = NotificationData(message='test')
        assert data.title is None
        assert data.notification_type == 'info'


class TestToolAnnotations:
    def test_defaults(self) -> None:
        ann = ToolAnnotations()
        assert ann.read_only is False
        assert ann.destructive is False
        assert ann.open_world is False

    def test_custom_values(self) -> None:
        ann = ToolAnnotations(read_only=True, destructive=False, open_world=True)
        assert ann.read_only is True
        assert ann.open_world is True


class TestSDKMetrics:
    def test_defaults(self) -> None:
        m = SDKMetrics()
        assert m.hook_invocations == 0
        assert m.guardrail_checks == 0
        assert m.handoff_count == 0
        assert m.guardrail_trips == 0
        assert m.hooks_blocked == 0

    def test_mutable(self) -> None:
        m = SDKMetrics()
        m.hook_invocations = 5
        assert m.hook_invocations == 5
