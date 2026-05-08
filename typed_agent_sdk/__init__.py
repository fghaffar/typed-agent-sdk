"""typed-agent-sdk: A lightweight, model-agnostic, type-safe agent SDK built on Pydantic AI.

Provides hooks, guardrails, skills, handoffs, and permissions as a thin
orchestration layer on top of Pydantic AI.
"""

from __future__ import annotations

from typed_agent_sdk.errors import (
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
from typed_agent_sdk.execution import (
    ExecResult,
    ExecutionBackend,
    LocalBackend,
)
from typed_agent_sdk.guardrails import (
    Guardrail,
    GuardrailResult,
    input_guardrail,
    output_guardrail,
)
from typed_agent_sdk.handoffs import Handoff, HandoffResult
from typed_agent_sdk.hooks import (
    Hook,
    HookMatcher,
    HookResult,
    HookToolset,
    fire_permission_request,
    fire_user_prompt_submit,
    on_error,
    on_notification,
    on_permission_request,
    on_post_handoff,
    on_post_model_call,
    on_post_tool_use,
    on_post_tool_use_failure,
    on_pre_compact,
    on_pre_handoff,
    on_pre_model_call,
    on_pre_tool_use,
    on_start,
    on_stop,
    on_subagent_start,
    on_subagent_stop,
    on_user_prompt_submit,
)
from typed_agent_sdk.permissions import PermissionMode, PermissionPolicy, PermissionResult
from typed_agent_sdk.query import (
    AgentOptions,
    AgentSDKClient,
    Message,
    ResultMessage,
    TextMessage,
    ToolCallMessage,
    ToolResultMessage,
    query,
    query_sync,
)
from typed_agent_sdk.runner import Runner, RunResult
from typed_agent_sdk.session import JSONSessionBackend, Session, SessionBackend
from typed_agent_sdk.skills import Skill, SkillMarkdown, load_skills
from typed_agent_sdk.system_tools import SystemTools
from typed_agent_sdk.testing import GuardrailRecorder, HookRecorder
from typed_agent_sdk.transport import InProcessTransport, Transport
from typed_agent_sdk.types import (
    HookEvent,
    HookEventData,
    SDKMetrics,
    ToolAnnotations,
)

__all__ = [
    'AgentOptions',
    'AgentSDKClient',
    # Errors
    'AgentSDKError',
    'BinaryFileError',
    'BudgetExhausted',
    'EditAmbiguousError',
    'EditNotFoundError',
    # Execution backends
    'ExecResult',
    'ExecutionBackend',
    # Guardrails
    'Guardrail',
    'GuardrailExecutionError',
    'GuardrailRecorder',
    'GuardrailResult',
    'GuardrailTripwireError',
    # Handoffs
    'Handoff',
    'HandoffConfigError',
    'HandoffDepthError',
    'HandoffExecutionError',
    'HandoffResult',
    # Hooks
    'Hook',
    'HookEvent',
    'HookEventData',
    'HookExecutionError',
    'HookMatcher',
    # Testing
    'HookRecorder',
    'HookResult',
    'HookToolset',
    'InProcessTransport',
    'JSONSessionBackend',
    'LocalBackend',
    'MaxTurnsExceeded',
    'Message',
    'PatternError',
    'PermissionCallbackError',
    'PermissionDeniedError',
    # Permissions
    'PermissionMode',
    'PermissionPolicy',
    'PermissionResult',
    'ProcessError',
    'ResultMessage',
    'RunResult',
    # Runner
    'Runner',
    # Types
    'SDKMetrics',
    # Session
    'Session',
    'SessionBackend',
    'SessionNotFoundError',
    'SessionPersistenceError',
    'SessionVersionError',
    # Skills
    'Skill',
    'SkillConflictError',
    'SkillLoadError',
    'SkillMarkdown',
    'SystemTools',
    'TextMessage',
    'ToolAnnotations',
    'ToolCallMessage',
    'ToolResultMessage',
    # Transport
    'Transport',
    'fire_permission_request',
    'fire_user_prompt_submit',
    'input_guardrail',
    'load_skills',
    'on_error',
    'on_notification',
    'on_permission_request',
    'on_post_handoff',
    'on_post_model_call',
    'on_post_tool_use',
    'on_post_tool_use_failure',
    'on_pre_compact',
    'on_pre_handoff',
    'on_pre_model_call',
    'on_pre_tool_use',
    'on_start',
    'on_stop',
    'on_subagent_start',
    'on_subagent_stop',
    'on_user_prompt_submit',
    'output_guardrail',
    # Query
    'query',
    'query_sync',
]

__version__ = '0.2.0'
