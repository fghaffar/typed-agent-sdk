"""Permission policies for agent_sdk.

Controls which tools an agent can use via glob-pattern based
allow/block lists and human approval requirements.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from agent_sdk._utils import glob_match
from agent_sdk.errors import PatternError, PermissionCallbackError, PermissionDeniedError

logger = logging.getLogger('agent_sdk.permissions')

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        pass


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
        if self.allowed_tools:
            if not any(glob_match(p, tool_name) for p in self.allowed_tools):
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
            raise ValueError(f'Unknown rule type: {rule_type}. Use "allowed", "blocked", or "approval".')

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
