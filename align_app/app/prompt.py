from trame.decorators import TrameApp, change, controller
from ..adm.adm_core import (
    scenarios,
    get_prompt,
    LLM_BACKBONES,
    deciders,
    get_attributes,
    get_system_prompt,
)
from .ui import readable_scenario
from ..utils.utils import get_id, readable, debounce

COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME = 0.1


def readable_items(items):
    return [
        {
            "value": item,
            "title": readable(item),
        }
        for item in items
    ]


def map_attributes(attributes):
    """Map UI attribute representation to backend format."""
    return [{"type": a["value"], "score": a["score"]} for a in attributes]


@TrameApp()
class PromptController:
    def __init__(self, server):
        self.server = server
        self.server.state.change(
            "alignment_attributes", "decision_maker", "prompt_scenario_id"
        )(
            debounce(COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME, self.server.state)(
                self.compute_system_prompt
            )
        )
        self.reset()

    def update_scenarios(self):
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
        self.server.state.decision_makers = readable_items(deciders)
        self.server.state.decision_maker = self.server.state.decision_makers[0]["value"]
        self.server.state.alignment_attributes = []

    @change("prompt_scenario_id")
    def on_scenario_change(self, prompt_scenario_id, **kwargs):
        s = scenarios[prompt_scenario_id]
        self.server.state.prompt_scenario = readable_scenario(s)

    def get_prompt(self):
        mapped_attributes = map_attributes(self.server.state.alignment_attributes)
        prompt = {
            **get_prompt(
                self.server.state.prompt_scenario_id,
                self.server.state.llm_backbone,
                self.server.state.decision_maker,
                mapped_attributes,
            ),
            "system_prompt": self.server.state.system_prompt,
        }
        return prompt

    @controller.add("add_alignment_attribute")
    def add_alignment_attribute(self):
        item = self.server.state.possible_alignment_attributes[0]
        self.server.state.alignment_attributes = [
            *self.server.state.alignment_attributes,
            {**item, "id": get_id(), "score": 0},
        ]

    @controller.add("update_value_alignment_attribute")
    def update_value_alignment_attribute(self, value, alignment_attribute_id):
        self._update_alignment_attribute(
            {"value": value, "title": readable(value)}, alignment_attribute_id
        )

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
        self.server.state.dirty("alignment_attributes")

    @controller.add("delete_alignment_attribute")
    def delete_alignment_attribute(self, alignment_attribute_id):
        self.server.state.alignment_attributes = [
            a
            for a in self.server.state.alignment_attributes
            if a["id"] != alignment_attribute_id
        ]

    @change("prompt_scenario_id")
    def limit_to_dataset_alignment_attributes(self, **_):
        scenario_id = self.server.state.prompt_scenario_id
        valid_attributes = get_attributes(scenario_id)
        # Remove attributes not in the current dataset
        self.server.state.alignment_attributes = [
            attr
            for attr in self.server.state.alignment_attributes
            if attr["value"] in valid_attributes
        ]

    @change("alignment_attributes", "prompt_scenario_id")
    def compute_possible_alignment_attributes(self, **_):
        attributes = get_attributes(self.server.state.prompt_scenario_id)
        used_values = [a["value"] for a in self.server.state.alignment_attributes]
        available = [attr for attr in attributes if attr not in used_values]
        self.server.state.possible_alignment_attributes = readable_items(available)

    def compute_system_prompt(self, **_):
        decider = self.server.state.decision_maker
        mapped_attributes = map_attributes(self.server.state.alignment_attributes)
        scenario_id = self.server.state.prompt_scenario_id
        sys_prompt = get_system_prompt(decider, mapped_attributes, scenario_id)
        self.server.state.system_prompt = sys_prompt
