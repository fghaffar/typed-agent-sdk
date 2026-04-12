"""Tests for typed_agent_sdk session management."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from typed_agent_sdk.errors import SessionPersistenceError, SessionVersionError
from typed_agent_sdk.session import JSONSessionBackend, Session

if TYPE_CHECKING:
    from pathlib import Path


class TestJSONSessionBackend:
    @pytest.mark.asyncio
    async def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        session = Session(session_id='test-1', messages=[{'role': 'user', 'content': 'hi'}])
        await backend.save(session)

        loaded = await backend.load('test-1')
        assert loaded is not None
        assert loaded.session_id == 'test-1'
        assert loaded.messages == [{'role': 'user', 'content': 'hi'}]

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        result = await backend.load('nonexistent')
        assert result is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        for i in range(3):
            await backend.save(Session(session_id=f'sess-{i}', agent_name='test'))

        sessions = await backend.list_sessions()
        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_delete_removes(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        await backend.save(Session(session_id='to-delete'))
        await backend.delete('to-delete')
        result = await backend.load('to-delete')
        assert result is None

    @pytest.mark.asyncio
    async def test_corrupt_json_raises(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        (tmp_path / 'sessions' / 'bad.json').write_text('not json{{{')
        with pytest.raises(SessionPersistenceError, match='load'):
            await backend.load('bad')

    @pytest.mark.asyncio
    async def test_schema_version_mismatch(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        data = {
            'schema_version': '999',
            'session_id': 'old',
            'messages': [],
            'metadata': {},
            'created_at': '2026-01-01T00:00:00+00:00',
            'updated_at': '2026-01-01T00:00:00+00:00',
        }
        (tmp_path / 'sessions' / 'old.json').write_text(json.dumps(data))
        with pytest.raises(SessionVersionError, match='999'):
            await backend.load('old')

    @pytest.mark.asyncio
    async def test_session_metadata(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        session = Session(
            session_id='meta',
            metadata={'project': 'test', 'user': 'alice'},
        )
        await backend.save(session)
        loaded = await backend.load('meta')
        assert loaded is not None
        assert loaded.metadata['project'] == 'test'

    @pytest.mark.asyncio
    async def test_parent_session_id(self, tmp_path: Path) -> None:
        backend = JSONSessionBackend(tmp_path / 'sessions')
        session = Session(session_id='child', parent_session_id='parent-1')
        await backend.save(session)
        loaded = await backend.load('child')
        assert loaded is not None
        assert loaded.parent_session_id == 'parent-1'


class TestSession:
    def test_default_id_generated(self) -> None:
        s = Session()
        assert s.session_id  # Not empty
        assert len(s.session_id) > 10  # UUID format

    def test_custom_id(self) -> None:
        s = Session(session_id='custom-123')
        assert s.session_id == 'custom-123'
