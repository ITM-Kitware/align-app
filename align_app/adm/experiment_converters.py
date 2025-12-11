"""Pure functions to convert experiment data to domain types."""

import copy
import hashlib
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from align_utils.models import (
    ExperimentItem,
    ExperimentData,
    ADMResult,
    Decision,
    ChoiceInfo,
)

from .probe import Probe, get_probe_id
from .decider_definitions import LLM_BACKBONES
from .experiment_config_loader import load_experiment_adm_config
from .decider.types import DeciderParams
from .run_models import Run, RunDecision


def probes_from_experiment_items(items: List[ExperimentItem]) -> List[Probe]:
    """Convert experiment items to probes, deduping by probe_id."""
    seen = set()
    probes = []
    for item in items:
        probe = Probe.from_input_output_item(item.item)
        if probe.probe_id not in seen:
            seen.add(probe.probe_id)
            probes.append(probe)
    return probes


def deciders_from_experiments(
    experiments: List[ExperimentData],
) -> Dict[str, Dict[str, Any]]:
    """Extract unique decider configs from experiments.

    Returns dict: {decider_name: decider_entry}
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

            if "structured_inference_engine" in adm_config:
                experiment_llm = adm_config["structured_inference_engine"].get(
                    "model_name"
                )
                llm_backbones = (
                    [experiment_llm]
                    + [llm for llm in LLM_BACKBONES if llm != experiment_llm]
                    if experiment_llm
                    else list(LLM_BACKBONES)
                )
            else:
                llm_backbones = ["no_llm"]

            decider_entry = {
                "experiment_path": str(exp.experiment_path),
                "experiment_config": True,
                "llm_backbones": llm_backbones,
                "max_alignment_attributes": 10,
            }
            seen_hashes[config_hash] = (exp_name, decider_entry)

    return {name: entry for name, entry in seen_hashes.values()}


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


def run_from_experiment_item(item: ExperimentItem) -> Optional[Run]:
    """Convert ExperimentItem to Run with decision populated."""
    if not item.item.output:
        return None

    probe_id = get_probe_id(item.item)

    resolved_config = load_experiment_adm_config(item.experiment_path) or {}
    decider_params = DeciderParams(
        scenario_input=item.item.input,
        alignment_target=item.config.alignment_target,
        resolved_config=resolved_config,
    )

    output = item.item.output
    decision = RunDecision(
        adm_result=ADMResult(
            decision=Decision(
                unstructured=output.action.unstructured,
                justification=output.action.justification or "",
            ),
            choice_info=item.item.choice_info or ChoiceInfo(),
        ),
        choice_index=output.choice,
    )

    decider_name = item.experiment_path.parent.name

    return Run(
        id=str(uuid.uuid4()),
        probe_id=probe_id,
        decider_name=decider_name,
        llm_backbone_name=item.config.adm.llm_backbone,
        system_prompt="",
        decider_params=decider_params,
        decision=decision,
    )


def runs_from_experiment_items(items: List[ExperimentItem]) -> List[Run]:
    """Convert experiment items to runs, filtering out items without output."""
    return [run for item in items if (run := run_from_experiment_item(item))]
