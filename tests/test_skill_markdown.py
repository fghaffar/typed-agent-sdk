"""Tests for markdown skill loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from typed_agent_sdk.errors import SkillConflictError, SkillLoadError
from typed_agent_sdk.skills import SkillMarkdown, load_skills

if TYPE_CHECKING:
    from pathlib import Path


class TestLoadSkills:
    def test_load_valid_skill(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'valid.md').write_text(
            '---\nname: valid-skill\ndescription: A valid skill\n'
            'tools: [read, grep]\n---\nDo stuff.\n'
        )
        skills = load_skills(tmp_skills_dir)
        assert len(skills) == 1
        assert skills[0].name == 'valid-skill'
        assert skills[0].description == 'A valid skill'
        assert skills[0].tools == ['read', 'grep']
        assert skills[0].instructions == 'Do stuff.'

    def test_arguments_placeholder(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'args.md').write_text(
            '---\nname: argskill\ndescription: Uses args\n---\nProcess: $ARGUMENTS\n'
        )
        skills = load_skills(tmp_skills_dir)
        replaced = skills[0].with_arguments('my input data')
        assert 'my input data' in replaced.instructions
        assert '$ARGUMENTS' not in replaced.instructions

    def test_nested_directory_namespacing(self, tmp_skills_dir: Path) -> None:
        sub = tmp_skills_dir / 'coding'
        sub.mkdir()
        (sub / 'reviewer.md').write_text(
            '---\nname: reviewer\ndescription: Reviews code\n---\nReview code.\n'
        )
        skills = load_skills(tmp_skills_dir)
        assert len(skills) == 1
        assert skills[0].name == 'coding.reviewer'

    def test_invalid_yaml_raises(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'bad.md').write_text('---\n: invalid: yaml:\n---\nBody\n')
        with pytest.raises(SkillLoadError, match='Invalid YAML'):
            load_skills(tmp_skills_dir)

    def test_missing_name_raises(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'noname.md').write_text('---\ndescription: No name field\n---\nBody\n')
        with pytest.raises(SkillLoadError, match='Missing required field: name'):
            load_skills(tmp_skills_dir)

    def test_missing_description_raises(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'nodesc.md').write_text('---\nname: test\n---\nBody\n')
        with pytest.raises(SkillLoadError, match='Missing required field: description'):
            load_skills(tmp_skills_dir)

    def test_non_utf8_file_raises(self, tmp_skills_dir: Path) -> None:
        bad_file = tmp_skills_dir / 'binary.md'
        bad_file.write_bytes(b'\x80\x81\x82invalid utf8')
        with pytest.raises(SkillLoadError, match='Not a valid UTF-8'):
            load_skills(tmp_skills_dir)

    def test_dashes_in_body(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'dashes.md').write_text(
            '---\nname: dashes\ndescription: Has dashes in body\n---\nLine 1\n---\nLine 3\n'
        )
        skills = load_skills(tmp_skills_dir)
        assert '---' in skills[0].instructions
        assert 'Line 3' in skills[0].instructions

    def test_empty_directory_returns_empty(self, tmp_skills_dir: Path) -> None:
        skills = load_skills(tmp_skills_dir)
        assert skills == []

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path) -> None:
        skills = load_skills(tmp_path / 'nonexistent')
        assert skills == []

    def test_handoffs_frontmatter(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'with-handoffs.md').write_text(
            '---\nname: delegator\ndescription: Delegates work\n'
            'handoffs:\n  - label: Code Review\n    agent: reviewer\n    prompt: Review this\n'
            '---\nDelegate tasks.\n'
        )
        skills = load_skills(tmp_skills_dir)
        assert len(skills[0].handoffs) == 1
        assert skills[0].handoffs[0].label == 'Code Review'
        assert skills[0].handoffs[0].agent == 'reviewer'

    def test_duplicate_name_raises(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'a.md').write_text('---\nname: dupe\ndescription: First\n---\nA\n')
        (tmp_skills_dir / 'b.md').write_text('---\nname: dupe\ndescription: Second\n---\nB\n')
        with pytest.raises(SkillConflictError, match='dupe'):
            load_skills(tmp_skills_dir)

    def test_safe_load_blocks_dangerous_yaml(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'evil.md').write_text(
            '---\nname: evil\ndescription: Bad\ndata: !!python/name:builtins.print\n---\nBody\n'
        )
        with pytest.raises(SkillLoadError, match='Invalid YAML'):
            load_skills(tmp_skills_dir)


class TestSkillMarkdown:
    def test_with_arguments_returns_copy(self) -> None:
        skill = SkillMarkdown(name='test', description='Test', instructions='Do $ARGUMENTS now')
        replaced = skill.with_arguments('the thing')
        assert replaced.instructions == 'Do the thing now'
        assert skill.instructions == 'Do $ARGUMENTS now'  # Original unchanged

    def test_source_path_preserved(self, tmp_skills_dir: Path) -> None:
        (tmp_skills_dir / 'src.md').write_text(
            '---\nname: src\ndescription: Has source\n---\nBody\n'
        )
        skills = load_skills(tmp_skills_dir)
        assert skills[0].source_path == tmp_skills_dir / 'src.md'
