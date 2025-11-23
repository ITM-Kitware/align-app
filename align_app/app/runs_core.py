from dataclasses import dataclass, replace
from typing import Dict, Optional, List, Tuple
from .run_models import Run, RunDecision
from ..adm.decider import get_decision


@dataclass(frozen=True)
class RunsData:
    runs: Dict[str, Run]
    decision_cache_index: Dict[str, str]

    @staticmethod
    def empty():
        return RunsData(runs={}, decision_cache_index={})


def add_run(data: RunsData, run: Run) -> RunsData:
    return replace(data, runs={**data.runs, run.id: run})


def get_run(data: RunsData, run_id: str) -> Optional[Run]:
    return data.runs.get(run_id)


def get_all_runs(data: RunsData) -> Dict[str, Run]:
    return data.runs


def filter_runs_by_probe(data: RunsData, probe_id: str) -> List[Run]:
    return [r for r in data.runs.values() if r.probe_id == probe_id]


def get_cached_decision(data: RunsData, cache_key: str) -> Optional[RunDecision]:
    run_id = data.decision_cache_index.get(cache_key)
    if run_id is None:
        return None
    run = data.runs.get(run_id)
    return run.decision if run else None


def add_cached_decision(data: RunsData, cache_key: str, run_id: str) -> RunsData:
    return replace(
        data, decision_cache_index={**data.decision_cache_index, cache_key: run_id}
    )


async def compute_decision(
    data: RunsData, run: Run, probe_choices: List[Dict]
) -> Tuple[RunsData, Run]:
    cache_key = run.compute_cache_key()

    if cached := get_cached_decision(data, cache_key):
        return data, run.model_copy(update={"decision": cached})

    adm_result = await get_decision(run.decider_params)
    decision = RunDecision.from_adm_result(adm_result, probe_choices)

    updated_run = run.model_copy(update={"decision": decision})
    new_data = add_run(data, updated_run)
    new_data = add_cached_decision(new_data, cache_key, updated_run.id)

    return new_data, updated_run


def clear_runs(_: RunsData) -> RunsData:
    return RunsData.empty()
