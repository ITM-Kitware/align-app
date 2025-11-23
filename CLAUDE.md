# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a web application showcasing the Align AI Decision Maker library for making human-value aligned decisions in ethical scenarios. The app is built with Python using the Trame framework for web UI and integrates with HuggingFace models via the align-system library.

## Development Setup
```bash
# Install with development dependencies
poetry install --with dev
pre-commit install

# Set required environment variable for HuggingFace models
export HF_TOKEN=<your_huggingface_token>
```

## Common Commands

### Running the Application
```bash
# Start the web server (default port 8080)
poetry run align-app

# Custom port/host
poetry run align-app --port 8081 --host 0.0.0.0
```

### Development Tools
```bash
# Run all tests
poetry run pytest

# Run end-to-end tests
poetry run pytest tests/e2e/ -v

# Run e2e tests with full output
poetry run pytest tests/e2e/ -xvs

# Lint and format code
ruff check --fix
ruff format

# Type checking
mypy align_app/

# Run all pre-commit hooks
pre-commit run --all-files

# Fix codespell issues
codespell -w
```

## Architecture

### Core Components
- `align_app/app/`: Web application framework using Trame
  - `core.py`: Main AlignApp class and UI components
  - `main.py`: Application entry point
  - `ui.py`: User interface layout and interactions
  - `prompt.py`: Prompt management for LLM interactions

- `align_app/adm/`: AI Decision Maker integration
  - `adm_core.py`: Core ADM functionality and model management
  - `decider.py`: Decision logic and scenario processing
  - `multiprocess_decider.py`: Multi-process decision handling
  - `input_output_files/`: Training data and scenarios (NAACL24, OpinionQA datasets)

- `align_app/utils/`: Shared utilities

### Key Dependencies
- `align-system`: Core AI decision making library (git dependency)
- `trame`: Web framework for Python applications
- `hydra-core`/`omegaconf`: Configuration management
- HuggingFace ecosystem for LLM backends

### Model Integration
The app supports various LLM backbones through HuggingFace transformers. Models are cached locally after first download. ADM types include different decision-making algorithms that can be configured via the UI.

### Data Flow
1. User selects ADM type, LLM backbone, alignment targets, and scenario via web UI
2. Parameters are processed through `adm_core.py` using Hydra configuration
3. Decision is made using the align-system library
4. Result with justification is returned to the UI for comparison with previous decisions

### Design Patterns

#### Unidirectional State Flow (Three-Layer Architecture)
1. **Functional Core** (`*_core.py`) - Pure functions on immutable data structures
   - Example: `add_run(data: Runs, run: Run) -> Runs`
2. **Registry** (`*_registry.py`) - State management via closures with `nonlocal data`
   - Calls functional core, captures returned state
3. **State Adapter** (`*_state_adapter.py`) - Trame UI bridge
   - Controllers trigger registry, sync to reactive state

Flow: UI → Adapter → Registry → Core → new data → Registry → Adapter → UI

#### Functional Programming
- Immutable data: `@dataclass(frozen=True)`, `replace()` instead of mutation
- Pure transformations: return new collections, no in-place modifications
- Separation: pure logic in `*_core.py`, side effects in registry/adapter
- Data-first: `fn(data: DataType, ...params) -> DataType`

## Testing

### End-to-End Tests
E2e tests use Playwright to test the full application stack. The test infrastructure captures all backend server logs, prints, and errors:
- Backend stdout and stderr are captured in real-time
- All logs are displayed after each test (both passing and failing)
- Backend errors and tracebacks are included in test failure reports
- Add `print()` statements in backend code to debug during e2e tests

## Pre-commit Configuration
- `codespell`: Spell checking (excludes .json files and CHANGELOG.md)
- `ruff`: Code linting and formatting
- `mypy`: Type checking with PyYAML types support

## Workflow Reminders
- Run ruff format after changes

## Development Guidelines
- **ALWAYS** do not add descriptive comments
- **ALWAYS** run ruff format after changes