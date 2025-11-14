from align_utils.models import ADMResult
from .types import DeciderParams
from .worker import decider_worker_func
from .multiprocess_worker import (
    WorkerHandle,
    create_worker,
    send_and_await,
    close_worker,
)


class MultiprocessDecider:
    def __init__(self):
        self.worker: WorkerHandle = create_worker(decider_worker_func)

    async def get_decision(self, params: DeciderParams) -> ADMResult:
        self.worker, result = await send_and_await(self.worker, params)

        if result is None:
            raise RuntimeError("Worker process died unexpectedly")

        if isinstance(result, Exception):
            raise RuntimeError(f"Worker error: {result}")

        return result

    def shutdown(self):
        if self.worker is not None:
            close_worker(self.worker)
            self.worker = None
