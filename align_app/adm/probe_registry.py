from collections import namedtuple
from pathlib import Path
import json
import align_system
from align_system.utils.hydrate_state import p2triage_hydrate_scenario_state
from align_utils.models import (
    InputOutputFile,
    InputOutputItem,
)
from align_app.adm.probe import Probe

DEFAULT_SCENARIOS_PATH = Path(__file__).parent / "input_output_files" / "phase2_july"


def list_json_files(dir_path: Path):
    """Recursively find all JSON files in a directory and its subdirectories."""
    return [str(path) for path in dir_path.rglob("*.json")]


def load_probes(evaluation_file: str):
    try:
        file_path = Path(evaluation_file)
        input_output = InputOutputFile.load(file_path)
    except (json.JSONDecodeError, ValueError, FileNotFoundError):
        return {}

    if not input_output.data:
        return {}

    def _process_probe(item: InputOutputItem):
        probe = Probe.from_input_output_item(item)
        return probe.probe_id, probe

    return dict(_process_probe(item) for item in input_output.data)


def get_probes(files):
    return {
        probe_id: probe
        for file in files
        for probe_id, probe in load_probes(file).items()
    }


def truncate_unstructured_text(probes):
    def _truncate_probe(probe: Probe) -> Probe:
        if probe.display_state and isinstance(probe.display_state, str):
            truncated_display = probe.display_state.split("\n")[0]
            return probe.model_copy(update={"display_state": truncated_display})
        return probe

    return {probe_id: _truncate_probe(probe) for probe_id, probe in probes.items()}


ProbeRegistry = namedtuple(
    "ProbeRegistry",
    [
        "get_probes",
        "get_dataset_name",
        "get_probe",
        "get_datasets",
        "get_attributes",
    ],
)


def get_dataset_name_for_probe(probe):
    return "phase2"


def create_probe_registry(scenarios_paths=None):
    """
    Creates a ProbeRegistry with probes loaded from the specified paths.
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
    probes = get_probes(all_files)

    datasets = {
        "phase2": {
            "probes": probes,
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
            if probe_id in dataset_info["probes"]:
                return name
        raise ValueError(f"Dataset name for probe ID {probe_id} not found.")

    def get_probe(probe_id):
        for dataset_info in datasets.values():
            if probe_id in dataset_info["probes"]:
                return dataset_info["probes"][probe_id]
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

    return ProbeRegistry(
        get_probes=lambda: probes,
        get_dataset_name=get_dataset_name,
        get_probe=get_probe,
        get_datasets=lambda: datasets,
        get_attributes=get_attributes,
    )
