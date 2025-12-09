import copy
import hashlib
import json
from collections import namedtuple
from pathlib import Path
from typing import List, Dict, Any
from align_utils.discovery import parse_experiments_directory
from align_utils.models import ExperimentItem, ExperimentData, get_experiment_items
from .experiment_config_loader import load_experiment_adm_config


ExperimentResultsRegistry = namedtuple(
    "ExperimentResultsRegistry",
    [
        "get_all_items",
        "get_experiments",
        "get_items_by_adm",
        "get_items_by_llm",
        "get_items_by_probe",
        "get_unique_deciders",
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
        return [item for item in all_items if _get_probe_id(item) == probe_id]

    def get_unique_deciders() -> Dict[str, Path]:
        """
        Extract unique decider configs from experiments.

        Returns dict: {decider_name: experiment_path}
        - decider_name: experiment directory name (parent of KDMA subdirs)
        - experiment_path: path to one experiment with this config
        """
        seen_hashes: Dict[str, tuple] = {}
        for exp in experiments:
            adm_config = load_experiment_adm_config(exp.experiment_path)
            if adm_config is None:
                continue
            normalized = _normalize_adm_config(adm_config)
            config_hash = _hash_config(normalized)
            if config_hash not in seen_hashes:
                exp_name = exp.experiment_path.parent.name
                seen_hashes[config_hash] = (exp_name, exp.experiment_path)
        return {name: path for name, path in seen_hashes.values()}

    return ExperimentResultsRegistry(
        get_all_items=lambda: all_items,
        get_experiments=lambda: experiments,
        get_items_by_adm=get_items_by_adm,
        get_items_by_llm=get_items_by_llm,
        get_items_by_probe=get_items_by_probe,
        get_unique_deciders=get_unique_deciders,
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


def _normalize_adm_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize config for comparison by stripping absolute paths to filenames."""
    normalized = copy.deepcopy(config)
    _normalize_paths_recursive(normalized)
    return normalized


def _normalize_paths_recursive(obj: Any) -> None:
    """Recursively normalize path-like strings to just filenames."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and "/" in value and value.endswith(".json"):
                obj[key] = Path(value).name
            else:
                _normalize_paths_recursive(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and "/" in item and item.endswith(".json"):
                obj[i] = Path(item).name
            else:
                _normalize_paths_recursive(item)


def _hash_config(config: Dict[str, Any]) -> str:
    """Create deterministic hash of config dict."""
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]
