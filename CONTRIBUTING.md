# Contributing to typed-agent-sdk

Thank you for considering contributing to typed-agent-sdk!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/fghaffar/typed-agent-sdk.git
cd typed-agent-sdk

# Install with dev dependencies
pip install -e ".[dev]"

# Verify everything works
pytest tests/ -v
ruff check .
mypy --strict typed_agent_sdk/
```

## Code Style

- Python 3.10+ with strict typing
- `ruff` for linting and formatting
- `mypy --strict` for type checking
- Google-style docstrings on all public APIs
- Async-first design (sync wrappers via anyio where needed)

## Pull Request Process

1. Fork the repo and create your branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Ensure linting passes: `ruff check . && ruff format --check .`
5. Ensure type checking passes: `mypy --strict typed_agent_sdk/`
6. Update documentation if you changed public APIs
7. Open a PR with a clear description of your changes

## Reporting Issues

- Use GitHub Issues
- Include Python version, OS, and a minimal reproducible example
- Check existing issues before opening a new one

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
