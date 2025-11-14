from typing import Dict, Any, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, ConfigDict
from align_utils.models import InputData, AlignmentTarget


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
    alignment_target: AlignmentTarget
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
