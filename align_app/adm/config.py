from typing import Dict, Any
import copy
from pathlib import Path
from omegaconf import OmegaConf
import align_system
from align_app.adm.hydra_config_loader import load_adm_config
from align_app.utils.utils import merge_dicts


base_align_system_config_dir = Path(align_system.__file__).parent / "configs"


def get_dataset_decider_configs(
    probe_id: str,
    decider: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
):
    """
    Merges base decider config, common decider config, and dataset-specific
    decider config using the merge_dicts utility.
    """

    def get_dataset_name_from_datasets(
        probe_id: str, datasets_dict: Dict[str, Any]
    ) -> str:
        for name, dataset_info in datasets_dict.items():
            if probe_id in dataset_info["probes"]:
                return name
        raise ValueError(f"Dataset name for probe ID {probe_id} not found.")

    dataset_name = get_dataset_name_from_datasets(probe_id, datasets)
    dataset_specific_config = copy.deepcopy(
        datasets[dataset_name].get("deciders", {}).get(decider, {})
    )

    decider_cfg = all_deciders.get(decider)

    if not decider_cfg:
        return None

    if not decider_cfg.get("runtime_config"):
        if not dataset_specific_config:
            if decider not in datasets[dataset_name].get("deciders", {}):
                return None

    config_path = decider_cfg["config_path"]

    full_cfg = load_adm_config(
        config_path,
        str(base_align_system_config_dir),
    )

    decider_base = full_cfg.get("adm", {})

    common_config = copy.deepcopy(decider_cfg)
    if "config_path" in common_config:
        del common_config["config_path"]

    common_config_no_postures = {
        k: v for k, v in common_config.items() if k != "postures"
    }
    dataset_config_no_postures = {
        k: v for k, v in dataset_specific_config.items() if k != "postures"
    }
    decider_with_postures = merge_dicts(
        common_config_no_postures, dataset_config_no_postures
    )

    merged_postures = {}
    common_postures = common_config.get("postures", {})
    dataset_postures = dataset_specific_config.get("postures", {})

    posture_keys = set(common_postures.keys()) | set(dataset_postures.keys())
    for posture in posture_keys:
        posturing_decider = copy.deepcopy(decider_base)

        common_posture_override = common_postures.get(posture, {})
        posturing_decider = merge_dicts(posturing_decider, common_posture_override)
        dataset_posture_override = dataset_postures.get(posture, {})
        posturing_decider = merge_dicts(posturing_decider, dataset_posture_override)

        merged_postures[posture] = posturing_decider

    decider_with_postures["postures"] = merged_postures

    if "aligned" in decider_with_postures["postures"]:
        if (
            "max_alignment_attributes"
            not in decider_with_postures["postures"]["aligned"]
        ):
            decider_with_postures["postures"]["aligned"]["max_alignment_attributes"] = (
                10
            )

    return decider_with_postures


def get_base_decider_config(probe_id, decider, baseline, all_deciders, datasets):
    merged_configs = get_dataset_decider_configs(
        probe_id, decider, all_deciders, datasets
    )
    if merged_configs is None:
        return None

    alignment = "baseline" if baseline else "aligned"
    if alignment not in merged_configs["postures"]:
        return None

    config = merged_configs["postures"][alignment]

    base_config = OmegaConf.create(config)

    if "config_overrides" in merged_configs:
        overrides = OmegaConf.create(merged_configs["config_overrides"])
        base_config = OmegaConf.merge(base_config, overrides)

    resolved_config = OmegaConf.to_container(base_config)

    decider_info = all_deciders.get(decider, {})
    if "model_path_keys" in decider_info:
        resolved_config["model_path_keys"] = decider_info["model_path_keys"]

    return resolved_config


def resolve_decider_config(probe_id, decider, alignment_target, all_deciders, datasets):
    """Resolve decider config based on alignment target."""
    baseline = len(alignment_target.kdma_values) == 0
    return get_base_decider_config(probe_id, decider, baseline, all_deciders, datasets)
