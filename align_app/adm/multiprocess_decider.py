from multiprocessing import Process, Queue
from typing import TypedDict, Any, Optional, Union, Literal
from enum import Enum
from . import adm_core
import asyncio

# Global counter and lock for request IDs
_request_counter = 0


def get_request_id() -> str:
    """Generate a unique request ID."""
    global _request_counter
    _request_counter += 1
    return f"req_{_request_counter}"


class RequestType(str, Enum):
    RUN = "run"
    SHUTDOWN = "shutdown"


class DeciderParams(TypedDict):
    llm_backbone: str
    decider_type: str
    aligned: bool


class RunPayload(TypedDict):
    prompt: str
    decider_params: DeciderParams


class RunDeciderRequest(TypedDict):
    request_type: Literal[RequestType.RUN]
    payload: RunPayload
    request_id: str


class ShutdownDeciderRequest(TypedDict):
    request_type: Literal[RequestType.SHUTDOWN]
    request_id: str


DeciderRequest = Union[RunDeciderRequest, ShutdownDeciderRequest]

Decision = Any


class DeciderResponse(TypedDict):
    request_id: str
    result: Optional[Any]
    error: Optional[Any]
    success: bool


def decider_process_worker(request_queue: Queue, response_queue: Queue):
    """Worker function to run in a separate process."""
    # Single decider cache instead of dictionary
    current_decider = None
    current_decider_key = None

    # Pre-load the default decider
    default_decider_key = (adm_core.LLM_BACKBONES[0], adm_core.deciders[0], True)
    current_decider = adm_core.load_adm()
    current_decider_key = default_decider_key

    shutdown = False
    while not shutdown:
        request: DeciderRequest = request_queue.get()

        if request["request_type"] == RequestType.SHUTDOWN:
            response_queue.put(
                DeciderResponse(
                    request_id=request["request_id"],
                    result="Shutting down",
                    error=None,
                    success=True,
                )
            )
            shutdown = True
        elif request["request_type"] == RequestType.RUN:
            run_payload: RunPayload = request["payload"]
            prompt = run_payload["prompt"]
            decider_params = run_payload["decider_params"]

            # Convert dictionary to tuple for use as key
            requested_decider_key = (
                decider_params["llm_backbone"],
                decider_params["decider_type"],
                decider_params["aligned"],
            )

            # Only load a new decider if parameters don't match current decider
            if requested_decider_key != current_decider_key:
                current_decider = adm_core.load_adm(
                    llm_backbone=decider_params["llm_backbone"],
                    decider=decider_params["decider_type"],
                    aligned=decider_params["aligned"],
                )
                current_decider_key = requested_decider_key

            action_decision = adm_core.execute_model(current_decider, prompt)

            # Convert to dictionary for serialization
            decision_dict = action_decision.to_dict()
            response_queue.put(
                DeciderResponse(
                    request_id=request["request_id"],
                    result=decision_dict,
                    error=None,
                    success=True,
                )
            )


class MultiprocessDecider:
    def __init__(self):
        self.request_queue = Queue()
        self.response_queue = Queue()
        self.process = None
        self._start_process()

    def _start_process(self):
        if self.process is None or not self.process.is_alive():
            self.process = Process(
                target=decider_process_worker,
                args=(self.request_queue, self.response_queue),
                daemon=True,
            )
            self.process.start()

    async def get_decision(
        self, prompt, decider_params: Union[None, DeciderParams] = None
    ) -> Decision:
        """Run a decider with the given prompt and optional decider key."""
        self._start_process()

        if decider_params is None:
            decider_params = {
                "llm_backbone": adm_core.LLM_BACKBONES[0],
                "decider_type": adm_core.deciders[0],
                "aligned": True,
            }

        payload: RunPayload = {
            "prompt": prompt,
            "decider_params": decider_params,
        }

        request: RunDeciderRequest = {
            "request_type": RequestType.RUN,
            "payload": payload,
            "request_id": get_request_id(),
        }
        self.request_queue.put(request)
        loop = asyncio.get_event_loop()
        response: DeciderResponse = await loop.run_in_executor(
            None, self.response_queue.get
        )
        if not response["success"]:
            raise RuntimeError(f"Decider execution failed: {response['error']}")
        return response["result"]

    def shutdown(self) -> None:
        """Shutdown the decider process."""
        if self.process and self.process.is_alive():
            request: ShutdownDeciderRequest = {
                "request_type": RequestType.SHUTDOWN,
                "request_id": get_request_id(),
            }
            self.request_queue.put(request)
            self.response_queue.get()  # Wait for acknowledgment
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
