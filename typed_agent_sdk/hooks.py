"""Hook lifecycle system for typed_agent_sdk.

Provides PreToolUse/PostToolUse hooks via WrapperToolset,
plus OnStart/OnStop/OnError and other lifecycle events.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic_ai._run_context import AgentDepsT, RunContext
from pydantic_ai.toolsets.wrapper import WrapperToolset

from typed_agent_sdk.errors import HookExecutionError
from typed_agent_sdk.types import HookEvent, HookEventData, SDKMetrics

if TYPE_CHECKING:
    from pydantic_ai.toolsets.abstract import ToolsetTool

    from typed_agent_sdk.permissions import PermissionPolicy

logger = logging.getLogger('typed_agent_sdk.hooks')

DepsT = TypeVar('DepsT')


@dataclass(frozen=True)
class HookResult:
    """Result returned by a hook callback to control agent behavior."""

    block: bool = False
    modified_args: dict[str, Any] | None = None
    modified_result: Any | None = None
    additional_context: str | None = None
    suppress_output: bool = False
    continue_: bool = True
    stop_reason: str | None = None


@dataclass(frozen=True)
class HookMatcher:
    """Filter that determines whether a hook fires for a given event."""

    pattern: str | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f'Invalid regex pattern "{self.pattern}": {e}') from e

    def matches(self, target: str) -> bool:
        """Check if a target name matches this matcher's pattern."""
        if self.pattern is None:
            return True
        return bool(re.search(self.pattern, target))


HookCallback = Callable[[HookEventData, Any], Awaitable[HookResult]]


@dataclass
class Hook:
    """A lifecycle callback bound to a specific event type."""

    event: HookEvent
    callback: HookCallback
    matcher: HookMatcher | None = None
    priority: int = 100
    fire_and_forget: bool = False

    def matches(self, target: str) -> bool:
        """Check if this hook should fire for the given target."""
        if self.matcher is None:
            return True
        return self.matcher.matches(target)

    @property
    def timeout(self) -> float | None:
        """Get timeout from matcher, if set."""
        return self.matcher.timeout if self.matcher else None


async def _fire_hooks(
    hooks: list[Hook],
    event: HookEvent,
    event_data: HookEventData,
    ctx: Any,
    target: str = '',
    metrics: SDKMetrics | None = None,
) -> HookResult | None:
    """Fire all matching hooks for an event, respecting priority and timeout.

    Returns the first HookResult that blocks, or None if all hooks allow.
    """
    matching = [h for h in hooks if h.event == event and h.matches(target)]
    matching.sort(key=lambda h: h.priority)

    combined_result: HookResult | None = None

    for hook in matching:
        if metrics:
            metrics.hook_invocations += 1

        try:
            if hook.fire_and_forget:
                _bg = asyncio.create_task(_run_hook_safe(hook, event_data, ctx))  # noqa: RUF006
                continue

            if hook.timeout:
                result = await asyncio.wait_for(
                    hook.callback(event_data, ctx), timeout=hook.timeout
                )
            else:
                result = await hook.callback(event_data, ctx)

            if not isinstance(result, HookResult):
                # Accept empty dict as "allow" for convenience
                if isinstance(result, dict) and not result:
                    result = HookResult()
                else:
                    raise TypeError(
                        f'Hook callback must return HookResult or empty dict, '
                        f'got {type(result).__name__}'
                    )

            if result.block:
                if metrics:
                    metrics.hooks_blocked += 1
                return result

            # Merge non-blocking results (last writer wins for modifications)
            if combined_result is None:
                combined_result = result
            else:
                combined_result = HookResult(
                    block=False,
                    modified_args=result.modified_args or combined_result.modified_args,
                    modified_result=result.modified_result or combined_result.modified_result,
                    additional_context=result.additional_context
                    or combined_result.additional_context,
                    suppress_output=result.suppress_output or combined_result.suppress_output,
                    continue_=result.continue_ and combined_result.continue_,
                    stop_reason=result.stop_reason or combined_result.stop_reason,
                )

        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(
                'Hook timed out for event %s (timeout=%ss), skipping',
                event.value,
                hook.timeout,
            )
        except TypeError:
            raise
        except Exception as e:
            raise HookExecutionError(event.value, e) from e

    return combined_result


async def _run_hook_safe(hook: Hook, event_data: HookEventData, ctx: Any) -> None:
    """Run a fire-and-forget hook, logging any errors."""
    try:
        await hook.callback(event_data, ctx)
    except Exception:
        logger.exception('Fire-and-forget hook failed for event %s', hook.event.value)


@dataclass
class HookToolset(WrapperToolset[AgentDepsT]):
    """Wraps a toolset to intercept tool calls with PreToolUse/PostToolUse hooks."""

    hooks: list[Hook] = field(default_factory=list)
    metrics: SDKMetrics = field(default_factory=SDKMetrics)
    policy: PermissionPolicy | None = None

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        """Intercept tool calls with PreToolUse/PostToolUse hooks."""
        from typed_agent_sdk.types import OnErrorData, PostToolUseData, PreToolUseData

        # Permission gate (runs before PreToolUse so denied tools never fire pre-hooks).
        if self.policy is not None:
            perm_result = await self.policy.check_with_hooks(
                name, tool_args, hooks=self.hooks, metrics=self.metrics
            )
            if not perm_result.allowed:
                reason = perm_result.reason or 'permission denied'
                if self.metrics:
                    self.metrics.hooks_blocked += 1
                return f'Tool "{name}" denied by permission policy: {reason}'

        # Fire PreToolUse hooks
        pre_data = PreToolUseData(
            tool_name=name,
            tool_args=tool_args,
            tool_call_id=getattr(ctx, 'tool_call_id', None),
        )
        pre_result = await _fire_hooks(
            self.hooks, HookEvent.PreToolUse, pre_data, ctx, target=name, metrics=self.metrics
        )

        if pre_result and pre_result.block:
            reason = pre_result.stop_reason or 'no reason given'
            return f'Tool "{name}" was blocked by a hook: {reason}'

        # Apply arg modifications from hooks
        effective_args = tool_args
        if pre_result and pre_result.modified_args is not None:
            effective_args = pre_result.modified_args

        # Execute the actual tool
        try:
            result = await self.wrapped.call_tool(name, effective_args, ctx, tool)
        except Exception as e:
            from typed_agent_sdk.types import PostToolUseFailureData

            failure_data = PostToolUseFailureData(
                tool_name=name,
                tool_args=effective_args,
                error=e,
                tool_call_id=getattr(ctx, 'tool_call_id', None),
            )
            await _fire_hooks(
                self.hooks,
                HookEvent.PostToolUseFailure,
                failure_data,
                ctx,
                target=name,
                metrics=self.metrics,
            )
            error_data = OnErrorData(error=e, context=f'tool:{name}')
            await _fire_hooks(
                self.hooks, HookEvent.OnError, error_data, ctx, target=name, metrics=self.metrics
            )
            raise

        # Fire PostToolUse hooks
        post_data = PostToolUseData(
            tool_name=name,
            tool_args=effective_args,
            tool_result=result,
            tool_call_id=getattr(ctx, 'tool_call_id', None),
        )
        post_result = await _fire_hooks(
            self.hooks, HookEvent.PostToolUse, post_data, ctx, target=name, metrics=self.metrics
        )

        # Apply result modifications
        if post_result and post_result.modified_result is not None:
            return post_result.modified_result

        if post_result and post_result.suppress_output:
            return '[output suppressed by hook]'

        return result


# --- Convenience Decorators ---


def _make_hook_decorator(
    event: HookEvent,
) -> Callable[..., Callable[[HookCallback], Hook]]:
    """Factory for creating event-specific hook decorators."""

    def decorator(
        matcher: str | None = None,
        *,
        priority: int = 100,
        fire_and_forget: bool = False,
        timeout: float | None = None,
    ) -> Callable[[HookCallback], Hook]:
        def wrapper(func: HookCallback) -> Hook:
            hook_matcher = None
            if matcher is not None or timeout is not None:
                hook_matcher = HookMatcher(pattern=matcher, timeout=timeout)
            return Hook(
                event=event,
                callback=func,
                matcher=hook_matcher,
                priority=priority,
                fire_and_forget=fire_and_forget,
            )

        return wrapper

    return decorator


on_pre_tool_use = _make_hook_decorator(HookEvent.PreToolUse)
on_post_tool_use = _make_hook_decorator(HookEvent.PostToolUse)
on_post_tool_use_failure = _make_hook_decorator(HookEvent.PostToolUseFailure)
on_pre_model_call = _make_hook_decorator(HookEvent.PreModelCall)
on_post_model_call = _make_hook_decorator(HookEvent.PostModelCall)
on_pre_handoff = _make_hook_decorator(HookEvent.PreHandoff)
on_post_handoff = _make_hook_decorator(HookEvent.PostHandoff)
# Anthropic-SDK-aligned aliases for handoff lifecycle.
on_subagent_start = _make_hook_decorator(HookEvent.SubagentStart)
on_subagent_stop = _make_hook_decorator(HookEvent.SubagentStop)
on_error = _make_hook_decorator(HookEvent.OnError)
on_start = _make_hook_decorator(HookEvent.OnStart)
on_stop = _make_hook_decorator(HookEvent.OnStop)
on_pre_compact = _make_hook_decorator(HookEvent.PreCompact)
on_notification = _make_hook_decorator(HookEvent.Notification)
on_user_prompt_submit = _make_hook_decorator(HookEvent.UserPromptSubmit)
on_permission_request = _make_hook_decorator(HookEvent.PermissionRequest)


async def fire_user_prompt_submit(
    hooks: list[Hook],
    prompt: str,
    agent_name: str | None = None,
    metrics: SDKMetrics | None = None,
) -> HookResult | None:
    """Fire UserPromptSubmit hooks. Returns the merged HookResult (or block)."""
    from typed_agent_sdk.types import UserPromptSubmitData

    data = UserPromptSubmitData(prompt=prompt, agent_name=agent_name)
    return await _fire_hooks(hooks, HookEvent.UserPromptSubmit, data, None, metrics=metrics)


async def fire_permission_request(
    hooks: list[Hook],
    tool_name: str,
    tool_args: dict[str, Any],
    reason: str | None = None,
    metrics: SDKMetrics | None = None,
) -> HookResult | None:
    """Fire PermissionRequest hooks. A returned HookResult with block=True denies."""
    from typed_agent_sdk.types import PermissionRequestData

    data = PermissionRequestData(tool_name=tool_name, tool_args=tool_args, reason=reason)
    return await _fire_hooks(
        hooks, HookEvent.PermissionRequest, data, None, target=tool_name, metrics=metrics
    )
