from typing import Dict
from trame.app import asynchronous
from trame.decorators import TrameApp, controller, change
from ..adm.decider import get_decision, DeciderParams
from ..utils.utils import get_id
from .run_models import Run, RunDecision
import json


@TrameApp()
class RunsController:
    def __init__(self, server, prompt_controller):
        self.server = server
        self.prompt_controller = prompt_controller
        self.decision_cache: Dict[str, RunDecision] = {}
        self.init_state()

    @property
    def state(self):
        return self.server.state

    def init_state(self):
        self.state.runs = {}
        self.state.runs_to_compare = []
        self.state.runs_json = "[]"

    @controller.set("reset_runs_state")
    def reset_state(self):
        self.init_state()
        self.decision_cache = {}

    @controller.set("update_run_to_compare")
    def update_run_to_compare(self, run_index, run_column_index):
        runs = list(self.state.runs.keys())
        self.state.runs_to_compare[run_column_index] = runs[run_index - 1]
        self.state.dirty("runs_to_compare")

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

        with self.state:
            self.state.runs = {
                **self.state.runs,
                run_id: run.to_state_dict(),
            }
            self.state.runs_to_compare = self.state.runs_to_compare + [run_id]

        cache_key = run.compute_cache_key()

        if cache_key in self.decision_cache:
            cached_decision = self.decision_cache[cache_key]
            run.decision = cached_decision
            with self.state:
                self.state.runs = {
                    id: ({**item, **run.to_state_dict()} if id == run_id else item)
                    for id, item in self.state.runs.items()
                }
            return

        await self.server.network_completion

        adm_result = await get_decision(run.decider_params)

        probe_choices = prompt_context["probe"].choices or []
        decision = RunDecision.from_adm_result(adm_result, probe_choices)

        self.decision_cache[cache_key] = decision
        run.decision = decision

        with self.state:
            self.state.runs = {
                id: ({**item, **run.to_state_dict()} if id == run_id else item)
                for id, item in self.state.runs.items()
            }

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.create_and_execute_run())

    def export_runs_to_json(self):
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
