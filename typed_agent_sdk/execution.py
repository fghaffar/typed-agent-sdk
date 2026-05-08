"""Pluggable execution backends for sandboxed tool execution.

An :class:`ExecutionBackend` is the seam that lets tools run locally, on
Modal, on E2B, or on any other runtime. The protocol is deliberately narrow
(``exec`` + ``aclose``) so adapters are thin and the core SDK depends on no
sandbox SDKs.

Quick start — use the default ``LocalBackend``::

    from typed_agent_sdk import Runner, SystemTools

    runner = Runner(agent, skills=[SystemTools(allowed=['bash'])])

Swap in a custom backend — any object satisfying the protocol works::

    from typed_agent_sdk import ExecResult, Runner, SystemTools

    class MyBackend:
        async def exec(
            self, command, *, timeout=120, cwd=None, env=None
        ) -> ExecResult:
            # delegate to Modal / E2B / SSH / a queue / a mock / ...
            return ExecResult(stdout='hi', stderr='', exit_code=0)

        async def aclose(self) -> None:
            ...

    runner = Runner(agent, skills=[SystemTools(backend=MyBackend())])

The protocol is :func:`runtime_checkable`, so ``isinstance(b, ExecutionBackend)``
is true for any duck-typed implementation.
"""

from __future__ import annotations

import asyncio
import os
from typing import Protocol, TypedDict, runtime_checkable


class ExecResult(TypedDict):
    """Structured result of an exec() call."""

    stdout: str
    stderr: str
    exit_code: int


@runtime_checkable
class ExecutionBackend(Protocol):
    """Protocol for sandbox/execution backends.

    Built-in implementations: :class:`LocalBackend` (default, in-process
    subprocess). First-party adapters are planned as separate extras:
    ``typed-agent-sdk[modal]`` and ``typed-agent-sdk[e2b]``.

    A backend is a long-lived session: create once, reuse across many
    ``exec()`` calls, ``aclose()`` when done. The SDK does not invoke
    ``aclose`` automatically — callers are responsible for it (typically
    in a ``finally`` block).
    """

    async def exec(
        self,
        command: str,
        *,
        timeout: float = 120.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        """Run ``command`` and return the result.

        Args:
            command: Shell command string. Interpretation is backend-specific
                (LocalBackend uses ``/bin/sh -c``).
            timeout: Maximum seconds to wait. On timeout the backend should
                terminate the running command and return ``exit_code = -1``
                with a stderr indicating the timeout.
            cwd: Working directory. ``None`` means the backend's default.
            env: Extra environment variables, merged onto the backend's env.
                Existing values are overridden by these.

        Returns:
            :class:`ExecResult` with stdout, stderr, and exit_code.
        """
        ...

    async def aclose(self) -> None:
        """Release resources held by the backend (connections, processes, ...).

        Must be idempotent. Safe to call on backends that hold no resources
        (e.g. :class:`LocalBackend`).
        """
        ...


class LocalBackend:
    """Default backend: runs commands in a local subprocess.

    This is what SystemTools uses when no backend is passed, so existing
    code continues to work unchanged.
    """

    async def exec(
        self,
        command: str,
        *,
        timeout: float = 120.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        full_env = {**os.environ, **(env or {})}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env,
            )
        except FileNotFoundError:
            first = command.split()[0] if command.split() else command
            return ExecResult(
                stdout='',
                stderr=f'[Command not found: {first}]',
                exit_code=127,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            proc.kill()
            await proc.wait()
            return ExecResult(
                stdout='',
                stderr=f'[Command timed out after {timeout}s]',
                exit_code=-1,
            )

        return ExecResult(
            stdout=stdout_bytes.decode('utf-8', errors='replace'),
            stderr=stderr_bytes.decode('utf-8', errors='replace'),
            exit_code=proc.returncode if proc.returncode is not None else 0,
        )

    async def aclose(self) -> None:
        return None
