from typing import Dict, Any
import copy
from pathlib import Path
import align_system
from align_app.adm.hydra_config_loader import load_adm_config
from align_app.utils.utils import merge_dicts


base_align_system_config_dir = Path(align_system.__file__).parent / "configs"


def get_decider_config(
    probe_id: str,
    decider: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
):
    """
    Merges base decider config with app-level overrides.
    Two-layer merge: base YAML config + (config_overrides + dataset_overrides)
    """

    def get_dataset_name_from_datasets(
        probe_id: str, datasets_dict: Dict[str, Any]
    ) -> str:
        for name, dataset_info in datasets_dict.items():
            if probe_id in dataset_info["probes"]:
                return name
        raise ValueError(f"Dataset name for probe ID {probe_id} not found.")

    dataset_name = get_dataset_name_from_datasets(probe_id, datasets)

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

    return merged_config
