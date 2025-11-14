# Contributing to align-app

1.  Clone the repository using `git clone`
2.  Install pre-commit via `pip install pre-commit`
3.  Run `pre-commit install` to set up pre-commit hooks
4.  Make changes to the code, and commit your changes to a separate branch
5.  Create a fork of the repository on GitHub
6.  Push your branch to your fork, and open a pull request

## Running E2E Tests

The project includes end-to-end tests using Playwright to test the full application workflow.

### Setup

1. Install development dependencies including Playwright:
   ```bash
   poetry install --with dev
   ```

2. Install Playwright browsers:
   ```bash
   poetry run playwright install chromium
   ```

### Running Tests Locally

Run all E2E tests:
```bash
poetry run pytest tests/e2e/
```

Run with verbose output:
```bash
poetry run pytest tests/e2e/ -v
```

Run in headed mode (visible browser):
```bash
poetry run pytest tests/e2e/ --headed
```

### Test Structure

- `tests/e2e/conftest.py` - Test fixtures for app server and browser configuration
- `tests/e2e/page_objects/` - Page object models for UI interactions
- `tests/e2e/test_*.py` - Test files

### CI/CD

E2E tests run automatically on pull requests and pushes to main via GitHub Actions (`.github/workflows/e2e-tests.yml`). Tests run in headless mode on Ubuntu with Chromium.

## Tips

- When first creating a new project, it is helpful to run `pre-commit run --all-files` to ensure all files pass the pre-commit checks.
- A quick way to fix `ruff` issues is by installing ruff (`pip install ".[dev]"`) and running the `ruff check --fix` command at the root of your repository.
- A quick way to fix `codespell` issues is by installing codespell (`pip install codespell`) and running the `codespell -w` command at the root of your directory.
- The `.codespellrc file <https://github.com/codespell-project/codespell#using-a-config-file>`\_ can be used fix any other codespell issues, such as ignoring certain files, directories, words, or regular expressions.
