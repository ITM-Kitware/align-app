from pathlib import Path
from typing import TypedDict, List
import json
import hydra
from omegaconf import OmegaConf, DictConfig
from align_system.utils.hydrate_state import hydrate_scenario_state
from .action_filtering import filter_actions
from align_system.utils import logging
import copy

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

deciders = ["outlines_transformers_structured", "outlines_comparative_regression"]

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
        scenarios[scenario_id] = input
    return scenarios


def get_scenarios():
    evaluation_file = list_json_files(oracles)[1]
    return load_scenarios(evaluation_file)


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

    alignment_targets = [
        load_alignment_target(kdma=a["type"], kdma_value=a["score"]) for a in attributes
    ]
    scenario = get_scenarios()[scenario_id]
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


def load_adm(llm_backbone=LLM_BACKBONES[0], decider=deciders[0], aligned=True):
    suffix = "aligned" if aligned else "baseline"
    name = f"{decider}_{suffix}.yaml"
    config_path = adm_configs / name
    config = OmegaConf.load(config_path)
    config["model_name"] = llm_backbone
    decider = hydra.utils.instantiate(config, recursive=True)
    return decider


def load_alignment_target(kdma=attributes[0], kdma_value=0):
    kdma_split = kdma.split("_")
    kdma_file = " ".join(kdma_split).capitalize()
    if kdma_file in ["Moral deservingness", "Maximization"]:
        binary_alignment = "high" if float(kdma_value) >= 0.5 else "low"
        filename = f"{kdma}_{binary_alignment}.yaml"

    return OmegaConf.load(alignment_configs / filename)


def create_scenario_state(scenario):
    """Create a scenario state from a scenario description"""
    state, actions = hydrate_scenario_state(scenario)
    actions = filter_actions(state, actions)
    return state, actions


def execute_model(model, prompt: ScenarioAndAlignment):
    """Execute a model with the given prompt"""
    state, actions = create_scenario_state(prompt["scenario"])
    # TODO: Handle multiple alignment targets
    alignment_target = (
        prompt["alignment_targets"][0] if len(prompt["alignment_targets"]) > 0 else None
    )

    action_decision, *_ = model.instance.top_level_choose_action(
        scenario_state=state,
        available_actions=actions,
        alignment_target=alignment_target,
        kdma_descriptions_map=kdma_descriptions_map,
        tokenizer_kwargs={"truncation": False},
        demo_kwargs={
            "max_generator_tokens": 8092,
            "generator_seed": 2,
            "shuffle_choices": False,
        },
    )

    return action_decision
