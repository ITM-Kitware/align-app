from dataclasses import dataclass, replace
from typing import Dict, Optional, List, Tuple
from .run_models import Run, RunDecision
from ..adm.decider import get_decision


@dataclass(frozen=True)
class RunsData:
    runs: Dict[str, Run]
    decision_cache: Dict[str, RunDecision]

    @staticmethod
    def empty():
        return RunsData(runs={}, decision_cache={})


def add_run(data: RunsData, run: Run) -> RunsData:
    return replace(data, runs={**data.runs, run.id: run})


def get_run(data: RunsData, run_id: str) -> Optional[Run]:
    return data.runs.get(run_id)


def get_all_runs(data: RunsData) -> Dict[str, Run]:
    return data.runs


def filter_runs_by_probe(data: RunsData, probe_id: str) -> List[Run]:
    return [r for r in data.runs.values() if r.probe_id == probe_id]


def get_cached_decision(data: RunsData, cache_key: str) -> Optional[RunDecision]:
    return data.decision_cache.get(cache_key)


def add_cached_decision(
    data: RunsData, cache_key: str, decision: RunDecision
) -> RunsData:
    return replace(data, decision_cache={**data.decision_cache, cache_key: decision})


async def compute_decision(
    data: RunsData, run: Run, probe_choices: List[Dict]
) -> Tuple[RunsData, Run]:
    cache_key = run.compute_cache_key()

    if cached := get_cached_decision(data, cache_key):
        return data, run.model_copy(update={"decision": cached})

    adm_result = await get_decision(run.decider_params)
    decision = RunDecision.from_adm_result(adm_result, probe_choices)

    new_data = add_cached_decision(data, cache_key, decision)
    updated_run = run.model_copy(update={"decision": decision})
    new_data = add_run(new_data, updated_run)

    return new_data, updated_run


def clear_runs(_: RunsData) -> RunsData:
    return RunsData.empty()
