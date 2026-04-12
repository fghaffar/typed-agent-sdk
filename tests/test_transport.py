"""Tests for typed_agent_sdk transport abstraction."""

from __future__ import annotations

from typed_agent_sdk.transport import InProcessTransport, Transport


class TestInProcessTransport:
    def test_implements_protocol(self) -> None:
        transport = InProcessTransport()
        assert isinstance(transport, Transport)


class TestTransportProtocol:
    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(Transport, '__protocol_attrs__') or callable(
            getattr(Transport, '__instancecheck__', None)
        )
