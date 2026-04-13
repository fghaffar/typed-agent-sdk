# typed-agent-sdk Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-12

 > **SELF-CORRECTING FILE**: This file describes common mistakes and confusion points
  > that agents encounter in this project. If you encounter something surprising,              
  > unexpected, or that contradicts your assumptions — **stop and alert the developer**.
  > Then add a new entry to the **Learned Rules** table at the bottom of this file
  > so future agents never hit the same issue. This file learns from every mistake.



## Active Technologies

- Python 3.10+ with pydantic-ai, pydantic, typing-extensions, PyYAML (001-agent-sdk-core)

## Project Structure

```text
typed_agent_sdk/     # Source package (16 modules)
tests/               # pytest + pytest-asyncio
examples/            # Usage examples with progressive complexity
```

## Commands

```bash
# Install
pip install -e ".[dev]"

# Test
pytest tests/ -v

# Lint + Format
ruff check . && ruff format .

# Type check
mypy --strict typed_agent_sdk/
```

## Code Style

- Python 3.10+ with strict typing (mypy --strict, pyright)
- Google-style docstrings on all public APIs
- ruff for linting and formatting
- All public APIs must use generics (DepsT, OutputT)
- Protocols over ABCs for extension points
- async-first design (sync wrappers via anyio)

## Constitution

See `.specify/memory/constitution.md` for 9 core principles.
Priority: Model Agnosticism > Type Safety > Lightweight > Composition > Progressive Complexity

## Recent Changes

- 001-agent-sdk-core: Initial SDK design — hooks, guardrails, skills, handoffs, permissions, system tools, session management

## Learned Rules

**PURPOSE**: This table is a living record of mistakes and confusion points agents have hit in this project. It prevents the same error from recurring across sessions and agents.

**PROTOCOL — when you encounter something surprising**:
1. **Stop** — do not silently work around it
2. **Alert the developer** — explain what you expected vs what you found
3. **Add a new LR entry** to this table with the rule and context
4. **Then proceed** with the corrected understanding

Rules are never removed, only added. Number sequentially (`LR-001`, `LR-002`, ...).

| # | Rule | Learned From |
|---|------|-------------|
| LR-001 | Gitignored directories (`.specify/`, `.claude/`) must be symlinked into worktrees before running tooling that depends on them. Worktrees only contain committed files. | speckit.analyze failed with "No such file or directory" in 002-event-layer worktree (2026-03-08) |
| LR-002 | Always use `uv` — never `pip`, `python`, or `venv`. Use `uv run` to execute scripts, `uv add` to add deps, `uv sync` to install. | User preference established (2026-03-08) |
| LR-003 | System Python is 3.10, not 3.11+. `StrEnum` requires a backport (`class StrEnum(str, Enum)`) for 3.10 compat. pyproject.toml should target `>=3.10`. | `from enum import StrEnum` ImportError during Phase 2 tests (2026-03-15) |
| LR-004 | On Python 3.10, `asyncio.TimeoutError` is NOT a subclass of builtin `TimeoutError`. Always catch `(TimeoutError, asyncio.TimeoutError)` for cross-version compat. Similarly, `datetime.UTC` doesn't exist in 3.10 — use `timezone.utc`. Never use `ruff --unsafe-fixes` without reviewing UP036/UP041/UP017 changes. | Timeout tests broke after ruff unsafe-fixes removed 3.10 compat shims (2026-04-12) |


<!-- MANUAL ADDITIONS START -->

## Git Checkpoint Policy

**IMPORTANT**: Claude must prompt the user to commit and push changes at these checkpoints:

### When to Prompt for Git Commit & Push

1. **After fixing a bug** - Once a bug is confirmed fixed and working
2. **After completing a feature** - When a new feature or endpoint is fully implemented and tested
3. **After significant refactoring** - When code has been restructured or reorganized
4. **Before switching to a different task** - To preserve current work before context switch
5. **After fixing multiple related errors** - When a series of related fixes have been applied (e.g., 3+ fixes in one session)
6. **After database migrations** - When new models or schema changes are added
7. **End of a productive session** - After making substantial progress on multiple items

### Checkpoint Prompt Format

When a checkpoint is reached, Claude should ask:

```
**Git Checkpoint**: [Brief description of what was accomplished]

Would you like me to commit and push these changes?
- Changes include: [list of modified files/features]
- Suggested commit message: "[type]: [description]"

Reply 'yes' to commit, or 'skip' to continue without committing.
```

### Commit Message Format
- `fix:` for bug fixes
- `feat:` for new features
- `refactor:` for code restructuring
- `chore:` for maintenance tasks
- `docs:` for documentation updates

<!-- MANUAL ADDITIONS END -->
