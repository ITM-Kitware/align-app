"""Functional multiprocess utility for long-running tasks in async applications.

This provides pure functions for managing worker processes with Ctrl+C handling.

Concurrent Request Handling:
- Automatically wraps tasks with unique request IDs
- Filters results by request ID to prevent cross-talk between concurrent requests
- Transparent to both worker functions and calling code
"""

import asyncio
import atexit
import signal
import sys
import uuid
from dataclasses import dataclass
from multiprocessing import Process, Queue
from typing import Any, Callable, Dict, NamedTuple, Optional, Set, Tuple


@dataclass
class _InternalRequest:
    """Internal wrapper for tasks with request IDs."""

    request_id: str
    task: Any


@dataclass
class _InternalResponse:
    """Internal wrapper for results with request IDs."""

    request_id: str
    result: Any


_active_workers: Set[Process] = set()
_signal_handler_registered = False
_result_buffer: Dict[str, Any] = {}
_buffer_lock = asyncio.Lock()


def _cleanup_all_workers():
    """Terminate all active workers."""
    for process in list(_active_workers):
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()


def _signal_handler(_signum, _frame):
    """Handle Ctrl+C by terminating all workers."""
    _cleanup_all_workers()
    sys.exit(1)


def _ensure_signal_handler_registered():
    """Register signal handler once on first worker creation."""
    global _signal_handler_registered
    if not _signal_handler_registered:
        signal.signal(signal.SIGINT, _signal_handler)
        atexit.register(_cleanup_all_workers)
        _signal_handler_registered = True


def _worker_wrapper(
    worker_func: Callable[[Queue, Queue], None], task_queue: Queue, result_queue: Queue
):
    """Wrapper that handles request ID wrapping/unwrapping transparently.

    Tasks are processed serially by the worker, so we use a FIFO queue of request IDs
    to match results back to requests.
    """
    from collections import deque

    unwrapped_task_queue = Queue()
    unwrapped_result_queue = Queue()
    request_id_queue = deque()

    import threading

    def unwrap_and_forward():
        """Unwrap incoming requests and track their IDs in FIFO order."""
        for item in iter(task_queue.get, None):
            if isinstance(item, _InternalRequest):
                request_id_queue.append(item.request_id)
                unwrapped_task_queue.put(item.task)
            else:
                unwrapped_task_queue.put(item)

        unwrapped_task_queue.put(None)

    def wrap_and_return():
        """Wrap outgoing results with their request IDs (FIFO order)."""
        while True:
            result = unwrapped_result_queue.get()
            if result is None:
                result_queue.put(None)
                break

            if request_id_queue:
                request_id = request_id_queue.popleft()
                result_queue.put(
                    _InternalResponse(request_id=request_id, result=result)
                )
            else:
                result_queue.put(result)

    unwrap_thread = threading.Thread(target=unwrap_and_forward, daemon=True)
    wrap_thread = threading.Thread(target=wrap_and_return, daemon=True)

    unwrap_thread.start()
    wrap_thread.start()

    try:
        worker_func(unwrapped_task_queue, unwrapped_result_queue)
    finally:
        unwrapped_result_queue.put(None)


class WorkerHandle(NamedTuple):
    """Immutable worker process handle."""

    worker_func: Callable[[Queue, Queue], None]
    task_queue: Queue
    result_queue: Queue
    process: Process


def create_worker(worker_func: Callable[[Queue, Queue], None]) -> WorkerHandle:
    """Create a new worker process.

    Args:
        worker_func: Function that runs in worker process.
                    Must accept (task_queue, result_queue) as arguments.

    Returns:
        WorkerHandle for the created worker
    """
    _ensure_signal_handler_registered()

    task_queue = Queue()
    result_queue = Queue()
    process = Process(
        target=_worker_wrapper,
        args=(worker_func, task_queue, result_queue),
        daemon=True,
    )
    process.start()

    _active_workers.add(process)

    return WorkerHandle(worker_func, task_queue, result_queue, process)


async def _await_result_with_id(
    worker: WorkerHandle, request_id: str, timeout: Optional[float] = None
) -> Tuple[WorkerHandle, Optional[Any]]:
    """Wait for result matching a specific request ID.

    Buffers non-matching results for other awaiters.
    """
    loop = asyncio.get_event_loop()
    start_time = loop.time() if timeout is not None else None

    while worker.process.is_alive():
        async with _buffer_lock:
            if request_id in _result_buffer:
                result = _result_buffer.pop(request_id)
                return worker, result

        try:
            wrapped_result = await loop.run_in_executor(
                None,
                worker.result_queue.get,
                True,
                0.1,
            )

            if isinstance(wrapped_result, _InternalResponse):
                if wrapped_result.request_id == request_id:
                    return worker, wrapped_result.result
                else:
                    async with _buffer_lock:
                        _result_buffer[wrapped_result.request_id] = (
                            wrapped_result.result
                        )
                    continue
            else:
                return worker, wrapped_result

        except Exception:
            if timeout is not None and start_time is not None:
                if loop.time() - start_time > timeout:
                    return worker, None
            continue

    return worker, None


async def send(
    worker: WorkerHandle, task: Any, timeout: Optional[float] = None
) -> Tuple[WorkerHandle, Optional[Any]]:
    """Send task to worker and await result.

    Automatically wraps tasks with unique request IDs to handle concurrent requests.
    Multiple concurrent send() calls are safe and will each receive their correct result.

    Args:
        worker: Worker handle
        task: Task to send
        timeout: Optional timeout in seconds (default: wait forever)

    Returns:
        Tuple of (worker_handle, result)
    """
    request_id = str(uuid.uuid4())
    wrapped_task = _InternalRequest(request_id=request_id, task=task)

    if not worker.process.is_alive():
        worker = create_worker(worker.worker_func)

    worker.task_queue.put(wrapped_task)
    return await _await_result_with_id(worker, request_id, timeout)


def close_worker(worker: WorkerHandle) -> None:
    """Close worker process gracefully.

    Args:
        worker: Worker handle to close
    """
    if worker.process.is_alive():
        worker.task_queue.put(None)  # Signal shutdown
        worker.process.join(timeout=1.0)
        if worker.process.is_alive():
            worker.process.terminate()

    _active_workers.discard(worker.process)


def cancel_worker(worker: WorkerHandle) -> WorkerHandle:
    """Cancel current operations and restart worker.

    Args:
        worker: Worker handle to cancel

    Returns:
        New worker handle
    """
    if worker.process.is_alive():
        worker.process.terminate()
        worker.process.join(timeout=1.0)
        if worker.process.is_alive():
            worker.process.kill()

    _active_workers.discard(worker.process)

    return create_worker(worker.worker_func)
