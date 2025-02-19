from pathlib import Path
import re
import json
from ast import literal_eval
import hydra
from omegaconf import OmegaConf
from align_system.utils.hydrate_state import hydrate_scenario_state
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

    alignment_target = OmegaConf.load(alignment_configs / filename)
    return OmegaConf.to_object(alignment_target)


def list_json_files(dir_path):
    return [str(file) for file in dir_path.iterdir() if file.suffix == ".json"]


def load_scenarios(evaluation_file):
    with open(evaluation_file, "r") as f:
        dataset = json.load(f)
    scenarios = {}
    for record in dataset:
        scenario_id = record["input"]["scenario_id"]

        if scenario_id not in scenarios:
            scenarios[scenario_id] = []

        scenarios[scenario_id].append(record["input"])
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


def compose_system_prompt(decider, structured_prompt):
    alignment_target = structured_prompt["alignment_target"]
    scenarios = structured_prompt["scenarios"]
    probe_id = structured_prompt["probe_id"]
    for scenario in scenarios:
        state, actions = hydrate_scenario_state(scenario)
        actions_filtered = filter_actions(state, actions)
        state_dict = state.to_dict()
        if state_dict["meta_info"]["probe_response"] is not None:
            if probe_id != state_dict["meta_info"]["probe_response"]["probe_id"]:
                continue
            probe_id = state_dict["meta_info"]["probe_response"]["probe_id"]
    kwargs = {
        "demo_kwargs": {
            "max_generator_tokens": 8092,
            "generator_seed": 2,
            "shuffle_choices": False,
        }
    }
    if alignment_target is not None:
        alignment_target = OmegaConf.create(alignment_target)

    prompts, *_ = decider.instance.get_dialog_texts(
        scenario_state=state,
        available_actions=actions_filtered,
        alignment_target=alignment_target,
        kdma_descriptions_map=kdma_descriptions_map,
        demo_kwargs=kwargs["demo_kwargs"],
    )

    prompt_sections = prompts[0].split("\n\n")

    prompt = "\n\n".join(
        section
        for section in prompt_sections
        if re.findall(r"-[A-za-z\s]*\n", section) == []
    )
    # action_choices = [
    #     section
    #     for section in prompt_sections
    #     if re.findall(r"-[A-za-z\s]*\n", section) != []
    # ]

    return prompt


def run_model(decider, prompt):
    structured_prompt = prompt["structured_prompt"]
    alignment_target = structured_prompt["alignment_target"]
    scenarios = structured_prompt["scenarios"]
    probe_id = structured_prompt["probe_id"]

    system_prompt = prompt["system_prompt"]
    # available_actions = prompt["action_choices"]
    for scenario in scenarios:
        state, actions = hydrate_scenario_state(scenario)
        available_actions = filter_actions(state, actions)
        state_dict = state.to_dict()
        if state_dict["meta_info"]["probe_response"] is not None:
            if probe_id != state_dict["meta_info"]["probe_response"]["probe_id"]:
                continue
            probe_id = state_dict["meta_info"]["probe_response"]["probe_id"]

    if isinstance(system_prompt, list):
        system_prompt = system_prompt[0]

    top_level_system_prompt = system_prompt.split("\n\n")[0].split("[INST]")[1]
    state.unstructured = re.findall(r"SITUATION:\n[\W\w]*", system_prompt)[0].split(
        "\n"
    )[1]
    character_info = re.findall(r"CHARACTERS:\n[\W\w]*", system_prompt)
    character_info = character_info[0].split("\n\n")[0].split("CHARACTERS:\n")[1]
    for i, j in zip(
        range(len(state.characters)), range(0, len(state.characters) * 2, 2)
    ):
        state.characters[i].unstructured = re.split(
            r"[\d\D]:\s", character_info.split("\n")[j]
        )[1]
        character_additional_info = re.split(
            r"[^\"]:\s", character_info.split("\n")[j + 1]
        )
        char_info = character_additional_info[1]
        state.characters[i].intent = char_info
        if character_additional_info[1][0] == "{":
            char_info = literal_eval(character_additional_info[1])
            if isinstance(char_info, dict):
                state.characters[i].intent = char_info["intent"]
                state.characters[i].directness_of_causality = char_info[
                    "directness_of_causality"
                ]
                state.characters[i].injuries = char_info["injuries"]

    decider.instance.system_ui_prompt = top_level_system_prompt

    if alignment_target is not None:
        alignment_target = OmegaConf.create(alignment_target)

    kwargs = {
        "demo_kwargs": {
            "max_generator_tokens": 8092,
            "generator_seed": 2,
            "shuffle_choices": False,
        }
    }
    action_taken, *_ = decider.instance.top_level_choose_action(
        scenario_state=state,
        available_actions=available_actions,
        alignment_target=alignment_target,
        kdma_descriptions_map=kdma_descriptions_map,
        tokenizer_kwargs={"truncation": False},
        demo_kwargs=kwargs["demo_kwargs"],
    )

    actions_dicts = [action.to_dict() for action in available_actions]
    action_taken_dict = action_taken.to_dict()
    for action_gt in actions_dicts:
        if action_gt["action_id"] == action_taken_dict["action_id"]:
            chosen_action_gt = action_gt
            break

    chosen_action_gt = chosen_action_gt["unstructured"]
    return [
        f"ACTION CHOICE:\n"
        f"{chosen_action_gt}"
        f"\n\nJUSTIFICATION:\n"
        f"{action_taken.justification}"
    ]


decider = load_llm()


def get_decider():
    global decider
    if decider is None:
        decider = load_llm()
    return decider


def get_structured_prompt():
    alignment_target = load_alignment_target()
    evaluation_file = list_json_files(oracles)[0]
    scenarios = load_scenarios(evaluation_file)
    first_scenarios = next(iter(scenarios.values()))
    probe_ids = get_probe_ids(first_scenarios)
    probe_id = probe_ids[0]
    return {
        "alignment_target": alignment_target,
        "scenarios": first_scenarios,
        "probe_id": probe_id,
    }


def get_prompt():
    structured_prompt = get_structured_prompt()
    system_prompt = compose_system_prompt(decider, structured_prompt)
    return {"system_prompt": system_prompt, "structured_prompt": structured_prompt}


def get_decision(prompt):
    decider = get_decider()

    decision = run_model(decider, prompt)
    return decision
