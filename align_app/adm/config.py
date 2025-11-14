from typing import Dict, Any
import copy
from pathlib import Path
import align_system
from align_app.adm.hydra_config_loader import load_adm_config
from align_app.utils.utils import merge_dicts


base_align_system_config_dir = Path(align_system.__file__).parent / "configs"


def _get_dataset_name(probe_id: str, datasets: Dict[str, Any]) -> str:
    """Get dataset name for a given probe ID."""
    for name, dataset_info in datasets.items():
        if probe_id in dataset_info["probes"]:
            return name
    raise ValueError(f"Dataset name for probe ID {probe_id} not found.")


def get_decider_metadata(
    probe_id: str,
    decider: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Get lightweight metadata for a decider without loading full Hydra config.

    Used by UI to get available options (llm_backbones, max_alignment_attributes).
    Much faster than get_decider_config() as it skips Hydra config loading.

    Returns:
        Dict with metadata fields, or None if decider doesn't exist for probe's dataset
    """
    try:
        dataset_name = _get_dataset_name(probe_id, datasets)
    except ValueError:
        return None

    decider_cfg = all_deciders.get(decider)
    if not decider_cfg:
        return None

    config_overrides = decider_cfg.get("config_overrides", {})
    dataset_overrides = decider_cfg.get("dataset_overrides", {}).get(dataset_name, {})

    metadata = {
        "llm_backbones": decider_cfg.get("llm_backbones", []),
        "model_path_keys": decider_cfg.get("model_path_keys", []),
        "max_alignment_attributes": config_overrides.get(
            "max_alignment_attributes",
            dataset_overrides.get("max_alignment_attributes", 0),
        ),
        "config_path": decider_cfg.get("config_path"),
        "exists": True,
    }

    return metadata


def get_decider_config(
    probe_id: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
    decider: str,
    llm_backbone: str = None,
):
    """
    Merges base decider config with app-level overrides.
    Two-layer merge: base YAML config + (config_overrides + dataset_overrides)

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

    config_path = decider_cfg["config_path"]

    # Layer 1: Load base config from align-system YAML
    full_cfg = load_adm_config(
        config_path,
        str(base_align_system_config_dir),
    )
    decider_base = full_cfg.get("adm", {})

    # Layer 2: Prepare app-level overrides
    config_overrides = decider_cfg.get("config_overrides", {})
    dataset_overrides = decider_cfg.get("dataset_overrides", {}).get(dataset_name, {})

    # Extract metadata fields from decider entry
    metadata = {
        k: v
        for k, v in decider_cfg.items()
        if k in ["llm_backbones", "model_path_keys"]
    }

    # Single deep merge: base + config_overrides + dataset_overrides + metadata
    merged_config = copy.deepcopy(decider_base)
    merged_config = merge_dicts(merged_config, config_overrides)
    merged_config = merge_dicts(merged_config, dataset_overrides)
    merged_config = merge_dicts(merged_config, metadata)

    if llm_backbone:
        merged_config["llm_backbone"] = llm_backbone
        if "structured_inference_engine" in merged_config:
            merged_config["structured_inference_engine"]["model_name"] = llm_backbone

    return merged_config
