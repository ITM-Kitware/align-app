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
    try:
        with open(evaluation_file, "r") as f:
            dataset = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}

    if not is_valid_scenario_file(dataset):
        return {}

    def _process_scenario(record):
        input = record["input"]
        scene_id = input["full_state"]["meta_info"]["scene_id"]
        probe_id = f"{input['scenario_id']}.{scene_id}"

        input["scene_id"] = scene_id
        input["probe_id"] = probe_id

        if "unstructured" in input["full_state"]:
            input["display_state"] = input["full_state"]["unstructured"]

        return probe_id, input

    return dict(_process_scenario(record) for record in dataset)


def get_scenarios(files):
    return {
        probe_id: scenario
        for file in files
        for probe_id, scenario in load_scenarios(file).items()
    }


def truncate_unstructured_text(scenarios):
    def _truncate_scenario(scenario):
        scenario_copy = copy.deepcopy(scenario)
        if "display_state" in scenario_copy and isinstance(
            scenario_copy["display_state"], str
        ):
            scenario_copy["display_state"] = scenario_copy["display_state"].split("\n")[
                0
            ]
        return scenario_copy

    return {
        probe_id: _truncate_scenario(scenario)
        for probe_id, scenario in scenarios.items()
    }


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


def get_dataset_name_for_scenario(scenario):
    return "phase2"


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

    def _get_files_from_path(path):
        path = Path(path)
        if path.is_file():
            return [str(path)]
        elif path.is_dir():
            return list_json_files(path)
        raise ValueError(f"Invalid scenarios path: {path}")

    all_files = [
        file for path in scenarios_paths for file in _get_files_from_path(path)
    ]
    scenarios = get_scenarios(all_files)

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
