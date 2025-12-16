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
        _get_dataset_name(probe_id, datasets)
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
        "add_edited_decider",
        "add_deciders",
    ],
)


def _get_root_decider_name(decider_name: str) -> str:
    """Extract the root decider name without any ' - edit N' suffix."""
    import re

    match = re.match(r"^(.+?) - edit \d+$", decider_name)
    if match:
        return _get_root_decider_name(match.group(1))
    return decider_name


def _find_matching_decider(
    resolved_config: Dict[str, Any],
    all_deciders: Dict[str, Any],
) -> str | None:
    for name, entry in all_deciders.items():
        if entry.get("resolved_config") == resolved_config:
            return name
    return None


def _add_edited_decider(
    base_decider_name: str,
    resolved_config: Dict[str, Any],
    llm_backbones: list,
    all_deciders: Dict[str, Any],
) -> str:
    """
    Add an edited decider to the registry.

    Args:
        base_decider_name: Original decider name this was edited from
        resolved_config: The edited resolved config
        llm_backbones: Available LLM backbones for this decider
        all_deciders: The mutable deciders dictionary (pre-bound via partial)

    Returns:
        The new decider name "{root_decider_name} - edit {n}"
    """
    existing = _find_matching_decider(resolved_config, all_deciders)
    if existing:
        return existing

    root_name = _get_root_decider_name(base_decider_name)

    edit_count = 1
    for name in all_deciders:
        if name.startswith(f"{root_name} - edit "):
            try:
                n = int(name.split(" - edit ")[-1])
                edit_count = max(edit_count, n + 1)
            except ValueError:
                pass

    new_name = f"{root_name} - edit {edit_count}"
    all_deciders[new_name] = {
        "edited_config": True,
        "resolved_config": resolved_config,
        "llm_backbones": llm_backbones,
        "max_alignment_attributes": 10,
    }
    return new_name


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

    def add_deciders(new_deciders: Dict[str, Any]):
        for name, entry in new_deciders.items():
            if name not in all_deciders:
                all_deciders[name] = entry

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
        add_edited_decider=partial(
            _add_edited_decider,
            all_deciders=all_deciders,
        ),
        add_deciders=add_deciders,
    )
