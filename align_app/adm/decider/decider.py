import asyncio
import multiprocessing as mp
from typing import Optional
from .types import (
    DeciderParams,
    ADMResult,
    RequestType,
    RunDeciderRequest,
    ShutdownDeciderRequest,
)
from .worker import decider_process_worker


class MultiprocessDecider:
    def __init__(self):
        self.manager = mp.Manager()
        self.request_queue = self.manager.Queue()
        self.response_queue = self.manager.Queue()
        self.worker_process: Optional[mp.Process] = None
        self.request_counter = 0
        self._ensure_worker_started()

    def _ensure_worker_started(self):
        if self.worker_process is None or not self.worker_process.is_alive():
            ctx = mp.get_context("spawn")
            self.worker_process = ctx.Process(
                target=decider_process_worker,
                args=(self.request_queue, self.response_queue),
                daemon=True,
            )
            self.worker_process.start()

    async def get_decision(self, params: DeciderParams) -> ADMResult:
        self._ensure_worker_started()

        self.request_counter += 1
        request_id = f"req-{self.request_counter}"

        request = RunDeciderRequest(
            request_type=RequestType.RUN, params=params, request_id=request_id
        )

        self.request_queue.put(request)

        while True:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.response_queue.get
            )
            if response.request_id == request_id:
                if not response.success:
                    raise RuntimeError(f"Worker error: {response.error}")
                return response.result

    def shutdown(self):
        if self.worker_process and self.worker_process.is_alive():
            shutdown_request = ShutdownDeciderRequest(
                request_type=RequestType.SHUTDOWN, request_id="shutdown"
            )
            self.request_queue.put(shutdown_request, block=True, timeout=1.0)
            self.worker_process.join(timeout=5)
            if self.worker_process.is_alive():
                self.worker_process.terminate()
                self.worker_process.join(timeout=1)

        self.manager.shutdown()
