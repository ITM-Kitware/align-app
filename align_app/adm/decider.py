from pathlib import Path
import json
import hydra
from omegaconf import OmegaConf
from align_system.utils.hydrate_state import hydrate_scenario_state
from align_system.prompt_engineering.outlines_prompts import (
    scenario_state_description_1,
    action_selection_prompt,
)
from .action_filtering import filter_actions

current_dir = Path(__file__).parent
configs = current_dir / "configs"
adm_configs = configs / "hydra" / "adm"
alignment_configs = configs / "hydra" / "alignment_target"
oracles = current_dir / "oracle-json-files"
kdma_descriptions_map = configs / "prompt_engineering" / "kdma_descriptions.yml"

LLM_BACKBONES = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "meta-llama/Meta-Llama-3-8B-Instruct",
]

deciders = ["outlines_transformers_structured", "outlines_comparative_regression"]


def load_llm(llm_backbone=LLM_BACKBONES[0], decider=deciders[0], aligned=True):
    suffix = "aligned" if aligned else "baseline"
    name = f"{decider}_{suffix}.yaml"
    config_path = adm_configs / name
    config = OmegaConf.load(config_path)
    config["model_name"] = llm_backbone
    decider = hydra.utils.instantiate(config, recursive=True)
    return decider


attributes = ["moral_deservingness", "maximization", "moral_judgement", "ingroup_bias"]


def load_alignment_target(kdma=attributes[0], kdma_value=0):
    kdma_split = kdma.split("_")
    kdma_file = " ".join(kdma_split).capitalize()
    if kdma_file in ["Moral deservingness", "Maximization"]:
        binary_alignment = "high" if float(kdma_value) >= 0.5 else "low"
        filename = f"{kdma}_{binary_alignment}.yaml"
    elif kdma_file in ["Moral judgement", "Ingroup bias"]:
        filename = (f"ADEPT-DryRun-{kdma_file}-{kdma_value}.yaml",)

    return OmegaConf.load(alignment_configs / filename)


def list_json_files(dir_path):
    return [str(file) for file in dir_path.iterdir() if file.suffix == ".json"]


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


def get_probe_ids(scenarios):
    probe_ids = []
    for scenario in scenarios:
        state, actions = hydrate_scenario_state(scenario)
        state_dict = state.to_dict()
        if state.elapsed_time != 0:
            probe_id = state_dict["meta_info"]["probe_response"]["probe_id"]
        else:
            probe_id = "N/A"
        probe_ids.append(probe_id)
    return probe_ids


def create_scenario_state(scenario):
    state, actions = hydrate_scenario_state(scenario)
    actions = filter_actions(state, actions)
    return state, actions


def readable_scenario(scenario):
    state, actions = create_scenario_state(scenario)
    scenario_description = scenario_state_description_1(state)
    actions_unstructured = [action.unstructured for action in actions]
    return action_selection_prompt(scenario_description, actions_unstructured)


def run_model(decider, prompt):
    state, actions = create_scenario_state(prompt["scenario"])

    alignment_target = prompt["alignment_target"]

    action_decision, *_ = decider.instance.top_level_choose_action(
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


decider = load_llm()


def get_decider():
    global decider
    if decider is None:
        decider = load_llm()
    return decider


def get_scenarios():
    evaluation_file = list_json_files(oracles)[1]
    return load_scenarios(evaluation_file)


def get_prompt(scenario_id):
    kdma_attribute = attributes[0]
    alignment_target = load_alignment_target(kdma=kdma_attribute)

    scenario = get_scenarios()[scenario_id]

    return {
        "alignment_target": alignment_target,
        "scenario": scenario,
    }


def serialize_prompt(prompt):
    return {
        "alignment_target": OmegaConf.to_container(prompt["alignment_target"]),
        "scenario": prompt["scenario"],
    }


def get_decision(prompt):
    decider = get_decider()

    decision = run_model(decider, prompt)
    return decision.to_dict()
