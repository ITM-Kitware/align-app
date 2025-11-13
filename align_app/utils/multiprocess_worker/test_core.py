"""Tests for MultiprocessWorker utility.

These tests cover the critical scenarios needed for robust multiprocess
communication in Trame applications, especially around shutdown behavior.
"""

import asyncio
import pytest
import sys
import time
from multiprocessing import Queue

from . import create_worker, send_and_await, close_worker, send_task, await_result


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
    state = {"counter": 0, "data": {}}

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

    @pytest.mark.asyncio
    async def test_send_and_await(self):
        """Test send_and_await convenience function."""
        worker = create_worker(simple_echo_worker)

        try:
            worker, result = await send_and_await(worker, "hello")
            assert result == "echo: hello"
        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_separate_operations(self):
        """Test separate send_task and await_result operations."""
        worker = create_worker(simple_echo_worker)

        try:
            worker = send_task(worker, "hello")
            worker, result = await await_result(worker)
            assert result == "echo: hello"
        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_multiple_tasks(self):
        """Test processing multiple tasks sequentially."""
        worker = create_worker(simple_echo_worker)

        try:
            tasks = ["task1", "task2", "task3"]
            expected = ["echo: task1", "echo: task2", "echo: task3"]

            results = []
            for task in tasks:
                worker, result = await send_and_await(worker, task)
                results.append(result)

            assert results == expected
        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_stateful_worker(self):
        """Test worker that maintains state between tasks."""
        worker = create_worker(stateful_worker)

        try:
            # Store data
            worker, result = await send_and_await(
                worker, {"command": "store", "key": "name", "value": "Alice"}
            )
            assert result["status"] == "stored"
            assert result["key"] == "name"

            # Retrieve data
            worker, result = await send_and_await(
                worker, {"command": "get", "key": "name"}
            )
            assert result["status"] == "retrieved"
            assert result["value"] == "Alice"

            # Check counter
            worker, result = await send_and_await(worker, {"command": "count"})
            assert result["status"] == "count"
            assert result["value"] == 3  # Three previous tasks

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_worker_error_handling(self):
        """Test how worker handles various types of errors."""
        worker = create_worker(error_prone_worker)

        try:
            # Test normal operation
            worker, result = await send_and_await(worker, "normal")
            assert result == "success: normal"

            # Test handled error
            worker, result = await send_and_await(worker, "error")
            assert "error: Test error" in result

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_worker_crash_recovery(self):
        """Test that worker handles process crashes gracefully."""
        worker = create_worker(stateful_worker)

        try:
            # Normal operation
            worker, result = await send_and_await(
                worker, {"command": "store", "key": "test", "value": "data"}
            )
            assert result["status"] == "stored"

            # Crash the worker
            worker = send_task(worker, {"command": "crash"})
            worker, result = await await_result(worker)
            # Should return None when process dies
            assert result is None

            # Worker should auto-restart for next task
            worker, result = await send_and_await(worker, {"command": "count"})
            # Counter should reset (new process)
            assert result["status"] == "count"
            assert result["value"] == 1  # Fresh start

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_handling(self):
        """Test critical Ctrl+C scenario - worker dies, main process detects."""
        worker = create_worker(error_prone_worker)

        try:
            # Send a task that triggers KeyboardInterrupt in worker
            worker = send_task(worker, "keyboard_interrupt")
            worker, result = await await_result(worker)

            # Should return None when worker process dies from interrupt
            assert result is None

            # Verify process is no longer alive
            assert not worker.process.is_alive()

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_timeout_behavior(self):
        """Test timeout behavior with custom timeout values."""
        worker = create_worker(slow_worker)

        try:
            # Send a quick task
            worker = send_task(worker, {"duration": 0.1})
            worker, result = await await_result(worker, timeout=1.0)  # Longer timeout
            # Should get result
            assert result is not None and "completed:" in result

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_process_lifecycle(self):
        """Test process startup, shutdown, and restart behavior."""
        worker = create_worker(simple_echo_worker)

        try:
            # Verify process starts
            assert worker.process is not None
            assert worker.process.is_alive()

            # Test normal operation
            worker = send_task(worker, "test")
            worker, result = await await_result(worker)
            assert result == "echo: test"

            # Test cancel (should restart process)
            original_pid = worker.process.pid
            from . import cancel_worker

            worker = cancel_worker(worker)

            # Send another task (should work with new process)
            worker = send_task(worker, "test2")
            worker, result = await await_result(worker)
            assert result == "echo: test2"

            # Should be a different process
            assert worker.process.pid != original_pid

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test graceful shutdown behavior."""
        worker = create_worker(simple_echo_worker)

        try:
            # Start a task
            worker = send_task(worker, "test")
            worker, result = await await_result(worker)
            assert result == "echo: test"

            # Close should shutdown gracefully
            close_worker(worker)

            # Process should be dead
            assert not worker.process.is_alive()

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test multiple concurrent await_result calls."""
        worker = create_worker(simple_echo_worker)

        try:
            # Send multiple tasks quickly
            tasks = ["task1", "task2", "task3", "task4"]
            for task in tasks:
                worker = send_task(worker, task)

            # Await results sequentially (queue is sequential)
            results = []
            for _ in tasks:
                worker, result = await await_result(worker)
                results.append(result)

            expected = [f"echo: {task}" for task in tasks]
            assert results == expected

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_no_result_timeout(self):
        """Test behavior when no result is available."""
        worker = create_worker(simple_echo_worker)

        try:
            # Don't send any task, just wait for result
            start_time = time.time()
            worker, result = await await_result(worker, timeout=0.1)
            end_time = time.time()

            # Should return None quickly due to short timeout
            assert result is None
            assert (end_time - start_time) < 1.0  # Should be much faster than 1 second

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

    @pytest.mark.asyncio
    async def test_worker_restart_after_death(self):
        """Test that worker automatically restarts when process dies."""
        worker = create_worker(stateful_worker)

        try:
            # Kill the process externally
            worker.process.terminate()
            worker.process.join(timeout=1.0)

            # Next operation should restart the worker
            worker = send_task(worker, {"command": "count"})
            worker, result = await await_result(worker)

            # Should work with fresh process
            assert result["status"] == "count"
            assert result["value"] == 1

        finally:
            close_worker(worker)


# Performance and stress tests


class TestWorkerPerformance:
    """Performance and stress tests."""

    @pytest.mark.asyncio
    async def test_rapid_task_processing(self):
        """Test processing many tasks rapidly."""
        worker = create_worker(simple_echo_worker)

        try:
            num_tasks = 50
            tasks = [f"task_{i}" for i in range(num_tasks)]

            start_time = time.time()

            # Send all tasks
            for task in tasks:
                worker = send_task(worker, task)

            # Collect all results
            results = []
            for _ in range(num_tasks):
                worker, result = await await_result(worker)
                results.append(result)

            end_time = time.time()

            # Verify all results
            expected = [f"echo: task_{i}" for i in range(num_tasks)]
            assert results == expected

            # Should complete reasonably quickly
            assert (end_time - start_time) < 10.0

        finally:
            close_worker(worker)

    @pytest.mark.asyncio
    async def test_memory_cleanup(self):
        """Test that resources are properly cleaned up."""
        # This test is more about ensuring no memory leaks
        for i in range(10):
            worker = create_worker(simple_echo_worker)

            try:
                worker = send_task(worker, f"test_{i}")
                worker, result = await await_result(worker)
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
        await test_instance.test_send_and_await()

        print("✓ Testing Ctrl+C handling...")
        await test_instance.test_keyboard_interrupt_handling()

        print("✓ Testing worker crash recovery...")
        await test_instance.test_worker_crash_recovery()

        print("✓ Testing stateful worker...")
        await test_instance.test_stateful_worker()

        print("All smoke tests passed!")

    asyncio.run(smoke_test())
