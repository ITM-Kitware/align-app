from typing import Dict, Any
from align_utils.models import ADMResult
from .types import DeciderParams
from .worker import decider_worker_func, CacheQuery, CacheQueryResult
from .multiprocess_worker import (
    WorkerHandle,
    create_worker,
    send,
    close_worker,
)


class MultiprocessDecider:
    def __init__(self):
        self.worker: WorkerHandle = create_worker(decider_worker_func)

    async def get_model_cache_status(
        self, resolved_config: Dict[str, Any]
    ) -> CacheQueryResult | None:
        self.worker, result = await send(self.worker, CacheQuery(resolved_config))
        if isinstance(result, CacheQueryResult):
            return result
        return None

    async def get_decision(self, params: DeciderParams) -> ADMResult:
        self.worker, result = await send(self.worker, params)

        if result is None:
            raise RuntimeError("Worker process died unexpectedly")

        if isinstance(result, Exception):
            raise RuntimeError(f"Worker error: {result}")

        return result

    def shutdown(self):
        if self.worker is not None:
            close_worker(self.worker)
            self.worker = None
