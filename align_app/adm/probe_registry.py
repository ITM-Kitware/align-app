import copy
from collections import namedtuple
from pathlib import Path
from typing import List, Dict, Any
import align_system
from align_utils.models import (
    InputOutputItem,
    InputData,
    ExperimentItem,
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
        "add_edited_probe",
        "add_probes_from_experiments",
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

    def add_edited_probe(
        base_probe_id: str, edited_text: str, edited_choices: List[Dict[str, Any]]
    ) -> Probe:
        """Create new probe with edited content and -edit-N suffix."""
        base_probe = get_probe(base_probe_id)

        base_scene = base_probe.scene_id.split(" edit ")[0]
        edit_num = 1
        for existing_id in probes:
            if f".{base_scene} edit " in existing_id:
                try:
                    num = int(existing_id.split(" edit ")[-1])
                    edit_num = max(edit_num, num + 1)
                except ValueError:
                    pass

        new_scene_id = f"{base_scene} edit {edit_num}"

        new_full_state = copy.deepcopy(base_probe.full_state)
        new_full_state["unstructured"] = edited_text
        new_full_state["meta_info"]["scene_id"] = new_scene_id

        new_input = InputData(
            scenario_id=base_probe.scenario_id,
            state=base_probe.state,
            full_state=new_full_state,
            choices=edited_choices,
        )
        new_item = InputOutputItem(input=new_input, output=base_probe.item.output)

        new_probe = Probe.from_input_output_item(new_item)
        probes[new_probe.probe_id] = new_probe

        dataset_name = get_dataset_name(base_probe_id)
        datasets[dataset_name]["probes"][new_probe.probe_id] = new_probe

        return new_probe

    def add_probes_from_experiments(experiment_items: List[ExperimentItem]):
        """Add probes from ExperimentItem list, skipping duplicates."""
        for exp_item in experiment_items:
            probe = Probe.from_input_output_item(exp_item.item)
            if probe.probe_id not in probes:
                probes[probe.probe_id] = probe
                datasets["phase2"]["probes"][probe.probe_id] = probe

    return ProbeRegistry(
        get_probes=lambda: probes,
        get_dataset_name=get_dataset_name,
        get_probe=get_probe,
        get_datasets=lambda: datasets,
        get_attributes=get_attributes,
        add_edited_probe=add_edited_probe,
        add_probes_from_experiments=add_probes_from_experiments,
    )
