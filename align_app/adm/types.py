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


def _alignment_target_id_from_attributes(attributes: List[Attribute]) -> str:
    """Generate alignment target ID from attributes (e.g., 'affiliation-0.5_merit-0.3')."""
    if not attributes:
        return "unknown"
    parts = [f"{a['type']}-{a['score']}" for a in attributes]
    return "_".join(sorted(parts))


def attributes_to_alignment_target(
    attributes: List[Attribute],
) -> AlignmentTarget:
    """Create AlignmentTarget Pydantic model from attributes."""
    return AlignmentTarget(
        id=_alignment_target_id_from_attributes(attributes),
        kdma_values=[
            KDMAValue(
                kdma=a["type"],
                value=a["score"],
                kdes=None,
            )
            for a in attributes
        ],
    )
