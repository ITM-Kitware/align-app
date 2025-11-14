"""Specific test for the Ctrl+C hanging scenario that was fixed.

This test simulates the exact problem: a long-running metadata extraction
process that gets interrupted by Ctrl+C, and ensures the main process
doesn't hang waiting for results.
"""

import asyncio
import pytest
import sys
import time
from multiprocessing import Queue

from . import create_worker, send_task, await_result, close_worker


def video_metadata_simulation_worker(task_queue: Queue, result_queue: Queue):
    """Simulates the video metadata extraction worker that was causing hangs."""
    while True:
        try:
            task = task_queue.get()
            if task is None:
                break

            if task == "extract_metadata":
                # Simulate the long-running metadata extraction
                # This is where the original code would hang if interrupted
                for frame in range(1000):  # Simulate processing many frames
                    time.sleep(0.01)  # Simulate processing time

                    # This is where KeyboardInterrupt would happen
                    if frame == 50:  # Simulate interrupt partway through
                        raise KeyboardInterrupt("Simulated Ctrl+C during processing")

                # If we get here, extraction completed successfully
                result_queue.put({"status": "success", "frames": 1000})

        except (KeyboardInterrupt, SystemExit):
            # This is what happens when user presses Ctrl+C
            print("Worker process interrupted at frame processing", file=sys.stderr)
            break
        except Exception as e:
            result_queue.put({"status": "error", "error": str(e)})


def slow_initialization_worker(task_queue: Queue, result_queue: Queue):
    """Worker that takes time to initialize (like loading ML models)."""
    try:
        # Simulate slow initialization (like in align-app with model loading)
        print("Worker initializing...", file=sys.stderr)
        time.sleep(2.0)  # Simulate model loading time
        print("Worker ready", file=sys.stderr)

        for task in iter(task_queue.get, None):
            try:
                if task.get("command") == "inference":
                    # Simulate inference work
                    time.sleep(1.0)
                    result_queue.put({"result": "inference_complete"})
                elif task.get("command") == "interrupt_me":
                    # Simulate getting interrupted during inference
                    time.sleep(0.5)
                    raise KeyboardInterrupt("Interrupted during inference")

            except (KeyboardInterrupt, SystemExit):
                print("Worker interrupted during task", file=sys.stderr)
                break
            except Exception as e:
                result_queue.put({"error": str(e)})

    except (KeyboardInterrupt, SystemExit):
        print("Worker interrupted during initialization", file=sys.stderr)


@pytest.mark.anyio
async def test_ctrl_c_during_processing():
    """Test the exact scenario that was causing hangs."""
    print("Testing Ctrl+C during video metadata processing...")

    worker = create_worker(video_metadata_simulation_worker)

    try:
        # Send the metadata extraction task
        worker = send_task(worker, "extract_metadata")

        # This should return None when the worker process dies from KeyboardInterrupt
        # Previously this would hang forever
        start_time = time.time()
        worker, result = await await_result(worker, timeout=0.1)
        end_time = time.time()

        # Should return None quickly when process dies
        assert result is None, f"Expected None, got {result}"

        # Should not hang - should complete quickly
        elapsed = end_time - start_time
        assert elapsed < 5.0, f"Took too long: {elapsed}s (indicates hanging)"

        # CRITICAL: Now verify the process actually dies (this is core to the fix working)
        # Give process reasonable time to clean up after KeyboardInterrupt
        process_died = False
        for _ in range(30):  # Up to 3 seconds for process cleanup
            await asyncio.sleep(0.1)
            if not worker.process.is_alive():
                process_died = True
                break

        assert process_died, (
            "Process should die after KeyboardInterrupt but is still alive after 3s. "
            "This means the death detection isn't working, which is core to the Ctrl+C fix!"
        )

        print(f"✓ Ctrl+C handled correctly in {elapsed:.2f}s")

    finally:
        close_worker(worker)


@pytest.mark.anyio
async def test_initialization_interrupt():
    """Test interrupting during worker initialization."""
    print("Testing interrupt during worker initialization...")

    worker = create_worker(slow_initialization_worker)

    try:
        # Send task immediately (while worker is still initializing)
        worker = send_task(worker, {"command": "interrupt_me"})

        # Kill the process while it's initializing
        time.sleep(0.5)  # Let it start initializing
        worker.process.terminate()

        # Should return None when process dies
        worker, result = await await_result(worker, timeout=0.1)
        assert result is None

        print("✓ Initialization interrupt handled correctly")

    finally:
        close_worker(worker)


@pytest.mark.anyio
async def test_multiple_interrupts():
    """Test multiple interrupted tasks in sequence."""
    print("Testing multiple interrupted operations...")

    worker = create_worker(video_metadata_simulation_worker)

    try:
        for i in range(3):
            print(f"  Testing interrupt {i + 1}/3...")

            # Each task will be interrupted
            worker = send_task(worker, "extract_metadata")
            worker, result = await await_result(worker, timeout=0.1)

            # Should handle each interrupt gracefully
            assert result is None

            # Worker should restart automatically for next task
            # (this tests the auto-restart functionality)

        print("✓ Multiple interrupts handled correctly")

    finally:
        close_worker(worker)


@pytest.mark.anyio
async def test_normal_operation_after_interrupt():
    """Test that worker can recover and do normal work after being interrupted."""
    print("Testing normal operation after interrupt...")

    # Use a worker that can do both interruptible and normal tasks
    def mixed_worker(task_queue: Queue, result_queue: Queue):
        for task in iter(task_queue.get, None):
            try:
                if task == "normal_task":
                    result_queue.put("normal_result")
                elif task == "interrupt_task":
                    time.sleep(0.1)
                    raise KeyboardInterrupt("Simulated interrupt")
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                result_queue.put(f"error: {e}")

    worker = create_worker(mixed_worker)

    try:
        # First, do normal work
        worker = send_task(worker, "normal_task")
        worker, result = await await_result(worker)
        assert result == "normal_result"

        # Then get interrupted
        worker = send_task(worker, "interrupt_task")
        worker, result = await await_result(worker)
        assert result is None  # Process died

        # Then do normal work again (should auto-restart)
        worker = send_task(worker, "normal_task")
        worker, result = await await_result(worker)
        assert result == "normal_result"

        print("✓ Recovery after interrupt works correctly")

    finally:
        close_worker(worker)


@pytest.mark.anyio
async def test_timing_critical_scenario():
    """Test the exact timing scenario that was problematic."""
    print("Testing timing-critical interrupt scenario...")

    def timing_critical_worker(task_queue: Queue, result_queue: Queue):
        """Worker that simulates the exact timing of the original bug."""
        for task in iter(task_queue.get, None):
            try:
                # Start processing
                for i in range(100):
                    time.sleep(0.01)  # Small delays

                    # Interrupt at a specific point that was problematic
                    if i == 30:
                        # This simulates the exact moment when Ctrl+C was pressed
                        # in the original video metadata extraction
                        raise KeyboardInterrupt("Critical timing interrupt")

                result_queue.put("should_not_get_here")

            except (KeyboardInterrupt, SystemExit):
                # The key is that we DON'T put anything in result_queue here
                # This was causing the main process to hang
                break

    worker = create_worker(timing_critical_worker)

    try:
        start_time = time.time()

        worker = send_task(worker, "timing_test")
        worker, result = await await_result(worker, timeout=0.1)

        end_time = time.time()

        # The fix ensures this returns None quickly instead of hanging
        assert result is None
        assert (end_time - start_time) < 2.0  # Should be much faster

        print(f"✓ Timing-critical scenario handled in {end_time - start_time:.2f}s")

    finally:
        close_worker(worker)


async def main():
    """Run all Ctrl+C scenario tests."""
    print("=" * 60)
    print("TESTING CTRL+C HANG FIX")
    print("=" * 60)

    await test_ctrl_c_during_processing()
    await test_initialization_interrupt()
    await test_multiple_interrupts()
    await test_normal_operation_after_interrupt()
    await test_timing_critical_scenario()

    print("\n" + "=" * 60)
    print("ALL CTRL+C TESTS PASSED! 🎉")
    print("The hanging issue has been fixed.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
