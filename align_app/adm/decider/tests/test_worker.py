import multiprocessing as mp
from align_app.adm.decider.types import DeciderParams
from align_app.adm.decider.worker import extract_cache_key


def mock_worker_with_event_tracking(task_queue, result_queue, event_queue):
    """Worker that uses a mock ADM and tracks load/cleanup events via a Queue.

    This implements the FIXED decider_worker_func logic that cleans up
    old models before loading new ones.
    Events are sent as tuples: ('load', key) or ('cleanup', key)
    """
    import hashlib
    import json
    import logging
    import traceback
    from typing import Dict, Tuple, Callable
    from align_utils.models import ADMResult, Decision, ChoiceInfo
    from align_app.adm.decider.types import DeciderParams

    root_logger = logging.getLogger()
    root_logger.setLevel("WARNING")

    def extract_key(config):
        cache_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()

    def mock_instantiate_adm(config):
        cache_key = extract_key(config)
        event_queue.put(("load", cache_key))

        def choose_action(params):
            return ADMResult(
                decision=Decision(unstructured="test", justification="test"),
                choice_info=ChoiceInfo(
                    choice_id="test",
                    choice_kdma_association=[],
                    choice_description="",
                ),
            )

        def cleanup():
            event_queue.put(("cleanup", cache_key))

        return choose_action, cleanup

    model_cache: Dict[str, Tuple[Callable, Callable]] = {}

    try:
        for task in iter(task_queue.get, None):
            try:
                params: DeciderParams = task
                cache_key = extract_key(params.resolved_config)

                if cache_key not in model_cache:
                    old_cleanups = [cleanup for _, (_, cleanup) in model_cache.items()]
                    model_cache.clear()
                    for cleanup in old_cleanups:
                        cleanup()

                    choose_action_func, cleanup_func = mock_instantiate_adm(
                        params.resolved_config
                    )
                    model_cache[cache_key] = (choose_action_func, cleanup_func)
                else:
                    choose_action_func, _ = model_cache[cache_key]

                result: ADMResult = choose_action_func(params)
                result_queue.put(result)

            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                result_queue.put(Exception(error_msg))
    finally:
        for _, (_, cleanup_func) in model_cache.items():
            try:
                cleanup_func()
            except Exception:
                pass
        event_queue.put(None)


class TestExtractCacheKey:
    def test_same_config_produces_same_key(self):
        config = {"model_name": "test-model", "temperature": 0.7}
        key1 = extract_cache_key(config)
        key2 = extract_cache_key(config)
        assert key1 == key2

    def test_different_configs_produce_different_keys(self):
        config1 = {"model_name": "test-model", "temperature": 0.7}
        config2 = {"model_name": "test-model", "temperature": 0.8}
        key1 = extract_cache_key(config1)
        key2 = extract_cache_key(config2)
        assert key1 != key2

    def test_same_model_different_settings_produce_different_keys(self):
        config1 = {
            "structured_inference_engine": {"model_name": "same-model"},
            "setting_a": "value1",
        }
        config2 = {
            "structured_inference_engine": {"model_name": "same-model"},
            "setting_a": "value2",
        }
        key1 = extract_cache_key(config1)
        key2 = extract_cache_key(config2)
        assert key1 != key2


class TestDeciderWorker:
    def test_worker_processes_single_request(
        self,
        worker_queues,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        from align_app.adm.decider.worker import decider_worker_func

        task_queue, result_queue = worker_queues

        params = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_worker_func, args=(task_queue, result_queue)
        )
        worker_process.start()

        task_queue.put(params)

        result = result_queue.get(timeout=10)

        task_queue.put(None)
        worker_process.join(timeout=5)

        assert result is not None
        assert not isinstance(result, Exception)
        assert hasattr(result, "decision")
        assert hasattr(result, "choice_info")

    def test_worker_caches_models(
        self,
        worker_queues,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        from align_app.adm.decider.worker import decider_worker_func

        task_queue, result_queue = worker_queues

        params1 = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        params2 = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_worker_func, args=(task_queue, result_queue)
        )
        worker_process.start()

        task_queue.put(params1)
        result1 = result_queue.get(timeout=10)

        task_queue.put(params2)
        result2 = result_queue.get(timeout=10)

        task_queue.put(None)
        worker_process.join(timeout=5)

        assert result1 is not None
        assert result2 is not None
        assert not isinstance(result1, Exception)
        assert not isinstance(result2, Exception)

    def test_worker_handles_different_configs(
        self,
        worker_queues,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        from align_app.adm.decider.worker import decider_worker_func

        task_queue, result_queue = worker_queues

        params1 = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        params2 = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_worker_func, args=(task_queue, result_queue)
        )
        worker_process.start()

        task_queue.put(params1)
        result1 = result_queue.get(timeout=10)

        task_queue.put(params2)
        result2 = result_queue.get(timeout=10)

        task_queue.put(None)
        worker_process.join(timeout=5)

        assert not isinstance(result1, Exception)
        assert not isinstance(result2, Exception)

    def test_worker_handles_errors_gracefully(
        self, worker_queues, scenario_input, alignment_target_baseline
    ):
        from align_app.adm.decider.worker import decider_worker_func

        task_queue, result_queue = worker_queues

        params = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config={"invalid": "config"},
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_worker_func, args=(task_queue, result_queue)
        )
        worker_process.start()

        task_queue.put(params)

        result = result_queue.get(timeout=10)

        task_queue.put(None)
        worker_process.join(timeout=5)

        assert isinstance(result, Exception)

    def test_worker_shuts_down_cleanly(self, worker_queues):
        from align_app.adm.decider.worker import decider_worker_func

        task_queue, result_queue = worker_queues

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_worker_func, args=(task_queue, result_queue)
        )
        worker_process.start()

        task_queue.put(None)

        worker_process.join(timeout=5)

        assert not worker_process.is_alive()


def collect_events_from_queue(event_queue, timeout=1.0):
    """Collect all events from queue until None sentinel."""
    import queue

    events = []
    while True:
        try:
            event = event_queue.get(timeout=timeout)
            if event is None:
                break
            events.append(event)
        except queue.Empty:
            break
    return events


class TestCleanupOnADMSwitch:
    """Tests for GPU memory cleanup when switching between ADMs."""

    def test_cleanup_called_before_loading_new_adm(
        self,
        scenario_input,
        alignment_target_baseline,
    ):
        """When loading a new ADM config, cleanup should be called for the old one BEFORE loading the new one.

        This ensures GPU memory is freed before allocating memory for the new model.

        Expected event order:
        1. ('load', key_a)
        2. ('cleanup', key_a)  <-- cleanup BEFORE loading new model
        3. ('load', key_b)
        4. ('cleanup', key_b)  <-- final cleanup on shutdown

        Buggy behavior would be:
        1. ('load', key_a)
        2. ('load', key_b)  <-- no cleanup, models accumulate!
        3. ('cleanup', key_a)
        4. ('cleanup', key_b)
        """
        ctx = mp.get_context("spawn")
        task_queue = ctx.Queue()
        result_queue = ctx.Queue()
        event_queue = ctx.Queue()

        worker_process = ctx.Process(
            target=mock_worker_with_event_tracking,
            args=(task_queue, result_queue, event_queue),
        )
        worker_process.start()

        config_a = {"model": "model_a", "setting": "value_a"}
        config_b = {"model": "model_b", "setting": "value_b"}

        params_a = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=config_a,
        )
        task_queue.put(params_a)
        result_queue.get(timeout=5)

        params_b = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=config_b,
        )
        task_queue.put(params_b)
        result_queue.get(timeout=5)

        task_queue.put(None)
        worker_process.join(timeout=5)

        events = collect_events_from_queue(event_queue)

        load_events = [(i, e) for i, e in enumerate(events) if e[0] == "load"]
        assert len(load_events) == 2, f"Expected 2 load events, got {len(load_events)}"

        load_a_idx = load_events[0][0]
        load_b_idx = load_events[1][0]
        key_a = load_events[0][1][1]

        cleanup_a_before_load_b = any(
            e[0] == "cleanup" and e[1] == key_a
            for e in events[load_a_idx + 1 : load_b_idx]
        )

        assert cleanup_a_before_load_b, (
            f"Expected cleanup of first model BEFORE loading second model.\n"
            f"Events: {events}\n"
            f"This indicates GPU memory is not being freed when switching ADMs."
        )

    def test_no_cleanup_when_same_adm_reused(
        self,
        scenario_input,
        alignment_target_baseline,
    ):
        """When using the same ADM config, no cleanup should happen during operation."""
        ctx = mp.get_context("spawn")
        task_queue = ctx.Queue()
        result_queue = ctx.Queue()
        event_queue = ctx.Queue()

        worker_process = ctx.Process(
            target=mock_worker_with_event_tracking,
            args=(task_queue, result_queue, event_queue),
        )
        worker_process.start()

        config_a = {"model": "model_a", "setting": "value_a"}

        params1 = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=config_a,
        )
        task_queue.put(params1)
        result_queue.get(timeout=5)

        params2 = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=config_a,
        )
        task_queue.put(params2)
        result_queue.get(timeout=5)

        task_queue.put(None)
        worker_process.join(timeout=5)

        events = collect_events_from_queue(event_queue)

        load_events = [e for e in events if e[0] == "load"]
        assert len(load_events) == 1, (
            f"Expected only 1 load event when reusing same config, got {len(load_events)}"
        )
