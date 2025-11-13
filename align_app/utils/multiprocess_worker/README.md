# Functional Multiprocess Worker

Pure functional multiprocess utility for long-running tasks in async applications, with proper Ctrl+C handling.

## API

```python
from burn_out.multiprocess_worker import create_worker, send_and_await, close_worker

def my_worker(task_queue, result_queue):
    while True:
        try:
            task = task_queue.get()
            if task is None:
                break
            result = process(task)
            result_queue.put(result)
        except (KeyboardInterrupt, SystemExit):
            break  # Critical for Ctrl+C handling
        except Exception as e:
            result_queue.put(f"error: {e}")

# Create and use worker
worker = create_worker(my_worker)
worker, result = await send_and_await(worker, "some task")
close_worker(worker)
```

## Core Functions

- `create_worker(worker_func)` → `WorkerHandle`
- `send_task(worker, task)` → `WorkerHandle`
- `await_result(worker, timeout=None)` → `(WorkerHandle, result)`
- `send_and_await(worker, task, timeout=None)` → `(WorkerHandle, result)`
- `close_worker(worker)` → `None`
- `cancel_worker(worker)` → `WorkerHandle`

## Key Features

- **Pure Functional**: Immutable handles, no side effects
- **Ctrl+C Safe**: Won't hang when child process is interrupted
- **Auto-restart**: Restarts dead workers automatically
- **Async Integration**: Works with asyncio event loops
- **Graceful Shutdown**: Proper cleanup and termination

## Testing

Run the comprehensive test suite:

```bash
# From the burnoutweb root directory
source .venv/bin/activate
cd app/burn_out/multiprocess_worker
pytest -v
```

The tests validate:

- Basic functionality and error handling
- Critical Ctrl+C interrupt scenarios
- Process lifecycle and auto-restart
- Performance and memory cleanup
