from typing import Dict, Any
import copy
from pathlib import Path
import align_system
from align_app.adm.hydra_config_loader import load_adm_config
from align_app.adm.experiment_config_loader import load_experiment_adm_config
from align_app.utils.utils import merge_dicts


base_align_system_config_dir = Path(align_system.__file__).parent / "configs"


def _get_dataset_name(probe_id: str, datasets: Dict[str, Any]) -> str:
    """Get dataset name for a given probe ID."""
    for name, dataset_info in datasets.items():
        if probe_id in dataset_info["probes"]:
            return name
    raise ValueError(f"Dataset name for probe ID {probe_id} not found.")


def get_decider_config(
    probe_id: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
    decider: str,
    llm_backbone: str | None = None,
):
    """
    Merges base decider config with app-level overrides.
    Two-layer merge: base YAML config + (config_overrides + dataset_overrides)

    For experiment configs (experiment_config: True), loads pre-resolved YAML directly.
    For edited configs (edited_config: True), returns the stored resolved_config directly.

    Args:
        probe_id: The probe ID to get config for
        all_deciders: Dict of all available deciders
        datasets: Dict of all datasets
        decider: Decider name
        llm_backbone: Optional LLM backbone to use (for execution with specific model)
    """
    dataset_name = _get_dataset_name(probe_id, datasets)

    decider_cfg = all_deciders.get(decider)
    if not decider_cfg:
        return None

    is_edited_config = decider_cfg.get("edited_config", False)
    is_experiment_config = decider_cfg.get("experiment_config", False)

    if is_edited_config:
        return copy.deepcopy(decider_cfg["resolved_config"])

    # Layer 1: Load base config - either pre-resolved experiment YAML or Hydra compose.
    # Both produce same structure with ${ref:...} that initialize_with_custom_references handles.
    if is_experiment_config:
        experiment_path = Path(decider_cfg["experiment_path"])
        decider_base = load_experiment_adm_config(experiment_path) or {}
    else:
        config_path = decider_cfg["config_path"]
        full_cfg = load_adm_config(
            config_path,
            str(base_align_system_config_dir),
        )
        decider_base = full_cfg.get("adm", {})

    # Layer 2: Prepare app-level overrides
    config_overrides = decider_cfg.get("config_overrides", {})
    dataset_overrides = decider_cfg.get("dataset_overrides", {}).get(dataset_name, {})

    # Deep merge: base + config_overrides + dataset_overrides
    merged_config = copy.deepcopy(decider_base)
    merged_config = merge_dicts(merged_config, config_overrides)
    merged_config = merge_dicts(merged_config, dataset_overrides)

    if llm_backbone and "structured_inference_engine" in merged_config:
        merged_config["structured_inference_engine"]["model_name"] = llm_backbone

    return merged_config
