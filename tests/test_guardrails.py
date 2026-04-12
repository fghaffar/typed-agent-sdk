"""Tests for typed_agent_sdk guardrails system."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from typed_agent_sdk.errors import GuardrailExecutionError, GuardrailTripwireError
from typed_agent_sdk.guardrails import (
    Guardrail,
    GuardrailResult,
    input_guardrail,
    output_guardrail,
    run_guardrails,
)
from typed_agent_sdk.types import SDKMetrics


class TestGuardrailResult:
    def test_defaults(self) -> None:
        r = GuardrailResult(passed=True)
        assert r.passed is True
        assert r.reason is None
        assert r.tripwire is False

    def test_tripwire(self) -> None:
        r = GuardrailResult(passed=False, reason='bad content', tripwire=True)
        assert r.tripwire is True


class TestGuardrailDecorators:
    def test_input_guardrail_decorator(self) -> None:
        @input_guardrail('test-guard')
        async def check(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=True)

        assert isinstance(check, Guardrail)
        assert check.name == 'test-guard'
        assert check.kind == 'input'

    def test_output_guardrail_decorator(self) -> None:
        @output_guardrail('out-guard', timeout=5.0, fail_closed=True)
        async def check(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=True)

        assert check.kind == 'output'
        assert check.timeout == 5.0
        assert check.fail_closed is True


class TestRunGuardrails:
    @pytest.mark.asyncio
    async def test_input_guardrail_passes(self) -> None:
        async def check(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=True)

        guards = [Guardrail(name='pass-guard', check=check, kind='input')]
        results = await run_guardrails(guards, 'input', 'hello', None)
        assert len(results) == 1
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_input_guardrail_tripwire_halts(self) -> None:
        async def check(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=False, reason='prohibited', tripwire=True)

        guards = [Guardrail(name='trip-guard', check=check, kind='input')]
        with pytest.raises(GuardrailTripwireError, match='trip-guard'):
            await run_guardrails(guards, 'input', 'bad content', None)

    @pytest.mark.asyncio
    async def test_output_guardrail_tripwire(self) -> None:
        async def check(data: Any, ctx: Any) -> GuardrailResult:
            if 'secret' in str(data):
                return GuardrailResult(passed=False, reason='PII detected', tripwire=True)
            return GuardrailResult(passed=True)

        guards = [Guardrail(name='pii-guard', check=check, kind='output')]
        with pytest.raises(GuardrailTripwireError, match='pii-guard'):
            await run_guardrails(guards, 'output', 'contains secret data', None)

    @pytest.mark.asyncio
    async def test_guardrails_run_in_parallel(self) -> None:
        async def slow_check(data: Any, ctx: Any) -> GuardrailResult:
            await asyncio.sleep(0.1)
            return GuardrailResult(passed=True)

        guards = [Guardrail(name=f'slow-{i}', check=slow_check, kind='input') for i in range(3)]

        start = time.monotonic()
        await run_guardrails(guards, 'input', 'test', None)
        elapsed = time.monotonic() - start

        # 3 guardrails at 0.1s each — if sequential would take 0.3s
        # Parallel should be ~0.1s
        assert elapsed < 0.25, f'Guardrails took {elapsed:.2f}s, expected parallel execution'

    @pytest.mark.asyncio
    async def test_guardrail_fail_without_tripwire_continues(self) -> None:
        async def soft_fail(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=False, reason='warning only')

        guards = [Guardrail(name='soft-guard', check=soft_fail, kind='input')]
        # Should NOT raise — no tripwire
        results = await run_guardrails(guards, 'input', 'test', None)
        assert len(results) == 1
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_zero_guardrails_skips(self) -> None:
        results = await run_guardrails([], 'input', 'test', None)
        assert results == []

    @pytest.mark.asyncio
    async def test_only_matching_kind_runs(self) -> None:
        called = False

        async def check(data: Any, ctx: Any) -> GuardrailResult:
            nonlocal called
            called = True
            return GuardrailResult(passed=True)

        guards = [Guardrail(name='out-only', check=check, kind='output')]
        await run_guardrails(guards, 'input', 'test', None)
        assert called is False  # Output guard not called for input

    @pytest.mark.asyncio
    async def test_guardrail_timeout_fail_open(self) -> None:
        async def slow(data: Any, ctx: Any) -> GuardrailResult:
            await asyncio.sleep(10)
            return GuardrailResult(passed=True)

        guards = [Guardrail(name='slow-guard', check=slow, kind='input', timeout=0.01)]
        results = await run_guardrails(guards, 'input', 'test', None)
        assert len(results) == 1
        assert results[0].passed is True  # fail-open

    @pytest.mark.asyncio
    async def test_guardrail_timeout_fail_closed(self) -> None:
        async def slow(data: Any, ctx: Any) -> GuardrailResult:
            await asyncio.sleep(10)
            return GuardrailResult(passed=True)

        guards = [
            Guardrail(
                name='slow-guard',
                check=slow,
                kind='input',
                timeout=0.01,
                fail_closed=True,
            )
        ]
        with pytest.raises(GuardrailTripwireError, match='slow-guard'):
            await run_guardrails(guards, 'input', 'test', None)

    @pytest.mark.asyncio
    async def test_guardrail_exception_wraps(self) -> None:
        async def bad_guard(data: Any, ctx: Any) -> GuardrailResult:
            raise RuntimeError('guardrail broke')

        guards = [Guardrail(name='bad-guard', check=bad_guard, kind='input')]
        with pytest.raises(GuardrailExecutionError, match='bad-guard'):
            await run_guardrails(guards, 'input', 'test', None)

    @pytest.mark.asyncio
    async def test_metrics_tracked(self) -> None:
        async def check(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=True)

        metrics = SDKMetrics()
        guards = [
            Guardrail(name='g1', check=check, kind='input'),
            Guardrail(name='g2', check=check, kind='input'),
        ]
        await run_guardrails(guards, 'input', 'test', None, metrics=metrics)
        assert metrics.guardrail_checks == 2

    @pytest.mark.asyncio
    async def test_tripwire_increments_metrics(self) -> None:
        async def tripper(data: Any, ctx: Any) -> GuardrailResult:
            return GuardrailResult(passed=False, tripwire=True)

        metrics = SDKMetrics()
        guards = [Guardrail(name='trip', check=tripper, kind='input')]
        with pytest.raises(GuardrailTripwireError):
            await run_guardrails(guards, 'input', 'test', None, metrics=metrics)
        assert metrics.guardrail_trips == 1
