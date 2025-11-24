from collections import namedtuple
from pathlib import Path
import align_system
from align_utils.models import (
    InputOutputItem,
)
from align_utils.discovery import load_input_output_files
from align_app.adm.probe import Probe

DEFAULT_SCENARIOS_PATH = Path(__file__).parent / "input_output_files" / "phase2_july"


def get_probes(input_output_files):
    """Convert InputOutputFile models to probe dictionary."""

    def _process_probe(item: InputOutputItem):
        probe = Probe.from_input_output_item(item)
        return probe.probe_id, probe

    return {
        probe_id: probe
        for input_output_file in input_output_files
        for probe_id, probe in (_process_probe(item) for item in input_output_file.data)
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

    all_input_output_files = [
        input_output_file
        for path in scenarios_paths
        for input_output_file in load_input_output_files(Path(path))
    ]
    probes = get_probes(all_input_output_files)

    datasets = {
        "phase2": {
            "probes": probes,
            "attributes": {
                "medical": {"possible_scores": "continuous"},
                "affiliation": {"possible_scores": "continuous"},
                "merit": {"possible_scores": "continuous"},
                "search": {"possible_scores": "continuous"},
                "personal_safety": {"possible_scores": "continuous"},
            },
            "attribute_descriptions_dir": attribute_descriptions_dir,
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

    def get_attributes(probe_id):
        """Get the attributes for a dataset."""
        dataset_name = get_dataset_name(probe_id)
        dataset_info = datasets[dataset_name]
        return dataset_info.get("attributes", {})

    return ProbeRegistry(
        get_probes=lambda: probes,
        get_dataset_name=get_dataset_name,
        get_probe=get_probe,
        get_datasets=lambda: datasets,
        get_attributes=get_attributes,
    )
