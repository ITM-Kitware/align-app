"""
Unified Hydra configuration loader for ADM configs.

This module provides a single, unified loader that handles both regular ADM configs
and experiment configs with @package _global_ directives.
"""

from pathlib import Path
from typing import Dict, Any, Optional, cast
from functools import lru_cache
import logging

import align_system
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf

logger = logging.getLogger(__name__)


def _find_config_file(config_path: str, config_dir_path: Path) -> Path | None:
    config_path_obj = Path(config_path)

    if config_path_obj.exists():
        return config_path_obj

    if config_path_obj.is_absolute() and config_path_obj.exists():
        return config_path_obj

    search_locations = [
        config_dir_path / config_path,
        config_dir_path / f"adm/{config_path}",
        config_dir_path / f"experiment/{config_path}",
    ]

    for test_path in search_locations:
        if test_path.exists():
            return test_path

    experiment_dir = config_dir_path / "experiment"
    if experiment_dir.exists():
        for subdir in experiment_dir.iterdir():
            if subdir.is_dir():
                test_file = subdir / config_path
                if test_file.exists():
                    return test_file

    return config_dir_path / config_path


def _get_hydra_config_path(config_file: Path, config_dir_path: Path) -> str:
    """Get the config path for Hydra - relative path without extension."""
    try:
        relative_path = config_file.relative_to(config_dir_path)
        return relative_path.with_suffix("").as_posix()
    except ValueError:
        return config_file.stem


@lru_cache(maxsize=32)
def load_adm_config(
    config_path: str,
    config_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Universal config loader for ADM configs with caching.

    Creates a fresh Hydra context for each unique configuration to avoid
    state pollution. Uses LRU cache to maintain performance for repeated loads.

    The config type (experiment vs regular) is determined by the presence of
    '# @package _global_' directive in the YAML file, NOT by the path.

    Args:
        config_path: Path to config file or config name (e.g., "adm/pipeline_baseline")
        config_dir: Base config directory (auto-detected if None)

    Returns:
        Loaded configuration dictionary
    """
    if config_dir is None:
        try:
            config_dir = str(Path(align_system.__file__).parent / "configs")
        except ImportError:
            raise ValueError(
                "Could not auto-detect config_dir. Please provide it explicitly."
            )

    config_dir_path = Path(config_dir)
    config_file = _find_config_file(config_path, config_dir_path)

    if not config_file or not config_file.exists():
        raise ValueError(f"Could not find config file: {config_path}")

    hydra_config_path = _get_hydra_config_path(config_file, config_dir_path)

    with open(config_file, "r") as f:
        first_line = f.readline().strip()
        is_experiment_config = first_line == "# @package _global_"

    if is_experiment_config:
        hydra_path = Path(hydra_config_path)
        if hydra_path.parts and hydra_path.parts[0] == "experiment":
            hydra_config_path = Path(*hydra_path.parts[1:]).as_posix()

    logger.debug(
        f"Loading config: path={config_path}, "
        f"hydra_config_path={hydra_config_path}, "
        f"is_experiment={is_experiment_config}"
    )

    hydra_instance = GlobalHydra.instance()
    if hydra_instance.is_initialized():
        hydra_instance.clear()

    with initialize_config_dir(str(config_dir_path), version_base=None):
        if is_experiment_config:
            cfg = compose(
                config_name="action_based",
                overrides=[f"+experiment={hydra_config_path}"],
            )
        else:
            cfg = compose(config_name=hydra_config_path)

        result = OmegaConf.to_container(cfg)
        assert isinstance(result, dict), "Config must be a dictionary"
        return cast(Dict[str, Any], result)
