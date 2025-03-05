from pathlib import Path
from typing import TypedDict, List
import json
import hydra
from omegaconf import OmegaConf, DictConfig
from align_system.utils.hydrate_state import hydrate_scenario_state
from .action_filtering import filter_actions

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

NO_ALIGNMENT = "no alignment"
attributes = [
    NO_ALIGNMENT,
    "moral_deservingness",
    "maximization",
    # "moral_judgement",
    # "ingroup_bias",
]


def list_json_files(dir_path):
    return [str(file) for file in dir_path.iterdir() if file.suffix == ".json"]


def get_scenarios():
    evaluation_file = list_json_files(oracles)[1]
    return load_scenarios(evaluation_file)


class DeciderParams(TypedDict):
    llm_backbone: str
    decider: str


class Choice(TypedDict):
    unstructured: str


class Scenario(TypedDict):
    scenario_id: str
    choices: List[Choice]


class Prompt(TypedDict):
    decider_params: DeciderParams
    alignment_target: DictConfig
    scenario: Scenario


def get_prompt(
    scenario_id,
    llm_backbone=LLM_BACKBONES[0],
    decider=deciders[0],
    alignment_attribute=attributes[0],
    alignment_score=0,
):
    decider_params = {
        "llm_backbone": llm_backbone,
        "decider": decider,
    }

    alignment_target = load_alignment_target(
        kdma=alignment_attribute, kdma_value=alignment_score
    )
    scenario = get_scenarios()[scenario_id]
    return {
        "decider_params": decider_params,
        "alignment_target": alignment_target,
        "scenario": scenario,
    }


def serialize_prompt(prompt):
    alignment_target = (
        OmegaConf.to_container(prompt["alignment_target"])
        if prompt["alignment_target"] is not NO_ALIGNMENT
        else prompt["alignment_target"]
    )
    return {
        **prompt,
        "alignment_target": alignment_target,
    }


def load_adm(llm_backbone=LLM_BACKBONES[0], decider=deciders[0], aligned=True):
    suffix = "aligned" if aligned else "baseline"
    name = f"{decider}_{suffix}.yaml"
    config_path = adm_configs / name
    config = OmegaConf.load(config_path)
    config["model_name"] = llm_backbone
    decider = hydra.utils.instantiate(config, recursive=True)
    return decider


def load_alignment_target(kdma=attributes[0], kdma_value=0):
    if kdma == NO_ALIGNMENT:
        return NO_ALIGNMENT
    kdma_split = kdma.split("_")
    kdma_file = " ".join(kdma_split).capitalize()
    if kdma_file in ["Moral deservingness", "Maximization"]:
        binary_alignment = "high" if float(kdma_value) >= 0.5 else "low"
        filename = f"{kdma}_{binary_alignment}.yaml"
    # elif kdma_file in ["Moral judgement", "Ingroup bias"]:
    #     filename = f"ADEPT-DryRun-{kdma_file}-{kdma_value}.yaml"

    return OmegaConf.load(alignment_configs / filename)


def load_scenarios(evaluation_file):
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


def create_scenario_state(scenario):
    """Create a scenario state from a scenario description"""
    state, actions = hydrate_scenario_state(scenario)
    actions = filter_actions(state, actions)
    return state, actions


def execute_model(model, prompt):
    """Execute a model with the given prompt"""
    state, actions = create_scenario_state(prompt["scenario"])
    alignment_target = prompt["alignment_target"]

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
