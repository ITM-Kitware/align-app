from pathlib import Path
import copy
from typing import TypedDict, List, NamedTuple, Dict, Any
import json
import hydra
from functools import partial, lru_cache
from omegaconf import OmegaConf, DictConfig
import align_system
from align_system.utils.hydrate_state import (
    p2triage_hydrate_scenario_state,
)
from align_system.utils import logging, call_with_coerced_args
from align_system.utils.alignment_utils import attributes_in_alignment_target
from align_system.utils.hydra_utils import initialize_with_custom_references


# from .action_filtering import filter_actions
from ..utils.utils import merge_dicts, create_nested_dict_from_path
import gc
import torch

MAX_GENERATOR_TOKENS = 8092


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


def list_json_files(dir_path: Path):
    """Recursively find all JSON files in a directory and its subdirectories."""
    return [str(path) for path in dir_path.rglob("*.json")]


def load_scenarios(evaluation_file: str):
    prefix = Path(evaluation_file).parent.name.split("_")[0]
    with open(evaluation_file, "r") as f:
        dataset = json.load(f)
    next_id = 0
    scenarios = {}
    for record in dataset:
        input = record["input"]
        # ensure id is unique
        scenario_id = f"{prefix}.{input['scenario_id']}.{next_id}"
        next_id += 1
        input["scenario_id"] = scenario_id

        # Create a display_state field if full_state.unstructured exists
        if (
            "full_state" in input
            and isinstance(input["full_state"], dict)
            and "unstructured" in input["full_state"]
        ):
            input["display_state"] = input["full_state"]["unstructured"]

        scenarios[scenario_id] = input
    return scenarios


def get_scenarios(files):
    scenarios = {id: s for file in files for id, s in load_scenarios(file).items()}
    return scenarios


align_system_path = Path(align_system.__file__).parent
base_align_system_config_dir = align_system_path / "configs"
hydra.initialize_config_dir(str(base_align_system_config_dir), version_base=None)

current_dir = Path(__file__).parent
configs = current_dir / "configs"
adm_configs = configs / "adm"
input_output_files = current_dir / "input_output_files"


def load_scenarios_dir(dir_path: Path):
    files = list_json_files(dir_path)
    return get_scenarios(files)


def truncate_unstructured_text(scenarios):
    """
    Takes scenarios dict from load_scenarios_dir and truncates each scenario's
    display_state string at the first newline character.
    """
    scenarios_copy = copy.deepcopy(scenarios)

    # Process each scenario to truncate display_state at first newline
    for scenario in scenarios_copy.values():
        if "display_state" in scenario and isinstance(scenario["display_state"], str):
            first_newline_pos = scenario["display_state"].find("\n")
            if first_newline_pos != -1:
                scenario["display_state"] = scenario["display_state"][
                    :first_newline_pos
                ]

    return scenarios_copy


def _generate_comparative_regression_pipeline_system_prompt(
    ctx, alignment, hydrated_instance_kwargs
):
    adm_config = ctx["config"]

    system_prompt_template_config = adm_config["step_definitions"][
        "comparative_regression"
    ]["system_prompt_template"]
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


deciders = {
    "phase2_pipeline_zeroshot_comparative_regression": {
        "config_path": "adm/phase2_pipeline_zeroshot_comparative_regression.yaml",
        "llm_backbones": [
            "mistralai/Mistral-7B-Instruct-v0.2",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "meta-llama/Meta-Llama-3-8B-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Qwen/Qwen2.5-32B-Instruct",
        ],
        "model_path_keys": ["structured_inference_engine", "model_name"],
        "instance_kwargs": {},
        "postures": {
            "aligned": {
                "max_alignment_attributes": 10,
            },
        },
        "system_prompt_generator": _generate_comparative_regression_pipeline_system_prompt,
    },
    "pipeline_random": {
        "config_path": "adm/pipeline_random.yaml",
        "instance_kwargs": {},
        "postures": {
            "baseline": {},
        },
    },
}


decider_names = list(deciders.keys())

datasets = {
    "phase2": {
        "scenarios": load_scenarios_dir(input_output_files / "phase2"),
        "scenario_hydration_func": p2triage_hydrate_scenario_state,
        "deciders": {
            "phase2_pipeline_zeroshot_comparative_regression": {
                "postures": {
                    "aligned": {
                        "inference_kwargs": {},
                    },
                },
            },
            "pipeline_random": {},
        },
        "attributes": {
            "medical": {"possible_scores": "continuous"},
            "affiliation": {"possible_scores": "continuous"},
            "merit": {"possible_scores": "continuous"},
            "search": {"possible_scores": "continuous"},
            "personal_safety": {"possible_scores": "continuous"},
        },
        "attribute_descriptions_dir": align_system_path
        / "configs"
        / "alignment_target",
    },
}


# Create a flat dictionary of all scenarios from all datasets
scenarios: dict[str, Scenario] = {}
for dataset_name, dataset_info in datasets.items():
    dataset_scenarios = dataset_info["scenarios"]
    # Check for duplicate keys before merging
    duplicate_keys = set(scenarios.keys()) & set(dataset_scenarios.keys())
    if duplicate_keys:
        raise ValueError(
            f"Found duplicate scenario keys across datasets: {duplicate_keys}"
        )
    scenarios.update(dataset_scenarios)


def get_dataset_name(scenario_id):
    for name, dataset_info in datasets.items():
        if scenario_id in dataset_info["scenarios"]:
            return name
    raise ValueError(f"Dataset name for scenario ID {scenario_id} not found.")


def _get_attributes(dataset_name, decider):
    """Get the attributes for a dataset, checking for decider-specific overrides."""
    dataset_info = datasets[dataset_name]

    decider_attrs = dataset_info.get("deciders", {}).get(decider, {}).get("attributes")
    if decider_attrs:
        return decider_attrs

    general_attrs = dataset_info.get("attributes")
    if general_attrs:
        return general_attrs

    raise ValueError(
        f"Attributes not found for dataset {dataset_name} (decider: {decider})"
    )


def get_attributes(scenario_id, decider):
    return _get_attributes(get_dataset_name(scenario_id), decider)


def create_scenario_state(scenario):
    """Create a scenario state from a scenario description"""
    scenario_id = scenario["scenario_id"]
    dataset_name = get_dataset_name(scenario_id)
    hydration_func = datasets[dataset_name]["scenario_hydration_func"]
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
    state, actions = hydration_func(scenario)
    # actions = filter_actions(state, actions)
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


def get_prompt(
    scenario_id: str,
    llm_backbone="",
    decider=decider_names[0],
    attributes: List[Attribute] = [],
) -> Prompt:
    return {
        "decider_params": DeciderParams(llm_backbone=llm_backbone, decider=decider),
        "alignment_target": attributes_to_alignment_target_dict_conf(attributes),
        "scenario": scenarios[scenario_id],
    }


def serialize_prompt(prompt: Prompt):
    p = {
        **prompt,
        "alignment_target": OmegaConf.to_container(prompt["alignment_target"]),
    }
    return copy.deepcopy(p)


@lru_cache(maxsize=32)
def _cached_hydra_compose(yaml_path):
    """Cached version of hydra.compose to speed up repeated calls with the same path"""
    return hydra.compose(yaml_path)  # takes .4 seconds on ITM machine


def get_dataset_decider_configs(scenario_id, decider):
    """
    Merges base decider config, common decider config, and dataset-specific
    decider config using the merge_dicts utility.
    """
    dataset_name = get_dataset_name(scenario_id)
    # Use .get() with default {} to handle cases where 'deciders' or the specific decider might be missing
    dataset_specific_config = copy.deepcopy(
        datasets[dataset_name].get("deciders", {}).get(decider, {})
    )

    if not dataset_specific_config:
        if decider not in datasets[dataset_name].get("deciders", {}):
            return None

    decider_cfg = deciders[decider]

    yaml_path = decider_cfg["config_path"]
    base_cfg = _cached_hydra_compose(yaml_path)
    adm_cfg = base_cfg["adm"]
    decider_base = OmegaConf.to_container(adm_cfg)

    common_config = copy.deepcopy(decider_cfg)
    #  Not needed in the merged config
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

    return decider_with_postures


def get_decider_config(scenario_id, decider, baseline):
    merged_configs = get_dataset_decider_configs(scenario_id, decider)
    if merged_configs is None:
        return None

    alignment = "baseline" if baseline else "aligned"
    if alignment not in merged_configs["postures"]:
        return None

    config = merged_configs["postures"][alignment]
    resolved_config = copy.deepcopy(config)
    instance_kwargs = merged_configs.get("instance_kwargs", {})
    resolved_config["instance_kwargs"] = merge_dicts(
        instance_kwargs,
        resolved_config.get("instance_kwargs", {}),
    )
    return resolved_config


def prepare_context(scenario, decider, alignment_target):
    state, actions = create_scenario_state(scenario)
    scenario_id = scenario["scenario_id"]
    baseline = len(alignment_target.kdma_values) == 0
    config = get_decider_config(scenario_id, decider, baseline)
    dataset_name = get_dataset_name(scenario_id)
    return {
        "state": state,
        "actions": actions,
        "scenario_id": scenario_id,
        "dataset_name": dataset_name,
        "config": config,
    }


def get_system_prompt(decider, attributes, scenario_id):
    decider_main_config = deciders.get(decider)

    generate_sys_prompt = decider_main_config.get("system_prompt_generator")
    if not generate_sys_prompt:
        return "N/A"

    scenario = scenarios.get(scenario_id)

    alignment_target = attributes_to_alignment_target_dict_conf(attributes)
    ctx = prepare_context(scenario, decider, alignment_target)

    if ctx.get("config") is None:
        # This implies that for the given decider and baseline/aligned posture,
        # a valid configuration was not found (e.g., kaleido needs an alignment and has no baseline posture).
        return ""

    alignment = attributes_to_alignment_target_dict_conf(attributes)

    hydrated_instance_kwargs = hydra.utils.instantiate(
        ctx["config"].get("instance_kwargs", {}), recursive=True
    )
    return generate_sys_prompt(ctx, alignment, hydrated_instance_kwargs)


def get_alignment_descriptions_map(prompt: Prompt) -> dict:
    scenario_id = prompt["scenario"]["scenario_id"]
    decider = prompt["decider_params"]["decider"]

    config = get_decider_config(scenario_id, decider, baseline=False)
    if not config:
        return {}

    # remove custom refs Omega errors on resolving
    del config["instance"]
    del config["step_definitions"]

    attributes_resolved = OmegaConf.to_container(
        OmegaConf.create({"adm": config}),
        resolve=True,
    )

    attribute_map = attributes_resolved["adm"].get("attribute_definitions", {})

    return attribute_map


def choose_action(model, prompt: Prompt):
    scenario = prompt["scenario"]
    decider = prompt["decider_params"]["decider"]
    alignment_target = prompt["alignment_target"]
    ctx = prepare_context(scenario, decider, alignment_target)
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
        generator_seed=2,
        max_generator_tokens=MAX_GENERATOR_TOKENS,
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


def instantiate_adm(
    llm_backbone="",
    decider=decider_names[0],
    baseline=True,
    scenario_id=None,
):
    config = get_decider_config(scenario_id, decider, baseline)

    if deciders[decider].get("model_path_keys") and llm_backbone:
        model_config = create_nested_dict_from_path(
            deciders[decider]["model_path_keys"], llm_backbone
        )
        config = merge_dicts(config, model_config)

    config["instance"] = OmegaConf.merge(
        config["instance"], config.get("instance_kwargs", {})
    )
    adm = initialize_with_custom_references({"adm": config})["adm"]
    cleanup = cleanup_generic_adm
    return adm, cleanup


def create_adm(
    llm_backbone="",
    decider=decider_names[0],
    baseline=True,
    scenario_id=None,
):
    model, cleanup = instantiate_adm(llm_backbone, decider, baseline, scenario_id)
    return partial(choose_action, model), partial(cleanup, model)
