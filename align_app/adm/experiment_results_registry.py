from collections import namedtuple
from pathlib import Path
from typing import List
from align_utils.discovery import parse_experiments_directory
from align_utils.models import ExperimentItem, ExperimentData, get_experiment_items


ExperimentResultsRegistry = namedtuple(
    "ExperimentResultsRegistry",
    [
        "get_all_items",
        "get_experiments",
        "get_items_by_adm",
        "get_items_by_llm",
        "get_items_by_probe",
    ],
)


def create_experiment_results_registry(
    experiments_path: Path,
) -> ExperimentResultsRegistry:
    """
    Creates an ExperimentResultsRegistry with pre-computed experiment results.
    Loads experiment directories containing input_output.json + hydra configs.
    """
    experiments: List[ExperimentData] = parse_experiments_directory(experiments_path)
    all_items: List[ExperimentItem] = [
        item for exp in experiments for item in get_experiment_items(exp)
    ]

    def get_items_by_adm(adm_name: str) -> List[ExperimentItem]:
        return [item for item in all_items if item.config.adm.name == adm_name]

    def get_items_by_llm(llm_name: str) -> List[ExperimentItem]:
        return [item for item in all_items if item.config.adm.llm_backbone == llm_name]

    def get_items_by_probe(probe_id: str) -> List[ExperimentItem]:
        """Filter by probe_id (scenario_id.scene_id)."""
        return [
            item
            for item in all_items
            if _get_probe_id(item) == probe_id
        ]

    return ExperimentResultsRegistry(
        get_all_items=lambda: all_items,
        get_experiments=lambda: experiments,
        get_items_by_adm=get_items_by_adm,
        get_items_by_llm=get_items_by_llm,
        get_items_by_probe=get_items_by_probe,
    )


def _get_probe_id(item: ExperimentItem) -> str:
    """Extract probe_id from an ExperimentItem matching Probe.probe_id format."""
    scenario_id = item.item.input.scenario_id
    scene_id = "unknown"
    full_state = item.item.input.full_state
    if full_state and isinstance(full_state, dict):
        meta_info = full_state.get("meta_info", {})
        if isinstance(meta_info, dict):
            scene_id = meta_info.get("scene_id", "unknown")
    return f"{scenario_id}.{scene_id}"
