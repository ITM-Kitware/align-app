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
from hydra import initialize_config_module, compose

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
]


def list_json_files(dir_path: Path):
    """Recursively find all JSON files in a directory and its subdirectories."""
    return [str(path) for path in dir_path.rglob("*.json")]


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


align_system_path = Path(align_system.__file__).parent
align_system_config_dir = align_system_path / "configs"
adm_demo_configs = align_system_config_dir / "experiment" / "demo"


datasets = {
    "naacl24": {
        "scenarios": load_scenarios_dir(naacl24_input_dir),
        "deciders": {
            "outlines_transformers_structured": {
                "aligned": "experiment/demo/outlines_structured_adm_aligned_naacl24",
                "baseline": "experiment/demo/outlines_structured_adm_baseline_naacl24",
            },
        },
    },
    "opinionqa": {
        "scenarios": load_scenarios_dir(opinionqa_input_dir),
        "deciders": {
            "outlines_transformers_structured": {
                "aligned": "experiment/demo/outlines_structured_adm_aligned_opinionqa",
                "baseline": "experiment/demo/outlines_structured_adm_baseline_opinionqa.yaml",
            },
        },
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


kdma_descriptions_map = configs / "prompt_engineering" / "kdma_descriptions.yml"


# deciders = ["outlines_transformers_structured", "outlines_comparative_regression"]
deciders = ["outlines_transformers_structured"]

attributes = [
    "moral_deservingness",
    "maximization",
    # "moral_judgement",
    # "ingroup_bias",
]


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


def get_decider_config(scenario_id, decider, baseline):
    # Find which dataset this scenario belongs to
    dataset_name = None
    for name, dataset_info in datasets.items():
        if scenario_id in dataset_info["scenarios"]:
            dataset_name = name
            break

    if dataset_name is None:
        raise ValueError(f"Scenario ID {scenario_id} not found in any dataset")

    alignment = "baseline" if baseline else "aligned"

    if decider not in datasets[dataset_name]["deciders"]:
        raise ValueError(f"Decider {decider} not found in dataset {dataset_name}")

    decider_configs = datasets[dataset_name]["deciders"][decider]
    if alignment not in decider_configs:
        raise ValueError(
            f"Alignment setting {alignment} not found for decider {decider} in dataset {dataset_name}"
        )

    config_name = decider_configs[alignment]
    with initialize_config_module(
        config_module="align_system.configs", job_name="decider_config"
    ):
        config = compose(config_name=config_name)
    resolved_config = OmegaConf.create(OmegaConf.to_container(config, resolve=True))
    return resolved_config


def prepare_context(scenario, alignment_targets):
    state, actions = create_scenario_state(scenario)
    alignment_target = alignment_targets[0] if alignment_targets else None
    return state, actions, alignment_target


def get_system_prompt(decider, attributes, scenario_id):
    alignment_targets = prepare_alignment_targets(attributes)
    scenario = scenarios[scenario_id]
    state, actions, alignment_target = prepare_context(scenario, alignment_targets)
    baseline = alignment_target is None
    config = get_decider_config(scenario_id, decider, baseline=baseline)
    target_class = hydra.utils.get_class(config.adm.instance._target_)
    dialogs = target_class.get_dialogs(
        state,
        actions,
        alignment_target,
        num_positive_samples=1,
        num_negative_samples=0,
        shuffle_choices=False,
        baseline=baseline,
        kdma_descriptions_map=kdma_descriptions_map,
    )
    return dialogs["positive_system_prompt"]


def instantiate_adm(
    llm_backbone=LLM_BACKBONES[0], decider=deciders[0], baseline=True, scenario_id=None
):
    config = get_decider_config(scenario_id, decider, baseline)
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


def create_adm(
    llm_backbone=LLM_BACKBONES[0], decider=deciders[0], baseline=True, scenario_id=None
):
    model = instantiate_adm(llm_backbone, decider, baseline, scenario_id)
    return partial(execute_model, model)
