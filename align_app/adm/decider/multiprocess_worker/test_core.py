"""Tests for MultiprocessWorker utility.

These tests cover the critical scenarios needed for robust multiprocess
communication in Trame applications, especially around shutdown behavior.
"""

import asyncio
import pytest
import sys
import time
from multiprocessing import Queue
from typing import Any

from . import create_worker, send, close_worker


# Test worker functions


def simple_echo_worker(task_queue: Queue, result_queue: Queue):
    """Simple worker that echoes tasks."""
    for task in iter(task_queue.get, None):
        try:
            result_queue.put(f"echo: {task}")
        except (KeyboardInterrupt, SystemExit):
            break


def slow_worker(task_queue: Queue, result_queue: Queue):
    """Worker that takes time to process tasks."""
    for task in iter(task_queue.get, None):
        try:
            # Simulate slow processing
            time.sleep(task.get("duration", 1.0) if isinstance(task, dict) else 1.0)
            result_queue.put(f"completed: {task}")
        except (KeyboardInterrupt, SystemExit):
            break


def error_prone_worker(task_queue: Queue, result_queue: Queue):
    """Worker that might throw errors."""
    for task in iter(task_queue.get, None):
        try:
            if task == "error":
                raise ValueError("Test error")
            elif task == "keyboard_interrupt":
                raise KeyboardInterrupt("Simulated Ctrl+C")
            elif task == "system_exit":
                raise SystemExit("Simulated exit")
            else:
                result_queue.put(f"success: {task}")
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            result_queue.put(f"error: {str(e)}")


def stateful_worker(task_queue: Queue, result_queue: Queue):
    """Worker that maintains state between tasks."""
    state: dict[str, Any] = {"counter": 0, "data": {}}

    for task in iter(task_queue.get, None):
        try:
            state["counter"] += 1

            if isinstance(task, dict):
                cmd = task.get("command")
                if cmd == "store":
                    state["data"][task["key"]] = task["value"]
                    result_queue.put({"status": "stored", "key": task["key"]})
                elif cmd == "get":
                    value = state["data"].get(task["key"])
                    result_queue.put({"status": "retrieved", "value": value})
                elif cmd == "count":
                    result_queue.put({"status": "count", "value": state["counter"]})
                elif cmd == "crash":
                    # Simulate worker crash
                    sys.exit(1)
            else:
                result_queue.put(
                    {"status": "processed", "task": task, "count": state["counter"]}
                )

        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            result_queue.put({"status": "error", "error": str(e)})


class TestWorker:
    """Test suite for functional multiprocess worker."""

    @pytest.mark.anyio
    async def test_send(self):
        """Test send function."""
        worker = create_worker(simple_echo_worker)

        try:
            worker, result = await send(worker, "hello")
            assert result == "echo: hello"
        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_multiple_tasks(self):
        """Test processing multiple tasks sequentially."""
        worker = create_worker(simple_echo_worker)

        try:
            tasks = ["task1", "task2", "task3"]
            expected = ["echo: task1", "echo: task2", "echo: task3"]

            results = []
            for task in tasks:
                worker, result = await send(worker, task)
                results.append(result)

            assert results == expected
        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_stateful_worker(self):
        """Test worker that maintains state between tasks."""
        worker = create_worker(stateful_worker)

        try:
            # Store data
            worker, result = await send(
                worker, {"command": "store", "key": "name", "value": "Alice"}
            )
            assert result["status"] == "stored"
            assert result["key"] == "name"

            # Retrieve data
            worker, result = await send(worker, {"command": "get", "key": "name"})
            assert result["status"] == "retrieved"
            assert result["value"] == "Alice"

            # Check counter
            worker, result = await send(worker, {"command": "count"})
            assert result["status"] == "count"
            assert result["value"] == 3  # Three previous tasks

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_worker_error_handling(self):
        """Test how worker handles various types of errors."""
        worker = create_worker(error_prone_worker)

        try:
            # Test normal operation
            worker, result = await send(worker, "normal")
            assert result == "success: normal"

            # Test handled error
            worker, result = await send(worker, "error")
            assert "error: Test error" in result

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_worker_crash_recovery(self):
        """Test that worker handles process crashes gracefully."""
        worker = create_worker(stateful_worker)

        try:
            # Normal operation
            worker, result = await send(
                worker, {"command": "store", "key": "test", "value": "data"}
            )
            assert result["status"] == "stored"

            # Crash the worker - send command and it will die before returning result
            worker, result = await send(worker, {"command": "crash"})
            # Should return None when process dies
            assert result is None

            # Worker should auto-restart for next task
            worker, result = await send(worker, {"command": "count"})
            # Counter should reset (new process)
            assert result["status"] == "count"
            assert result["value"] == 1  # Fresh start

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_keyboard_interrupt_handling(self):
        """Test critical Ctrl+C scenario - worker dies, main process detects."""
        worker = create_worker(error_prone_worker)

        try:
            # Send a task that triggers KeyboardInterrupt in worker
            worker, result = await send(worker, "keyboard_interrupt")

            # Should return None when worker inner function exits
            # (The wrapper process may still be cleaning up threads)
            assert result is None

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_timeout_behavior(self):
        """Test timeout behavior with custom timeout values."""
        worker = create_worker(slow_worker)

        try:
            # Send a quick task
            worker, result = await send(worker, {"duration": 0.1}, timeout=1.0)
            # Should get result
            assert result is not None and "completed:" in result

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_process_lifecycle(self):
        """Test process startup, shutdown, and restart behavior."""
        worker = create_worker(simple_echo_worker)

        try:
            # Verify process starts
            assert worker.process is not None
            assert worker.process.is_alive()

            # Test normal operation
            worker, result = await send(worker, "test")
            assert result == "echo: test"

            # Test cancel (should restart process)
            original_pid = worker.process.pid
            from . import cancel_worker

            worker = cancel_worker(worker)

            # Send another task (should work with new process)
            worker, result = await send(worker, "test2")
            assert result == "echo: test2"

            # Should be a different process
            assert worker.process.pid != original_pid

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_graceful_shutdown(self):
        """Test graceful shutdown behavior."""
        worker = create_worker(simple_echo_worker)

        try:
            # Start a task
            worker, result = await send(worker, "test")
            assert result == "echo: test"

            # Close should shutdown gracefully
            close_worker(worker)

            # Process should be dead
            assert not worker.process.is_alive()

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_concurrent_operations(self):
        """Test multiple concurrent send calls with asyncio.gather (like Promise.all)."""
        worker = create_worker(simple_echo_worker)

        try:
            import asyncio

            # Send multiple tasks concurrently
            tasks = ["task1", "task2", "task3", "task4"]

            # Launch all sends concurrently (like Promise.all)
            send_coroutines = [send(worker, task) for task in tasks]

            # Gather all results - each returns (worker, result)
            results_with_workers = await asyncio.gather(*send_coroutines)

            # Extract just the results
            results = [result for _, result in results_with_workers]

            expected = [f"echo: {task}" for task in tasks]
            assert results == expected

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_many_concurrent_sends(self):
        """Test sending many tasks concurrently and gathering all results (like Promise.all)."""
        worker = create_worker(simple_echo_worker)

        try:
            import asyncio

            # Send many tasks at once
            num_tasks = 20
            tasks = [f"task_{i}" for i in range(num_tasks)]

            # Launch all sends concurrently (like Promise.all in JavaScript)
            send_coroutines = [send(worker, task) for task in tasks]

            # Wait for all to complete
            results_with_workers = await asyncio.gather(*send_coroutines)

            # Extract just the results
            results = [result for _, result in results_with_workers]

            # Verify all results came back correctly
            expected = [f"echo: task_{i}" for i in range(num_tasks)]
            assert results == expected

        finally:
            close_worker(worker)

    def test_daemon_process_property(self):
        """Test that worker processes are daemon processes."""
        worker = create_worker(simple_echo_worker)

        try:
            # Process should be daemon
            assert worker.process.daemon is True

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_worker_restart_after_death(self):
        """Test that worker automatically restarts when process dies."""
        worker = create_worker(stateful_worker)

        try:
            # Kill the process externally
            worker.process.terminate()
            worker.process.join(timeout=1.0)

            # Next operation should restart the worker
            worker, result = await send(worker, {"command": "count"})

            # Should work with fresh process
            assert result["status"] == "count"
            assert result["value"] == 1

        finally:
            close_worker(worker)


# Performance and stress tests


class TestWorkerPerformance:
    """Performance and stress tests."""

    @pytest.mark.anyio
    async def test_rapid_task_processing(self):
        """Test processing many tasks rapidly."""
        worker = create_worker(simple_echo_worker)

        try:
            num_tasks = 50
            tasks = [f"task_{i}" for i in range(num_tasks)]

            start_time = time.time()

            # Send all tasks sequentially
            results = []
            for task in tasks:
                worker, result = await send(worker, task)
                results.append(result)

            end_time = time.time()

            # Verify all results
            expected = [f"echo: task_{i}" for i in range(num_tasks)]
            assert results == expected

            # Should complete reasonably quickly
            assert (end_time - start_time) < 10.0

        finally:
            close_worker(worker)

    @pytest.mark.anyio
    async def test_memory_cleanup(self):
        """Test that resources are properly cleaned up."""
        # This test is more about ensuring no memory leaks
        for i in range(10):
            worker = create_worker(simple_echo_worker)

            try:
                worker, result = await send(worker, f"test_{i}")
                assert f"echo: test_{i}" == result
            finally:
                close_worker(worker)

                # Ensure process is really dead
                assert not worker.process.is_alive()


if __name__ == "__main__":
    # Run basic smoke tests
    async def smoke_test():
        print("Running smoke tests...")

        test_instance = TestWorker()

        print("✓ Testing basic functionality...")
        await test_instance.test_send()

        print("✓ Testing Ctrl+C handling...")
        await test_instance.test_keyboard_interrupt_handling()

        print("✓ Testing worker crash recovery...")
        await test_instance.test_worker_crash_recovery()

        print("✓ Testing stateful worker...")
        await test_instance.test_stateful_worker()

        print("All smoke tests passed!")

    asyncio.run(smoke_test())
