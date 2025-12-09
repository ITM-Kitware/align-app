from functools import partial
from collections import namedtuple
from typing import Dict, Any
from .decider_definitions import (
    get_runtime_deciders,
    get_system_prompt,
    _BASE_DECIDERS,
)
from .config import get_decider_config, _get_dataset_name


def _get_decider_options(
    probe_id: str,
    decider: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
) -> Dict[str, Any] | None:
    """
    Get available options for a decider without loading full Hydra config.

    Used by UI to get available options (llm_backbones, max_alignment_attributes).
    Much faster than get_decider_config() as it skips Hydra config loading.

    Returns:
        Dict with option fields, or None if decider doesn't exist for probe's dataset
    """
    try:
        dataset_name = _get_dataset_name(probe_id, datasets)
    except ValueError:
        return None

    decider_cfg = all_deciders.get(decider)
    if not decider_cfg:
        return None

    metadata = {
        "llm_backbones": decider_cfg.get("llm_backbones", []),
        "max_alignment_attributes": decider_cfg.get("max_alignment_attributes", 0),
        "config_path": decider_cfg.get("config_path"),
        "exists": True,
    }

    return metadata


DeciderRegistry = namedtuple(
    "DeciderRegistry",
    [
        "get_decider_config",
        "get_decider_options",
        "get_system_prompt",
        "get_all_deciders",
    ],
)


def create_decider_registry(config_paths, scenario_registry, experiment_deciders=None):
    """
    Takes config paths and scenario_registry, returns a DeciderRegistry namedtuple
    with all_deciders and datasets pre-bound using partial application.

    Args:
        config_paths: List of paths to runtime decider configs
        scenario_registry: Registry for scenarios/probes
        experiment_deciders: Optional dict of experiment deciders to merge
    """
    all_deciders = {
        **_BASE_DECIDERS,
        **(experiment_deciders or {}),
        **get_runtime_deciders(config_paths),
    }
    datasets = scenario_registry.get_datasets()

    return DeciderRegistry(
        get_decider_config=partial(
            get_decider_config,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_decider_options=partial(
            _get_decider_options,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_system_prompt=partial(
            get_system_prompt,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_all_deciders=lambda: all_deciders,
    )
