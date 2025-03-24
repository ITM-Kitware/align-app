from pathlib import Path
from typing import TypedDict, List
import json
import hydra
from omegaconf import OmegaConf, DictConfig
from align_system.utils.hydrate_state import hydrate_scenario_state
from .action_filtering import filter_actions
from align_system.utils import logging
import copy
from functools import partial

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


# Core configuration paths
current_dir = Path(__file__).parent
configs = current_dir / "configs"
adm_configs = configs / "hydra" / "adm"
alignment_configs = configs / "hydra" / "alignment_target"
oracles = current_dir / "oracle-json-files"
kdma_descriptions_map = configs / "prompt_engineering" / "kdma_descriptions.yml"

# Available model configurations
LLM_BACKBONES = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "meta-llama/Meta-Llama-3-8B-Instruct",
]

# deciders = ["outlines_transformers_structured", "outlines_comparative_regression"]
deciders = ["outlines_transformers_structured"]

attributes = [
    "moral_deservingness",
    "maximization",
    # "moral_judgement",
    # "ingroup_bias",
]


def list_json_files(dir_path: Path):
    return [str(file) for file in dir_path.iterdir() if file.suffix == ".json"]


def load_scenarios(evaluation_file: str):
    with open(evaluation_file, "r") as f:
        dataset = json.load(f)
    next_id = 0
    scenarios = {}
    for record in dataset:
        input = record["input"]
        scenario_id = f"{input['scenario_id']}.{next_id}"
        next_id += 1
        input["scenario_id"] = scenario_id  # ensure id is unique
        scenarios[scenario_id] = input
    return scenarios


def filter_actions_scenario(scenario: Scenario):
    s, a = hydrate_scenario_state(scenario)
    actions = filter_actions(s, a)
    actions = [action.to_dict() for action in actions]
    filtered_s = {**scenario, "choices": actions}
    return filtered_s


def get_scenarios():
    evaluation_file = list_json_files(oracles)[1]
    scenarios = load_scenarios(evaluation_file)
    scenarios = {id: filter_actions_scenario(s) for id, s in scenarios.items()}
    return scenarios


def get_scenario(scenario_id: str):
    return get_scenarios()[scenario_id]


def create_scenario_state(scenario):
    """Create a scenario state from a scenario description"""
    state, actions = hydrate_scenario_state(scenario)
    actions = filter_actions(state, actions)
    return state, actions


def load_alignment_target(kdma=attributes[0], kdma_value=0):
    kdma_split = kdma.split("_")
    kdma_file = " ".join(kdma_split).capitalize()
    if kdma_file in ["Moral deservingness", "Maximization"]:
        binary_alignment = "high" if float(kdma_value) >= 0.5 else "low"
        filename = f"{kdma}_{binary_alignment}.yaml"

    return OmegaConf.load(alignment_configs / filename)


def prepare_alignment_targets(attributes: List[Attribute]) -> List[DictConfig]:
    return [
        load_alignment_target(kdma=a["type"], kdma_value=a["score"]) for a in attributes
    ]


def get_prompt(
    scenario_id: str,
    llm_backbone=LLM_BACKBONES[0],
    decider=deciders[0],
    attributes: List[Attribute] = [],
):
    decider_params = {
        "llm_backbone": llm_backbone,
        "decider": decider,
    }
    alignment_targets = prepare_alignment_targets(attributes)
    scenario = get_scenario(scenario_id)
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


def get_decider_config(decider, aligned):
    suffix = "aligned" if aligned else "baseline"
    name = f"{decider}_{suffix}.yaml"
    config_path = adm_configs / name
    config = OmegaConf.load(config_path)
    return config


def prepare_context(scenario, alignment_targets):
    state, actions = create_scenario_state(scenario)
    alignment_target = alignment_targets[0] if alignment_targets else None
    return state, actions, alignment_target


def get_system_prompt(decider, attributes, scenario_id):
    alignment_targets = prepare_alignment_targets(attributes)
    state, actions, alignment_target = prepare_context(
        get_scenario(scenario_id), alignment_targets
    )
    config = get_decider_config(decider, aligned=True)
    target_class = hydra.utils.get_class(config.instance._target_)
    dialogs = target_class.get_dialogs(
        state,
        actions,
        alignment_target,
        num_positive_samples=1,
        num_negative_samples=0,
        shuffle_choices=False,
        baseline=len(attributes) == 0,
        kdma_descriptions_map=kdma_descriptions_map,
    )
    return dialogs["positive_system_prompt"]


def instantiate_adm(llm_backbone=LLM_BACKBONES[0], decider=deciders[0], aligned=True):
    config = get_decider_config(decider, aligned)
    config["instance"]["model_name"] = llm_backbone
    decider = hydra.utils.instantiate(config, recursive=True)
    return decider


def execute_model(model, prompt: ScenarioAndAlignment):
    """Execute a model with the given prompt"""
    state, actions, alignment_target = prepare_context(
        prompt["scenario"], prompt["alignment_targets"]
    )
    action_decision, *_ = model.instance.top_level_choose_action(
        scenario_state=state,
        available_actions=actions,
        alignment_target=alignment_target,
        kdma_descriptions_map=kdma_descriptions_map,
        reasoning_max_length=-1,
        generator_seed=2,
        shuffle_choices=False,
        max_generator_tokens=MAX_GENERATOR_TOKENS,
    )

    return action_decision


def create_adm(llm_backbone=LLM_BACKBONES[0], decider=deciders[0], aligned=True):
    model = instantiate_adm(llm_backbone, decider, aligned)
    return partial(execute_model, model)
