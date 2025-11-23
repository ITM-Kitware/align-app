from collections import namedtuple
from typing import Optional, Dict, List
from .run_models import Run
from . import runs_core


RunsRegistry = namedtuple(
    "RunsRegistry",
    [
        "add_run",
        "execute_decision",
        "create_and_execute_run",
        "get_run",
        "get_all_runs",
        "clear_runs",
    ],
)


def create_runs_registry():
    data = runs_core.init_runs()

    def add_run(run: Run) -> Run:
        nonlocal data
        data = runs_core.add_run(data, run)
        return run

    async def execute_decision(run: Run, probe_choices: List[Dict]) -> Run:
        nonlocal data
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

    return RunsRegistry(
        add_run=add_run,
        execute_decision=execute_decision,
        create_and_execute_run=create_and_execute_run,
        get_run=get_run,
        get_all_runs=get_all_runs,
        clear_runs=clear_runs,
    )
