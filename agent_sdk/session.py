"""Session management for agent_sdk.

Provides conversation persistence, resumption, and forking.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from agent_sdk.errors import SessionNotFoundError, SessionPersistenceError, SessionVersionError

logger = logging.getLogger('agent_sdk.session')

SCHEMA_VERSION = '1'


@dataclass
class SessionInfo:
    """Summary info about a session (for listing)."""

    session_id: str
    agent_name: str | None
    created_at: str
    updated_at: str


@dataclass
class Session:
    """A persistent conversation state."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_name: str | None = None
    parent_session_id: str | None = None


@runtime_checkable
class SessionBackend(Protocol):
    """Protocol for session storage backends."""

    async def save(self, session: Session) -> None: ...
    async def load(self, session_id: str) -> Session | None: ...
    async def list_sessions(self, limit: int = 100) -> list[SessionInfo]: ...
    async def delete(self, session_id: str) -> None: ...


class JSONSessionBackend:
    """File-based session backend using JSON files.

    Each session is stored as a separate JSON file in the directory.
    """

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self._dir / f'{session_id}.json'

    async def save(self, session: Session) -> None:
        """Save a session to a JSON file."""
        session.updated_at = datetime.now(timezone.utc)
        data = {
            'schema_version': SCHEMA_VERSION,
            'session_id': session.session_id,
            'messages': session.messages,
            'metadata': session.metadata,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'agent_name': session.agent_name,
            'parent_session_id': session.parent_session_id,
        }
        try:
            path = self._session_path(session.session_id)
            path.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
        except OSError as e:
            raise SessionPersistenceError('save', e) from e

    async def load(self, session_id: str) -> Session | None:
        """Load a session from a JSON file."""
        path = self._session_path(session_id)
        if not path.exists():
            return None

        try:
            text = path.read_text(encoding='utf-8')
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise SessionPersistenceError('load', e) from e
        except OSError as e:
            raise SessionPersistenceError('load', e) from e

        # Check schema version
        version = data.get('schema_version', '0')
        if version != SCHEMA_VERSION:
            raise SessionVersionError(version, SCHEMA_VERSION)

        return Session(
            session_id=data['session_id'],
            messages=data.get('messages', []),
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            agent_name=data.get('agent_name'),
            parent_session_id=data.get('parent_session_id'),
        )

    async def list_sessions(self, limit: int = 100) -> list[SessionInfo]:
        """List all sessions, most recently updated first."""
        sessions = []
        for path in sorted(self._dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(sessions) >= limit:
                break
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                sessions.append(
                    SessionInfo(
                        session_id=data['session_id'],
                        agent_name=data.get('agent_name'),
                        created_at=data.get('created_at', ''),
                        updated_at=data.get('updated_at', ''),
                    )
                )
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return sessions

    async def delete(self, session_id: str) -> None:
        """Delete a session file."""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
