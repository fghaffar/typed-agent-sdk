"""Tests for typed_agent_sdk system tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from typed_agent_sdk.errors import EditAmbiguousError, EditNotFoundError
from typed_agent_sdk.system_tools import (
    SystemTools,
    bash,
    file_edit,
    file_read,
    file_write,
    glob_files,
    grep_content,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestBash:
    @pytest.mark.asyncio
    async def test_echo(self) -> None:
        result = await bash('echo hello')
        assert 'hello' in result

    @pytest.mark.asyncio
    async def test_timeout_kills(self) -> None:
        result = await bash('sleep 999', timeout=0.1)
        assert 'timed out' in result

    @pytest.mark.asyncio
    async def test_empty_command_raises(self) -> None:
        with pytest.raises(ValueError, match='empty'):
            await bash('')

    @pytest.mark.asyncio
    async def test_output_truncation(self) -> None:
        # Generate output > 100 bytes
        result = await bash('python3 -c "print(\'x\' * 500)"', max_output_bytes=100)
        assert 'TRUNCATED' in result

    @pytest.mark.asyncio
    async def test_cwd(self, tmp_path: Path) -> None:
        result = await bash('pwd', cwd=tmp_path)
        assert str(tmp_path) in result

    @pytest.mark.asyncio
    async def test_stderr_included(self) -> None:
        result = await bash('echo err >&2')
        assert 'err' in result


class TestFileRead:
    @pytest.mark.asyncio
    async def test_reads_content(self, tmp_path: Path) -> None:
        f = tmp_path / 'test.txt'
        f.write_text('line1\nline2\nline3\n')
        result = await file_read('test.txt', cwd=tmp_path)
        assert 'line1' in result
        assert 'line2' in result

    @pytest.mark.asyncio
    async def test_offset_limit(self, tmp_path: Path) -> None:
        f = tmp_path / 'test.txt'
        f.write_text('\n'.join(f'line{i}' for i in range(10)))
        result = await file_read('test.txt', cwd=tmp_path, offset=2, limit=3)
        assert 'line2' in result
        assert 'line4' in result
        assert 'line0' not in result

    @pytest.mark.asyncio
    async def test_binary_detection(self, tmp_path: Path) -> None:
        f = tmp_path / 'binary.bin'
        f.write_bytes(b'\x00\x01\x02binary content')
        result = await file_read('binary.bin', cwd=tmp_path)
        assert 'Binary file' in result

    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path: Path) -> None:
        result = await file_read('nonexistent.txt', cwd=tmp_path)
        assert 'not found' in result

    @pytest.mark.asyncio
    async def test_sandbox_blocks_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(PermissionError, match='escapes sandbox'):
            await file_read('../../etc/passwd', cwd=tmp_path, sandbox=True)


class TestFileWrite:
    @pytest.mark.asyncio
    async def test_creates_file(self, tmp_path: Path) -> None:
        result = await file_write('new.txt', 'hello world', cwd=tmp_path)
        assert 'written' in result
        assert (tmp_path / 'new.txt').read_text() == 'hello world'

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        await file_write('sub/dir/file.txt', 'content', cwd=tmp_path)
        assert (tmp_path / 'sub' / 'dir' / 'file.txt').exists()


class TestFileEdit:
    @pytest.mark.asyncio
    async def test_replaces(self, tmp_path: Path) -> None:
        f = tmp_path / 'edit.txt'
        f.write_text('hello world')
        result = await file_edit('edit.txt', 'world', 'universe', cwd=tmp_path)
        assert 'replaced' in result
        assert f.read_text() == 'hello universe'

    @pytest.mark.asyncio
    async def test_not_found_raises(self, tmp_path: Path) -> None:
        f = tmp_path / 'edit.txt'
        f.write_text('hello world')
        with pytest.raises(EditNotFoundError):
            await file_edit('edit.txt', 'missing', 'new', cwd=tmp_path)

    @pytest.mark.asyncio
    async def test_ambiguous_raises(self, tmp_path: Path) -> None:
        f = tmp_path / 'edit.txt'
        f.write_text('hello hello hello')
        with pytest.raises(EditAmbiguousError, match='3 times'):
            await file_edit('edit.txt', 'hello', 'hi', cwd=tmp_path)

    @pytest.mark.asyncio
    async def test_file_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(EditNotFoundError):
            await file_edit('nonexistent.txt', 'old', 'new', cwd=tmp_path)


class TestGlob:
    @pytest.mark.asyncio
    async def test_finds_files(self, tmp_path: Path) -> None:
        (tmp_path / 'a.py').write_text('# a')
        (tmp_path / 'b.py').write_text('# b')
        (tmp_path / 'c.txt').write_text('c')
        result = await glob_files('*.py', cwd=tmp_path)
        assert 'a.py' in result
        assert 'b.py' in result
        assert 'c.txt' not in result

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_path: Path) -> None:
        result = await glob_files('*.xyz', cwd=tmp_path)
        assert 'No files' in result


class TestGrep:
    @pytest.mark.asyncio
    async def test_finds_content(self, tmp_path: Path) -> None:
        (tmp_path / 'search.py').write_text('def hello_world():\n    pass\n')
        result = await grep_content('hello_world', cwd=tmp_path)
        assert 'search.py' in result

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_path: Path) -> None:
        (tmp_path / 'empty.py').write_text('# nothing here')
        result = await grep_content('nonexistent_pattern_xyz', cwd=tmp_path)
        assert 'No matches' in result


class TestSystemToolsSkill:
    def test_default_all_tools(self) -> None:
        st = SystemTools()
        assert st.name == 'system_tools'
        assert len(st.tools) == 6

    def test_selective_enabling(self) -> None:
        st = SystemTools(allowed=['file_read', 'grep'])
        assert len(st.tools) == 2

    def test_custom_cwd(self, tmp_path: Path) -> None:
        st = SystemTools(cwd=tmp_path)
        assert st._cwd == tmp_path

    def test_custom_timeout(self) -> None:
        st = SystemTools(bash_timeout=30.0)
        assert st._bash_timeout == 30.0
