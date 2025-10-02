from functools import partial
from collections import namedtuple
from . import adm_core


DeciderRegistry = namedtuple(
    "DeciderRegistry",
    [
        "get_dataset_decider_configs",
        "get_system_prompt",
        "get_base_decider_config",
        "resolve_decider_config",
        "prepare_context",
        "create_adm",
        "instantiate_adm",
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

    def create_adm_wrapper(llm_backbone="", decider=None, baseline=True, probe_id=None):
        config = adm_core.get_base_decider_config(
            probe_id, decider, baseline, all_deciders, datasets
        )
        return adm_core.create_adm(config, llm_backbone)

    def instantiate_adm_wrapper(
        llm_backbone="", decider=None, baseline=True, probe_id=None
    ):
        config = adm_core.get_base_decider_config(
            probe_id, decider, baseline, all_deciders, datasets
        )
        return adm_core.instantiate_adm(config, llm_backbone)

    return DeciderRegistry(
        get_dataset_decider_configs=partial(
            adm_core.get_dataset_decider_configs,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        get_system_prompt=partial(
            adm_core.get_system_prompt, all_deciders=all_deciders, datasets=datasets
        ),
        get_base_decider_config=partial(
            adm_core.get_base_decider_config,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        resolve_decider_config=partial(
            adm_core.resolve_decider_config,
            all_deciders=all_deciders,
            datasets=datasets,
        ),
        prepare_context=partial(
            adm_core.prepare_context, all_deciders=all_deciders, datasets=datasets
        ),
        create_adm=create_adm_wrapper,
        instantiate_adm=instantiate_adm_wrapper,
        get_all_deciders=lambda: all_deciders,
    )
