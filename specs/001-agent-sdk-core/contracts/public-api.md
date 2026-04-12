# Public API Contract: typed_agent_sdk

**Phase 1 Output** | **Date**: 2026-03-15

## Package Exports (`typed_agent_sdk/__init__.py`)

```python
# Core orchestration
from typed_agent_sdk.runner import Runner, RunResult
from typed_agent_sdk.hooks import Hook, HookEvent, HookMatcher, HookResult
from typed_agent_sdk.guardrails import Guardrail, GuardrailResult, InputGuardrail, OutputGuardrail
from typed_agent_sdk.skills import Skill, SkillMarkdown, load_skills
from typed_agent_sdk.handoffs import Handoff, HandoffResult
from typed_agent_sdk.permissions import PermissionPolicy, PermissionMode, PermissionResult
from typed_agent_sdk.system_tools import SystemTools
from typed_agent_sdk.session import Session, SessionBackend, JSONSessionBackend
from typed_agent_sdk.transport import Transport, InProcessTransport
from typed_agent_sdk.types import ToolAnnotations, SDKMetrics, HookEventData
from typed_agent_sdk.errors import (
    AgentSDKError,
    SkillConflictError,
    HandoffConfigError,
    HandoffDepthError,
    GuardrailTripwireError,
    PermissionDeniedError,
    SkillLoadError,
    SessionNotFoundError,
)
from typed_agent_sdk.testing import HookRecorder, GuardrailRecorder

# Re-export key Pydantic AI types for convenience
from pydantic_ai import Agent, RunContext, Tool
```

## API Signatures

### Runner

```python
class Runner(Generic[DepsT, OutputT]):
    def __init__(
        self,
        agent: Agent[DepsT, OutputT],
        *,
        hooks: list[Hook] | None = None,
        guardrails: list[Guardrail[DepsT]] | None = None,
        skills: list[Skill[DepsT]] | None = None,
        handoffs: list[Handoff[DepsT]] | None = None,
        permissions: PermissionPolicy | None = None,
        max_turns: int | None = None,
        max_budget_tokens: int | None = None,
        session_backend: SessionBackend | None = None,
        transport: Transport | None = None,
        debug_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None: ...

    async def run(
        self,
        prompt: str | Sequence[UserContent] | AsyncIterable[str],
        *,
        deps: DepsT = ...,
        session_id: str | None = None,
        model: Model | KnownModelName | None = None,
        model_settings: ModelSettings | None = None,
        message_history: list[ModelMessage] | None = None,
    ) -> RunResult[OutputT]: ...

    def run_sync(
        self,
        prompt: str,
        *,
        deps: DepsT = ...,
        **kwargs: Any,
    ) -> RunResult[OutputT]: ...

    async def run_stream(
        self,
        prompt: str,
        *,
        deps: DepsT = ...,
        event_handler: EventStreamHandler[DepsT] | None = None,
        **kwargs: Any,
    ) -> AsyncContextManager[AgentStream[DepsT, OutputT]]: ...

    async def interrupt(self) -> None: ...

    async def resume(
        self,
        session_id: str,
        prompt: str,
        *,
        deps: DepsT = ...,
        **kwargs: Any,
    ) -> RunResult[OutputT]: ...

    async def fork_session(
        self,
        session_id: str,
    ) -> str: ...  # Returns new session_id
```

### Hook

```python
class Hook:
    def __init__(
        self,
        event: HookEvent,
        callback: HookCallback[Any],
        *,
        matcher: HookMatcher | str | None = None,  # str shortcut for pattern
        priority: int = 100,
        fire_and_forget: bool = False,
    ) -> None: ...

# Convenience decorators
def on_pre_tool_use(
    matcher: str | None = None,
    *,
    priority: int = 100,
) -> Callable[[HookCallback[DepsT]], Hook]: ...

def on_post_tool_use(matcher: str | None = None, ...) -> ...: ...
def on_error(...) -> ...: ...
def on_start(...) -> ...: ...
def on_stop(...) -> ...: ...
# ... one decorator per event type
```

### Guardrail

```python
class Guardrail(Generic[DepsT]):
    def __init__(
        self,
        name: str,
        check: GuardrailCheckFunc[DepsT],
        *,
        kind: Literal["input", "output"],
        timeout: float | None = None,
        fail_closed: bool = False,
    ) -> None: ...

# Convenience constructors
def input_guardrail(
    name: str,
    *,
    timeout: float | None = None,
    fail_closed: bool = False,
) -> Callable[[GuardrailCheckFunc[DepsT]], Guardrail[DepsT]]: ...

def output_guardrail(name: str, ...) -> ...: ...
```

### Skill

```python
class Skill(AbstractToolset[DepsT], Generic[DepsT]):
    def __init__(
        self,
        name: str,
        *,
        description: str = "",
        tools: list[Tool[DepsT] | ToolFuncEither[DepsT, ...]] | None = None,
        instructions: str | None = None,
        hooks: list[Hook] | None = None,
        guardrails: list[Guardrail[DepsT]] | None = None,
        permissions: PermissionPolicy | None = None,
    ) -> None: ...

def load_skills(
    directory: str | Path,
    *,
    recursive: bool = True,
) -> list[SkillMarkdown]: ...
```

### Handoff

```python
class Handoff(Generic[DepsT]):
    def __init__(
        self,
        target: Agent[DepsT, Any],
        *,
        description: str,
        filter: Callable[[RunContext[DepsT]], bool] | None = None,
        context_transformer: Callable[[list[ModelMessage]], list[ModelMessage]] | None = None,
        max_depth: int = 10,
    ) -> None: ...
```

### PermissionPolicy

```python
class PermissionPolicy:
    def __init__(
        self,
        *,
        mode: PermissionMode = PermissionMode.default,
        allowed_tools: list[str] | None = None,
        blocked_tools: list[str] | None = None,
        require_approval: list[str] | None = None,
        approval_callback: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None,
    ) -> None: ...

    async def check(self, tool_name: str, tool_args: dict[str, Any]) -> PermissionResult: ...
    def add_rule(self, rule_type: str, pattern: str) -> None: ...
    def remove_rule(self, rule_type: str, pattern: str) -> None: ...
```

### SystemTools

```python
class SystemTools(Skill[Any]):
    def __init__(
        self,
        *,
        allowed: list[str] | None = None,  # None = all tools
        cwd: str | Path | None = None,
        bash_timeout: float = 120.0,
        env: dict[str, str] | None = None,
    ) -> None: ...
```

### Testing Utilities

```python
class HookRecorder:
    """Records hook invocations for testing assertions."""
    events: list[tuple[HookEvent, HookEventData]]

    def assert_called(self, event: HookEvent, *, times: int | None = None) -> None: ...
    def assert_not_called(self, event: HookEvent) -> None: ...
    def assert_order(self, events: list[HookEvent]) -> None: ...
    def get_hook(self) -> Hook: ...  # Returns a Hook that records

class GuardrailRecorder:
    """Records guardrail checks for testing assertions."""
    checks: list[tuple[str, GuardrailResult]]

    def assert_tripped(self, name: str | None = None) -> None: ...
    def assert_passed(self, name: str | None = None) -> None: ...
```
