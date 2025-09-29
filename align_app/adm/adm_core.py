from pathlib import Path
import copy
from typing import TypedDict, List, NamedTuple, Dict, Any
import gc
import torch
from functools import partial

import hydra
from omegaconf import OmegaConf, DictConfig
import align_system
import align_system.utils.hydrate_state
from align_system.utils.hydrate_state import (
    p2triage_hydrate_scenario_state,
)
from align_system.utils import logging, call_with_coerced_args
from align_system.utils.alignment_utils import attributes_in_alignment_target
from align_system.utils.hydra_utils import initialize_with_custom_references

# Import prompt classes at module level to avoid 6.7s delay on first use
from align_system.prompt_engineering.outlines_prompts import (
    ComparativeKDMASystemPrompt,
    ComparativeRegressionSystemPromptWithTemplate,
)

# from .action_filtering import filter_actions
from ..utils.utils import merge_dicts, create_nested_dict_from_path
from .hydra_config_loader import load_adm_config


def get_icl_data_paths():
    """Get paths to ICL data files from align-system repository"""
    icl_base_path = Path(align_system.__file__).parent / "resources" / "icl" / "phase2"

    data_mapping = {
        "medical": "July2025-MU-train_20250804.json",
        "affiliation": "July2025-AF-train_20250804.json",
        "merit": "July2025-MF-train_20250804.json",
        "personal_safety": "July2025-PS-train_20250804.json",
        "search": "July2025-SS-train_20250804.json",
    }

    return {
        key: str(icl_base_path / filename) for key, filename in data_mapping.items()
    }


def add_default_state_fields(scenario):
    """Add default environment and supplies fields to scenario if missing.
    Modifies scenario in place.
    """
    # keep swagger_client validation happy for phase 2 JSON shape
    if (
        "environment" not in scenario["full_state"]
        or not scenario["full_state"]["environment"]
    ):
        scenario["full_state"]["environment"] = {}
    if (
        "supplies" not in scenario["full_state"]
        or not scenario["full_state"]["supplies"]
    ):
        scenario["full_state"]["supplies"] = {}


def p2triage_hydrate_scenario_state_with_defaults(record):
    """Add default fields if missing (needed for phase2 ICL data) then call original function"""
    record_copy = record.copy()
    record_copy["full_state"] = record_copy["full_state"].copy()
    add_default_state_fields(record_copy)
    return p2triage_hydrate_scenario_state(record_copy)


# Monkey-patch the hydration function
align_system.utils.hydrate_state.p2triage_hydrate_scenario_state = (
    p2triage_hydrate_scenario_state_with_defaults
)


class ChoiceInfo(TypedDict, total=False):
    """Choice info structure - all keys are optional and ADM-dependent"""

    # Known possible keys (all optional)
    predicted_kdma_values: Dict[str, Dict[str, float]]  # Choice -> KDMA -> score
    true_kdma_values: Dict[str, Dict[str, float]]  # Choice -> KDMA -> score
    true_relevance: Dict[str, float]  # KDMA -> relevance
    icl_example_responses: Dict[str, Any]  # In-context learning examples
    # Allow any other arbitrary keys that different ADMs might provide
    # Note: TypedDict with total=False makes all keys optional


class Decision(TypedDict):
    """Decision structure containing only fields used by the app"""

    unstructured: str
    justification: str


class ADMResult(NamedTuple):
    """Result from ADM containing decision and choice_info"""

    decision: Decision
    choice_info: ChoiceInfo


root_logger = logging.getLogger()
root_logger.setLevel("WARNING")


class DeciderParams(TypedDict):
    llm_backbone: str
    decider: str


class Choice(TypedDict):
    unstructured: str


class Scenario(TypedDict):
    scenario_id: str
    choices: List[Choice]


class Attribute(TypedDict):
    type: str
    score: float


class AlignmentTarget(DictConfig):
    """
    example of an alignment target:
    _target_: swagger_client.models.AlignmentTarget

    id: ADEPT-DryRun-Ingroup Bias-0.0
    kdma_values:
        - kdma: Ingroup Bias
          value: 0.0
    """

    pass


class ScenarioAndAlignment(TypedDict):
    scenario: Scenario
    alignment_target: AlignmentTarget


class Prompt(ScenarioAndAlignment):
    decider_params: DeciderParams


class DeciderContext(Prompt):
    resolved_config: dict


align_system_path = Path(align_system.__file__).parent
base_align_system_config_dir = align_system_path / "configs"


def _generate_comparative_regression_pipeline_system_prompt(ctx, alignment):
    adm_config = ctx["config"]

    system_prompt_template_config = adm_config["step_definitions"][
        "comparative_regression"
    ]["system_prompt_template"]

    target_class = system_prompt_template_config.get("_target_")
    if (
        target_class
        == "align_system.prompt_engineering.outlines_prompts.ComparativeKDMASystemPrompt"
    ):
        system_prompt_template = ComparativeKDMASystemPrompt()
    elif (
        target_class
        == "align_system.prompt_engineering.outlines_prompts.ComparativeRegressionSystemPromptWithTemplate"
    ):
        system_prompt_template = ComparativeRegressionSystemPromptWithTemplate()
    else:
        # Fall back to Hydra for unknown classes.  Was slow.
        system_prompt_template = hydra.utils.instantiate(system_prompt_template_config)

    # To resolve references like `${adm.mu}`, we need to provide the 'adm' context to hydra.
    # We can wrap the config and then instantiate the 'attribute_definitions' part.
    config_for_instantiation = OmegaConf.create({"adm": adm_config})
    all_attributes = hydra.utils.instantiate(
        config_for_instantiation.adm.attribute_definitions
    )

    target_attribute_names = attributes_in_alignment_target(alignment)
    target_attributes = [all_attributes[n] for n in target_attribute_names]
    attribute_prompts = [
        call_with_coerced_args(system_prompt_template, {"target_attribute": attribute})
        for attribute in target_attributes
    ]
    return "\n\n".join(attribute_prompts)


def _generate_baseline_pipeline_system_prompt(ctx, alignment):
    """Generate system prompt for pipeline_baseline ADM.

    The baseline ADM always uses the same prompt regardless of alignment,
    as it represents an unaligned baseline approach.
    """
    return (
        "You are an assistant specialized in answering multiple-choice "
        "questions related to medical triage. When a question is posed, "
        "carefully analyze the symptoms or conditions "
        "described. Respond by providing a detailed reasoning using a "
        "step-by-step process or process of elimination. Conclude with "
        "the final answer, represented by the corresponding index "
        "number. Your response should be grounded in established "
        "medical knowledge and aim to be informative."
    )


LLM_BACKBONES = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mistral-7B-Instruct-v0.2",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
]


def create_decider_entry(config_path, overrides={}):
    """Base factory for creating decider entries with overrides."""
    return {
        "config_path": config_path,
        "llm_backbones": LLM_BACKBONES,
        "model_path_keys": ["structured_inference_engine", "model_name"],
        "postures": {"baseline": {}},
        **overrides,
    }


_BASE_DECIDERS = {
    "phase2_pipeline_zeroshot_comparative_regression": create_decider_entry(
        "adm/phase2_pipeline_zeroshot_comparative_regression.yaml",
        {
            "config_overrides": {
                "comparative_regression_choice_schema": {"reasoning_max_length": -1}
            },
            "postures": {"aligned": {}},
            "system_prompt_generator": _generate_comparative_regression_pipeline_system_prompt,
        },
    ),
    "phase2_pipeline_fewshot_comparative_regression": create_decider_entry(
        "adm/phase2_pipeline_fewshot_comparative_regression.yaml",
        {
            "config_overrides": {
                "comparative_regression_choice_schema": {"reasoning_max_length": -1},
                "step_definitions": {
                    "regression_icl": {
                        "icl_generator_partial": {
                            "incontext_settings": {"datasets": get_icl_data_paths()}
                        }
                    }
                },
            },
            "postures": {"aligned": {}},
            "system_prompt_generator": _generate_comparative_regression_pipeline_system_prompt,
        },
    ),
    "pipeline_baseline": create_decider_entry(
        "adm/pipeline_baseline.yaml",
        {
            "config_overrides": {
                "step_definitions": {
                    "outlines_baseline": {
                        "scenario_description_template": {
                            "_target_": "align_system.prompt_engineering.outlines_prompts.Phase2ScenarioDescription"
                        },
                        "prompt_template": {
                            "_target_": "align_system.prompt_engineering.outlines_prompts.Phase2BaselinePrompt"
                        },
                        "enable_caching": True,
                    }
                }
            },
            "postures": {"baseline": {}},
            "system_prompt_generator": _generate_baseline_pipeline_system_prompt,
        },
    ),
    "pipeline_random": create_decider_entry(
        "adm/pipeline_random.yaml",
        {"postures": {"baseline": {}}},
    ),
}


def create_runtime_decider_entry(config_path):
    """Create a decider entry for a runtime config."""
    return create_decider_entry(
        config_path,
        {
            "postures": {
                "aligned": {
                    "max_alignment_attributes": 10,
                },
                "baseline": {},
            },
            "runtime_config": True,
        },
    )


def get_all_deciders(config_paths=[]):
    """Get all deciders, merging runtime configs from paths with base deciders."""
    runtime_deciders = {
        Path(config_path).stem: create_runtime_decider_entry(config_path)
        for config_path in config_paths
    }
    return {**runtime_deciders, **_BASE_DECIDERS}


decider_names = list(_BASE_DECIDERS.keys())


def create_scenario_state(scenario, datasets):
    """Create a scenario state from a scenario description"""
    scenario_id = scenario["scenario_id"]
    dataset_name = get_dataset_name_from_datasets(scenario_id, datasets)
    hydration_func = datasets[dataset_name]["scenario_hydration_func"]
    # Ensure scenario has required fields
    scenario_copy = scenario.copy()
    scenario_copy["full_state"] = scenario_copy.get("full_state", {}).copy()
    add_default_state_fields(scenario_copy)
    state, actions = hydration_func(scenario_copy)
    return state, actions


def attributes_to_alignment_target_dict_conf(
    attributes: List[Attribute],
):
    target = {
        "_target_": "swagger_client.models.AlignmentTarget",
        "id": "ad_hoc",
        "kdma_values": [
            {
                "kdes": None,
                "kdma": a["type"],
                "value": a["score"],
            }
            for a in attributes
        ],
    }
    return OmegaConf.create(target)


def build_prompt_data(scenario, llm_backbone, decider, attributes):
    """Build a prompt data structure from components."""
    return {
        "decider_params": DeciderParams(llm_backbone=llm_backbone, decider=decider),
        "alignment_target": attributes_to_alignment_target_dict_conf(attributes),
        "scenario": scenario,
    }


def serialize_prompt(prompt: Prompt):
    """Serialize a prompt for JSON/state storage, removing non-serializable fields."""
    p = {
        **prompt,
        "alignment_target": OmegaConf.to_container(prompt["alignment_target"]),
    }
    # Remove non-serializable fields that are only needed internally
    p.pop("datasets", None)
    p.pop("all_deciders", None)
    return copy.deepcopy(p)


def get_dataset_name_from_datasets(scenario_id, datasets_dict):
    for name, dataset_info in datasets_dict.items():
        if scenario_id in dataset_info["scenarios"]:
            return name
    raise ValueError(f"Dataset name for scenario ID {scenario_id} not found.")


def get_dataset_decider_configs(scenario_id, decider, all_deciders, datasets):
    """
    Merges base decider config, common decider config, and dataset-specific
    decider config using the merge_dicts utility.
    """
    dataset_name = get_dataset_name_from_datasets(scenario_id, datasets)
    dataset_specific_config = copy.deepcopy(
        datasets[dataset_name].get("deciders", {}).get(decider, {})
    )

    decider_cfg = all_deciders.get(decider)

    if not decider_cfg:
        # Decider not found - return None to indicate it's not available
        return None

    # Runtime configs are valid for all datasets
    # Only check dataset compatibility for non-runtime configs
    if not decider_cfg.get("runtime_config"):
        if not dataset_specific_config:
            if decider not in datasets[dataset_name].get("deciders", {}):
                return None

    config_path = decider_cfg["config_path"]

    full_cfg = load_adm_config(
        config_path,
        str(base_align_system_config_dir),
    )

    decider_base = full_cfg.get("adm", {})

    common_config = copy.deepcopy(decider_cfg)
    #  Not needed in the merged config
    if "config_path" in common_config:
        del common_config["config_path"]

    # Merge non-posture configurations
    common_config_no_postures = {
        k: v for k, v in common_config.items() if k != "postures"
    }
    dataset_config_no_postures = {
        k: v for k, v in dataset_specific_config.items() if k != "postures"
    }
    decider_with_postures = merge_dicts(
        common_config_no_postures, dataset_config_no_postures
    )

    # Merge postures: Base YAML <- Common Posture Overrides <- Dataset Posture Overrides
    merged_postures = {}
    common_postures = common_config.get("postures", {})
    dataset_postures = dataset_specific_config.get("postures", {})

    posture_keys = set(common_postures.keys()) | set(dataset_postures.keys())
    for posture in posture_keys:
        posturing_decider = copy.deepcopy(decider_base)

        common_posture_override = common_postures.get(posture, {})
        posturing_decider = merge_dicts(posturing_decider, common_posture_override)
        dataset_posture_override = dataset_postures.get(posture, {})
        posturing_decider = merge_dicts(posturing_decider, dataset_posture_override)

        merged_postures[posture] = posturing_decider

    decider_with_postures["postures"] = merged_postures

    # Set default max_alignment_attributes for aligned postures
    if "aligned" in decider_with_postures["postures"]:
        if (
            "max_alignment_attributes"
            not in decider_with_postures["postures"]["aligned"]
        ):
            decider_with_postures["postures"]["aligned"]["max_alignment_attributes"] = (
                10
            )

    return decider_with_postures


def get_base_decider_config(scenario_id, decider, baseline, all_deciders, datasets):
    merged_configs = get_dataset_decider_configs(
        scenario_id, decider, all_deciders, datasets
    )
    if merged_configs is None:
        return None

    alignment = "baseline" if baseline else "aligned"
    if alignment not in merged_configs["postures"]:
        return None

    config = merged_configs["postures"][alignment]

    base_config = OmegaConf.create(config)

    if "config_overrides" in merged_configs:
        overrides = OmegaConf.create(merged_configs["config_overrides"])
        base_config = OmegaConf.merge(base_config, overrides)

    resolved_config = OmegaConf.to_container(base_config)

    decider_info = all_deciders.get(decider, {})
    if "model_path_keys" in decider_info:
        resolved_config["model_path_keys"] = decider_info["model_path_keys"]

    return resolved_config


def resolve_decider_config(
    scenario_id, decider, alignment_target, all_deciders, datasets
):
    """Resolve decider config based on alignment target."""
    baseline = len(alignment_target.kdma_values) == 0
    return get_base_decider_config(
        scenario_id, decider, baseline, all_deciders, datasets
    )


def prepare_context(scenario, decider, alignment_target, all_deciders, datasets):
    state, actions = create_scenario_state(scenario, datasets)
    scenario_id = scenario["scenario_id"]
    config = resolve_decider_config(
        scenario_id, decider, alignment_target, all_deciders, datasets
    )
    dataset_name = get_dataset_name_from_datasets(scenario_id, datasets)
    return {
        "state": state,
        "actions": actions,
        "scenario_id": scenario_id,
        "dataset_name": dataset_name,
        "config": config,
    }


def get_system_prompt(decider, attributes, scenario_id, all_deciders, datasets):
    decider_main_config = all_deciders.get(decider)

    generate_sys_prompt = decider_main_config.get("system_prompt_generator")
    if not generate_sys_prompt:
        return "Unknown"

    # Get scenario from datasets
    scenario = None
    for dataset_info in datasets.values():
        if scenario_id in dataset_info["scenarios"]:
            scenario = dataset_info["scenarios"][scenario_id]
            break

    alignment_target = attributes_to_alignment_target_dict_conf(attributes)
    ctx = prepare_context(scenario, decider, alignment_target, all_deciders, datasets)

    if ctx.get("config") is None:
        # This implies that for the given decider and baseline/aligned posture,
        # a valid configuration was not found (e.g., kaleido needs an alignment and has no baseline posture).
        return ""

    alignment = attributes_to_alignment_target_dict_conf(attributes)
    return generate_sys_prompt(ctx, alignment)


def get_alignment_descriptions_map(prompt: Prompt) -> dict:
    scenario_id = prompt["scenario"]["scenario_id"]
    decider = prompt["decider_params"]["decider"]
    all_deciders = prompt.get("all_deciders")
    datasets = prompt.get("datasets")

    config = get_base_decider_config(
        scenario_id,
        decider,
        baseline=False,
        all_deciders=all_deciders,
        datasets=datasets,
    )
    if not config:
        return {}

    # remove custom refs which cause errors when Omega is trying to resolve them
    config.pop("instance", None)
    config.pop("step_definitions", None)

    attributes_resolved = OmegaConf.to_container(
        OmegaConf.create({"adm": config}),
        resolve=True,
    )

    if not isinstance(attributes_resolved, dict):
        return {}

    adm_section = attributes_resolved.get("adm", {})
    if not isinstance(adm_section, dict):
        return {}

    attribute_map = adm_section.get("attribute_definitions", {})

    return attribute_map


def choose_action(model, prompt: Prompt):
    scenario = prompt["scenario"]
    decider = prompt["decider_params"]["decider"]
    alignment_target = prompt["alignment_target"]
    all_deciders = prompt.get("all_deciders")
    datasets = prompt.get("datasets")
    ctx = prepare_context(scenario, decider, alignment_target, all_deciders, datasets)
    func = (
        model.instance.top_level_choose_action
        if hasattr(model.instance, "top_level_choose_action")
        else model.instance.choose_action
    )
    result = func(
        scenario_state=ctx["state"],
        available_actions=ctx["actions"],
        alignment_target=alignment_target,
        **model.get("inference_kwargs", {}),
        reasoning_max_length=-1,
        max_generator_tokens=-1,
        generator_seed=2,
    )
    raw_decision = result[0]
    choice_info = result[1]["choice_info"]

    decision_dict: Decision = {
        "unstructured": raw_decision.unstructured,
        "justification": raw_decision.justification,
    }

    return ADMResult(decision=decision_dict, choice_info=choice_info)


def cleanup_generic_adm(_):
    gc.collect()
    torch.cuda.empty_cache()


def instantiate_adm(decider_config, llm_backbone=""):
    """Instantiate an ADM from a resolved config."""
    if decider_config is None:
        raise ValueError("decider_config is required")

    config = decider_config

    if config.get("model_path_keys") and llm_backbone:
        model_config = create_nested_dict_from_path(
            config["model_path_keys"], llm_backbone
        )
        config = merge_dicts(config, model_config)

    adm = initialize_with_custom_references({"adm": config})["adm"]
    return adm, cleanup_generic_adm


def create_adm(decider_config, llm_backbone=""):
    """Create an ADM from a resolved config."""
    model, cleanup = instantiate_adm(decider_config, llm_backbone)
    return partial(choose_action, model), partial(cleanup, model)
