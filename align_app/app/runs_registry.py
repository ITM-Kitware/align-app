from collections import namedtuple
from typing import Optional, Dict, List, Any, Callable
from .run_models import Run
from . import runs_core
from . import runs_edit_logic


RunsRegistry = namedtuple(
    "RunsRegistry",
    [
        "add_run",
        "execute_decision",
        "execute_run_decision",
        "create_and_execute_run",
        "get_run",
        "get_all_runs",
        "clear_runs",
        "update_run_scene",
        "update_run_scenario",
    ],
)


def create_runs_registry(probe_registry):
    data = runs_core.init_runs()

    def _create_update_method(
        prepare_fn: Callable[[Run, Any], Optional[Run]],
    ) -> Callable[[str, Any], Optional[Run]]:
        """Factory that generates registry update methods.

        Args:
            prepare_fn: Orchestration helper that prepares updated run.
                       Signature: (run, value, *, probe_registry) -> Optional[Run]

        Returns:
            Update method with signature: (run_id, value) -> Optional[Run]
        """

        def update_method(run_id: str, value: Any) -> Optional[Run]:
            nonlocal data

            run = runs_core.get_run(data, run_id)
            if not run:
                return None

            updated_run = prepare_fn(run, value, probe_registry=probe_registry)
            if not updated_run:
                return None

            data = runs_core.update_run(data, run_id, updated_run)
            return runs_core.get_run(data, run_id)

        return update_method

    def add_run(run: Run) -> Run:
        nonlocal data
        data = runs_core.add_run(data, run)
        return run

    async def execute_decision(run: Run, probe_choices: List[Dict]) -> Run:
        nonlocal data
        data, updated_run = await runs_core.compute_decision(data, run, probe_choices)
        return updated_run

    async def execute_run_decision(run_id: str) -> Optional[Run]:
        nonlocal data

        run = runs_core.get_run(data, run_id)
        if not run:
            return None

        probe = probe_registry.get_probe(run.probe_id)
        if not probe:
            return None

        probe_choices = probe.choices or []
        data, updated_run = await runs_core.compute_decision(data, run, probe_choices)
        return updated_run

    async def create_and_execute_run(run: Run, probe_choices: List[Dict]):
        nonlocal data
        data, updated_run = await runs_core.compute_decision(data, run, probe_choices)
        return data, updated_run

    def get_run(run_id: str) -> Optional[Run]:
        return runs_core.get_run(data, run_id)

    def get_all_runs() -> Dict[str, Run]:
        return dict(runs_core.get_all_runs(data))

    def clear_runs():
        nonlocal data
        data = runs_core.clear_runs(data)
        return data

    update_run_scene = _create_update_method(runs_edit_logic.prepare_scene_update)
    update_run_scenario = _create_update_method(runs_edit_logic.prepare_scenario_update)

    return RunsRegistry(
        add_run=add_run,
        execute_decision=execute_decision,
        execute_run_decision=execute_run_decision,
        create_and_execute_run=create_and_execute_run,
        get_run=get_run,
        get_all_runs=get_all_runs,
        clear_runs=clear_runs,
        update_run_scene=update_run_scene,
        update_run_scenario=update_run_scenario,
    )
