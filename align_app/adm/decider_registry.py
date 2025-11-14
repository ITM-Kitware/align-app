from functools import partial
from collections import namedtuple
from . import adm_core
from .config import get_decider_config, get_decider_metadata


DeciderRegistry = namedtuple(
    "DeciderRegistry",
    [
        "get_decider_config",
        "get_decider_metadata",
        "get_system_prompt",
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
        get_decider_config=partial(
            get_decider_config,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_decider_metadata=partial(
            get_decider_metadata,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_system_prompt=partial(
            adm_core.get_system_prompt,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        prepare_context=partial(
            adm_core.prepare_context,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_all_deciders=lambda: all_deciders,
    )
