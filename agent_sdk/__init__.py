"""agent-sdk: A lightweight, model-agnostic, type-safe agent SDK built on Pydantic AI.

Provides hooks, guardrails, skills, handoffs, and permissions as a thin
orchestration layer on top of Pydantic AI.
"""

from __future__ import annotations

from agent_sdk.errors import (
    AgentSDKError,
    BinaryFileError,
    BudgetExhausted,
    EditAmbiguousError,
    EditNotFoundError,
    GuardrailExecutionError,
    GuardrailTripwireError,
    HandoffConfigError,
    HandoffDepthError,
    HandoffExecutionError,
    HookExecutionError,
    MaxTurnsExceeded,
    PatternError,
    PermissionCallbackError,
    PermissionDeniedError,
    ProcessError,
    SessionNotFoundError,
    SessionPersistenceError,
    SessionVersionError,
    SkillConflictError,
    SkillLoadError,
)
from agent_sdk.hooks import (
    Hook,
    HookMatcher,
    HookResult,
    HookToolset,
    on_error,
    on_post_tool_use,
    on_pre_tool_use,
    on_start,
    on_stop,
)
from agent_sdk.runner import Runner, RunResult
from agent_sdk.types import (
    HookEvent,
    HookEventData,
    SDKMetrics,
    ToolAnnotations,
)

__all__ = [
    # Runner
    'Runner',
    'RunResult',
    # Hooks
    'Hook',
    'HookEvent',
    'HookEventData',
    'HookMatcher',
    'HookResult',
    'HookToolset',
    'on_error',
    'on_post_tool_use',
    'on_pre_tool_use',
    'on_start',
    'on_stop',
    # Types
    'SDKMetrics',
    'ToolAnnotations',
    # Errors
    'AgentSDKError',
    'BinaryFileError',
    'BudgetExhausted',
    'EditAmbiguousError',
    'EditNotFoundError',
    'GuardrailExecutionError',
    'GuardrailTripwireError',
    'HandoffConfigError',
    'HandoffDepthError',
    'HandoffExecutionError',
    'HookExecutionError',
    'MaxTurnsExceeded',
    'PatternError',
    'PermissionCallbackError',
    'PermissionDeniedError',
    'ProcessError',
    'SessionNotFoundError',
    'SessionPersistenceError',
    'SessionVersionError',
    'SkillConflictError',
    'SkillLoadError',
]

__version__ = '0.1.0'
