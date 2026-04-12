"""Tests for typed_agent_sdk._utils."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from typed_agent_sdk._utils import (
    glob_match,
    parse_frontmatter,
    truncate_output,
    validate_path_sandbox,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestGlobMatch:
    def test_exact_match(self) -> None:
        assert glob_match('calculate', 'calculate') is True

    def test_exact_no_match(self) -> None:
        assert glob_match('calculate', 'search') is False

    def test_wildcard_suffix(self) -> None:
        assert glob_match('file_*', 'file_read') is True
        assert glob_match('file_*', 'file_write') is True
        assert glob_match('file_*', 'search') is False

    def test_wildcard_prefix(self) -> None:
        assert glob_match('*_tool', 'search_tool') is True
        assert glob_match('*_tool', 'calculate') is False

    def test_star_matches_all(self) -> None:
        assert glob_match('*', 'anything') is True

    def test_question_mark(self) -> None:
        assert glob_match('file_?', 'file_a') is True
        assert glob_match('file_?', 'file_ab') is False

    def test_special_chars_in_name(self) -> None:
        assert glob_match('mcp__*', 'mcp__server__tool') is True


class TestParseFrontmatter:
    def test_valid_frontmatter(self) -> None:
        content = '---\nname: test\ndescription: A test\n---\nBody text here'
        fm, body = parse_frontmatter(content)
        assert fm['name'] == 'test'
        assert fm['description'] == 'A test'
        assert body == 'Body text here'

    def test_frontmatter_with_list(self) -> None:
        content = '---\nname: test\ntools:\n  - file_read\n  - grep\n---\nBody'
        fm, _body = parse_frontmatter(content)
        assert fm['tools'] == ['file_read', 'grep']

    def test_missing_frontmatter_raises(self) -> None:
        with pytest.raises(ValueError, match='No YAML frontmatter found'):
            parse_frontmatter('Just body text')

    def test_missing_closing_delimiter_raises(self) -> None:
        with pytest.raises(ValueError, match='No closing ---'):
            parse_frontmatter('---\nname: test\nBody without closing')

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(ValueError, match='Invalid YAML'):
            parse_frontmatter('---\n: invalid: yaml:\n---\nBody')

    def test_dashes_in_body_not_treated_as_delimiter(self) -> None:
        content = '---\nname: test\n---\nBody with\n---\nmore dashes'
        fm, body = parse_frontmatter(content)
        assert fm['name'] == 'test'
        assert '---' in body
        assert 'more dashes' in body

    def test_empty_body(self) -> None:
        content = '---\nname: test\n---\n'
        fm, body = parse_frontmatter(content)
        assert fm['name'] == 'test'
        assert body == ''

    def test_scalar_yaml_raises(self) -> None:
        with pytest.raises(ValueError, match='must be a mapping'):
            parse_frontmatter('---\njust a string\n---\nBody')

    def test_safe_load_blocks_dangerous_tags(self) -> None:
        # Verify yaml.safe_load rejects dangerous YAML tags
        content = '---\ndata: !!python/name:builtins.print\n---\nBody'
        with pytest.raises(ValueError, match='Invalid YAML'):
            parse_frontmatter(content)


class TestValidatePathSandbox:
    def test_valid_subpath(self, tmp_path: Path) -> None:
        subfile = tmp_path / 'subdir' / 'file.txt'
        result = validate_path_sandbox('subdir/file.txt', tmp_path)
        assert result == subfile

    def test_traversal_blocked(self, tmp_path: Path) -> None:
        with pytest.raises(PermissionError, match='escapes sandbox'):
            validate_path_sandbox('../../../etc/passwd', tmp_path)

    def test_absolute_path_outside_cwd(self, tmp_path: Path) -> None:
        with pytest.raises(PermissionError, match='escapes sandbox'):
            validate_path_sandbox('/etc/passwd', tmp_path)

    def test_path_at_cwd_root(self, tmp_path: Path) -> None:
        result = validate_path_sandbox('file.txt', tmp_path)
        assert result == tmp_path / 'file.txt'

    def test_dot_path_stays_in_sandbox(self, tmp_path: Path) -> None:
        result = validate_path_sandbox('./file.txt', tmp_path)
        assert result == tmp_path / 'file.txt'


class TestTruncateOutput:
    def test_under_limit(self) -> None:
        text = 'short text'
        assert truncate_output(text, max_bytes=1000) == text

    def test_at_limit(self) -> None:
        text = 'x' * 100
        assert truncate_output(text, max_bytes=100) == text

    def test_over_limit_truncates(self) -> None:
        text = 'x' * 200
        result = truncate_output(text, max_bytes=100)
        assert '[OUTPUT TRUNCATED' in result
        assert len(result.encode('utf-8')) < 200

    def test_default_5mb_limit(self) -> None:
        text = 'short'
        assert truncate_output(text) == text

    def test_unicode_safe(self) -> None:
        text = 'a' * 50 + '\U0001f600' * 50
        result = truncate_output(text, max_bytes=100)
        assert '[OUTPUT TRUNCATED' in result
