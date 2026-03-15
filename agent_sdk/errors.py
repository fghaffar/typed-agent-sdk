"""Exception hierarchy for agent_sdk."""

from __future__ import annotations


class AgentSDKError(Exception):
    """Base exception for all agent_sdk errors."""


# --- Hook Errors ---


class HookExecutionError(AgentSDKError):
    """Raised when a hook callback fails during execution."""

    def __init__(self, hook_event: str, original_error: Exception) -> None:
        self.hook_event = hook_event
        self.original_error = original_error
        super().__init__(f'Hook failed during {hook_event}: {original_error}')


# --- Guardrail Errors ---


class GuardrailTripwireError(AgentSDKError):
    """Raised when a guardrail tripwire is triggered, halting execution."""

    def __init__(self, guardrail_name: str, reason: str | None = None) -> None:
        self.guardrail_name = guardrail_name
        self.reason = reason
        msg = f'Guardrail "{guardrail_name}" tripped'
        if reason:
            msg += f': {reason}'
        super().__init__(msg)


class GuardrailExecutionError(AgentSDKError):
    """Raised when a guardrail check function fails."""

    def __init__(self, guardrail_name: str, original_error: Exception) -> None:
        self.guardrail_name = guardrail_name
        self.original_error = original_error
        super().__init__(f'Guardrail "{guardrail_name}" failed: {original_error}')


# --- Skill Errors ---


class SkillConflictError(AgentSDKError):
    """Raised when two skills register tools with the same name."""

    def __init__(self, tool_name: str, skill_a: str, skill_b: str) -> None:
        self.tool_name = tool_name
        self.skill_a = skill_a
        self.skill_b = skill_b
        super().__init__(
            f'Tool name conflict: "{tool_name}" registered by both '
            f'skill "{skill_a}" and skill "{skill_b}"'
        )


class SkillLoadError(AgentSDKError):
    """Raised when a markdown skill file cannot be loaded or parsed."""

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(f'Failed to load skill from {file_path}: {reason}')


# --- Handoff Errors ---


class HandoffConfigError(AgentSDKError):
    """Raised when a handoff target is misconfigured."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class HandoffDepthError(AgentSDKError):
    """Raised when handoff chain exceeds maximum depth."""

    def __init__(self, depth: int, max_depth: int) -> None:
        self.depth = depth
        self.max_depth = max_depth
        super().__init__(
            f'Handoff depth {depth} exceeds maximum {max_depth}. '
            f'Possible circular handoff chain.'
        )


class HandoffExecutionError(AgentSDKError):
    """Raised when a handoff target agent fails during execution."""

    def __init__(self, target_agent: str, original_error: Exception) -> None:
        self.target_agent = target_agent
        self.original_error = original_error
        super().__init__(f'Handoff to "{target_agent}" failed: {original_error}')


# --- Permission Errors ---


class PermissionDeniedError(AgentSDKError):
    """Raised when a tool is blocked by the permission policy."""

    def __init__(self, tool_name: str, reason: str | None = None) -> None:
        self.tool_name = tool_name
        self.reason = reason
        msg = f'Permission denied for tool "{tool_name}"'
        if reason:
            msg += f': {reason}'
        super().__init__(msg)


class PermissionCallbackError(AgentSDKError):
    """Raised when a permission approval callback fails."""

    def __init__(self, tool_name: str, original_error: Exception) -> None:
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f'Approval callback failed for "{tool_name}": {original_error}')


class PatternError(AgentSDKError):
    """Raised when an invalid glob pattern is provided."""

    def __init__(self, pattern: str, reason: str) -> None:
        self.pattern = pattern
        self.reason = reason
        super().__init__(f'Invalid pattern "{pattern}": {reason}')


# --- Runner Errors ---


class MaxTurnsExceeded(AgentSDKError):
    """Raised when the agent exceeds the configured maximum turns."""

    def __init__(self, turns: int, max_turns: int) -> None:
        self.turns = turns
        self.max_turns = max_turns
        super().__init__(f'Agent exceeded max turns: {turns}/{max_turns}')


class BudgetExhausted(AgentSDKError):
    """Raised when token usage exceeds the configured budget."""

    def __init__(self, tokens_used: int, max_tokens: int) -> None:
        self.tokens_used = tokens_used
        self.max_tokens = max_tokens
        super().__init__(f'Token budget exhausted: {tokens_used}/{max_tokens}')


# --- SystemTools Errors ---


class EditNotFoundError(AgentSDKError):
    """Raised when old_string is not found in the target file."""

    def __init__(self, file_path: str, old_string: str) -> None:
        self.file_path = file_path
        self.old_string = old_string
        preview = old_string[:50] + '...' if len(old_string) > 50 else old_string
        super().__init__(f'String not found in {file_path}: "{preview}"')


class EditAmbiguousError(AgentSDKError):
    """Raised when old_string appears multiple times in the target file."""

    def __init__(self, file_path: str, old_string: str, count: int) -> None:
        self.file_path = file_path
        self.old_string = old_string
        self.count = count
        preview = old_string[:50] + '...' if len(old_string) > 50 else old_string
        super().__init__(
            f'String appears {count} times in {file_path}: "{preview}". '
            f'Must be unique for unambiguous replacement.'
        )


class BinaryFileError(AgentSDKError):
    """Raised when a binary file is encountered where text is expected."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        super().__init__(f'File is binary: {file_path}')


class ProcessError(AgentSDKError):
    """Raised when a subprocess fails."""

    def __init__(
        self, command: str, exit_code: int | None = None, stderr: str | None = None
    ) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        msg = f'Process failed: {command}'
        if exit_code is not None:
            msg += f' (exit code {exit_code})'
        if stderr:
            msg += f'\n{stderr[:500]}'
        super().__init__(msg)


# --- Session Errors ---


class SessionNotFoundError(AgentSDKError):
    """Raised when a session cannot be found."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f'Session not found: {session_id}')


class SessionPersistenceError(AgentSDKError):
    """Raised when session save/load fails."""

    def __init__(self, operation: str, original_error: Exception) -> None:
        self.operation = operation
        self.original_error = original_error
        super().__init__(f'Session {operation} failed: {original_error}')


class SessionVersionError(AgentSDKError):
    """Raised when a session's schema version doesn't match current."""

    def __init__(self, found_version: str, expected_version: str) -> None:
        self.found_version = found_version
        self.expected_version = expected_version
        super().__init__(
            f'Session schema version mismatch: found {found_version}, '
            f'expected {expected_version}'
        )
