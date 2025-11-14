# Functional Multiprocess Worker

Pure functional multiprocess utility for long-running tasks in async applications, with proper Ctrl+C handling and concurrent request support.

## API

```python
from align_app.adm.decider.multiprocess_worker import create_worker, send, close_worker

def my_worker(task_queue, result_queue):
    while True:
        try:
            task = task_queue.get()
            if task is None:
                break
            result = process(task)
            result_queue.put(result)
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            result_queue.put(Exception(str(e)))

# Create worker
worker = create_worker(my_worker)

# Send tasks and get results (safe for concurrent calls)
worker, result = await send(worker, "task 1")
worker, result = await send(worker, "task 2")

# Or send many tasks concurrently (like Promise.all)
import asyncio
results = await asyncio.gather(
    send(worker, "task 1"),
    send(worker, "task 2"),
    send(worker, "task 3"),
)

# Cleanup
close_worker(worker)
```

## Core Functions

- `create_worker(worker_func)` → `WorkerHandle`
- `send(worker, task, timeout=None)` → `(WorkerHandle, result)` - Safe for concurrent calls
- `close_worker(worker)` → `None`
- `cancel_worker(worker)` → `WorkerHandle`

## Key Features

- **Concurrent Safe**: Multiple `send()` calls work correctly, each gets its own result
- **Pure Functional**: Immutable handles, no side effects
- **Ctrl+C Safe**: Won't hang when child process is interrupted
- **Auto-restart**: Restarts dead workers automatically
- **Async Integration**: Works with asyncio event loops and `asyncio.gather()`
- **Graceful Shutdown**: Proper cleanup and termination
