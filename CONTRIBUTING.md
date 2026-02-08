# Contributing to Sentry Tool

Thank you for your interest in contributing to Sentry Tool!

## Development Setup

### Prerequisites

- Python >= 3.13
- uv package manager
- direnv (optional, for .envrc support)

### Initial Setup

```bash
# Navigate to project directory
cd sentry-tool

# Install dependencies (including dev dependencies)
uv sync --group dev

# Install pre-commit hooks (if configured at repository level)
pre-commit install

# Verify installation
uv run sentry-tool --help
```

### Environment Configuration

Create a `.envrc` file for local development (never commit this file):

```bash
# .envrc (example)
export SENTRY_AUTH_TOKEN=your_auth_token_here
export SENTRY_URL=https://sentry.io
export SENTRY_ORG=your-org
export SENTRY_PROJECT=your-project
```

**Security:** Never commit `.envrc` with real credentials. Use the provided `.env.template` as a guide.

## Development Workflow

### Running the CLI Locally

```bash
# Run any command
uv run sentry-tool list
uv run sentry-tool show ISSUE-ID
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_cli.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

Before committing, ensure all quality checks pass:

```bash
# Stage your changes first
git add <files>

# Run linting
uv run ruff check src tests

# Auto-fix issues
uv run ruff check --fix src tests

# Format code
uv run ruff format src tests

# Type checking (source only, not tests)
uv run mypy src

# Run pre-commit hooks on staged files
pre-commit run --files $(git diff --cached --name-only)
```

**Quality Gate:** All of the following must pass before committing:
- pytest (all tests pass)
- ruff check (no linting errors)
- mypy (no type errors)
- pre-commit hooks (all hooks pass)

### Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add dev dependency
uv add --group dev package-name

# Remove dependency
uv remove package-name

# Update all dependencies
uv sync --upgrade
```

**Always commit `uv.lock`** after changing dependencies to ensure reproducible builds.

## Code Style Guidelines

### General Principles

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Write descriptive docstrings for public APIs
- Keep functions focused and small
- Prefer composition over inheritance

### CLI Command Structure

When adding new commands:

```python
@app.command()
def new_command(
    arg: str = typer.Argument(..., help="Argument description"),
    opt: str = typer.Option("default", "--option", "-o", help="Option description"),
):
    """
    Brief command description.

    Longer description with usage examples.

    Examples:
        sentry-tool new-command value
        sentry-tool new-command value --option custom
    """
    ...
```

### Error Handling

- Use appropriate exit codes (see `ExitCode` enum in patterns)
- Write errors to stderr: `typer.echo("Error: ...", err=True)`
- Provide actionable error messages
- Never expose stack traces to users (unless --debug flag)

### Testing

- Write tests for all new features
- Use `requests-mock` for mocking Sentry API calls
- Aim for >80% code coverage
- Test both success and error paths

## Pull Request Process

1. **Create a branch** for your feature or fix
2. **Make your changes** following the style guide
3. **Write tests** for new functionality
4. **Run quality checks** (pytest, ruff, mypy, pre-commit)
5. **Update documentation** if needed (README, docstrings)
6. **Commit with clear message** describing the change
7. **Push and create PR** with detailed description

### Commit Message Format

```
type: brief description (50 chars max)

Longer description if needed, explaining why the change
was made and any important context.

Examples:
- feat: add support for filtering issues by level
- fix: handle 404 errors gracefully in show command
- docs: update README with new configuration options
- test: add tests for tag analysis command
```

## Testing Guidelines

### Unit Tests

- Test individual functions and methods
- Mock external dependencies (Sentry API)
- Focus on business logic

### Integration Tests

- Test command-line interface end-to-end
- Use `typer.testing.CliRunner`
- Mock Sentry API responses

### Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── test_cli.py          # CLI command tests
├── test_client.py       # API client tests
└── test_config.py       # Configuration tests
```

## Getting Help

- Check existing issues and PRs
- Ask questions in issues or discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
