from typing import Dict, Any, Optional, Union, Literal, List
from enum import Enum
from pydantic import BaseModel, ConfigDict
from omegaconf import DictConfig
from align_utils.models import InputData


KDMAValue = Union[float, List[float]]
KDMAChoiceValues = Dict[str, KDMAValue]
KDMANestedValues = Dict[str, KDMAChoiceValues]


class Attribute(BaseModel):
    """Alignment attribute"""

    type: str
    score: float


class Decision(BaseModel):
    """Decision result"""

    unstructured: str
    justification: str


class ChoiceInfo(BaseModel):
    """ADM-specific metadata - all fields optional, allows extra fields"""

    model_config = ConfigDict(extra="allow")

    predicted_kdma_values: Optional[KDMANestedValues] = None
    true_kdma_values: Optional[Dict[str, Dict[str, float]]] = None
    true_relevance: Optional[Dict[str, float]] = None
    icl_example_responses: Optional[Dict[str, Any]] = None


class ADMResult(BaseModel):
    """Result from ADM execution"""

    decision: Decision
    choice_info: ChoiceInfo


class DeciderParams(BaseModel):
    """Arguments for decider execution

    Contains everything needed to make a decision:
    - scenario_input: The scenario input data for decision-making (from align_utils)
    - alignment_target: The value alignment to optimize for
    - resolved_config: The fully resolved ADM configuration

    Note: All fields are pickle-serializable for multiprocessing.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    scenario_input: InputData
    alignment_target: DictConfig
    resolved_config: Dict[str, Any]


class RequestType(str, Enum):
    RUN = "run"
    SHUTDOWN = "shutdown"


class RunDeciderRequest(BaseModel):
    request_type: Literal[RequestType.RUN]
    params: DeciderParams
    request_id: str


class ShutdownDeciderRequest(BaseModel):
    request_type: Literal[RequestType.SHUTDOWN]
    request_id: str


DeciderRequest = Union[RunDeciderRequest, ShutdownDeciderRequest]


class DeciderResponse(BaseModel):
    request_id: str
    result: Optional[Any] = None
    error: Optional[Any] = None
    success: bool
