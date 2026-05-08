"""Tests for the ExecutionBackend protocol and LocalBackend.

Also covers SystemTools.bash routing through a custom backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from typed_agent_sdk.execution import ExecResult, ExecutionBackend, LocalBackend
from typed_agent_sdk.system_tools import SystemTools, bash

if TYPE_CHECKING:
    from pathlib import Path


class RecordingBackend:
    """Test double: captures every call and returns a fixed result."""

    def __init__(self, result: ExecResult | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._result: ExecResult = result or ExecResult(
            stdout='from-backend', stderr='', exit_code=0
        )
        self.closed = False

    async def exec(
        self,
        command: str,
        *,
        timeout: float = 120.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        self.calls.append({'command': command, 'timeout': timeout, 'cwd': cwd, 'env': env})
        return self._result

    async def aclose(self) -> None:
        self.closed = True


class TestLocalBackend:
    @pytest.mark.asyncio
    async def test_runs_echo(self) -> None:
        r = await LocalBackend().exec('echo hello')
        assert r['exit_code'] == 0
        assert 'hello' in r['stdout']

    @pytest.mark.asyncio
    async def test_captures_stderr(self) -> None:
        r = await LocalBackend().exec('echo err >&2')
        assert 'err' in r['stderr']

    @pytest.mark.asyncio
    async def test_timeout_returns_negative_exit(self) -> None:
        r = await LocalBackend().exec('sleep 999', timeout=0.1)
        assert r['exit_code'] == -1
        assert 'timed out' in r['stderr']

    @pytest.mark.asyncio
    async def test_aclose_is_safe(self) -> None:
        await LocalBackend().aclose()

    @pytest.mark.asyncio
    async def test_cwd_is_applied(self, tmp_path: Path) -> None:
        r = await LocalBackend().exec('pwd', cwd=str(tmp_path))
        assert str(tmp_path) in r['stdout']

    @pytest.mark.asyncio
    async def test_env_is_merged(self) -> None:
        r = await LocalBackend().exec(
            'echo "$TYPED_AGENT_SDK_TEST_VAR"',
            env={'TYPED_AGENT_SDK_TEST_VAR': 'sentinel-42'},
        )
        assert 'sentinel-42' in r['stdout']

    @pytest.mark.asyncio
    async def test_unknown_command_returns_nonzero(self) -> None:
        # Shell handles "command not found" by exiting 127, not by raising.
        r = await LocalBackend().exec('this_command_does_not_exist_xyz123')
        assert r['exit_code'] != 0
        assert 'not found' in r['stderr'].lower() or r['stderr']


class TestExecutionBackendProtocol:
    def test_local_backend_satisfies_protocol(self) -> None:
        assert isinstance(LocalBackend(), ExecutionBackend)

    def test_recording_backend_satisfies_protocol(self) -> None:
        assert isinstance(RecordingBackend(), ExecutionBackend)

    def test_incomplete_backend_does_not_satisfy_protocol(self) -> None:
        # An object missing aclose() must NOT pass the runtime check —
        # this is the guarantee runtime_checkable buys us.
        class MissingAclose:
            async def exec(
                self,
                command: str,
                *,
                timeout: float = 120.0,
                cwd: str | None = None,
                env: dict[str, str] | None = None,
            ) -> ExecResult:
                return ExecResult(stdout='', stderr='', exit_code=0)

        assert not isinstance(MissingAclose(), ExecutionBackend)


class TestBashRoutesToBackend:
    @pytest.mark.asyncio
    async def test_default_backend_is_local(self) -> None:
        out = await bash('echo via-local')
        assert 'via-local' in out

    @pytest.mark.asyncio
    async def test_custom_backend_receives_call(self) -> None:
        b = RecordingBackend()
        out = await bash('whatever', backend=b, timeout=5.0, cwd='/tmp')
        assert 'from-backend' in out
        assert b.calls == [{'command': 'whatever', 'timeout': 5.0, 'cwd': '/tmp', 'env': None}]

    @pytest.mark.asyncio
    async def test_stderr_appended_when_present(self) -> None:
        b = RecordingBackend(ExecResult(stdout='ok', stderr='warn!', exit_code=0))
        out = await bash('x', backend=b)
        assert 'ok' in out
        assert '[STDERR]' in out
        assert 'warn!' in out

    @pytest.mark.asyncio
    async def test_empty_stderr_omits_stderr_marker(self) -> None:
        b = RecordingBackend(ExecResult(stdout='quiet', stderr='', exit_code=0))
        out = await bash('x', backend=b)
        assert out == 'quiet'
        assert '[STDERR]' not in out

    @pytest.mark.asyncio
    async def test_nonzero_exit_code_is_surfaced(self) -> None:
        b = RecordingBackend(ExecResult(stdout='nope', stderr='', exit_code=2))
        out = await bash('x', backend=b)
        assert 'nope' in out
        assert '[exit code: 2]' in out

    @pytest.mark.asyncio
    async def test_zero_exit_code_does_not_emit_marker(self) -> None:
        b = RecordingBackend(ExecResult(stdout='ok', stderr='', exit_code=0))
        out = await bash('x', backend=b)
        assert '[exit code' not in out

    @pytest.mark.asyncio
    async def test_long_backend_exception_message_is_truncated(self) -> None:
        class LeakyBackend:
            async def exec(
                self,
                command: str,
                *,
                timeout: float = 120.0,
                cwd: str | None = None,
                env: dict[str, str] | None = None,
            ) -> ExecResult:
                # Simulate a backend leaking a long, sensitive-looking message.
                raise RuntimeError('secret-token-' + ('A' * 500))

            async def aclose(self) -> None:
                return None

        out = await bash('x', backend=LeakyBackend())
        assert '[truncated]' in out
        assert len(out) < 400  # truncated to 200 + framing

    @pytest.mark.asyncio
    async def test_backend_exception_is_returned_as_error_string(self) -> None:
        class BoomBackend:
            async def exec(
                self,
                command: str,
                *,
                timeout: float = 120.0,
                cwd: str | None = None,
                env: dict[str, str] | None = None,
            ) -> ExecResult:
                raise RuntimeError('backend offline')

            async def aclose(self) -> None:
                return None

        out = await bash('anything', backend=BoomBackend())
        assert 'Error running command' in out
        assert 'RuntimeError' in out  # exception type appears for debuggability
        assert 'backend offline' in out


class TestSystemToolsThreadsBackend:
    @pytest.mark.asyncio
    async def test_skill_bash_uses_provided_backend(self) -> None:
        b = RecordingBackend()
        st = SystemTools(allowed=['bash'], backend=b)
        bash_tool = st.tools[0]
        result = await bash_tool('ls -la')
        assert 'from-backend' in result
        assert b.calls[0]['command'] == 'ls -la'

    def test_skill_default_backend_is_none(self) -> None:
        st = SystemTools()
        assert st._backend is None

    def test_tool_names_are_public_not_underscore_prefixed(self) -> None:
        # Pydantic AI registers tools by __name__; the closures inside
        # SystemTools must expose the public name (bash, file_read, ...)
        # rather than the internal underscore-prefixed name (_bash, _file_read).
        st = SystemTools()
        names = sorted(t.__name__ for t in st.tools)
        assert names == ['bash', 'file_edit', 'file_read', 'file_write', 'glob', 'grep']

    def test_two_instances_have_independent_backends(self) -> None:
        # Closure isolation: a backend on one instance must not bleed into another.
        b1 = RecordingBackend()
        b2 = RecordingBackend()
        st1 = SystemTools(allowed=['bash'], backend=b1)
        st2 = SystemTools(allowed=['bash'], backend=b2)
        assert st1._backend is b1
        assert st2._backend is b2
        assert st1.tools[0] is not st2.tools[0]


class TestConcurrentBash:
    @pytest.mark.asyncio
    async def test_parallel_calls_to_local_backend(self) -> None:
        # LocalBackend is stateless; concurrent calls must not interfere.
        import asyncio as _asyncio

        results = await _asyncio.gather(
            LocalBackend().exec('echo a'),
            LocalBackend().exec('echo b'),
            LocalBackend().exec('echo c'),
        )
        outs = sorted(r['stdout'].strip() for r in results)
        assert outs == ['a', 'b', 'c']

    @pytest.mark.asyncio
    async def test_parallel_bash_with_shared_backend(self) -> None:
        # A single backend instance reused across parallel bash() calls.
        import asyncio as _asyncio

        b = RecordingBackend()
        outs = await _asyncio.gather(
            bash('one', backend=b),
            bash('two', backend=b),
            bash('three', backend=b),
        )
        assert all('from-backend' in o for o in outs)
        assert sorted(c['command'] for c in b.calls) == ['one', 'three', 'two']
