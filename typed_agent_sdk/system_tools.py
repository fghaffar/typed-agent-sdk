"""Built-in system tools wrapping the OS/Linux ecosystem.

Provides bash, file_read, file_write, file_edit, glob, and grep
as a selectively-enabled Skill.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from typed_agent_sdk._utils import truncate_output, validate_path_sandbox
from typed_agent_sdk.errors import (
    EditAmbiguousError,
    EditNotFoundError,
)
from typed_agent_sdk.skills import Skill

logger = logging.getLogger('typed_agent_sdk.system_tools')

ALL_SYSTEM_TOOLS = ['bash', 'file_read', 'file_write', 'file_edit', 'glob', 'grep']


async def bash(
    command: str,
    *,
    cwd: str | Path | None = None,
    timeout: float = 120.0,
    env: dict[str, str] | None = None,
    max_output_bytes: int = 5_242_880,
) -> str:
    """Execute a shell command and return stdout + stderr.

    Args:
        command: Shell command to execute.
        cwd: Working directory. Defaults to current directory.
        timeout: Maximum execution time in seconds.
        env: Additional environment variables.
        max_output_bytes: Maximum output size in bytes (default 5MB).

    Returns:
        Combined stdout and stderr output.
    """
    if not command.strip():
        raise ValueError('Command cannot be empty')

    full_env = {**os.environ, **(env or {})}
    effective_cwd = str(cwd) if cwd else None

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=effective_cwd,
            env=full_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            proc.kill()
            await proc.wait()
            return f'[Command timed out after {timeout}s]'

        stdout = stdout_bytes.decode('utf-8', errors='replace')
        stderr = stderr_bytes.decode('utf-8', errors='replace')

        output = stdout
        if stderr:
            output += f'\n[STDERR]\n{stderr}'

        return truncate_output(output, max_bytes=max_output_bytes)

    except FileNotFoundError:
        return f'[Command not found: {command.split()[0]}]'
    except Exception as e:
        return f'[Error executing command: {e}]'


async def file_read(
    path: str,
    *,
    cwd: str | Path | None = None,
    offset: int = 0,
    limit: int | None = None,
    sandbox: bool = True,
) -> str:
    """Read a file's contents with optional offset and limit.

    Args:
        path: File path (relative to cwd).
        cwd: Working directory for sandbox.
        offset: Line offset to start reading from (0-indexed).
        limit: Maximum number of lines to read.
        sandbox: If True, restrict to cwd subtree.
    """
    if sandbox and cwd:
        resolved = validate_path_sandbox(path, cwd)
    else:
        resolved = Path(path).resolve() if not Path(path).is_absolute() else Path(path)

    if not resolved.exists():
        return f'[File not found: {path}]'

    # Check for binary
    try:
        with open(resolved, 'rb') as f:
            chunk = f.read(8192)
            if b'\x00' in chunk:
                size = resolved.stat().st_size
                return f'[Binary file: {path} ({size} bytes)]'
    except OSError as e:
        return f'[Error reading file: {e}]'

    try:
        text = resolved.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        return f'[Error reading file: {e}]'

    lines = text.splitlines(keepends=True)
    if offset or limit:
        end = (offset + limit) if limit else None
        lines = lines[offset:end]

    # Add line numbers
    numbered = []
    for i, line in enumerate(lines, start=offset + 1):
        numbered.append(f'{i:6d}\t{line}')

    return ''.join(numbered) if numbered else '[Empty file]'


async def file_write(
    path: str,
    content: str,
    *,
    cwd: str | Path | None = None,
    sandbox: bool = True,
) -> str:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: File path (relative to cwd).
        content: Content to write.
        cwd: Working directory for sandbox.
        sandbox: If True, restrict to cwd subtree.
    """
    if sandbox and cwd:
        resolved = validate_path_sandbox(path, cwd)
    else:
        resolved = Path(path).resolve() if not Path(path).is_absolute() else Path(path)

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding='utf-8')
    return f'File written: {path} ({len(content)} bytes)'


async def file_edit(
    path: str,
    old_string: str,
    new_string: str,
    *,
    cwd: str | Path | None = None,
    sandbox: bool = True,
) -> str:
    """Replace a unique string in a file.

    Args:
        path: File path.
        old_string: The exact string to find and replace. Must be unique.
        new_string: The replacement string.
        cwd: Working directory for sandbox.
        sandbox: If True, restrict to cwd subtree.
    """
    if sandbox and cwd:
        resolved = validate_path_sandbox(path, cwd)
    else:
        resolved = Path(path).resolve() if not Path(path).is_absolute() else Path(path)

    if not resolved.exists():
        raise EditNotFoundError(str(path), old_string)

    content = resolved.read_text(encoding='utf-8')
    count = content.count(old_string)

    if count == 0:
        raise EditNotFoundError(str(path), old_string)
    if count > 1:
        raise EditAmbiguousError(str(path), old_string, count)

    new_content = content.replace(old_string, new_string, 1)
    resolved.write_text(new_content, encoding='utf-8')

    return f'Edited {path}: replaced 1 occurrence'


async def glob_files(
    pattern: str,
    *,
    path: str | Path | None = None,
    cwd: str | Path | None = None,
) -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py").
        path: Directory to search in (defaults to cwd).
        cwd: Working directory.
    """
    search_dir = Path(path or cwd or '.')
    if not search_dir.exists():
        return '[Directory not found]'

    matches = sorted(search_dir.glob(pattern))
    files = [str(m.relative_to(search_dir)) for m in matches if m.is_file()]

    if not files:
        return f'[No files matching "{pattern}"]'

    return '\n'.join(files)


async def grep_content(
    pattern: str,
    *,
    path: str | Path | None = None,
    cwd: str | Path | None = None,
    include: str | None = None,
) -> str:
    """Search file contents using regex.

    Uses subprocess grep/rg if available, falls back to Python re.

    Args:
        pattern: Regex pattern to search for.
        path: Directory to search in.
        cwd: Working directory.
        include: File glob filter (e.g., "*.py").
    """
    search_dir = Path(path or cwd or '.')
    if not search_dir.exists():
        return '[Directory not found]'

    # Try ripgrep first, then grep, then Python fallback
    for cmd in ['rg', 'grep']:
        try:
            args = [cmd, '-rn', pattern, str(search_dir)]
            if include and cmd == 'grep':
                args = [cmd, '-rn', '--include', include, pattern, str(search_dir)]
            elif include and cmd == 'rg':
                args = [cmd, '-n', '--glob', include, pattern, str(search_dir)]

            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode <= 1:  # 0 = found, 1 = not found
                return result.stdout or f'[No matches for "{pattern}"]'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Python fallback
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return f'[Invalid regex: {e}]'

    results = []
    file_pattern = include.replace('*', '**/*') if include else '**/*'
    for file_path in search_dir.glob(file_pattern):
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding='utf-8', errors='ignore')
            for i, line in enumerate(text.splitlines(), 1):
                if compiled.search(line):
                    rel = file_path.relative_to(search_dir)
                    results.append(f'{rel}:{i}:{line}')
        except OSError:
            continue

    return '\n'.join(results) if results else f'[No matches for "{pattern}"]'


class SystemTools(Skill[Any]):
    """Built-in skill providing OS/system interaction tools.

    Wraps bash, file_read, file_write, file_edit, glob, and grep.
    Tools can be selectively enabled.

    Usage:
        sys_tools = SystemTools(allowed=["file_read", "grep"])
        runner = Runner(agent, skills=[sys_tools])
    """

    def __init__(
        self,
        *,
        allowed: list[str] | None = None,
        cwd: str | Path | None = None,
        bash_timeout: float = 120.0,
        env: dict[str, str] | None = None,
        sandbox: bool = True,
        max_output_bytes: int = 5_242_880,
    ) -> None:
        self._allowed = allowed or ALL_SYSTEM_TOOLS
        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._bash_timeout = bash_timeout
        self._env = env
        self._sandbox = sandbox
        self._max_output_bytes = max_output_bytes

        # Build tool functions with bound parameters
        tools: list[Any] = []
        tool_map = self._build_tool_map()
        for name in self._allowed:
            if name in tool_map:
                tools.append(tool_map[name])

        super().__init__(
            name='system_tools',
            description='Built-in OS/system interaction tools',
            tools=tools,
        )

    def _build_tool_map(self) -> dict[str, Any]:
        """Build a map of tool name -> async function with bound params."""
        cwd = self._cwd
        sandbox = self._sandbox
        bash_timeout = self._bash_timeout
        env = self._env
        max_output = self._max_output_bytes

        async def _bash(command: str) -> str:
            """Execute a shell command."""
            return await bash(
                command,
                cwd=cwd,
                timeout=bash_timeout,
                env=env,
                max_output_bytes=max_output,
            )

        async def _file_read(path: str, offset: int = 0, limit: int | None = None) -> str:
            """Read a file's contents."""
            return await file_read(path, cwd=cwd, offset=offset, limit=limit, sandbox=sandbox)

        async def _file_write(path: str, content: str) -> str:
            """Write content to a file."""
            return await file_write(path, content, cwd=cwd, sandbox=sandbox)

        async def _file_edit(path: str, old_string: str, new_string: str) -> str:
            """Replace a string in a file."""
            return await file_edit(path, old_string, new_string, cwd=cwd, sandbox=sandbox)

        async def _glob(pattern: str) -> str:
            """Find files matching a glob pattern."""
            return await glob_files(pattern, cwd=cwd)

        async def _grep(pattern: str, include: str | None = None) -> str:
            """Search file contents using regex."""
            return await grep_content(pattern, cwd=cwd, include=include)

        return {
            'bash': _bash,
            'file_read': _file_read,
            'file_write': _file_write,
            'file_edit': _file_edit,
            'glob': _glob,
            'grep': _grep,
        }
