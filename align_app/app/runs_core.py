from dataclasses import dataclass, replace
from typing import Dict, Optional, List
from ..adm.run_models import Run, RunDecision
from ..adm.decider import get_decision


@dataclass(frozen=True)
class Runs:
    runs: Dict[str, Run]
    decision_cache: Dict[str, RunDecision]

    @staticmethod
    def empty():
        return Runs(runs={}, decision_cache={})


def add_run(data: Runs, run: Run) -> Runs:
    new_data = replace(data, runs={**data.runs, run.id: run})
    if run.decision:
        cache_key = run.compute_cache_key()
        new_data = add_cached_decision(new_data, cache_key, run.decision)
    return new_data


def add_runs_bulk(data: Runs, runs: List[Run]) -> Runs:
    """Add multiple runs efficiently in a single operation."""
    new_runs = {**data.runs}
    new_cache = {**data.decision_cache}

    for run in runs:
        new_runs[run.id] = run
        if run.decision:
            cache_key = run.compute_cache_key()
            new_cache[cache_key] = run.decision

    return Runs(runs=new_runs, decision_cache=new_cache)


def populate_cache_bulk(data: Runs, runs: List[Run]) -> Runs:
    """Populate decision cache from runs without adding to runs dict.

    Use for pre-computed experiment results that should populate cache
    but not appear in UI.
    """
    new_cache = {**data.decision_cache}

    for run in runs:
        if run.decision:
            cache_key = run.compute_cache_key()
            new_cache[cache_key] = run.decision

    return replace(data, decision_cache=new_cache)


def remove_run(data: Runs, run_id: str) -> Runs:
    runs = {rid: run for rid, run in data.runs.items() if rid != run_id}
    return replace(data, runs=runs)


def get_run(data: Runs, run_id: str) -> Optional[Run]:
    return data.runs.get(run_id)


def get_all_runs(data: Runs) -> Dict[str, Run]:
    return data.runs


def get_all_runs_with_cached_decisions(data: Runs) -> Dict[str, Run]:
    return {
        run_id: apply_cached_decision(data, run) for run_id, run in data.runs.items()
    }


def filter_runs_by_probe(data: Runs, probe_id: str) -> List[Run]:
    return [r for r in data.runs.values() if r.probe_id == probe_id]


def get_cached_decision(data: Runs, cache_key: str) -> Optional[RunDecision]:
    return data.decision_cache.get(cache_key)


def apply_cached_decision(data: Runs, run: Run) -> Run:
    cache_key = run.compute_cache_key()
    cached_decision = get_cached_decision(data, cache_key)
    return run.model_copy(update={"decision": cached_decision})


def add_cached_decision(data: Runs, cache_key: str, decision: RunDecision) -> Runs:
    return replace(data, decision_cache={**data.decision_cache, cache_key: decision})


async def fetch_decision(run: Run, probe_choices: List[Dict]) -> RunDecision:
    """Async function that just fetches the decision without modifying data.

    This separation is critical for concurrency: the caller should add the
    result to CURRENT data state after awaiting, not to stale data.
    """
    adm_result = await get_decision(run.decider_params)
    return RunDecision.from_adm_result(adm_result, probe_choices)


def update_run(data: Runs, run_id: str, updated_run: Run) -> Runs:
    """Generic run updater with cache check.

    Updates run and sets decision from cache (None if no cache hit).

    Pure domain operation - receives already-transformed run.
    """
    updated_run = apply_cached_decision(data, updated_run)
    return replace(data, runs={**data.runs, run_id: updated_run})


def init_runs() -> Runs:
    return Runs.empty()


def clear_runs(data: Runs) -> Runs:
    return replace(data, runs={})
