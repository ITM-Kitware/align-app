"""Functional multiprocess utility for long-running tasks in async applications.

This provides pure functions for managing worker processes with Ctrl+C handling.
"""

import asyncio
import atexit
import signal
import sys
from multiprocessing import Process, Queue
from typing import Any, Callable, NamedTuple, Optional, Set, Tuple


_active_workers: Set[Process] = set()
_signal_handler_registered = False


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
    process = Process(target=worker_func, args=(task_queue, result_queue), daemon=True)
    process.start()

    _active_workers.add(process)

    return WorkerHandle(worker_func, task_queue, result_queue, process)


def send_task(worker: WorkerHandle, task: Any) -> WorkerHandle:
    """Send task to worker process.

    Args:
        worker: Worker handle
        task: Task to send

    Returns:
        Worker handle (same if alive, new if restarted)
    """
    # Restart if process is dead
    if not worker.process.is_alive():
        worker = create_worker(worker.worker_func)

    worker.task_queue.put(task)
    return worker


async def await_result(
    worker: WorkerHandle, timeout: Optional[float] = None
) -> Tuple[WorkerHandle, Optional[Any]]:
    """Wait for result from worker process.

    This function monitors the worker process and returns None if the process
    dies (e.g., from Ctrl+C) instead of hanging forever.

    Args:
        worker: Worker handle
        timeout: Optional timeout in seconds (default: wait forever)

    Returns:
        Tuple of (worker_handle, result). Result is None if process died.
    """
    loop = asyncio.get_event_loop()
    start_time = asyncio.get_event_loop().time() if timeout is not None else None

    while worker.process.is_alive():
        try:
            result = await loop.run_in_executor(
                None,
                worker.result_queue.get,
                True,
                0.1,
            )
            return worker, result
        except Exception:
            if timeout is not None and start_time is not None:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    return worker, None
            continue

    return worker, None


async def send_and_await(
    worker: WorkerHandle, task: Any, timeout: Optional[float] = None
) -> Tuple[WorkerHandle, Optional[Any]]:
    """Send task and await result in one operation.

    Args:
        worker: Worker handle
        task: Task to send
        timeout: Optional timeout in seconds (default: wait forever)

    Returns:
        Tuple of (worker_handle, result)
    """
    worker = send_task(worker, task)
    return await await_result(worker, timeout)


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
