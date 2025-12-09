"""Shared loader for experiment config files."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Any
import yaml


@lru_cache(maxsize=256)
def load_experiment_adm_config(experiment_path: Path) -> Dict[str, Any] | None:
    """Load the adm section from experiment's .hydra/config.yaml.

    Args:
        experiment_path: Path to the experiment directory (containing .hydra/)

    Returns:
        The 'adm' section of the config, or None if not found
    """
    config_path = experiment_path / ".hydra" / "config.yaml"
    if not config_path.exists():
        return None
    with open(config_path) as f:
        full_config = yaml.safe_load(f)
    return full_config.get("adm", {})
