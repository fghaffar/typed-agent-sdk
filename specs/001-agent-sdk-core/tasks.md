# Tasks: Agent SDK Core

**Input**: Design documents from `/specs/001-agent-sdk-core/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Test tasks included — the constitution mandates test-first development (Principle VII), and the plan targets 90%+ coverage with ~45 test cases.

**Organization**: Tasks grouped by user story. Each story is independently testable after the Foundational phase completes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Package**: `agent_sdk/` at repository root
- **Tests**: `tests/` at repository root
- **Examples**: `examples/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, packaging, and tooling

- [x] T001 Create project directory structure: `agent_sdk/`, `tests/`, `examples/`, `examples/skills/` per plan.md
- [x] T002 Create `pyproject.toml` with metadata (name=agent-sdk, version=0.1.0, python>=3.11), dependencies (pydantic-ai>=1.0, pydantic>=2.0, typing-extensions>=4.0, PyYAML>=6.0), optional extras ([telemetry], [dev]), and build system
- [x] T003 [P] Create `agent_sdk/py.typed` marker file (PEP 561)
- [x] T004 [P] Configure `ruff` in pyproject.toml (linting + formatting rules)
- [x] T005 [P] Configure `mypy` strict mode in pyproject.toml (mypy --strict settings)
- [x] T006 [P] Create `tests/conftest.py` with shared fixtures: FunctionModel agent fixture, sample tool fixtures, tmp_path skill directory fixture
- [ ] T007 Create `.github/workflows/ci.yml` for pytest + ruff + mypy (if GitHub Actions desired)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, errors, and utilities that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T008 Create `agent_sdk/types.py` with shared types: HookEvent (StrEnum with 11 values), HookEventData union type (per-event dataclasses), ToolAnnotations dataclass (read_only, destructive, open_world), SDKMetrics dataclass (hook_invocations, guardrail_checks, handoff_count, guardrail_trips, hooks_blocked)
- [x] T009 [P] Create `agent_sdk/errors.py` with full exception hierarchy: AgentSDKError (base), GuardrailTripwireError, GuardrailExecutionError, HookExecutionError, SkillConflictError, SkillLoadError, HandoffConfigError, HandoffDepthError, HandoffExecutionError, PermissionDeniedError, MaxTurnsExceeded, BudgetExhausted, EditNotFoundError, EditAmbiguousError, BinaryFileError, ProcessError, SessionNotFoundError, SessionPersistenceError, SessionVersionError, PatternError, PermissionCallbackError
- [x] T010 [P] Create `agent_sdk/_utils.py` with internal utilities: `glob_match(pattern, name) -> bool` using fnmatch, `parse_frontmatter(content) -> tuple[dict, str]` for robust YAML frontmatter extraction (handles `---` in body), `validate_path_sandbox(path, cwd) -> Path` for path traversal prevention, `truncate_output(text, max_bytes) -> str` for output capping
- [x] T011 [P] Create `tests/test_types.py` with tests for HookEvent enum values, HookEventData construction, SDKMetrics defaults
- [x] T012 [P] Create `tests/test_utils.py` with tests for glob_match (wildcards, exact, special chars), parse_frontmatter (valid, invalid YAML, `---` in body, missing frontmatter), validate_path_sandbox (valid subpath, `../` traversal, absolute path outside cwd, symlink escape), truncate_output (under limit, at limit, over limit)
- [x] T013 Create `agent_sdk/__init__.py` with all public exports per contracts/public-api.md (initially importing from types and errors only; other imports added as modules are created)

**Checkpoint**: Foundation ready — types, errors, utilities, and test fixtures in place. User story implementation can begin.

---

## Phase 3: User Story 1 — Single Agent with Hooks (Priority: P1) MVP

**Goal**: Developers can create agents with lifecycle hooks that fire around tool calls, with regex-based matching, blocking, arg modification, and priority ordering.

**Independent Test**: Create an agent with FunctionModel, register PreToolUse/PostToolUse hooks, run the agent, and assert hooks fired with correct event data in correct order.

### Tests for User Story 1

- [ ] T014 [P] [US1] Create `tests/test_hooks.py` with tests: test_hook_fires_on_pre_tool_use (FunctionModel agent with tool, PreToolUse hook, assert hook called with tool_name + args), test_hook_fires_on_post_tool_use (assert result available), test_hook_matcher_regex_filters (hook with pattern "Write|Edit" skips "Read" tool), test_hook_matcher_none_matches_all, test_hook_blocks_tool_execution (PreToolUse returns block=True, assert tool NOT called), test_hook_modifies_args (PreToolUse returns modified_args, assert tool receives new args), test_hooks_execute_in_priority_order (3 hooks with priority 1,2,3, assert order), test_multiple_hooks_same_event (all fire), test_hook_timeout_skips (hook that sleeps beyond timeout, assert skipped with warning), test_fire_and_forget_hook (non-blocking hook, assert run completes without waiting), test_on_error_hook_fires (tool raises, OnError hook fires with error details), test_hook_invalid_regex_raises (HookMatcher with bad regex raises at construction), test_hook_bad_return_type_raises (hook returns non-HookResult, assert HookExecutionError)

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create `agent_sdk/hooks.py` with: HookMatcher dataclass (pattern: str|None, timeout: float|None), HookResult dataclass (block, modified_args, modified_result, additional_context, suppress_output, continue_, stop_reason), HookCallback Protocol, Hook dataclass (event, callback, matcher, priority, fire_and_forget), convenience decorators (on_pre_tool_use, on_post_tool_use, on_error, on_start, on_stop, on_pre_model_call, on_post_model_call, on_pre_handoff, on_post_handoff, on_pre_compact, on_notification)
- [ ] T016 [US1] Create internal `HookToolset` class in `agent_sdk/hooks.py` extending WrapperToolset: override `call_tool()` to fire PreToolUse hooks (with matcher filtering, priority sorting, timeout, block/modify support), execute wrapped tool, fire PostToolUse hooks. Handle fire-and-forget hooks via `asyncio.create_task()`. Handle hook errors via HookExecutionError.
- [ ] T017 [US1] Create minimal `agent_sdk/runner.py` with Runner class (agent, hooks params only for now): `run()` method that wraps agent toolsets with HookToolset via `agent.override(toolsets=...)`, fires OnStart/OnStop hooks around `agent.run()`, returns RunResult. Include re-entrancy guard (asyncio.Lock or flag), empty prompt validation (ValueError), and OnError hook cascade.
- [ ] T018 [US1] Create `agent_sdk/runner.py` RunResult dataclass: output (generic OutputT), messages, usage (RunUsage from Pydantic AI), sdk_metrics (SDKMetrics), session_id, stop_reason
- [ ] T019 [US1] Update `agent_sdk/__init__.py` to export Hook, HookEvent, HookMatcher, HookResult, Runner, RunResult, and all hook decorators
- [ ] T020 [US1] Create `examples/simple_agent.py` demonstrating agent with PreToolUse logging hook per quickstart.md

**Checkpoint**: User Story 1 complete. An agent with hooks works end-to-end. This is the MVP.

---

## Phase 4: User Story 2 — Guardrails for Input/Output Safety (Priority: P1)

**Goal**: Developers can add input and output guardrails that run in parallel, validate prompts/responses, and halt execution via tripwire.

**Independent Test**: Create an input guardrail that blocks prohibited content, run the agent, and assert GuardrailTripwireError is raised before model call.

### Tests for User Story 2

- [ ] T021 [P] [US2] Create `tests/test_guardrails.py` with tests: test_input_guardrail_passes (guardrail returns passed=True, agent runs normally), test_input_guardrail_tripwire_halts (returns tripwire=True, assert GuardrailTripwireError raised before model call), test_output_guardrail_tripwire_halts (checks model response, trips), test_guardrails_run_in_parallel (3 guardrails with sleep, assert total time < sum of sleeps), test_guardrail_fail_without_tripwire_logs (passed=False without tripwire, assert warning logged, execution continues), test_guardrail_typed_deps (guardrail accesses RunContext[MyDeps].deps), test_zero_guardrails_skips_phase, test_guardrail_timeout_fail_open (slow guardrail, fail_closed=False, assert passes), test_guardrail_timeout_fail_closed (slow guardrail, fail_closed=True, assert tripwire), test_guardrail_exception_wraps (guardrail raises ValueError, assert GuardrailExecutionError)

### Implementation for User Story 2

- [ ] T022 [P] [US2] Create `agent_sdk/guardrails.py` with: GuardrailResult dataclass (passed, reason, tripwire), GuardrailCheckFunc Protocol, Guardrail[DepsT] generic class (name, check, kind, timeout, fail_closed), InputGuardrail/OutputGuardrail convenience aliases, input_guardrail/output_guardrail decorator factories
- [ ] T023 [US2] Extend `agent_sdk/runner.py` Runner: add guardrails parameter, implement `_run_input_guardrails()` (asyncio.gather with per-guardrail asyncio.wait_for timeout, fail-open/fail-closed logic, tripwire short-circuit), implement `_run_output_guardrails()` (same pattern on RunResult.output). Wire into run() lifecycle: OnStart → input guardrails → agent.run() → output guardrails → OnStop. Log GuardrailResult.reason for non-passing guardrails.
- [ ] T024 [US2] Update `agent_sdk/__init__.py` to export Guardrail, GuardrailResult, InputGuardrail, OutputGuardrail, input_guardrail, output_guardrail
- [ ] T025 [US2] Create `examples/guardrailed_agent.py` demonstrating input content filter guardrail per quickstart.md

**Checkpoint**: User Stories 1 AND 2 complete. Hooks + Guardrails work independently.

---

## Phase 5: User Story 7 — Markdown-Based Skill Definitions (Priority: P1)

**Goal**: Non-developers can define skills as markdown files with YAML frontmatter. SDK auto-discovers and loads them.

**Independent Test**: Create a `skills/test-skill.md` file with frontmatter, call `load_skills()`, and assert the skill has correct name, description, tools, and instructions.

### Tests for User Story 7

- [ ] T026 [P] [US7] Create `tests/test_skill_markdown.py` with tests: test_load_valid_skill_md (valid frontmatter + body, assert SkillMarkdown fields), test_load_skill_with_arguments_placeholder ($ARGUMENTS substitution), test_load_nested_directory_namespacing (skills/category/skill.md → "category.skill"), test_load_invalid_yaml_raises_skill_load_error (bad YAML, assert SkillLoadError with file path), test_load_missing_required_fields_raises (no name field), test_load_non_utf8_file_raises (binary file in skills dir), test_load_frontmatter_with_dashes_in_body (--- appears in markdown body, not treated as frontmatter delimiter), test_load_empty_directory_returns_empty_list, test_load_skill_with_handoffs_frontmatter, test_yaml_safe_load_blocks_code_execution (!!python/object tag in YAML)

### Implementation for User Story 7

- [ ] T027 [P] [US7] Create markdown skill loading in `agent_sdk/skills.py`: `load_skills(directory, recursive=True) -> list[SkillMarkdown]` function, SkillMarkdown dataclass (name, description, tools, handoffs, instructions, source_path). Uses `_utils.parse_frontmatter()` and `yaml.safe_load()`. Validates required fields (name, description). Supports nested directory namespacing. Handles $ARGUMENTS placeholder.
- [ ] T028 [US7] Create `examples/skills/code-reviewer.md` example markdown skill per quickstart.md
- [ ] T029 [US7] Create `examples/skills/researcher.md` example markdown skill
- [ ] T030 [US7] Update `agent_sdk/__init__.py` to export SkillMarkdown, load_skills

**Checkpoint**: Markdown skills can be loaded and parsed. No Python code required to define a skill.

---

## Phase 6: User Story 3 — Composable Skills/Plugins (Priority: P2)

**Goal**: Developers package tools, instructions, hooks, and guardrails into reusable Skill bundles that compose cleanly on agents.

**Independent Test**: Create a Skill with tools + instructions + hook, attach to agent via Runner, and assert all components register correctly.

### Tests for User Story 3

- [ ] T031 [P] [US3] Create `tests/test_skills.py` with tests: test_skill_registers_tools (Skill with 2 tools, attach to Runner, assert tools available), test_skill_appends_instructions (Skill with instructions, assert appended to system prompt), test_skill_registers_hooks (Skill with PreToolUse hook, assert hook fires), test_skill_registers_guardrails (Skill with guardrail, assert guardrail runs), test_two_skills_compose (2 Skills, no conflicts, all tools available), test_skill_name_conflict_raises (2 Skills with same tool name, assert SkillConflictError), test_skill_with_zero_tools_allowed (instructions-only Skill), test_skill_typed_deps (Skill[MyDeps] with tool accessing deps), test_skill_shared_across_agents (same Skill on 2 Runners, no shared mutable state), test_python_skill_overrides_markdown_skill (same name, Python wins with warning)

### Implementation for User Story 3

- [ ] T032 [P] [US3] Create `agent_sdk/skills.py` Skill[DepsT] class extending AbstractToolset[DepsT]: __init__(name, description, tools, instructions, hooks, guardrails, permissions), implement get_tools() returning tool dict, implement call_tool() delegating to function tools. Include tool name conflict detection across skills.
- [ ] T033 [US3] Extend `agent_sdk/runner.py` Runner: add skills parameter. On run(), merge skill toolsets into CombinedToolset, merge skill hooks into hooks list, merge skill guardrails into guardrails list, append skill instructions to agent system prompt via agent.override(). Handle SkillConflictError at registration time.
- [ ] T034 [US3] Update `agent_sdk/__init__.py` to export Skill
- [ ] T035 [US3] Create `examples/skill_composition.py` demonstrating multiple skills composed on one agent per quickstart.md

**Checkpoint**: Skills compose cleanly. Users can package and share reusable agent capabilities.

---

## Phase 7: User Story 4 — Multi-Agent Handoffs (Priority: P2)

**Goal**: Agents can delegate to specialist agents via tool calls. The LLM decides when to delegate.

**Independent Test**: Create triage agent with Handoff to specialist, provide prompt, and assert specialist handles it.

### Tests for User Story 4

- [ ] T036 [P] [US4] Create `tests/test_handoffs.py` with tests: test_handoff_delegates_to_target (triage agent with Handoff, FunctionModel returns handoff tool call, assert target agent runs), test_handoff_appears_as_tool (assert handoff description visible in tool list), test_handoff_shares_deps (both agents deps_type=SharedDeps, assert same deps instance), test_handoff_chain_propagates (A→B→C, result returns to A), test_handoff_max_depth_raises (depth 11 with max 10, assert HandoffDepthError), test_handoff_filter_excludes (filter returns False, handoff not in tool list), test_handoff_context_transformer (custom transformer modifies messages before target), test_pre_handoff_hook_fires (PreHandoff hook fires before delegation), test_post_handoff_hook_fires (PostHandoff hook fires after delegation), test_pre_handoff_hook_blocks (hook blocks handoff, tool returns blocked message)

### Implementation for User Story 4

- [ ] T037 [P] [US4] Create `agent_sdk/handoffs.py` with: Handoff[DepsT] generic class (target, description, filter, context_transformer, max_depth), HandoffResult dataclass (output, agent_name, depth, usage). Create internal `_create_handoff_tool()` that returns a Pydantic AI Tool wrapping the handoff logic: check depth via RunContext metadata, fire PreHandoff hooks, optionally transform context, call target.run(), fire PostHandoff hooks, return result.
- [ ] T038 [US4] Extend `agent_sdk/runner.py` Runner: add handoffs parameter. On run(), create handoff tools via `_create_handoff_tool()` for each Handoff, add to CombinedToolset alongside skill tools. Track handoff depth in RunContext metadata. Increment SDKMetrics.handoff_count.
- [ ] T039 [US4] Update `agent_sdk/__init__.py` to export Handoff, HandoffResult
- [ ] T040 [US4] Create `examples/multi_agent.py` demonstrating triage → coder → reviewer handoff per quickstart.md

**Checkpoint**: Multi-agent handoffs work. Users can build delegation hierarchies.

---

## Phase 8: User Story 8 — Built-in System Tools (Priority: P1)

**Goal**: Agents get real-world capabilities via built-in bash, file_read, file_write, file_edit, glob, grep tools.

**Independent Test**: Create agent with SystemTools(allowed=["file_read", "grep"]), run with FunctionModel, assert tools execute correctly on filesystem.

### Tests for User Story 8

- [ ] T041 [P] [US8] Create `tests/test_system_tools.py` with tests: test_bash_executes_command (echo "hello", assert stdout), test_bash_timeout_kills (sleep 999 with timeout=1, assert timeout message), test_bash_empty_command_raises (empty string, assert ValueError), test_bash_output_cap_truncates (command producing >5MB, assert truncated), test_bash_cwd_override (cwd param, assert command runs in dir), test_file_read_returns_content (create tmp file, read it), test_file_read_offset_limit (read lines 5-10), test_file_read_binary_detects (read binary file, assert metadata returned), test_file_write_creates_file (write to new path, assert content), test_file_write_creates_parents (write to nested dir, assert dirs created), test_file_edit_replaces (create file, edit, assert new content), test_file_edit_not_found_error (old_string missing), test_file_edit_ambiguous_error (old_string appears twice), test_glob_finds_files (create *.py files, glob "**/*.py"), test_grep_finds_content (create files with pattern, grep regex), test_sandbox_blocks_path_traversal (file_read("../../etc/passwd"), assert PermissionError), test_sandbox_blocks_absolute_path (file_read("/etc/passwd"), assert PermissionError), test_system_tools_selective_enabling (allowed=["file_read"], assert only file_read available)

### Implementation for User Story 8

- [ ] T042 [P] [US8] Create `agent_sdk/system_tools.py` with individual tool functions: `async bash(command, cwd, timeout, env) -> str` using asyncio.create_subprocess_exec with output capping via `_utils.truncate_output()`, `async file_read(path, offset, limit) -> str` with binary detection and sandbox check via `_utils.validate_path_sandbox()`, `async file_write(path, content) -> str` with parent dir creation and sandbox check, `async file_edit(path, old_string, new_string) -> str` with uniqueness check and sandbox check, `async glob_files(pattern, path) -> str` using pathlib.Path.glob, `async grep_content(pattern, path, include) -> str` wrapping subprocess grep/rg with Python re fallback
- [ ] T043 [US8] Create `SystemTools` class in `agent_sdk/system_tools.py` extending Skill: __init__(allowed, cwd, bash_timeout, env, sandbox, max_output_bytes). Registers selected tool functions as Pydantic AI tools using @tool decorator. Default sandbox=True. Default max_output_bytes=5_242_880 (5MB).
- [ ] T044 [US8] Update `agent_sdk/__init__.py` to export SystemTools
- [ ] T045 [US8] Create `examples/system_tools_agent.py` demonstrating agent with SystemTools(allowed=["file_read", "grep", "glob"]) per quickstart.md

**Checkpoint**: Agents can interact with the filesystem and run commands. Linux ecosystem integration complete.

---

## Phase 9: User Story 5 — Permission Policies (Priority: P3)

**Goal**: Developers control which tools agents can use via declarative glob-pattern policies.

**Independent Test**: Create PermissionPolicy with allowed/blocked patterns, attach to Runner, and assert tools are correctly filtered.

### Tests for User Story 5

- [ ] T046 [P] [US5] Create `tests/test_permissions.py` with tests: test_allowed_tools_filters (allowed=["search_*"], assert only matching tools visible), test_blocked_tools_excludes (blocked=["file_delete"], assert excluded), test_blocked_overrides_allowed (tool matches both, assert excluded), test_require_approval_triggers_callback (require_approval=["execute_*"], assert callback invoked), test_approval_denied_blocks (callback returns False, assert tool not executed), test_permission_mode_readonly (mode=readOnly, assert only readOnly-annotated tools pass), test_permission_mode_unrestricted (all tools pass), test_empty_patterns_allow_all, test_invalid_glob_raises_pattern_error, test_dynamic_add_rule (add_rule at runtime, assert new rule active), test_dynamic_remove_rule, test_permission_from_skill (Skill with PermissionPolicy, assert policy applies globally)

### Implementation for User Story 5

- [ ] T047 [P] [US5] Create `agent_sdk/permissions.py` with: PermissionMode (StrEnum: default, readOnly, unrestricted, planOnly), PermissionResult dataclass (allowed, reason, requires_approval), PermissionPolicy class (mode, allowed_tools, blocked_tools, require_approval, approval_callback). Implement `check(tool_name, tool_args) -> PermissionResult` with evaluation chain: blocked check → allowed check → mode check → approval check. Implement `add_rule()` and `remove_rule()` for dynamic modification. Use `_utils.glob_match()` for pattern matching.
- [ ] T048 [US5] Create internal `PermissionToolset` in `agent_sdk/permissions.py` extending PreparedToolset or WrapperToolset: override `get_tools()` to filter tools based on PermissionPolicy. For require_approval matches, wrap tools with Pydantic AI's ApprovalRequiredToolset. Wire into Runner toolset chain.
- [ ] T049 [US5] Extend `agent_sdk/runner.py` Runner: add permissions parameter. On run(), wrap toolsets with PermissionToolset if permissions configured. Position in chain: HookToolset(PermissionToolset(CombinedToolset(...))).
- [ ] T050 [US5] Update `agent_sdk/__init__.py` to export PermissionPolicy, PermissionMode, PermissionResult

**Checkpoint**: Permission policies work. Tools are filtered before the model sees them.

---

## Phase 10: User Story 6 — Agent Runner with Full Lifecycle (Priority: P3)

**Goal**: Runner orchestrates the complete lifecycle: hooks, guardrails, permissions, handoffs, budgets, interrupts, streaming.

**Independent Test**: Configure Runner with all features, run agent, assert full lifecycle fires in correct order.

### Tests for User Story 6

- [ ] T051 [P] [US6] Create `tests/test_runner.py` with tests: test_runner_lifecycle_order (HookRecorder asserts OnStart → guardrails → agent → guardrails → OnStop), test_runner_max_turns_stops (max_turns=2, assert MaxTurnsExceeded), test_runner_max_budget_stops (max_budget_tokens=100, assert BudgetExhausted), test_runner_interrupt_stops (run in background task, interrupt(), assert partial result), test_runner_run_sync_works (synchronous wrapper), test_runner_run_stream_works (streaming with event handler), test_runner_empty_prompt_raises (empty string, assert ValueError), test_runner_concurrent_run_raises (two run() simultaneously, assert error), test_runner_reentrant_guard (hook calls runner.run(), assert error), test_runner_sdk_metrics_populated (assert hook_invocations, guardrail_checks counts correct), test_runner_with_all_features (hooks + guardrails + skills + handoffs + permissions, assert all interact correctly)

### Implementation for User Story 6

- [ ] T052 [US6] Complete `agent_sdk/runner.py` Runner with remaining features: max_turns tracking (count tool call rounds, raise MaxTurnsExceeded), max_budget_tokens tracking (check RunUsage after each step, raise BudgetExhausted), interrupt() method (set asyncio.Event flag, check flag in loop), run_sync() wrapper (use anyio.from_thread.run), run_stream() (use agent.run_stream() with override, fire hooks via EventStreamHandler integration), PreModelCall/PostModelCall hooks (via HistoryProcessor for pre, post-run inspection for post), PreCompact hook (via HistoryProcessor detecting message count reduction), Notification hook (callable from user code)
- [ ] T053 [US6] Implement SDKMetrics tracking in Runner: count hook_invocations (increment in HookToolset), guardrail_checks (increment in _run_guardrails), handoff_count (increment in handoff tool), guardrail_trips, hooks_blocked. Attach to RunResult.
- [ ] T054 [US6] Add debug_callback support to Runner: structured log output for all lifecycle events (hook fired, guardrail checked, tool called, handoff executed). Format: `debug_callback(event_type: str, data: dict[str, Any])`.

**Checkpoint**: Runner is feature-complete with full lifecycle management.

---

## Phase 11: User Story 9 — Session Management (Priority: P2)

**Goal**: Conversations persist across process restarts. Sessions can be saved, loaded, resumed, and forked.

**Independent Test**: Run agent, save session, restart, resume with new prompt, and assert conversation continues.

### Tests for User Story 9

- [ ] T055 [P] [US9] Create `tests/test_session.py` with tests: test_session_save_load_roundtrip (save session, load by ID, assert messages match), test_session_resume_continues (run agent, save, resume with new prompt, assert prior context preserved), test_session_fork_creates_branch (fork session, assert new ID with parent_session_id set), test_session_not_found_raises (load non-existent ID, assert SessionNotFoundError), test_session_corrupt_json_raises (write invalid JSON, assert error), test_session_schema_version_mismatch (load old schema, assert SessionVersionError), test_session_list_returns_sessions (save 3 sessions, list, assert 3 returned), test_session_delete_removes (save + delete, assert not found)

### Implementation for User Story 9

- [ ] T056 [P] [US9] Create `agent_sdk/session.py` with: Session dataclass (session_id UUID, messages, metadata, created_at, updated_at, agent_name, parent_session_id), SessionBackend Protocol (save, load, list, delete async methods), JSONSessionBackend class (directory-based, one JSON file per session, uses Pydantic AI's ModelMessagesTypeAdapter, includes schema_version field)
- [ ] T057 [US9] Extend `agent_sdk/runner.py` Runner: add session_backend parameter. On run(), if session_id provided, load session and prepend messages. After run(), save session with updated messages. Implement resume(session_id, prompt) as load + run. Implement fork_session(session_id) as load + copy with new ID + parent ref.
- [ ] T058 [US9] Update `agent_sdk/__init__.py` to export Session, SessionBackend, JSONSessionBackend

**Checkpoint**: Sessions persist. Conversations can be resumed across restarts.

---

## Phase 12: Transport & Testing Utilities

**Purpose**: Transport abstraction for remote agents + test utilities for SDK consumers

- [ ] T059 [P] Create `agent_sdk/transport.py` with: Transport Protocol (run, run_stream methods), InProcessTransport class (direct agent.run() passthrough). Minimal for v0.1 — enables future HTTP/WebSocket transports.
- [ ] T060 [P] Create `agent_sdk/testing.py` with: HookRecorder class (records hook invocations, provides assert_called, assert_not_called, assert_order, get_hook methods), GuardrailRecorder class (records guardrail checks, provides assert_tripped, assert_passed methods). Both integrate with FunctionModel testing pattern.
- [ ] T061 [P] Create `tests/test_transport.py` with tests: test_in_process_transport_runs (basic run through InProcessTransport), test_transport_protocol_compliance (assert InProcessTransport implements Protocol)
- [ ] T062 [P] Update `agent_sdk/__init__.py` to export Transport, InProcessTransport, HookRecorder, GuardrailRecorder

---

## Phase 13: Integration Tests & Examples

**Purpose**: End-to-end validation that all features work together

- [ ] T063 Create `tests/test_integration.py` with tests: test_full_pipeline_hooks_guardrails_skills_handoffs_permissions (Runner with all 5 features active, assert lifecycle fires correctly), test_model_agnostic_openai_anthropic_google (same agent code, 3 different model strings, assert identical SDK behavior), test_markdown_skill_to_running_agent (load skill from file, attach to Runner, run agent, assert skill instructions active), test_system_tools_with_permissions (SystemTools + PermissionPolicy blocking bash, assert bash blocked but file_read works), test_handoff_with_guardrails (parent guardrail applies to handoff target results)
- [ ] T064 [P] Verify all examples run without errors: `examples/simple_agent.py`, `examples/guardrailed_agent.py`, `examples/skill_composition.py`, `examples/multi_agent.py`, `examples/system_tools_agent.py` (with TestModel/FunctionModel, no real API calls)

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, type checking, final quality gates

- [ ] T065 Run `mypy --strict agent_sdk/` and fix all type errors across all modules
- [ ] T066 Run `ruff check agent_sdk/ tests/` and fix all linting issues
- [ ] T067 [P] Add Google-style docstrings to all public APIs in all modules (13 classes + decorators + functions)
- [ ] T068 [P] Run full test suite `pytest tests/ -v` and ensure all tests pass with 90%+ coverage
- [ ] T069 [P] Review all ASCII diagrams in plan.md — verify they match final implementation
- [ ] T070 Create quickstart validation: run each code snippet from `specs/001-agent-sdk-core/quickstart.md` and verify it works

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3-5 (US1, US2, US7)**: All P1 stories. Depend on Phase 2. US1 (hooks) SHOULD be first as other features use hooks. US2 (guardrails) and US7 (markdown skills) can run in parallel after US1.
- **Phase 6 (US3 - Skills)**: Depends on US1 (hooks) and US7 (markdown loading)
- **Phase 7 (US4 - Handoffs)**: Depends on US1 (hooks for PreHandoff/PostHandoff)
- **Phase 8 (US8 - SystemTools)**: Depends on US3 (Skills, since SystemTools extends Skill)
- **Phase 9 (US5 - Permissions)**: Depends on Phase 2 only, but best after US1 for hook integration
- **Phase 10 (US6 - Full Runner)**: Depends on ALL other user stories
- **Phase 11 (US9 - Sessions)**: Depends on US6 (Runner)
- **Phase 12 (Transport/Testing)**: Depends on Phase 2 only
- **Phase 13 (Integration)**: Depends on ALL phases
- **Phase 14 (Polish)**: Depends on ALL phases

### User Story Dependencies

```
Phase 1 (Setup) ──▶ Phase 2 (Foundation) ──┬──▶ US1 (Hooks) ──┬──▶ US2 (Guardrails)
                                            │                   ├──▶ US7 (MD Skills)
                                            │                   ├──▶ US4 (Handoffs)
                                            │                   └──▶ US5 (Permissions)
                                            │
                                            │   US7 + US1 ──▶ US3 (Skills)
                                            │   US3 ──▶ US8 (SystemTools)
                                            │
                                            │   ALL US ──▶ US6 (Full Runner)
                                            │   US6 ──▶ US9 (Sessions)
                                            │
                                            └──▶ Phase 12 (Transport/Testing)

                    ALL ──▶ Phase 13 (Integration) ──▶ Phase 14 (Polish)
```

### Parallel Opportunities

After Phase 2 completes:
- US2 (Guardrails) and US7 (Markdown Skills) can start in parallel
- US4 (Handoffs) and US5 (Permissions) can start in parallel (both only need US1)
- Phase 12 (Transport/Testing) can start anytime after Phase 2

Within each user story:
- Test tasks [P] and implementation tasks [P] of the same story can start together (TDD: write tests first, they'll fail, then implement)
- All test files across stories are parallelizable

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Hooks)
4. **STOP and VALIDATE**: Agent with hooks works end-to-end
5. Ship v0.1.0-alpha.1

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (Hooks) → MVP: agent with lifecycle hooks (v0.1.0-alpha.1)
3. US2 (Guardrails) → Safety layer (v0.1.0-alpha.2)
4. US7 (MD Skills) + US3 (Skills) → Packaging/reuse (v0.1.0-alpha.3)
5. US4 (Handoffs) → Multi-agent (v0.1.0-alpha.4)
6. US8 (SystemTools) → Linux ecosystem (v0.1.0-alpha.5)
7. US5 (Permissions) + US6 (Full Runner) → Production features (v0.1.0-beta.1)
8. US9 (Sessions) + Transport + Integration → v0.1.0-rc.1
9. Polish → v0.1.0

### Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Write tests FIRST (TDD) — they should fail before implementation
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
