from multiprocessing import Process, Queue
from typing import TypedDict, Any, Optional, Union, Literal, cast
from enum import Enum
from .adm_core import Prompt, load_adm, execute_model, ScenarioAndAlignment
from ..utils.utils import get_id
import asyncio
import gc
import torch


class RequestType(str, Enum):
    RUN = "run"
    SHUTDOWN = "shutdown"


class RunDeciderRequest(TypedDict):
    request_type: Literal[RequestType.RUN]
    prompt: Prompt
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
    current_decider = None
    current_decider_key = None

    def cleanup_decider():
        nonlocal current_decider
        if current_decider is None:
            return
        del current_decider
        gc.collect()
        torch.cuda.empty_cache()

    shutdown = False
    while not shutdown:
        request = cast(DeciderRequest, request_queue.get())

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
            prompt: Prompt = request["prompt"]
            decider_params = prompt["decider_params"]
            aligned = len(prompt["alignment_targets"]) > 0

            requested_decider_key = (
                decider_params["llm_backbone"],
                decider_params["decider"],
                aligned,
            )

            if requested_decider_key != current_decider_key:
                cleanup_decider()
                current_decider_key = requested_decider_key
                current_decider = load_adm(
                    llm_backbone=decider_params["llm_backbone"],
                    decider=decider_params["decider"],
                    aligned=aligned,
                )

            scenario_align: ScenarioAndAlignment = {
                "scenario": prompt["scenario"],
                "alignment_targets": prompt["alignment_targets"],
            }
            action_decision = execute_model(current_decider, scenario_align)

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

    async def get_decision(self, prompt: Prompt) -> Decision:
        """Run a decider with the given prompt and optional decider key."""
        self._start_process()

        request: RunDeciderRequest = {
            "request_type": RequestType.RUN,
            "prompt": prompt,
            "request_id": get_id(),
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
                "request_id": get_id(),
            }
            self.request_queue.put(request)
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
