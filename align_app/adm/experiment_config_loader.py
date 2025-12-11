"""Shared loader for experiment config files."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Any
import yaml


@lru_cache(maxsize=256)
def load_experiment_adm_config(experiment_path: Path) -> Dict[str, Any] | None:
    """Load the adm config from experiment's .hydra/config.yaml."""
    config_path = experiment_path / ".hydra" / "config.yaml"
    if not config_path.exists():
        return None
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config.get("adm", config)
