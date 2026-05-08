"""Test utilities for typed_agent_sdk consumers.

Provides HookRecorder and GuardrailRecorder for asserting
hook execution order and guardrail trigger behavior in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typed_agent_sdk.hooks import Hook, HookResult
from typed_agent_sdk.types import HookEvent, HookEventData

if TYPE_CHECKING:
    from typed_agent_sdk.guardrails import GuardrailResult


class HookRecorder:
    """Records hook invocations for testing assertions.

    Usage:
        recorder = HookRecorder()
        runner = Runner(agent, hooks=[recorder.get_hook()])
        result = await runner.run('test')
        recorder.assert_called(HookEvent.OnStart)
        recorder.assert_order([HookEvent.OnStart, HookEvent.OnStop])
    """

    def __init__(self) -> None:
        self.events: list[tuple[HookEvent, HookEventData]] = []

    async def _record(self, event_data: HookEventData, ctx: Any) -> HookResult:
        """Record an event and return allow result."""
        # Determine event type from data class name
        data_name = type(event_data).__name__
        event_map = {
            'OnStartData': HookEvent.OnStart,
            'OnStopData': HookEvent.OnStop,
            'OnErrorData': HookEvent.OnError,
            'PreToolUseData': HookEvent.PreToolUse,
            'PostToolUseData': HookEvent.PostToolUse,
            'PostToolUseFailureData': HookEvent.PostToolUseFailure,
            'PreHandoffData': HookEvent.PreHandoff,
            'PostHandoffData': HookEvent.PostHandoff,
            'PreModelCallData': HookEvent.PreModelCall,
            'PostModelCallData': HookEvent.PostModelCall,
            'PreCompactData': HookEvent.PreCompact,
            'NotificationData': HookEvent.Notification,
            'UserPromptSubmitData': HookEvent.UserPromptSubmit,
            'PermissionRequestData': HookEvent.PermissionRequest,
        }
        event = event_map.get(data_name, HookEvent.Notification)
        self.events.append((event, event_data))
        return HookResult()

    def get_hooks(self) -> list[Hook]:
        """Return hooks for ALL event types that record to this recorder."""
        return [Hook(event=event, callback=self._record) for event in HookEvent]

    def get_hook(self, event: HookEvent | None = None) -> Hook:
        """Return a single hook. If event is None, returns an OnStart hook."""
        return Hook(event=event or HookEvent.OnStart, callback=self._record)

    def assert_called(self, event: HookEvent, *, times: int | None = None) -> None:
        """Assert a specific event was recorded."""
        matches = [e for e, _ in self.events if e == event]
        if not matches:
            recorded = [e.value for e, _ in self.events]
            raise AssertionError(
                f'HookEvent.{event.value} was not called. Recorded events: {recorded}'
            )
        if times is not None and len(matches) != times:
            raise AssertionError(
                f'HookEvent.{event.value} called {len(matches)} times, expected {times}'
            )

    def assert_not_called(self, event: HookEvent) -> None:
        """Assert a specific event was NOT recorded."""
        matches = [e for e, _ in self.events if e == event]
        if matches:
            raise AssertionError(
                f'HookEvent.{event.value} was called {len(matches)} times, expected 0'
            )

    def assert_order(self, events: list[HookEvent]) -> None:
        """Assert events were recorded in the given order."""
        recorded = [e for e, _ in self.events]
        filtered = [e for e in recorded if e in events]
        if filtered != events:
            raise AssertionError(
                f'Expected event order {[e.value for e in events]}, '
                f'got {[e.value for e in filtered]}'
            )

    def clear(self) -> None:
        """Clear recorded events."""
        self.events.clear()


class GuardrailRecorder:
    """Records guardrail checks for testing assertions.

    Usage:
        recorder = GuardrailRecorder()
        # ... run agent with guardrails ...
        recorder.assert_passed('my-guard')
        recorder.assert_tripped('safety-guard')
    """

    def __init__(self) -> None:
        self.checks: list[tuple[str, GuardrailResult]] = []

    def record(self, name: str, result: GuardrailResult) -> None:
        """Record a guardrail check result."""
        self.checks.append((name, result))

    def assert_tripped(self, name: str | None = None) -> None:
        """Assert a guardrail was tripped."""
        matches = [(n, r) for n, r in self.checks if (name is None or n == name) and r.tripwire]
        if not matches:
            target = f'"{name}"' if name else 'any guardrail'
            raise AssertionError(f'{target} was not tripped')

    def assert_passed(self, name: str | None = None) -> None:
        """Assert a guardrail passed."""
        matches = [(n, r) for n, r in self.checks if (name is None or n == name) and r.passed]
        if not matches:
            target = f'"{name}"' if name else 'any guardrail'
            raise AssertionError(f'{target} did not pass')

    def clear(self) -> None:
        """Clear recorded checks."""
        self.checks.clear()
