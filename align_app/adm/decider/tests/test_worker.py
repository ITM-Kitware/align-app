import multiprocessing as mp
from align_app.adm.decider.types import DeciderParams


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
