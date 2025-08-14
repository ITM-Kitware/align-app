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
# Run tests
poetry run pytest

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

## Pre-commit Configuration
- `codespell`: Spell checking (excludes .json files and CHANGELOG.md)
- `ruff`: Code linting and formatting
- `mypy`: Type checking with PyYAML types support

## Workflow Reminders
- Run ruff format after changes

## Development Guidelines
- **ALWAYS** do not add descriptive comments
- **ALWAYS** run ruff format after changes