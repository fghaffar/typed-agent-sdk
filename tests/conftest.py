"""Shared test fixtures for typed_agent_sdk tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

if TYPE_CHECKING:
    from pathlib import Path


def make_tool_call_model(
    tool_name: str = 'test_tool',
    tool_args: dict[str, Any] | None = None,
) -> FunctionModel:
    """Create a FunctionModel that calls a specific tool then returns text."""

    call_count = 0

    async def model_func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal call_count
        call_count += 1

        # First call: make the tool call
        if call_count == 1:
            return ModelResponse(
                parts=[ToolCallPart(tool_name=tool_name, args=tool_args or {}, tool_call_id='tc_1')]
            )
        # Second call: return final text
        return ModelResponse(parts=[TextPart(content='Done.')])

    return FunctionModel(model_func)


def make_text_model(response: str = 'Hello from test model.') -> FunctionModel:
    """Create a FunctionModel that returns a simple text response."""

    async def model_func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=response)])

    return FunctionModel(model_func)


@pytest.fixture
def tool_call_model() -> FunctionModel:
    """FunctionModel that calls 'test_tool' then returns text."""
    return make_tool_call_model()


@pytest.fixture
def text_model() -> FunctionModel:
    """FunctionModel that returns simple text."""
    return make_text_model()


@pytest.fixture
def tmp_skills_dir(tmp_path: Path) -> Path:
    """Temporary directory for markdown skill files."""
    skills_dir = tmp_path / 'skills'
    skills_dir.mkdir()
    return skills_dir


@pytest.fixture
def sample_skill_md(tmp_skills_dir: Path) -> Path:
    """Create a sample markdown skill file."""
    skill_file = tmp_skills_dir / 'test-skill.md'
    skill_file.write_text(
        '---\n'
        'name: test-skill\n'
        'description: A test skill\n'
        'tools: [file_read, grep]\n'
        '---\n'
        '\n'
        'You are a test skill. Arguments: $ARGUMENTS\n'
    )
    return skill_file
