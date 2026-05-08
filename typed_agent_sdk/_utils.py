"""Internal utilities for typed_agent_sdk."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def glob_match(pattern: str, name: str) -> bool:
    """Match a name against a glob pattern using fnmatch.

    Args:
        pattern: Glob pattern (e.g., "file_*", "search_*", "calculate").
        name: Tool or resource name to match.

    Returns:
        True if the name matches the pattern.
    """
    return fnmatch(name, pattern)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    Handles the case where `---` appears in the markdown body by only
    treating the FIRST pair of `---` delimiters as frontmatter boundaries.

    Args:
        content: Full markdown file content.

    Returns:
        Tuple of (frontmatter dict, body string).

    Raises:
        ValueError: If frontmatter is missing or YAML is invalid.
    """
    content = content.strip()

    if not content.startswith('---'):
        raise ValueError('No YAML frontmatter found (file must start with ---)')

    # Find the closing --- after the opening one
    # Start searching after the first ---
    end_idx = content.find('\n---', 3)
    if end_idx == -1:
        raise ValueError('No closing --- found for YAML frontmatter')

    yaml_content = content[3:end_idx].strip()
    body = content[end_idx + 4 :].strip()  # Skip past \n---

    try:
        frontmatter = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f'Invalid YAML in frontmatter: {e}') from e

    if not isinstance(frontmatter, dict):
        raise ValueError('YAML frontmatter must be a mapping (dict), not a scalar or list')

    return frontmatter, body


def validate_path_sandbox(path: str | Path, cwd: str | Path) -> Path:
    """Validate that a file path is within the sandbox (cwd subtree).

    Args:
        path: The file path to validate.
        cwd: The working directory that serves as the sandbox root.

    Returns:
        The resolved, absolute Path.

    Raises:
        PermissionError: If the path escapes the sandbox.
    """
    cwd_resolved = Path(cwd).resolve()
    target = (cwd_resolved / Path(path)).resolve()

    if not str(target).startswith(str(cwd_resolved)):
        raise PermissionError(
            f'Path "{path}" escapes sandbox. All file operations must be within "{cwd_resolved}"'
        )

    return target


def truncate_output(text: str, max_bytes: int = 5_242_880) -> str:
    """Truncate text output to a maximum byte size.

    Args:
        text: The text to potentially truncate.
        max_bytes: Maximum size in bytes (default: 5MB).

    Returns:
        Original text if under limit, otherwise truncated with marker.
    """
    encoded = text.encode('utf-8', errors='replace')
    if len(encoded) <= max_bytes:
        return text

    # Truncate at byte boundary, decode safely
    truncated = encoded[:max_bytes].decode('utf-8', errors='ignore')
    return truncated + f'\n\n[OUTPUT TRUNCATED at {max_bytes // 1_048_576}MB]'


def escape_tool_name_for_regex(tool_name: str) -> str:
    """Escape a tool name for use as a literal in a regex pattern.

    Args:
        tool_name: The raw tool name.

    Returns:
        Regex-escaped tool name safe for use in HookMatcher patterns.
    """
    return re.escape(tool_name)
