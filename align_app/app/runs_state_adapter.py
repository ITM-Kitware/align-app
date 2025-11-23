from typing import Dict, Any
from trame.app import asynchronous
from trame.decorators import TrameApp, controller, change
from .run_models import Run, RunDecision
from .runs_registry import RunsRegistry
from ..adm.decider.types import DeciderParams
from .ui import prep_decision_for_state
from ..utils.utils import get_id
import json


def run_to_state_dict(run: Run) -> Dict[str, Any]:
    scenario_input = run.decider_params.scenario_input

    display_state = None
    if scenario_input.full_state and "unstructured" in scenario_input.full_state:
        display_state = scenario_input.full_state["unstructured"]

    scene_id = None
    if (
        scenario_input.full_state
        and "meta_info" in scenario_input.full_state
        and "scene_id" in scenario_input.full_state["meta_info"]
    ):
        scene_id = scenario_input.full_state["meta_info"]["scene_id"]

    probe_dict = {
        "probe_id": run.probe_id,
        "scene_id": scene_id,
        "scenario_id": scenario_input.scenario_id,
        "display_state": display_state,
        "state": scenario_input.state,
        "choices": scenario_input.choices,
        "full_state": scenario_input.full_state,
    }

    result = {
        "id": run.id,
        "prompt": {
            "probe": probe_dict,
            "alignment_target": run.decider_params.alignment_target.model_dump(),
            "decider_params": {
                "llm_backbone": run.llm_backbone_name,
                "decider": run.decider_name,
            },
            "system_prompt": run.system_prompt,
            "resolved_config": run.decider_params.resolved_config,
            "decider": {"name": run.decider_name},
            "llm_backbone": run.llm_backbone_name,
        },
    }

    if run.decision:
        result["decision"] = decision_to_state_dict(run.decision)

    return result


def decision_to_state_dict(decision: RunDecision) -> Dict[str, Any]:
    choice_letter = chr(decision.choice_index + ord("A"))

    decision_dict = {
        "unstructured": f"{choice_letter}. {decision.adm_result.decision.unstructured}",
        "justification": decision.adm_result.decision.justification,
        "choice_info": decision.adm_result.choice_info.model_dump(exclude_none=True),
    }

    return prep_decision_for_state(decision_dict)


@TrameApp()
class RunsStateAdapter:
    def __init__(self, server, prompt_controller, runs_registry: RunsRegistry):
        self.server = server
        self.prompt_controller = prompt_controller
        self.runs_registry = runs_registry
        self._sync_from_runs_data(runs_registry.get_all_runs())

    @property
    def state(self):
        return self.server.state

    def _sync_from_runs_data(self, runs_dict: Dict[str, Run]):
        self.state.runs = {
            run_id: run_to_state_dict(run) for run_id, run in runs_dict.items()
        }
        if not self.state.runs:
            self.state.runs_to_compare = []
            self.state.runs_json = "[]"
            self.state.run_edit_configs = {}

    @controller.set("reset_runs_state")
    def reset_state(self):
        self.runs_registry.clear_runs()
        self._sync_from_runs_data({})

    @controller.set("update_run_to_compare")
    def update_run_to_compare(self, run_index, run_column_index):
        runs = list(self.state.runs.keys())
        self.state.runs_to_compare[run_column_index] = runs[run_index - 1]
        self.state.dirty("runs_to_compare")

    def _sync_run_to_state(self, run: Run):
        run_dict = run_to_state_dict(run)

        with self.state:
            self.state.runs = {
                run_id: ({**item, **run_dict} if run_id == run.id else item)
                for run_id, item in self.state.runs.items()
            }
            if run.id not in self.state.runs:
                self.state.runs = {**self.state.runs, run.id: run_dict}
                self.state.runs_to_compare = self.state.runs_to_compare + [run.id]

    async def create_and_execute_run(self):
        prompt_context = self.prompt_controller.get_prompt()
        run_id = get_id()

        decider_params = DeciderParams(
            scenario_input=prompt_context["probe"].item.input,
            alignment_target=prompt_context["alignment_target"],
            resolved_config=prompt_context["resolved_config"],
        )

        run = Run(
            id=run_id,
            decider_params=decider_params,
            probe_id=prompt_context["probe"].probe_id,
            decider_name=prompt_context.get("decider_params", {}).get("decider", ""),
            llm_backbone_name=prompt_context.get("decider_params", {}).get(
                "llm_backbone", ""
            ),
            system_prompt=prompt_context.get("system_prompt", ""),
        )

        self.runs_registry.add_run(run)
        self._sync_run_to_state(run)

        await self.server.network_completion  # show spinner

        probe_choices = prompt_context["probe"].choices or []
        updated_run = await self.runs_registry.execute_decision(run, probe_choices)

        self._sync_run_to_state(updated_run)

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.create_and_execute_run())

    def export_runs_to_json(self) -> str:
        exported_runs = []

        for run_dict in self.state.runs.values():
            if "decision" not in run_dict:
                continue

            prompt = run_dict["prompt"]
            decision = run_dict["decision"]

            choice_idx = 0
            if "unstructured" in decision:
                decision_text = decision["unstructured"]
                if decision_text and len(decision_text) > 0:
                    first_char = decision_text[0]
                    if first_char.isalpha() and first_char.upper() >= "A":
                        choice_idx = ord(first_char.upper()) - ord("A")

            input_data = {
                "scenario_id": prompt["probe"]["scenario_id"],
                "full_state": prompt["probe"]["full_state"],
                "state": prompt["probe"]["full_state"]["unstructured"],
                "choices": prompt["probe"]["choices"],
            }

            output_data = {"choice": choice_idx}

            if choice_idx < len(prompt["probe"]["choices"]):
                selected_choice = prompt["probe"]["choices"][choice_idx]
                output_data["action"] = {
                    "unstructured": selected_choice["unstructured"],
                    "justification": decision.get("justification", ""),
                }

            exported_run = {"input": input_data, "output": output_data}
            exported_runs.append(exported_run)

        return json.dumps(exported_runs, indent=2)

    @change("runs")
    def update_runs_json(self, **_):
        json_data = self.export_runs_to_json()
        self.state.runs_json = json_data
        self.state.flush()
