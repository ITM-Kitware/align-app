from trame.decorators import TrameApp, change, controller
from ..adm.adm_core import (
    scenarios,
    get_prompt,
    decider_names,
    get_attributes,
    get_system_prompt,
    get_dataset_decider_configs,
)
from .ui import readable_scenario
from ..utils.utils import get_id, readable, debounce

COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME = 0.1

# Add constants for error messages
DECISION_ATTRIBUTE_ERROR = (
    "Decision maker requires alignment attributes. Please add at least one."
)
DECISION_MAKER_NOT_SUPPORTED_FOR_DATASET = (
    "The selected decision maker is not supported for the current dataset."
)


def readable_items(items):
    def _item(item):
        if isinstance(item, dict):
            value = item["value"]
            return {
                "value": value,
                "title": readable(value),
                "possible_scores": item.get("possible_scores", []),
            }
        return {"value": item, "title": readable(item)}

    return [_item(item) for item in items]


def map_ui_to_align_attributes(attributes):
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
        self.server.state.decision_makers = readable_items(decider_names)
        self.server.state.decision_maker = self.server.state.decision_makers[0]["value"]
        self.server.state.alignment_attributes = []
        self.update_decision_maker_params()
        self.server.state.llm_backbone = self.server.state.llm_backbones[0]

    def update_decider_message(self, add, message):
        current = self.server.state.decider_messages or []
        if add:
            if message not in current:
                current.append(message)
        else:
            current = [m for m in current if m != message]
        self.server.state.decider_messages = current

    @change("prompt_scenario_id")
    def on_scenario_change(self, prompt_scenario_id, **kwargs):
        s = scenarios[prompt_scenario_id]
        self.server.state.prompt_scenario = readable_scenario(s)

    def get_prompt(self):
        mapped_attributes = map_ui_to_align_attributes(
            self.server.state.alignment_attributes
        )
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
    def update_value_alignment_attribute(self, alignment_attribute_id, value):
        self._update_alignment_attribute(
            alignment_attribute_id, {"value": value, "title": readable(value)}
        )

    @controller.add("update_score_alignment_attribute")
    def update_score_alignment_attribute(self, alignment_attribute_id, score):
        self._update_alignment_attribute(alignment_attribute_id, {"score": score})

    def _update_alignment_attribute(self, alignment_attribute_id, patch):
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

    @change("decision_maker", "prompt_scenario_id")
    def update_max_alignment_attributes(self, **_):
        decider_configs = get_dataset_decider_configs(
            self.server.state.prompt_scenario_id, self.server.state.decision_maker
        )
        if (
            decider_configs
            and "aligned" in decider_configs["postures"]
            and "max_alignment_attributes" in decider_configs["postures"]["aligned"]
        ):
            self.server.state.max_alignment_attributes = decider_configs["postures"][
                "aligned"
            ]["max_alignment_attributes"]
        else:
            self.server.state.max_alignment_attributes = 0

    @change("max_alignment_attributes")
    def clamp_attributes(self, max_alignment_attributes, **_):
        if len(self.server.state.alignment_attributes) > max_alignment_attributes:
            self.server.state.alignment_attributes = (
                self.server.state.alignment_attributes[:max_alignment_attributes]
            )

    @change("decision_maker", "alignment_attributes", "prompt_scenario_id")
    def ensure_alignment_attribute(self, **_):
        decider_configs = get_dataset_decider_configs(
            self.server.state.prompt_scenario_id, self.server.state.decision_maker
        )
        if (
            decider_configs
            and "baseline" not in decider_configs["postures"]
            and len(self.server.state.alignment_attributes) == 0
        ):
            self.update_decider_message(True, DECISION_ATTRIBUTE_ERROR)
        else:
            self.update_decider_message(False, DECISION_ATTRIBUTE_ERROR)

    @change("decision_maker", "prompt_scenario_id")
    def ensure_decision_maker_exists_for_dataset(self, **_):
        decider_configs = get_dataset_decider_configs(
            self.server.state.prompt_scenario_id, self.server.state.decision_maker
        )
        if not decider_configs:
            self.update_decider_message(True, DECISION_MAKER_NOT_SUPPORTED_FOR_DATASET)
        else:
            self.update_decider_message(False, DECISION_MAKER_NOT_SUPPORTED_FOR_DATASET)

    @change("decider_messages")
    def gate_send_button(self, **_):
        if self.server.state.decider_messages:
            self.server.state.send_button_disabled = True
        else:
            self.server.state.send_button_disabled = False

    @change("decision_maker")
    def update_decision_maker_params(self, **_):
        decider_configs = get_dataset_decider_configs(
            self.server.state.prompt_scenario_id, self.server.state.decision_maker
        )
        if decider_configs and "llm_backbones" in decider_configs:
            self.server.state.llm_backbones = decider_configs["llm_backbones"]
            if (
                self.server.state.llm_backbone
                and self.server.state.llm_backbone
                not in self.server.state.llm_backbones
            ):
                self.server.state.llm_backbone = self.server.state.llm_backbones[0]
        else:
            self.server.state.llm_backbones = []

    @change("prompt_scenario_id")
    def limit_to_dataset_alignment_attributes(self, **_):
        scenario_id = self.server.state.prompt_scenario_id
        valid_attributes = get_attributes(scenario_id)  # now returns a dict
        self.server.state.alignment_attributes = [
            attr
            for attr in self.server.state.alignment_attributes
            if attr["value"] in valid_attributes
        ]

    @change("alignment_attributes", "prompt_scenario_id")
    def compute_possible_alignment_attributes(self, **_):
        attrs = get_attributes(self.server.state.prompt_scenario_id)
        used = {a["value"] for a in self.server.state.alignment_attributes}
        possible = [
            {"value": key, **details}
            for key, details in attrs.items()
            if key not in used
        ]
        self.server.state.possible_alignment_attributes = readable_items(possible)

    def compute_system_prompt(self, **_):
        decider = self.server.state.decision_maker
        mapped_attributes = map_ui_to_align_attributes(
            self.server.state.alignment_attributes
        )
        scenario_id = self.server.state.prompt_scenario_id
        sys_prompt = get_system_prompt(decider, mapped_attributes, scenario_id)
        self.server.state.system_prompt = sys_prompt
