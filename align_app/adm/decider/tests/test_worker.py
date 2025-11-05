import pytest
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
        from align_app.adm.decider.worker import decider_process_worker
        from align_app.adm.decider.decider import RunDeciderRequest, RequestType

        request_queue, response_queue = worker_queues

        params = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        request = RunDeciderRequest(
            request_type=RequestType.RUN, params=params, request_id="test-1"
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_process_worker, args=(request_queue, response_queue)
        )
        worker_process.start()

        request_queue.put(request)

        response = response_queue.get(timeout=10)

        from align_app.adm.decider.decider import ShutdownDeciderRequest

        shutdown_request = ShutdownDeciderRequest(
            request_type=RequestType.SHUTDOWN, request_id="shutdown"
        )
        request_queue.put(shutdown_request)
        worker_process.join(timeout=5)

        assert response.request_id == "test-1"
        assert response.success is True
        assert response.result is not None
        assert hasattr(response.result, "decision")
        assert hasattr(response.result, "choice_info")

    def test_worker_caches_models(
        self,
        worker_queues,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        from align_app.adm.decider.worker import decider_process_worker
        from align_app.adm.decider.decider import RunDeciderRequest, RequestType

        request_queue, response_queue = worker_queues

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

        request1 = RunDeciderRequest(
            request_type=RequestType.RUN, params=params1, request_id="test-1"
        )

        request2 = RunDeciderRequest(
            request_type=RequestType.RUN, params=params2, request_id="test-2"
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_process_worker, args=(request_queue, response_queue)
        )
        worker_process.start()

        request_queue.put(request1)
        response1 = response_queue.get(timeout=10)

        request_queue.put(request2)
        response2 = response_queue.get(timeout=10)

        from align_app.adm.decider.decider import ShutdownDeciderRequest

        shutdown_request = ShutdownDeciderRequest(
            request_type=RequestType.SHUTDOWN, request_id="shutdown"
        )
        request_queue.put(shutdown_request)
        worker_process.join(timeout=5)

        assert response1.success is True
        assert response2.success is True
        assert response1.result is not None
        assert response2.result is not None

    def test_worker_handles_different_configs(
        self,
        worker_queues,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        from align_app.adm.decider.worker import decider_process_worker
        from align_app.adm.decider.decider import RunDeciderRequest, RequestType

        request_queue, response_queue = worker_queues

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

        request1 = RunDeciderRequest(
            request_type=RequestType.RUN, params=params1, request_id="test-1"
        )

        request2 = RunDeciderRequest(
            request_type=RequestType.RUN, params=params2, request_id="test-2"
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_process_worker, args=(request_queue, response_queue)
        )
        worker_process.start()

        request_queue.put(request1)
        response1 = response_queue.get(timeout=10)

        request_queue.put(request2)
        response2 = response_queue.get(timeout=10)

        from align_app.adm.decider.decider import ShutdownDeciderRequest

        shutdown_request = ShutdownDeciderRequest(
            request_type=RequestType.SHUTDOWN, request_id="shutdown"
        )
        request_queue.put(shutdown_request)
        worker_process.join(timeout=5)

        assert response1.success is True
        assert response2.success is True

    def test_worker_handles_errors_gracefully(
        self, worker_queues, scenario_input, alignment_target_baseline
    ):
        from align_app.adm.decider.worker import decider_process_worker
        from align_app.adm.decider.decider import RunDeciderRequest, RequestType

        request_queue, response_queue = worker_queues

        params = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config={"invalid": "config"},
        )

        request = RunDeciderRequest(
            request_type=RequestType.RUN, params=params, request_id="test-error"
        )

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_process_worker, args=(request_queue, response_queue)
        )
        worker_process.start()

        request_queue.put(request)

        response = response_queue.get(timeout=10)

        from align_app.adm.decider.decider import ShutdownDeciderRequest

        shutdown_request = ShutdownDeciderRequest(
            request_type=RequestType.SHUTDOWN, request_id="shutdown"
        )
        request_queue.put(shutdown_request)
        worker_process.join(timeout=5)

        assert response.request_id == "test-error"
        assert response.success is False
        assert response.error is not None

    def test_worker_shuts_down_cleanly(self, worker_queues):
        from align_app.adm.decider.worker import decider_process_worker
        from align_app.adm.decider.decider import (
            ShutdownDeciderRequest,
            RequestType,
        )

        request_queue, response_queue = worker_queues

        ctx = mp.get_context("spawn")
        worker_process = ctx.Process(
            target=decider_process_worker, args=(request_queue, response_queue)
        )
        worker_process.start()

        shutdown_request = ShutdownDeciderRequest(
            request_type=RequestType.SHUTDOWN, request_id="shutdown"
        )
        request_queue.put(shutdown_request)

        worker_process.join(timeout=5)

        assert not worker_process.is_alive()
