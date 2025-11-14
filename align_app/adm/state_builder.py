"""State preparation and hydration for ADM execution."""

from typing import Dict, Any, List
from align_system.utils.hydrate_state import p2triage_hydrate_scenario_state
from align_utils.models import AlignmentTarget, KDMAValue
from .types import Attribute
from .probe import Probe
from .config import get_decider_config


def get_probe_from_datasets(probe_id: str, datasets: Dict[str, Any]) -> Probe:
    """Find and return a probe from the datasets."""
    for dataset_info in datasets.values():
        if probe_id in dataset_info["probes"]:
            return dataset_info["probes"][probe_id]
    raise ValueError(f"Probe '{probe_id}' not found in datasets configuration")


def attributes_to_alignment_target(
    attributes: List[Attribute],
) -> AlignmentTarget:
    """Create AlignmentTarget Pydantic model from attributes."""
    return AlignmentTarget(
        id="ad_hoc",
        kdma_values=[
            KDMAValue(
                kdma=a["type"],
                value=a["score"],
                kdes=None,
            )
            for a in attributes
        ],
    )


def probe_to_dict(probe: Probe) -> Dict[str, Any]:
    """
    Convert Probe to dictionary representation for serialization.

    Returns a dict with all probe fields suitable for JSON serialization
    or passing to hydration functions.
    """
    return {
        "probe_id": probe.probe_id,
        "scene_id": probe.scene_id,
        "scenario_id": probe.scenario_id,
        "display_state": probe.display_state,
        "full_state": probe.full_state,
        "state": probe.state,
        "choices": probe.choices,
    }


def create_probe_state(probe: Probe):
    """Create a probe state from a probe"""
    probe_dict = probe_to_dict(probe)

    state, actions = p2triage_hydrate_scenario_state(probe_dict)
    return state, actions


def prepare_context(
    probe: Probe,
    decider: str,
    alignment_target: AlignmentTarget,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare execution context for ADM with state, actions, and config."""
    state, actions = create_probe_state(probe)
    config = get_decider_config(probe.probe_id, all_deciders, datasets, decider)
    return {
        "state": state,
        "actions": actions,
        "scenario_id": probe.probe_id,
        "config": config,
    }
