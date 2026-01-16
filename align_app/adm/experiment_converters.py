"""Pure functions to convert experiment data to domain types."""

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


def get_decider_batch_name(experiment_path: Path, root_path: Path) -> str:
    """Derive decider batch name from experiment path depth relative to root.

    Depth 1: experiment folder IS the batch (flat structure)
    Depth 2+: parent folder is the batch (nested with alignment subdirs)
    """
    relative = experiment_path.relative_to(root_path)
    depth = len(relative.parts)

    if depth == 1:
        return experiment_path.name
    else:
        return experiment_path.parent.name


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
    root_path: Path,
) -> Dict[str, Dict[str, Any]]:
    """Extract deciders from experiments, one per unique decider batch name.

    Returns dict: {decider_name: decider_entry}
    """
    deciders: Dict[str, Dict[str, Any]] = {}

    sorted_experiments = sorted(experiments, key=lambda e: str(e.experiment_path))
    for exp in sorted_experiments:
        decider_batch = get_decider_batch_name(exp.experiment_path, root_path)
        if decider_batch in deciders:
            continue

        adm_config = load_experiment_adm_config(exp.experiment_path)
        if adm_config is None:
            continue

        if "structured_inference_engine" in adm_config:
            experiment_llm = adm_config["structured_inference_engine"].get("model_name")
            llm_backbones = (
                [experiment_llm]
                + [llm for llm in LLM_BACKBONES if llm != experiment_llm]
                if experiment_llm
                else list(LLM_BACKBONES)
            )
        else:
            llm_backbones = []

        deciders[decider_batch] = {
            "experiment_path": str(exp.experiment_path),
            "experiment_config": True,
            "llm_backbones": llm_backbones,
            "max_alignment_attributes": 10,
        }

    return deciders


def run_from_experiment_item(item: ExperimentItem, root_path: Path) -> Optional[Run]:
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

    decider_batch = get_decider_batch_name(item.experiment_path, root_path)

    return Run(
        id=str(uuid.uuid4()),
        probe_id=probe_id,
        decider_name=decider_batch,
        llm_backbone_name=item.config.adm.llm_backbone or "N/A",
        system_prompt="",
        decider_params=decider_params,
        decision=decision,
    )


def runs_from_experiment_items(
    items: List[ExperimentItem], root_path: Path
) -> List[Run]:
    """Convert experiment items to runs, filtering out items without output."""
    return [run for item in items if (run := run_from_experiment_item(item, root_path))]
