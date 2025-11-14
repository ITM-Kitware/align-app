"""Type definitions for ADM system."""

from typing import TypedDict, List, Any


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
