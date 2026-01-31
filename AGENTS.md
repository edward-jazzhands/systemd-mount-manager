# AGENTS.md

This file contains guidelines and commands for agentic coding agents working on the systemd-mount-manager project.

## Project Overview

Systemd Mount Manager is a Python CLI/TUI/GUI application for managing systemd mount units. It uses Click for CLI, Textual for TUI, and follows a layered architecture separating pure logic, system interaction, and interfaces.

## Development Commands

The project uses `just` for task automation. Use `just --list` to see all available commands. Prefer to use the justfile for available tasks, but the commands below are provided for reference.

### Installation and Setup
```bash
# Install dependencies and set up environment
just install
```

### Code Quality Tools
```bash
# Format code with Black (line length: 100)
just format
# Or: uv run black src/

# Lint with Ruff
just lint
# Or: uv run ruff check src/

# Type checking with MyPy and basedpyright
just typecheck
# Or: uv run mypy src/ && uv run basedpyright src/
```

### Testing
```bash
# Run all tests with verbose output
just test
# Or: uv run pytest tests -v

# Run single test file
# uv run pytest tests/test_file.py

# Run single test function
# uv run pytest tests/test_file.py::test_function

# Run with coverage
# uv run pytest --cov=src/systemd_mount_manager [this is incomplete do not use]

# Run the Nox testing suite for comprehensive testing.
# just nox [this is incomplete do not use]
```

### Development and Debugging
```bash
# Run the CLI with flags
# just run [this is incomplete do not use]

# Run TUI in development mode
just run --dev tui
# Or: uv run textual run --dev src/systemd_mount_manager/tui/tui_main.py

# Run GUI in development mode
# just run --dev gui [this is incomplete do not use]

# Run Textual console for debugging
just console

# Run original bash script
# src/systemd_mount_manager/original.py [Do not run this. Its just for reference]
```

### Build and Distribution
```bash

# You do not have permission to build packages

```

### Environment Management
```bash
# Clean caches and temporary files
just clean

# Remove virtual environment and lock file
just del-env

# Full nuke (clean + delete environment)
just nuke

# Complete reset (nuke then reinstall)
just reset

```

## Code Style Guidelines

### Python Version and Imports
- Target Python 3.10+ (project requires ~=3.12.0)
- All files must start with `from __future__ import annotations`
- Use standard library imports first, then third-party, then local imports
- Group imports by category with blank lines between groups
- Use absolute imports for local modules (e.g., `import systemd_mount_manager.logic`)

### Code Formatting
- Use Black with line length of 100 characters
- Follow PEP 8 conventions
- Use f-strings for string formatting
- Prefer explicit type hints for all function parameters and return values

### Type Hints
- Use strict type checking (configured in basedpyright and mypy)
- Use `str | None` syntax instead of `Optional[str]`
- Use `list[str]` instead of `List[str]`
- Use `dict[str, str]` instead of `Dict[str, str]`
- All functions should have complete type annotations

### Naming Conventions
- Classes: `PascalCase` (e.g., `CustomHeader`, `SettingsTab`)
- Functions and variables: `snake_case` (e.g., `tui_run`, `debug_msg`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `CSS_PATH`, `TITLE`)
- Private methods: prefix with underscore (`_internal_method`)
- Module names: `snake_case`

### Error Handling
- Use specific exceptions where possible
- Log errors using appropriate logging mechanisms
- For CLI operations, use `click.echo()` for user messages
- For TUI operations, use Textual's built-in error handling
- Validate user input before processing

### Architecture Guidelines

#### Module Structure
The project follows a three-layer architecture:
1. **Pure Logic Module Group** (`src/systemd_mount_manager/logic/`): Deterministic transformations, validation for filesystem, sudo, systemctl operations. No I/O. Usable by CLI, TUI, and GUI.
2. **Outer CLI** (`src/systemd_mount_manager/main.py`): CLI entry point - controls dropping into TUI, GUI, or stdio mode, and handles CLI commands / flags.
3. **Interfaces** (`src/systemd_mount_manager/main.py`, `tui/`, `gui/`): CLI, TUI, GUI

#### Import Patterns
- Import logic modules as: `import systemd_mount_manager.logic as logic`
- Access specific logic functions: `logic.config.write_default_config()`
- NEVER import UI modules from logic modules
- Logic modules CAN import other logic modules

#### CLI and Click Usage
- Use `@click.group()` for main commands
- Use `@click.pass_context` to pass context between commands
- Use `click.echo()` for output (not `print()`)
- Use `click.Abort()` for fatal errors
- Validate input with Click's built-in validators

#### TUI and Textual Usage
- Use `TabPane` for main content areas
- Implement `compose()` -> `ComposeResult` for widget composition
- Use `@on` decorators for event handling
- Follow the widget naming pattern: `ClassWidget`, `ClassTab`, `ClassScreen`
- Use `Binding` class for keyboard shortcuts

### Testing Guidelines
- Write tests for all pure logic functions
- Use pytest fixtures for test setup
- Mock system interactions in tests
- Test error conditions and edge cases
- Use descriptive test names

### Documentation
- Use docstrings for all public functions and classes
- Include parameter and return type documentation
- Keep comments minimal and explanatory
- Document complex algorithms or business logic with a comment block if necessary

### File Organization
```
src/systemd_mount_manager/
├── main.py                 # CLI entry point
├── logic/                  # Pure logic and system interaction
│   ├── core.py            # System operations (sudo, subprocess)
│   ├── config.py          # Configuration management
│   ├── mounts.py          # Mount data structures and logic
│   └── ...
├── tui/                    # Textual user interface
│   ├── tui_main.py        # Main TUI application
│   ├── dashboard.py       # Dashboard tab
│   ├── settings.py        # Settings tab
│   └── ...
└── gui/                    # GTK user interface (placeholder)
    └── ...
```

### Security Considerations
- Use the sudo caching for elevated operations
- Validate file paths to prevent directory traversal
- Handle user input sanitization
- Use proper permission checking for file operations

### Git Workflow
- You do not have permission to use git whatsoever.
- You have been set up to work on your own branch where you are free to build whatever you want.
- When you're happy with your work, make a request for a git commit. The admin will review your work and commit for you.

### Performance Guidelines
- Use async/await for I/O operations in TUI
- Cache expensive computations where appropriate
- Avoid blocking operations in UI threads
- Use efficient data structures for large datasets

## Configuration Files

- `pyproject.toml`: Project metadata, dependencies, tool configurations
- `basedpyright` and `mypy` configured for strict type checking
- `black` configured with line length 100
- `pytest` configured with `asyncio_mode = "auto"`

This project emphasizes code quality, type safety, and clear separation of concerns. All contributions should follow these guidelines to maintain consistency and reliability.