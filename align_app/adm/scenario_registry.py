from collections import namedtuple
from pathlib import Path
import json
import copy
import align_system
from align_system.utils.hydrate_state import p2triage_hydrate_scenario_state

# Default scenarios directory
DEFAULT_SCENARIOS_PATH = Path(__file__).parent / "input_output_files" / "phase2_july"


def list_json_files(dir_path: Path):
    """Recursively find all JSON files in a directory and its subdirectories."""
    return [str(path) for path in dir_path.rglob("*.json")]


def is_valid_scenario_file(data):
    """Check if data has the expected scenario file structure."""
    if not isinstance(data, list):
        return False
    if len(data) == 0:
        return True
    first_item = data[0]
    return isinstance(first_item, dict) and "input" in first_item


def load_scenarios(evaluation_file: str):
    prefix = Path(evaluation_file).parent.name.split("_")[0]
    try:
        with open(evaluation_file, "r") as f:
            dataset = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}

    if not is_valid_scenario_file(dataset):
        return {}

    scenarios = {}
    id_counter: dict[str, int] = {}

    for record in dataset:
        input = record["input"]

        scene_id = input["full_state"]["meta_info"]["scene_id"]

        input["scene_id"] = scene_id
        # scenario_id already contains the original value from JSON (e.g., "July2025-AF-train")

        probe_id_base = f"{prefix}.{input['scenario_id']}.{scene_id}"

        if probe_id_base in id_counter:
            id_counter[probe_id_base] += 1
            resolved_id = f"{prefix}.{input['scenario_id']}.{scene_id}.{id_counter[probe_id_base]}"
        else:
            id_counter[probe_id_base] = 0
            resolved_id = probe_id_base

        input["probe_id"] = resolved_id

        if (
            "full_state" in input
            and isinstance(input["full_state"], dict)
            and "unstructured" in input["full_state"]
        ):
            input["display_state"] = input["full_state"]["unstructured"]

        scenarios[resolved_id] = input
    return scenarios


def get_scenarios(files):
    scenarios = {id: s for file in files for id, s in load_scenarios(file).items()}
    return scenarios


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


ScenarioRegistry = namedtuple(
    "ScenarioRegistry",
    [
        "get_scenarios",
        "get_dataset_name",
        "get_scenario",
        "get_datasets",
        "get_attributes",
    ],
)


def create_scenario_registry(scenarios_paths=None):
    """
    Creates a ScenarioRegistry with scenarios loaded from the specified paths.
    If no paths provided, uses default location.
    Can handle a single path or a list of paths.
    """
    align_system_path = Path(align_system.__file__).parent
    attribute_descriptions_dir = align_system_path / "configs" / "alignment_target"

    if scenarios_paths is None:
        scenarios_paths = DEFAULT_SCENARIOS_PATH

    if not isinstance(scenarios_paths, list):
        scenarios_paths = [scenarios_paths]

    def load_from_path(path):
        path = Path(path)
        if path.is_file():
            return load_scenarios(path)
        elif path.is_dir():
            return load_scenarios_dir(path)
        else:
            raise ValueError(f"Invalid scenarios path: {path}")

    scenarios = {
        scenario_id: scenario
        for path in scenarios_paths
        for scenario_id, scenario in load_from_path(path).items()
    }

    datasets = {
        "phase2": {
            "scenarios": scenarios,
            "scenario_hydration_func": p2triage_hydrate_scenario_state,
            "attributes": {
                "medical": {"possible_scores": "continuous"},
                "affiliation": {"possible_scores": "continuous"},
                "merit": {"possible_scores": "continuous"},
                "search": {"possible_scores": "continuous"},
                "personal_safety": {"possible_scores": "continuous"},
            },
            "attribute_descriptions_dir": attribute_descriptions_dir,
            "deciders": {
                "phase2_pipeline_zeroshot_comparative_regression": {
                    "postures": {
                        "aligned": {
                            "inference_kwargs": {},
                        },
                    },
                },
                "phase2_pipeline_fewshot_comparative_regression": {
                    "postures": {
                        "aligned": {
                            "inference_kwargs": {},
                        },
                    },
                },
                "pipeline_random": {},
                "pipeline_baseline": {},
            },
        },
    }

    def get_dataset_name(probe_id):
        for name, dataset_info in datasets.items():
            if probe_id in dataset_info["scenarios"]:
                return name
        raise ValueError(f"Dataset name for probe ID {probe_id} not found.")

    def get_scenario(probe_id):
        for dataset_info in datasets.values():
            if probe_id in dataset_info["scenarios"]:
                return dataset_info["scenarios"][probe_id]
        raise ValueError(f"Probe ID {probe_id} not found.")

    def get_attributes(probe_id, decider):
        """Get the attributes for a dataset, checking for decider-specific overrides."""
        dataset_name = get_dataset_name(probe_id)
        dataset_info = datasets[dataset_name]

        decider_config = dataset_info.get("deciders", {}).get(decider, {})
        decider_specific_attributes = decider_config.get("attributes")

        if decider_specific_attributes is not None:
            return decider_specific_attributes

        return dataset_info.get("attributes", {})

    return ScenarioRegistry(
        get_scenarios=lambda: scenarios,
        get_dataset_name=get_dataset_name,
        get_scenario=get_scenario,
        get_datasets=lambda: datasets,
        get_attributes=get_attributes,
    )
