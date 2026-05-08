"""Shared types, enums, and type aliases for typed_agent_sdk."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:

    class StrEnum(str, Enum):
        """Backport for Python 3.10."""


class HookEvent(StrEnum):
    """Lifecycle events that hooks can listen to."""

    PreToolUse = 'PreToolUse'
    PostToolUse = 'PostToolUse'
    PostToolUseFailure = 'PostToolUseFailure'
    PreModelCall = 'PreModelCall'
    PostModelCall = 'PostModelCall'
    PreHandoff = 'PreHandoff'
    PostHandoff = 'PostHandoff'
    SubagentStart = 'SubagentStart'
    SubagentStop = 'SubagentStop'
    OnError = 'OnError'
    OnStart = 'OnStart'
    OnStop = 'OnStop'
    PreCompact = 'PreCompact'
    Notification = 'Notification'
    UserPromptSubmit = 'UserPromptSubmit'
    PermissionRequest = 'PermissionRequest'


@dataclass(frozen=True)
class PreToolUseData:
    """Event data for PreToolUse hooks."""

    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str | None = None


@dataclass(frozen=True)
class PostToolUseData:
    """Event data for PostToolUse hooks."""

    tool_name: str
    tool_args: dict[str, Any]
    tool_result: Any
    tool_call_id: str | None = None


@dataclass(frozen=True)
class PostToolUseFailureData:
    """Event data for PostToolUseFailure hooks."""

    tool_name: str
    tool_args: dict[str, Any]
    error: Exception
    tool_call_id: str | None = None


@dataclass(frozen=True)
class PreModelCallData:
    """Event data for PreModelCall hooks."""

    messages: list[Any]


@dataclass(frozen=True)
class PostModelCallData:
    """Event data for PostModelCall hooks."""

    response: Any
    messages: list[Any]


@dataclass(frozen=True)
class PreHandoffData:
    """Event data for PreHandoff hooks."""

    source_agent: str
    target_agent: str
    handoff_description: str


@dataclass(frozen=True)
class PostHandoffData:
    """Event data for PostHandoff hooks."""

    source_agent: str
    target_agent: str
    result: Any


@dataclass(frozen=True)
class OnErrorData:
    """Event data for OnError hooks."""

    error: Exception
    context: str


@dataclass(frozen=True)
class OnStartData:
    """Event data for OnStart hooks."""

    prompt: str | Any
    agent_name: str | None = None


@dataclass(frozen=True)
class OnStopData:
    """Event data for OnStop hooks."""

    result: Any = None
    stop_reason: str | None = None


@dataclass(frozen=True)
class PreCompactData:
    """Event data for PreCompact hooks."""

    messages: list[Any]
    trigger: str = 'auto'


@dataclass(frozen=True)
class NotificationData:
    """Event data for Notification hooks."""

    message: str
    title: str | None = None
    notification_type: str = 'info'


@dataclass(frozen=True)
class UserPromptSubmitData:
    """Event data for UserPromptSubmit hooks."""

    prompt: str
    agent_name: str | None = None


@dataclass(frozen=True)
class PermissionRequestData:
    """Event data for PermissionRequest hooks."""

    tool_name: str
    tool_args: dict[str, Any]
    reason: str | None = None


HookEventData = (
    PreToolUseData
    | PostToolUseData
    | PostToolUseFailureData
    | PreModelCallData
    | PostModelCallData
    | PreHandoffData
    | PostHandoffData
    | OnErrorData
    | OnStartData
    | OnStopData
    | PreCompactData
    | NotificationData
    | UserPromptSubmitData
    | PermissionRequestData
)


@dataclass(frozen=True)
class ToolAnnotations:
    """Metadata about a tool's behavior for permission and UI decisions."""

    read_only: bool = False
    destructive: bool = False
    open_world: bool = False


@dataclass
class SDKMetrics:
    """Per-run SDK-level metrics extending Pydantic AI's RunUsage."""

    hook_invocations: int = 0
    guardrail_checks: int = 0
    handoff_count: int = 0
    guardrail_trips: int = 0
    hooks_blocked: int = 0
