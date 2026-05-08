"""Input/output guardrails for typed_agent_sdk.

Guardrails validate prompts before they reach the model (input)
and responses before they reach the user (output). They run in
parallel and can halt execution via tripwire.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from typed_agent_sdk.errors import GuardrailExecutionError, GuardrailTripwireError

if TYPE_CHECKING:
    from typed_agent_sdk.types import SDKMetrics

logger = logging.getLogger('typed_agent_sdk.guardrails')

DepsT = TypeVar('DepsT')


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of a guardrail check."""

    passed: bool
    reason: str | None = None
    tripwire: bool = False


GuardrailCheckFunc = Callable[[Any, Any], Awaitable[GuardrailResult]]


@dataclass
class Guardrail(Generic[DepsT]):
    """A safety check that runs in parallel with the agent.

    Args:
        name: Identifier for logging and error messages.
        check: Async function that validates data and returns GuardrailResult.
        kind: "input" to validate prompts, "output" to validate responses.
        timeout: Max execution time in seconds. None means no timeout.
        fail_closed: If True, timeout triggers tripwire. If False, timeout passes.
    """

    name: str
    check: GuardrailCheckFunc
    kind: str  # "input" or "output"
    timeout: float | None = None
    fail_closed: bool = False


# Convenience aliases
InputGuardrail = Guardrail
OutputGuardrail = Guardrail


def input_guardrail(
    name: str,
    *,
    timeout: float | None = None,
    fail_closed: bool = False,
) -> Callable[[GuardrailCheckFunc], Guardrail[Any]]:
    """Decorator factory for creating input guardrails."""

    def wrapper(func: GuardrailCheckFunc) -> Guardrail[Any]:
        return Guardrail(
            name=name,
            check=func,
            kind='input',
            timeout=timeout,
            fail_closed=fail_closed,
        )

    return wrapper


def output_guardrail(
    name: str,
    *,
    timeout: float | None = None,
    fail_closed: bool = False,
) -> Callable[[GuardrailCheckFunc], Guardrail[Any]]:
    """Decorator factory for creating output guardrails."""

    def wrapper(func: GuardrailCheckFunc) -> Guardrail[Any]:
        return Guardrail(
            name=name,
            check=func,
            kind='output',
            timeout=timeout,
            fail_closed=fail_closed,
        )

    return wrapper


async def _run_single_guardrail(
    guardrail: Guardrail[Any],
    data: Any,
    ctx: Any,
) -> GuardrailResult:
    """Run a single guardrail with timeout and error handling."""
    try:
        if guardrail.timeout:
            result = await asyncio.wait_for(guardrail.check(data, ctx), timeout=guardrail.timeout)
        else:
            result = await guardrail.check(data, ctx)

        if not isinstance(result, GuardrailResult):
            raise TypeError(
                f'Guardrail "{guardrail.name}" must return GuardrailResult, '
                f'got {type(result).__name__}'
            )
        return result

    except (TimeoutError, asyncio.TimeoutError):
        if guardrail.fail_closed:
            logger.warning(
                'Guardrail "%s" timed out (fail-closed) — triggering tripwire',
                guardrail.name,
            )
            return GuardrailResult(
                passed=False,
                reason=f'Guardrail "{guardrail.name}" timed out',
                tripwire=True,
            )
        else:
            logger.warning(
                'Guardrail "%s" timed out (fail-open) — allowing',
                guardrail.name,
            )
            return GuardrailResult(passed=True, reason='Timed out (fail-open)')

    except TypeError:
        raise
    except Exception as e:
        raise GuardrailExecutionError(guardrail.name, e) from e


async def run_guardrails(
    guardrails: list[Guardrail[Any]],
    kind: str,
    data: Any,
    ctx: Any,
    metrics: SDKMetrics | None = None,
) -> list[GuardrailResult]:
    """Run all guardrails of a given kind in parallel.

    Args:
        guardrails: All registered guardrails.
        kind: "input" or "output" to filter.
        data: The data to validate (prompt for input, output for output).
        ctx: RunContext or None.
        metrics: SDK metrics to update.

    Returns:
        List of GuardrailResult from all checks.

    Raises:
        GuardrailTripwireError: If any guardrail triggers a tripwire.
    """
    matching = [g for g in guardrails if g.kind == kind]
    if not matching:
        return []

    if metrics:
        metrics.guardrail_checks += len(matching)

    # Run all guardrails in parallel
    tasks = [_run_single_guardrail(g, data, ctx) for g in matching]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    checked_results: list[GuardrailResult] = []
    for guardrail, result in zip(matching, results, strict=False):
        if isinstance(result, BaseException):
            raise result

        checked_results.append(result)

        # Log non-passing results
        if not result.passed:
            logger.warning(
                'Guardrail "%s" failed: %s',
                guardrail.name,
                result.reason or 'no reason given',
            )

        # Tripwire halts immediately
        if result.tripwire:
            if metrics:
                metrics.guardrail_trips += 1
            raise GuardrailTripwireError(guardrail.name, result.reason)

    return checked_results
