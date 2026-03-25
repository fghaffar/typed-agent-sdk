"""Composable skills system for agent_sdk.

Skills are reusable bundles of tools, instructions, hooks, and guardrails.
They can be defined in Python (Skill class) or as markdown files (SkillMarkdown).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from agent_sdk._utils import parse_frontmatter
from agent_sdk.errors import SkillConflictError, SkillLoadError
from agent_sdk.guardrails import Guardrail
from agent_sdk.hooks import Hook

logger = logging.getLogger('agent_sdk.skills')

DepsT = TypeVar('DepsT')


@dataclass
class HandoffDef:
    """A handoff target defined in markdown skill frontmatter."""

    label: str
    agent: str
    prompt: str | None = None


@dataclass
class SkillMarkdown:
    """A skill loaded from a markdown file with YAML frontmatter."""

    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    handoffs: list[HandoffDef] = field(default_factory=list)
    instructions: str = ''
    source_path: Path | None = None

    def with_arguments(self, arguments: str) -> SkillMarkdown:
        """Return a copy with $ARGUMENTS replaced in instructions."""
        return SkillMarkdown(
            name=self.name,
            description=self.description,
            tools=self.tools,
            handoffs=self.handoffs,
            instructions=self.instructions.replace('$ARGUMENTS', arguments),
            source_path=self.source_path,
        )


@dataclass
class Skill(Generic[DepsT]):
    """A composable package of agent capabilities.

    Bundles tools, instructions, hooks, and guardrails into a reusable unit.
    Can be attached to any Runner.
    """

    name: str
    description: str = ''
    tools: list[Any] = field(default_factory=list)
    instructions: str | None = None
    hooks: list[Hook] = field(default_factory=list)
    guardrails: list[Guardrail[Any]] = field(default_factory=list)


def _parse_handoffs(raw: list[Any]) -> list[HandoffDef]:
    """Parse handoff definitions from YAML frontmatter."""
    result = []
    for item in raw:
        if isinstance(item, dict):
            result.append(
                HandoffDef(
                    label=item.get('label', ''),
                    agent=item.get('agent', ''),
                    prompt=item.get('prompt'),
                )
            )
        elif isinstance(item, str):
            result.append(HandoffDef(label=item, agent=item))
    return result


def _load_skill_file(file_path: Path, namespace_prefix: str = '') -> SkillMarkdown:
    """Load a single markdown skill file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError as e:
        raise SkillLoadError(str(file_path), f'Not a valid UTF-8 file: {e}') from e
    except OSError as e:
        raise SkillLoadError(str(file_path), str(e)) from e

    try:
        frontmatter, body = parse_frontmatter(content)
    except ValueError as e:
        raise SkillLoadError(str(file_path), str(e)) from e

    name = frontmatter.get('name')
    if not name:
        raise SkillLoadError(str(file_path), 'Missing required field: name')

    description = frontmatter.get('description', '')
    if not description:
        raise SkillLoadError(str(file_path), 'Missing required field: description')

    # Apply namespace prefix from directory structure
    full_name = f'{namespace_prefix}{name}' if namespace_prefix else name

    tools_raw = frontmatter.get('tools', [])
    tools = tools_raw if isinstance(tools_raw, list) else [tools_raw]

    handoffs_raw = frontmatter.get('handoffs', [])
    handoffs = _parse_handoffs(handoffs_raw) if isinstance(handoffs_raw, list) else []

    return SkillMarkdown(
        name=full_name,
        description=description,
        tools=[str(t) for t in tools],
        handoffs=handoffs,
        instructions=body,
        source_path=file_path,
    )


def load_skills(
    directory: str | Path,
    *,
    recursive: bool = True,
) -> list[SkillMarkdown]:
    """Auto-discover and load markdown skill files from a directory.

    Args:
        directory: Path to skills directory.
        recursive: If True, scan subdirectories (with namespace prefixing).

    Returns:
        List of loaded SkillMarkdown objects.

    Raises:
        SkillLoadError: If any skill file is invalid.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    skills: list[SkillMarkdown] = []
    seen_names: dict[str, Path] = {}

    pattern = '**/*.md' if recursive else '*.md'
    for md_file in sorted(dir_path.glob(pattern)):
        if not md_file.is_file():
            continue

        # Build namespace prefix from relative directory path
        rel = md_file.parent.relative_to(dir_path)
        namespace = '.'.join(rel.parts) + '.' if rel.parts else ''

        skill = _load_skill_file(md_file, namespace_prefix=namespace)

        # Check for name conflicts
        if skill.name in seen_names:
            raise SkillConflictError(
                skill.name,
                str(seen_names[skill.name]),
                str(md_file),
            )
        seen_names[skill.name] = md_file
        skills.append(skill)

    return skills


def check_skill_conflicts(skills: list[Skill[Any] | SkillMarkdown]) -> None:
    """Check for tool name conflicts across multiple skills.

    Raises:
        SkillConflictError: If two skills register tools with the same name.
    """
    tool_owners: dict[str, str] = {}
    for skill in skills:
        if isinstance(skill, Skill):
            for tool in skill.tools:
                tool_name = getattr(tool, 'name', str(tool))
                if tool_name in tool_owners:
                    raise SkillConflictError(tool_name, tool_owners[tool_name], skill.name)
                tool_owners[tool_name] = skill.name
