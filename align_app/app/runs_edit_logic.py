from typing import Optional
from .run_models import Run
from ..adm.probe import Probe
from .prompt_logic import find_probe_by_base_and_scene


def build_run_with_new_scene(run: Run, probe: Probe) -> Run:
    """Build new Run with updated scene probe.

    Pure domain transformation - just updates scene/probe data.
    Doesn't touch decision field.
    """
    updated_params = run.decider_params.model_copy(
        update={"scenario_input": probe.item.input}
    )

    return run.model_copy(
        update={"probe_id": probe.probe_id, "decider_params": updated_params}
    )


def prepare_scene_update(run: Run, scene_id: str, *, probe_registry) -> Optional[Run]:
    """Prepare run with new scene (orchestration + transformation).

    Performs lookups and builds updated run with new scene.
    Used by factory-generated registry methods.
    """
    current_probe = probe_registry.get_probe(run.probe_id)
    if not current_probe:
        return None

    base_scenario_id = current_probe.scenario_id

    probes = probe_registry.get_probes()
    new_probe_id = find_probe_by_base_and_scene(probes, base_scenario_id, scene_id)
    new_probe = probe_registry.get_probe(new_probe_id)

    if not new_probe:
        return None

    return build_run_with_new_scene(run, new_probe)
