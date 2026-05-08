"""Pluggable execution backends — run shell commands anywhere.

By default, ``SystemTools`` runs shell commands via :class:`LocalBackend`,
a thin wrapper around ``asyncio.create_subprocess_shell``. Swap in any
object that satisfies the :class:`ExecutionBackend` protocol — Modal, E2B,
Daytona, a remote SSH session, an in-memory mock for tests — without
touching agent code or tool schemas.

This example shows three layers:

1. Default (local subprocess) — what you get with no extra config.
2. A custom backend (``ScriptedBackend``) that satisfies the protocol in
   ten lines, useful for tests and demos.
3. A read-only backend (``ReadOnlyBackend``) showing how to layer policy
   over an inner backend.

Run it: ``uv run examples/sandbox_backend.py``
"""

from __future__ import annotations

import asyncio

from typed_agent_sdk import ExecResult, ExecutionBackend, LocalBackend, SystemTools


class ScriptedBackend:
    """Returns canned outputs by command prefix — handy for tests and demos."""

    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    async def exec(
        self,
        command: str,
        *,
        timeout: float = 120.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        for prefix, stdout in self._responses.items():
            if command.startswith(prefix):
                return ExecResult(stdout=stdout, stderr='', exit_code=0)
        return ExecResult(stdout='', stderr=f'no scripted response for: {command}', exit_code=1)

    async def aclose(self) -> None:
        return None


class ReadOnlyBackend:
    """Wraps another backend and refuses commands that look like writes.

    .. warning::
        DEMO ONLY. The substring denylist below is trivially bypassable
        (``touch foo``, ``echo x>foo`` without spaces, ``bash -c '...'``,
        compound commands, etc.). For real isolation use OS-level controls
        (read-only filesystem, container/seccomp policy, a sandbox like
        Modal or E2B with a read-only mount), not string matching.
    """

    BLOCKED = ('rm ', 'mv ', 'cp ', '> ', '>>', 'mkdir', 'chmod', 'chown')

    def __init__(self, inner: ExecutionBackend) -> None:
        self._inner = inner

    async def exec(
        self,
        command: str,
        *,
        timeout: float = 120.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        if any(token in command for token in self.BLOCKED):
            return ExecResult(
                stdout='',
                stderr=f'blocked by ReadOnlyBackend: {command!r}',
                exit_code=126,
            )
        return await self._inner.exec(command, timeout=timeout, cwd=cwd, env=env)

    async def aclose(self) -> None:
        await self._inner.aclose()


async def main() -> None:
    local = SystemTools(allowed=['bash'])
    print('--- LocalBackend (default) ---')
    print(await local.tools[0]('echo hello from local'))

    scripted = SystemTools(
        allowed=['bash'],
        backend=ScriptedBackend({'ls': 'file1.txt\nfile2.txt\n'}),
    )
    print('--- ScriptedBackend ---')
    print(await scripted.tools[0]('ls -la'))

    readonly = SystemTools(
        allowed=['bash'],
        backend=ReadOnlyBackend(LocalBackend()),
    )
    print('--- ReadOnlyBackend (allows reads) ---')
    print(await readonly.tools[0]('echo permitted'))
    print('--- ReadOnlyBackend (blocks writes) ---')
    print(await readonly.tools[0]('rm -rf /tmp/anything'))


if __name__ == '__main__':
    asyncio.run(main())
