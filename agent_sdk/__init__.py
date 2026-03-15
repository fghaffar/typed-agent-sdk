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
from agent_sdk.types import (
    HookEvent,
    HookEventData,
    SDKMetrics,
    ToolAnnotations,
)

__all__ = [
    # Types
    'HookEvent',
    'HookEventData',
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
