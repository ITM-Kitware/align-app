from functools import partial
from collections import namedtuple
from . import adm_core
from .config import (
    get_dataset_decider_configs,
    get_base_decider_config,
    resolve_decider_config,
)


DeciderRegistry = namedtuple(
    "DeciderRegistry",
    [
        "get_dataset_decider_configs",
        "get_system_prompt",
        "get_base_decider_config",
        "resolve_decider_config",
        "prepare_context",
        "get_all_deciders",
    ],
)


def create_decider_registry(config_paths, scenario_registry):
    """
    Takes config paths and scenario_registry, returns a DeciderRegistry namedtuple
    with all_deciders and datasets pre-bound using partial application.
    """
    all_deciders = adm_core.get_all_deciders(config_paths)
    datasets = scenario_registry.get_datasets()

    return DeciderRegistry(
        get_dataset_decider_configs=partial(
            get_dataset_decider_configs,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_system_prompt=partial(
            adm_core.get_system_prompt, all_deciders=all_deciders, datasets=datasets
        ),
        get_base_decider_config=partial(
            get_base_decider_config,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        resolve_decider_config=partial(
            resolve_decider_config,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        prepare_context=partial(
            adm_core.prepare_context, all_deciders=all_deciders, datasets=datasets
        ),
        get_all_deciders=lambda: all_deciders,
    )
