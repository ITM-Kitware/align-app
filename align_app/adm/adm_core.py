from pathlib import Path
import copy
from typing import TypedDict, List
import json
import hydra
from functools import partial
from omegaconf import OmegaConf, DictConfig
from align_system.utils.hydrate_state import hydrate_scenario_state
import align_system
from align_system.utils import logging
from .action_filtering import filter_actions

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


LLM_BACKBONES = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
]


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
    # Make a copy to avoid modifying the original
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


align_system_path = Path(align_system.__file__).parent
# align_system_config_dir = align_system_path / "configs"
# adm_demo_configs = align_system_config_dir / "experiment" / "demo"

decider_configs = {
    "outlines_transformers_structured": (
        adm_configs / "outlines_transformers_structured.yaml"
    ),
    "kaleido": (adm_configs / "kaleido.yaml"),
}

deciders = list(decider_configs.keys())

datasets = {
    "naacl24": {
        "scenarios": load_scenarios_dir(naacl24_input_dir),
        "deciders": {
            "outlines_transformers_structured": {
                "llm_backbones": LLM_BACKBONES,
                "instance_kwargs": {},
                "aligned": {
                    "max_alignment_attributes": 1,
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
            "kaleido": {
                "llm_backbones": [
                    "allenai/kaleido-small",
                    "allenai/kaleido-large",
                    "allenai/kaleido-xl",
                ],
                "instance_kwargs": {},
                "aligned": {
                    "max_alignment_attributes": 1,
                    "inference_kwargs": {
                        "kdma_descriptions_map": str(
                            align_system_path
                            / "algorithms"
                            / "lib"
                            / "templates"
                            / "kdma_descriptions_short_naacl24_paper.yml"
                        )
                    },
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
                "llm_backbones": LLM_BACKBONES,
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
                "aligned": {
                    "max_alignment_attributes": 1,
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
        "attributes": {
            "CREGION_Northeast": {"possible_scores": ["HIGH"]},
            "CREGION_South": {"possible_scores": ["HIGH"]},
            "EDUCATION_College_graduate_some_postgrad": {"possible_scores": ["HIGH"]},
            "EDUCATION_Less_than_high_school": {"possible_scores": ["HIGH"]},
            "INCOME_$100,000_or_more": {"possible_scores": ["HIGH"]},
            "INCOME_Less_than_$30,000": {"possible_scores": ["HIGH"]},
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


def get_attributes(scenario_id):
    """Get the attributes for a scenario"""
    dataset_name = get_dataset_name(scenario_id)
    if dataset_name is None:
        raise ValueError(f"Scenario ID {scenario_id} not found in any dataset")

    return datasets[dataset_name]["attributes"]


def create_scenario_state(scenario):
    """Create a scenario state from a scenario description"""
    state, actions = hydrate_scenario_state(scenario)
    actions = filter_actions(state, actions)
    return state, actions


def load_alignment_target(dataset_name, kdma, kdma_value=0):
    attribute_descriptions_dir = datasets[dataset_name]["attribute_descriptions_dir"]

    dataset_attrs = datasets[dataset_name]["attributes"]
    attr_config = dataset_attrs.get(kdma)
    if attr_config is None:
        raise ValueError(f"Attribute {kdma} not found in dataset {dataset_name}")
    scores = attr_config.get("possible_scores", [])
    if len(scores) == 1:
        binary_alignment = scores[0].lower()
    else:
        binary_alignment = (
            scores[1].lower() if float(kdma_value) >= 0.5 else scores[0].lower()
        )

    filename = f"{kdma}_{binary_alignment}.yaml"
    return OmegaConf.load(attribute_descriptions_dir / filename)


def alignment_targets_to_dict_conf(
    dataset_name, attributes: List[Attribute]
) -> List[DictConfig]:
    return [
        load_alignment_target(dataset_name, kdma=a["type"], kdma_value=a["score"])
        for a in attributes
    ]


def truncate_alignment_targets(targets: List[DictConfig], decider_config):
    max_attr = decider_config.get("max_alignment_attributes", len(targets))
    if max_attr == 1:
        return targets[0] if targets else None
    return targets[:max_attr]


def prepare_alignment(dataset_name, attributes: List[Attribute], decider_config):
    targets = alignment_targets_to_dict_conf(dataset_name, attributes)
    return truncate_alignment_targets(targets, decider_config)


def get_prompt(
    scenario_id: str,
    llm_backbone=LLM_BACKBONES[0],
    decider=deciders[0],
    attributes: List[Attribute] = [],
) -> Prompt:
    decider_params = DeciderParams(llm_backbone=llm_backbone, decider=decider)
    dataset_name = get_dataset_name(scenario_id)
    alignment_targets = alignment_targets_to_dict_conf(dataset_name, attributes)
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


def get_dataset_specific_decider_configs(scenario_id, decider):
    dataset_name = get_dataset_name(scenario_id)
    dataset_specific_decider_configs = datasets[dataset_name]["deciders"].get(decider)
    return dataset_specific_decider_configs


def get_decider_config(scenario_id, decider, baseline):
    dataset_specific_decider_configs = get_dataset_specific_decider_configs(
        scenario_id, decider
    )
    if dataset_specific_decider_configs is None:
        return None

    # Use baseline config only if it exists; otherwise, fall back to aligned.
    if baseline and "baseline" in dataset_specific_decider_configs:
        alignment = "baseline"
    else:
        alignment = "aligned"

    if alignment not in dataset_specific_decider_configs:
        raise ValueError(
            f"Alignment setting {alignment} not found for decider {decider} in dataset {dataset_name}"
        )

    dataset_specific_decider_config = dataset_specific_decider_configs[alignment]

    yaml_path = decider_configs[decider]
    resolved_config = OmegaConf.load(yaml_path)

    resolved_config = OmegaConf.merge(resolved_config, dataset_specific_decider_config)
    instance_kwargs = dataset_specific_decider_configs.get("instance_kwargs", {})
    resolved_config["instance_kwargs"] = instance_kwargs

    # Only set baseline flag if a baseline configuration exists
    if "baseline" in dataset_specific_decider_configs:
        resolved_config["instance"]["baseline"] = baseline
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
        "baseline": baseline,
        "config": config,
    }


def get_system_prompt(decider, attributes, scenario_id):
    scenario = scenarios[scenario_id]
    ctx = prepare_context(scenario, decider, attributes)
    if ctx["config"] is None:
        return ""  # No config found for the given decider and scenario_id
    alignment = prepare_alignment(ctx["dataset_name"], attributes, ctx["config"])
    if decider == "kaleido":
        target_class = hydra.utils.get_class(
            ctx["config"].instance.outlines_adm._target_
        )
        ctx["baseline"] = True
    else:
        target_class = hydra.utils.get_class(ctx["config"].instance._target_)
    instance_kwargs = hydra.utils.instantiate(
        ctx["config"].get("instance_kwargs", {}), recursive=True
    )
    dialogs = target_class.get_dialogs(
        ctx["state"],
        ctx["actions"],
        alignment,
        baseline=ctx["baseline"],
        **ctx["config"].get("inference_kwargs", {}),
        **instance_kwargs,
    )
    return dialogs["positive_system_prompt"]


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


def instantiate_adm(
    llm_backbone=LLM_BACKBONES[0], decider=deciders[0], baseline=True, scenario_id=None
):
    config = get_decider_config(scenario_id, decider, baseline)
    if decider != "kaleido":
        config["instance"]["model_name"] = llm_backbone

    config["instance"] = OmegaConf.merge(
        config["instance"], config.get("instance_kwargs", {})
    )
    decider = hydra.utils.instantiate(config, recursive=True)
    return decider


def create_adm(
    llm_backbone=LLM_BACKBONES[0], decider=deciders[0], baseline=True, scenario_id=None
):
    model = instantiate_adm(llm_backbone, decider, baseline, scenario_id)
    return partial(execute_model, model)
