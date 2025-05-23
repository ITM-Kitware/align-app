from pathlib import Path
import copy
from typing import TypedDict, List
import json
import yaml
import hydra
from functools import partial
from omegaconf import OmegaConf, DictConfig
from align_system.utils.hydrate_state import hydrate_scenario_state
import align_system
from align_system.utils import logging
from .action_filtering import filter_actions
from ..utils.utils import merge_dicts
import gc
import torch

MAX_GENERATOR_TOKENS = 8092

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


class ScenarioAndAlignment(TypedDict):
    scenario: Scenario
    alignment_targets: List[DictConfig]


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
        scenario_id = f"{prefix}.{input['scenario_id']}.{next_id}"
        next_id += 1
        input["scenario_id"] = scenario_id  # ensure id is unique

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

current_dir = Path(__file__).parent
configs = current_dir / "configs"
adm_configs = configs / "hydra" / "adm"
alignment_configs = configs / "hydra" / "alignment_target"

naacl24_input_dir = current_dir / "input_output_files" / "NAACL24_dataset_split"
opinionqa_input_dir = current_dir / "input_output_files" / "OpinionQA_dataset_split"


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


deciders = {
    "outlines_transformers_structured": {
        "config_path": adm_configs / "outlines_transformers_structured.yaml",
        "llm_backbones": [
            "mistralai/Mistral-7B-Instruct-v0.2",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "meta-llama/Meta-Llama-3-8B-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Qwen/Qwen2.5-32B-Instruct",
        ],
        "instance_kwargs": {},
        "postures": {
            "aligned": {
                "max_alignment_attributes": 1,
                "inference_kwargs": {},
                "instance_kwargs": {"baseline": False},
            },
            "baseline": {
                "inference_kwargs": {},
                "instance_kwargs": {"baseline": True},
            },
        },
    },
    "kaleido": {
        "config_path": adm_configs / "kaleido.yaml",
        "llm_backbones": [
            "allenai/kaleido-large",
            "allenai/kaleido-xl",
            "allenai/kaleido-xxl",
        ],
        "instance_kwargs": {},
        "postures": {
            "aligned": {
                "max_alignment_attributes": 1,
                "inference_kwargs": {
                    "action_template": (
                        'What action do you take? "{{choice}}" instead of {{other_choices}}. '
                        "In the context of the following scenario: {{scene_state}} "
                    ),
                },
            },
        },
    },
}


decider_names = list(deciders.keys())

datasets = {
    "naacl24": {
        "scenarios": load_scenarios_dir(naacl24_input_dir),
        "deciders": {
            "outlines_transformers_structured": {
                "postures": {
                    "aligned": {
                        "inference_kwargs": {
                            "kdma_descriptions_map": str(
                                align_system_path
                                / "prompt_engineering"
                                / "naacl24_kdma_descriptions.yml"
                            )
                        },
                    },
                    "baseline": {"inference_kwargs": {}},
                },
            },
            "kaleido": {
                "postures": {
                    "aligned": {
                        "inference_kwargs": {
                            "kdma_descriptions_map": str(
                                align_system_path
                                / "algorithms"
                                / "lib"
                                / "templates"
                                / "kdma_descriptions_short_naacl24_paper.yml"
                            ),
                        },
                    },
                },
                "attributes": {
                    "continuing_care": {"possible_scores": "continuous"},
                    "fairness": {"possible_scores": "continuous"},
                    "moral_desert": {"possible_scores": "continuous"},
                    "protocol_focus": {"possible_scores": "continuous"},
                    "risk_aversion": {"possible_scores": "continuous"},
                    "utilitarianism": {"possible_scores": "continuous"},
                },
            },
        },
        "attributes": {
            "continuing_care": {"possible_scores": ["Low", "High"]},
            "fairness": {"possible_scores": ["Low", "High"]},
            "moral_desert": {"possible_scores": ["Low", "High"]},
            "protocol_focus": {"possible_scores": ["Low", "High"]},
            "risk_aversion": {"possible_scores": ["Low", "High"]},
            "utilitarianism": {"possible_scores": ["Low", "High"]},
        },
        "attribute_descriptions_dir": align_system_path
        / "configs"
        / "alignment_target"
        / "NAACL24_dataset_attributes",
    },
    "opinionqa": {
        "scenarios": truncate_unstructured_text(
            load_scenarios_dir(opinionqa_input_dir)
        ),
        "deciders": {
            "outlines_transformers_structured": {
                "instance_kwargs": {
                    "scenario_description_template": {
                        "_target_": "align_system.prompt_engineering.outlines_prompts.opinion_qa_scenario_description"
                    },
                    "action_selection_prompt_template": {
                        "_target_": "align_system.prompt_engineering.outlines_prompts.opinion_qa_action_selection"
                    },
                    "baseline_system_prompt": {
                        "_target_": "align_system.prompt_engineering.outlines_prompts.opinion_qa_baseline_system_prompt"
                    },
                },
                "postures": {
                    "aligned": {
                        "inference_kwargs": {
                            "kdma_descriptions_map": str(
                                align_system_path
                                / "prompt_engineering"
                                / "opinionqa_kdma_descriptions.yml"
                            )
                        },
                    },
                    "baseline": {"inference_kwargs": {}},
                },
            },
        },
        "attributes": {
            "CREGION_Northeast": {"possible_scores": ["High"]},
            "CREGION_South": {"possible_scores": ["High"]},
            "EDUCATION_College_graduate_some_postgrad": {"possible_scores": ["High"]},
            "EDUCATION_Less_than_high_school": {"possible_scores": ["High"]},
            "INCOME_$100,000_or_more": {"possible_scores": ["High"]},
            "INCOME_Less_than_$30,000": {"possible_scores": ["High"]},
        },
        "attribute_descriptions_dir": align_system_path
        / "configs"
        / "alignment_target"
        / "OpinionQA_dataset_attributes",
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
    state, actions = hydrate_scenario_state(scenario)
    actions = filter_actions(state, actions)
    return state, actions


def load_alignment_target(dataset_name, decider, kdma, kdma_value=0):
    attribute_descriptions_dir = datasets[dataset_name]["attribute_descriptions_dir"]

    all_dataset_attrs = _get_attributes(dataset_name, decider)
    attr_config = all_dataset_attrs.get(kdma)

    if attr_config is None:
        raise ValueError(
            f"Attribute {kdma} not found in dataset {dataset_name} (decider: {decider})"
        )

    scores = attr_config.get("possible_scores", [])
    is_continuous = scores == "continuous"

    if is_continuous:
        alignment_suffix = "high" if float(kdma_value) >= 0.5 else "low"
    elif isinstance(scores, list) and len(scores) == 1:
        alignment_suffix = scores[0].lower()
    elif isinstance(scores, list) and len(scores) > 1:
        num_scores = len(scores)
        # Map 0 to 1 kdma_value to index [0, num_scores - 1]
        index = round(float(kdma_value) * (num_scores - 1))
        clamped_index = max(0, min(index, num_scores - 1))
        alignment_suffix = scores[clamped_index].lower()
    else:
        raise ValueError(
            f"Unsupported score format for {kdma} in {dataset_name}: {scores}"
        )

    filename = f"{kdma}_{alignment_suffix}.yaml"
    filepath = attribute_descriptions_dir / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Alignment target file not found: {filepath}")
    alignment = OmegaConf.load(filepath)

    if is_continuous:
        for i in range(len(alignment.kdma_values)):
            alignment.kdma_values[i].value = float(kdma_value)

    return alignment


def alignment_targets_to_dict_conf(
    dataset_name, attributes: List[Attribute], decider
) -> List[DictConfig]:
    return [
        load_alignment_target(
            dataset_name, kdma=a["type"], kdma_value=a["score"], decider=decider
        )
        for a in attributes
    ]


def truncate_alignment_targets(targets: List[DictConfig], decider_config):
    max_attr = decider_config.get("max_alignment_attributes", len(targets))
    if max_attr == 1:
        return targets[0] if targets else None
    return targets[:max_attr]


def prepare_alignment(
    dataset_name, attributes: List[Attribute], decider_config, decider: str
):
    targets = alignment_targets_to_dict_conf(dataset_name, attributes, decider=decider)
    return truncate_alignment_targets(targets, decider_config)


def get_prompt(
    scenario_id: str,
    llm_backbone="",
    decider=decider_names[0],
    attributes: List[Attribute] = [],
) -> Prompt:
    decider_params = DeciderParams(llm_backbone=llm_backbone, decider=decider)
    dataset_name = get_dataset_name(scenario_id)
    alignment_targets = alignment_targets_to_dict_conf(
        dataset_name, attributes, decider=decider
    )
    scenario = scenarios[scenario_id]
    return {
        "decider_params": decider_params,
        "alignment_targets": alignment_targets,
        "scenario": scenario,
    }


def serialize_prompt(prompt: Prompt):
    alignment_targets = [
        OmegaConf.to_container(target) for target in prompt["alignment_targets"]
    ]
    p = {
        **prompt,
        "alignment_targets": alignment_targets,
    }
    return copy.deepcopy(p)


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

    # Load the base configuration from the YAML file
    yaml_path = deciders[decider]["config_path"]
    base_cfg = OmegaConf.load(yaml_path)
    decider_base = OmegaConf.to_container(base_cfg, resolve=True)

    common_config = copy.deepcopy(deciders[decider])
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
    resolved_config = OmegaConf.create(config)
    instance_kwargs = merged_configs.get("instance_kwargs", {})
    resolved_config["instance_kwargs"] = merge_dicts(
        instance_kwargs,
        resolved_config.get("instance_kwargs", {}),
    )
    return resolved_config


def prepare_context(scenario, decider, attributes):
    state, actions = create_scenario_state(scenario)
    scenario_id = scenario["scenario_id"]
    baseline = len(attributes) == 0
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
    scenario = scenarios[scenario_id]
    ctx = prepare_context(scenario, decider, attributes)
    if ctx["config"] is None:
        return ""  # No config found for the given decider and scenario_id
    # Pass decider name to prepare_alignment
    alignment = prepare_alignment(
        ctx["dataset_name"], attributes, ctx["config"], decider=decider
    )
    instance_kwargs = hydra.utils.instantiate(
        ctx["config"].get("instance_kwargs", {}), recursive=True
    )
    if decider == "kaleido":
        target_class = hydra.utils.get_class(
            ctx["config"].instance.kaleido_adm._target_
        )
        partial_template = target_class.get_partial_template(
            ctx["state"],
            **ctx["config"].get("inference_kwargs", {}),
            **instance_kwargs,
        )

        return partial_template
    else:
        target_class = hydra.utils.get_class(ctx["config"].instance._target_)
        dialogs = target_class.get_dialogs(
            ctx["state"],
            ctx["actions"],
            alignment,
            **ctx["config"].get("inference_kwargs", {}),
            **instance_kwargs,
        )
        return dialogs["positive_system_prompt"]


def get_alignment_descriptions_map(prompt: Prompt) -> dict:
    """Loads the KDMA descriptions map based on the prompt context."""
    scenario_id = prompt["scenario"]["scenario_id"]
    decider = prompt["decider_params"]["decider"]

    config = get_decider_config(scenario_id, decider, baseline=False)
    if not config:
        return {}

    # Check nested structure for kdma_descriptions_map
    kdma_map_path_str = None
    if (
        "inference_kwargs" in config
        and "kdma_descriptions_map" in config["inference_kwargs"]
    ):
        kdma_map_path_str = config["inference_kwargs"]["kdma_descriptions_map"]
    elif (
        "instance_kwargs" in config
        and "kdma_descriptions_map" in config["instance_kwargs"]
    ):
        kdma_map_path_str = config["instance_kwargs"]["kdma_descriptions_map"]

    if not kdma_map_path_str:
        print(
            f"Warning: KDMA descriptions map path not found in config for {scenario_id}, {decider}"
        )
        return {}

    kdma_map_path = Path(kdma_map_path_str)
    if not kdma_map_path.exists():
        print(f"Warning: KDMA descriptions file not found: {kdma_map_path}")
        return {}

    try:
        with open(kdma_map_path, "r") as f:
            kdma_descriptions = yaml.safe_load(f)
        return kdma_descriptions or {}
    except Exception as e:
        print(f"Error loading KDMA descriptions from {kdma_map_path}: {e}")
        return {}


def execute_model(model, prompt: Prompt):
    scenario = prompt["scenario"]
    decider = prompt["decider_params"]["decider"]
    attributes = prompt["alignment_targets"]
    ctx = prepare_context(scenario, decider, attributes)
    alignment = truncate_alignment_targets(attributes, ctx["config"])
    func = (
        model.instance.top_level_choose_action
        if hasattr(model.instance, "top_level_choose_action")
        else model.instance.choose_action
    )
    action_decision, *_ = func(
        scenario_state=ctx["state"],
        available_actions=ctx["actions"],
        alignment_target=alignment,
        **model.get("inference_kwargs", {}),
        reasoning_max_length=-1,
        generator_seed=2,
        max_generator_tokens=MAX_GENERATOR_TOKENS,
    )
    return action_decision


def cleanup_hybrid_kaleido_adm(hybrid_adm_obj_config):
    hybrid_adm_obj = hybrid_adm_obj_config.instance
    try:
        kaleido_adm = hybrid_adm_obj.kaleido_adm
        ks = kaleido_adm.kaleido
        if hasattr(ks, "model") and ks.model is not None:
            try:
                ks.model.cpu()
                delattr(ks, "model")
            except Exception as e:
                print("Error moving KaleidoSys model to CPU:", e)

        if hasattr(ks, "embed_model") and ks.embed_model is not None:
            try:
                ks.embed_model.cpu()
                delattr(ks, "embed_model")
            except Exception as e:
                print("Error moving KaleidoSys embed_model to CPU:", e)

        hybrid_adm_obj.kaleido_adm.kaleido = None

        hybrid_adm_obj.kaleido_adm = None

        hybrid_adm_obj.outlines_adm = None
    except Exception as e:
        print(f"Exception during cleanup: {e}")
    finally:
        gc.collect()
        torch.cuda.empty_cache()


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
    if decider != "kaleido":
        config["instance"]["model_name"] = llm_backbone
    else:
        config["instance"]["kaleido_adm"]["model_name"] = llm_backbone

    config["instance"] = OmegaConf.merge(
        config["instance"], config.get("instance_kwargs", {})
    )
    model = hydra.utils.instantiate(config, recursive=True)
    if decider == "kaleido":
        cleanup = cleanup_hybrid_kaleido_adm
    else:
        cleanup = cleanup_generic_adm
    return model, cleanup


def create_adm(
    llm_backbone="",
    decider=decider_names[0],
    baseline=True,
    scenario_id=None,
):
    model, cleanup = instantiate_adm(llm_backbone, decider, baseline, scenario_id)
    return partial(execute_model, model), partial(cleanup, model)
