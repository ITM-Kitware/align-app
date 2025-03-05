from trame.decorators import TrameApp, change, controller
from ..adm.adm_core import (
    get_scenarios,
    get_prompt,
    LLM_BACKBONES,
    deciders,
    attributes,
)


@TrameApp()
class PromptController:
    def __init__(self, server):
        self.server = server

        self._alignment_id = 0
        self.reset()

    def update_scenarios(self):
        scenarios = get_scenarios()
        items = [
            {"value": id, "title": f"{id} - {s['state']}"}
            for id, s in scenarios.items()
        ]
        self.server.state.scenarios = items
        self.server.state.prompt_scenario_id = self.server.state.scenarios[0]["value"]

    def reset(self):
        self.update_scenarios()
        self.server.state.llm_backbones = LLM_BACKBONES
        self.server.state.llm_backbone = LLM_BACKBONES[0]
        self.server.state.decision_makers = deciders
        self.server.state.decision_maker = deciders[0]
        self.server.state.alignment_attributes = []

    @change("prompt_scenario_id")
    def on_scenario_change(self, prompt_scenario_id, **kwargs):
        s = get_scenarios()[prompt_scenario_id]
        self.server.state.prompt_scenario = s

    def get_prompt(self):
        return get_prompt(
            self.server.state.prompt_scenario_id,
            self.server.state.llm_backbone,
            self.server.state.decision_maker,
            self.server.state.alignment_attributes,
        )

    @controller.add("add_alignment_attribute")
    def add_alignment_attribute(self):
        self._alignment_id += 1
        type = self.server.state.possible_alignment_attributes[0]
        self.server.state.alignment_attributes = [
            *self.server.state.alignment_attributes,
            {"id": self._alignment_id, "type": type, "score": 0},
        ]

    @controller.add("update_type_alignment_attribute")
    def update_type_alignment_attribute(self, type, alignment_attribute_id):
        self._update_alignment_attribute({"type": type}, alignment_attribute_id)

    @controller.add("update_score_alignment_attribute")
    def update_score_alignment_attribute(self, score, alignment_attribute_id):
        self._update_alignment_attribute({"score": score}, alignment_attribute_id)

    def _update_alignment_attribute(self, patch, alignment_attribute_id):
        attributes = self.server.state.alignment_attributes
        target = next(
            (a for a in attributes if a["id"] == alignment_attribute_id), None
        )
        for key, value in patch.items():
            target[key] = value
        self.server.state.alignment_attributes = [*attributes]
        # We mutate elements so need this to update GUI
        self.server.state.dirty("alignment_attributes")

    @controller.add("delete_alignment_attribute")
    def delete_alignment_attribute(self, alignment_attribute_id):
        self.server.state.alignment_attributes = [
            a
            for a in self.server.state.alignment_attributes
            if a["id"] != alignment_attribute_id
        ]

    @change("alignment_attributes")
    def compute_possible_alignment_attributes(self, **_):
        used_types = [a["type"] for a in self.server.state.alignment_attributes]
        self.server.state.possible_alignment_attributes = [
            a for a in attributes if a not in used_types
        ]
