"""Shared pytest fixtures for align-app tests."""

import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import pytest

EXPERIMENTS_ZIP_URL = (
    "https://github.com/ITM-Kitware/align-app/releases/download/v1.0.0/experiments.zip"
)

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_CACHE_DIR = REPO_ROOT / "tests" / "fixtures" / ".cache"


@pytest.fixture(scope="session")
def experiments_fixtures_path() -> Path:
    """Download and cache experiment fixtures for testing.

    Downloads experiments.zip from GitHub releases, extracts it, and caches
    the result in tests/fixtures/.cache/ (gitignored).
    """
    FIXTURES_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    experiments_dir = FIXTURES_CACHE_DIR / "experiments"
    zip_path = FIXTURES_CACHE_DIR / "experiments.zip"

    if experiments_dir.exists() and any(experiments_dir.iterdir()):
        return experiments_dir

    if not zip_path.exists():
        print(f"\nDownloading experiment fixtures from {EXPERIMENTS_ZIP_URL}...")
        urlretrieve(EXPERIMENTS_ZIP_URL, zip_path)

    print(f"\nExtracting experiment fixtures to {experiments_dir}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(FIXTURES_CACHE_DIR)

    return experiments_dir
