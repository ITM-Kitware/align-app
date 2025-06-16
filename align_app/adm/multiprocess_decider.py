from multiprocessing import Queue, get_context, Manager
from typing import TypedDict, Any, Optional, Union, Literal, cast
from enum import Enum
from .adm_core import Prompt, create_adm
from ..utils.utils import get_id
import asyncio
import gc
import torch
from queue import Empty


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
    decider = None
    decider_cleanup = None
    decider_key = None
    shutdown_requested = False

    def cleanup_decider():
        nonlocal decider, decider_cleanup
        if decider_cleanup is not None:
            decider = None
            decider_cleanup()
            decider_cleanup = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _initialize_or_update_decider(prompt: Prompt, current_decider_key):
        nonlocal decider, decider_cleanup, decider_key
        decider_params = prompt["decider_params"]
        baseline = len(prompt["alignment_target"].kdma_values) == 0
        dataset_name = prompt["scenario"]["scenario_id"].split(".")[0]
        requested_decider_key = (
            decider_params["llm_backbone"],
            decider_params["decider"],
            baseline,
            dataset_name,
        )

        if requested_decider_key != current_decider_key:
            cleanup_decider()
            try:
                new_decider, new_decider_cleanup = create_adm(
                    llm_backbone=decider_params["llm_backbone"],
                    decider=decider_params["decider"],
                    baseline=baseline,
                    scenario_id=prompt["scenario"]["scenario_id"],
                )
                decider = new_decider
                decider_cleanup = new_decider_cleanup
                decider_key = requested_decider_key
            except Exception:
                decider = None
                decider_cleanup = None
                decider_key = None
                raise

    def _execute_decision(
        decider: Any,
        prompt: Prompt,
    ) -> Decision:
        action_decision = decider(prompt)
        decision_dict = action_decision.to_dict()
        return decision_dict

    # Main worker loop
    try:
        while not shutdown_requested:
            request = None
            try:
                request = cast(DeciderRequest, request_queue.get(timeout=1.0))
            except Empty:
                continue
            except (KeyboardInterrupt, SystemExit):
                shutdown_requested = True
                break

            current_request_id = request["request_id"]

            if request["request_type"] == RequestType.SHUTDOWN:
                response_queue.put(
                    DeciderResponse(
                        request_id=current_request_id,
                        result="Shutting down",
                        error=None,
                        success=True,
                    )
                )
                shutdown_requested = True

            elif request["request_type"] == RequestType.RUN:
                run_request = cast(RunDeciderRequest, request)
                prompt_data: Prompt = run_request["prompt"]

                try:
                    _initialize_or_update_decider(prompt_data, decider_key)

                    decision_result = _execute_decision(decider, prompt_data)
                    response_queue.put(
                        DeciderResponse(
                            request_id=current_request_id,
                            result=decision_result,
                            error=None,
                            success=True,
                        )
                    )

                except (KeyboardInterrupt, SystemExit):
                    shutdown_requested = True
                    response_queue.put(
                        DeciderResponse(
                            request_id=current_request_id,
                            result=None,
                            error=f"Shutdown requested during RUN processing for request {current_request_id}.",
                            success=False,
                        )
                    )
                    break
    finally:
        cleanup_decider()


class MultiprocessDecider:
    def __init__(self):
        # Use a Manager to create Queues that are compatible with spawn method
        self.manager = Manager()
        self.request_queue = self.manager.Queue()
        self.response_queue = self.manager.Queue()
        self.process = None
        self._start_process()

    def _start_process(self):
        if self.process is None or not self.process.is_alive():
            ctx = get_context("spawn")
            self.process = ctx.Process(
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
            self.request_queue.put(request, block=True, timeout=1.0)

            self.process.join(timeout=5)

            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)

        self.manager.shutdown()
