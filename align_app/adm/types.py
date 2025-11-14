"""Type definitions for ADM system."""

from typing import Dict, TypedDict, List, Any
from align_utils.models import AlignmentTarget, KDMAValue


class DeciderParams(TypedDict):
    llm_backbone: str
    decider: str


class Choice(TypedDict):
    unstructured: str


class Attribute(TypedDict):
    type: str
    score: float


class ProbeAndAlignment(TypedDict):
    probe: Any  # Probe model
    alignment_target: Any  # AlignmentTarget model


class Prompt(ProbeAndAlignment):
    decider_params: DeciderParams
    all_deciders: Dict[str, Any]
    datasets: Dict[str, Any]


class SerializedKDMAValue(TypedDict):
    kdma: str
    value: float
    kdes: Any | None


class SerializedAlignmentTarget(TypedDict):
    id: str
    kdma_values: List[SerializedKDMAValue]


class SerializedProbeAndAlignment(TypedDict):
    probe: dict
    alignment_target: SerializedAlignmentTarget


class SerializedPrompt(SerializedProbeAndAlignment):
    decider_params: DeciderParams
    system_prompt: str


class DeciderContext(Prompt):
    resolved_config: dict


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
