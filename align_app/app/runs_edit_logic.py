"""Update runs with new scenes and scenarios."""

from typing import Optional, Dict
from .run_models import Run
from ..adm.probe import Probe
from .prompt_logic import find_probe_by_base_and_scene
from .prompt import get_scenes_for_base_scenario


def get_first_scene_for_scenario(probes: Dict[str, Probe], scenario_id: str) -> str:
    scene_items = get_scenes_for_base_scenario(probes, scenario_id)
    return scene_items[0]["value"] if scene_items else ""


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


def prepare_scenario_update(
    run: Run, scenario_id: str, *, probe_registry
) -> Optional[Run]:
    """Prepare run with new scenario (orchestration + transformation).

    Performs lookups and builds updated run with new scenario.
    Auto-selects first scene_id in the new scenario.
    Used by factory-generated registry methods.
    """
    probes = probe_registry.get_probes()
    first_scene_id = get_first_scene_for_scenario(probes, scenario_id)

    if not first_scene_id:
        return None

    new_probe_id = find_probe_by_base_and_scene(probes, scenario_id, first_scene_id)
    new_probe = probe_registry.get_probe(new_probe_id)

    if not new_probe:
        return None

    return build_run_with_new_scene(run, new_probe)
