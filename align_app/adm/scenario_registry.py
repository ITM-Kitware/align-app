from collections import namedtuple
from pathlib import Path
from . import adm_core
import align_system
from align_system.utils.hydrate_state import p2triage_hydrate_scenario_state


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


def create_scenario_registry(scenarios_path=None):
    """
    Creates a ScenarioRegistry with scenarios loaded from the specified path.
    If no path provided, uses default location.
    """
    align_system_path = Path(align_system.__file__).parent
    attribute_descriptions_dir = align_system_path / "configs" / "alignment_target"

    if scenarios_path is None:
        scenarios_path = adm_core.input_output_files / "phase2_july"

    scenarios_path = Path(scenarios_path)

    if scenarios_path.is_file():
        scenarios = adm_core.load_scenarios(scenarios_path)
    elif scenarios_path.is_dir():
        scenarios = adm_core.load_scenarios_dir(scenarios_path)
    else:
        raise ValueError(f"Invalid scenarios path: {scenarios_path}")

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

    def get_dataset_name(scenario_id):
        for name, dataset_info in datasets.items():
            if scenario_id in dataset_info["scenarios"]:
                return name
        raise ValueError(f"Dataset name for scenario ID {scenario_id} not found.")

    def get_scenario(scenario_id):
        for dataset_info in datasets.values():
            if scenario_id in dataset_info["scenarios"]:
                return dataset_info["scenarios"][scenario_id]
        raise ValueError(f"Scenario ID {scenario_id} not found.")

    def get_attributes(scenario_id, decider):
        """Get the attributes for a dataset, checking for decider-specific overrides."""
        dataset_name = get_dataset_name(scenario_id)
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
