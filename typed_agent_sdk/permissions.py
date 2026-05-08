"""Permission policies for typed_agent_sdk.

Controls which tools an agent can use via glob-pattern based
allow/block lists and human approval requirements.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from typed_agent_sdk._utils import glob_match

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from typed_agent_sdk.hooks import Hook
    from typed_agent_sdk.types import SDKMetrics

logger = logging.getLogger('typed_agent_sdk.permissions')

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport for Python 3.10."""


class PermissionMode(StrEnum):
    """Predefined permission presets."""

    default = 'default'
    readOnly = 'readOnly'
    unrestricted = 'unrestricted'
    planOnly = 'planOnly'


@dataclass(frozen=True)
class PermissionResult:
    """Result of a permission check."""

    allowed: bool
    reason: str | None = None
    requires_approval: bool = False


@dataclass
class PermissionPolicy:
    """Declarative access control policy for tools.

    Args:
        mode: Predefined permission preset.
        allowed_tools: Glob patterns for allowed tools. Empty = allow all.
        blocked_tools: Glob patterns for blocked tools (overrides allowed).
        require_approval: Glob patterns for tools requiring human approval.
        approval_callback: Async callback for approval decisions.
    """

    mode: PermissionMode = PermissionMode.default
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    require_approval: list[str] = field(default_factory=list)
    approval_callback: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None

    def check(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> PermissionResult:
        """Check if a tool is allowed by this policy.

        Evaluation order: blocked > allowed > mode > approval.
        """
        # 1. Check blocked list (always wins)
        for pattern in self.blocked_tools:
            if glob_match(pattern, tool_name):
                return PermissionResult(
                    allowed=False,
                    reason=f'Tool "{tool_name}" blocked by pattern "{pattern}"',
                )

        # 2. Check allowed list (if specified, only matching tools pass)
        if self.allowed_tools and not any(glob_match(p, tool_name) for p in self.allowed_tools):
            return PermissionResult(
                allowed=False,
                reason=f'Tool "{tool_name}" not in allowed list',
            )

        # 3. Check mode
        if self.mode == PermissionMode.planOnly:
            return PermissionResult(
                allowed=False,
                reason='Plan-only mode: no tool execution allowed',
            )

        # 4. Check approval requirement
        for pattern in self.require_approval:
            if glob_match(pattern, tool_name):
                return PermissionResult(
                    allowed=True,
                    reason=f'Tool "{tool_name}" requires approval',
                    requires_approval=True,
                )

        return PermissionResult(allowed=True)

    def add_rule(self, rule_type: str, pattern: str) -> None:
        """Add a permission rule at runtime.

        Args:
            rule_type: One of "allowed", "blocked", "approval".
            pattern: Glob pattern to add.
        """
        if rule_type == 'allowed':
            self.allowed_tools.append(pattern)
        elif rule_type == 'blocked':
            self.blocked_tools.append(pattern)
        elif rule_type == 'approval':
            self.require_approval.append(pattern)
        else:
            raise ValueError(
                f'Unknown rule type: {rule_type}. Use "allowed", "blocked", or "approval".'
            )

    def remove_rule(self, rule_type: str, pattern: str) -> None:
        """Remove a permission rule at runtime."""
        target = {
            'allowed': self.allowed_tools,
            'blocked': self.blocked_tools,
            'approval': self.require_approval,
        }.get(rule_type)
        if target is None:
            raise ValueError(f'Unknown rule type: {rule_type}')
        if pattern in target:
            target.remove(pattern)

    def filter_tools(self, tool_names: list[str]) -> list[str]:
        """Filter a list of tool names according to this policy.

        Returns only the tools that are allowed.
        """
        return [name for name in tool_names if self.check(name).allowed]

    async def check_with_hooks(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
        hooks: list[Hook] | None = None,
        metrics: SDKMetrics | None = None,
    ) -> PermissionResult:
        """Async permission check that consults PermissionRequest hooks.

        Resolution order when ``requires_approval`` is True:
          1. Fire ``PermissionRequest`` hooks. A hook returning ``block=True`` denies.
          2. If a non-blocking hook responded, treat the request as approved.
          3. Otherwise, fall back to ``approval_callback`` if set.
          4. Otherwise, return the original ``requires_approval=True`` result so
             the caller can implement its own approval flow.
        """
        result = self.check(tool_name, tool_args)
        if not result.requires_approval:
            return result

        args = tool_args or {}

        if hooks:
            from typed_agent_sdk.hooks import fire_permission_request

            hook_result = await fire_permission_request(
                hooks, tool_name, args, reason=result.reason, metrics=metrics
            )
            if hook_result is not None and hook_result.block:
                return PermissionResult(
                    allowed=False,
                    reason=hook_result.stop_reason
                    or f'Tool "{tool_name}" denied by PermissionRequest hook',
                )
            if hook_result is not None:
                # A hook responded without blocking — treat as approval.
                return PermissionResult(allowed=True, requires_approval=False)

        if self.approval_callback is not None:
            approved = await self.approval_callback(tool_name, args)
            if approved:
                return PermissionResult(allowed=True, requires_approval=False)
            return PermissionResult(
                allowed=False,
                reason=f'Tool "{tool_name}" denied by approval_callback',
            )

        return result
