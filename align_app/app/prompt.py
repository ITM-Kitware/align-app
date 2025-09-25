from typing import List, Dict
from trame.decorators import TrameApp, change, controller
from ..adm.adm_core import (
    scenarios,
    get_attributes,
    get_alignment_descriptions_map,
)
from ..adm.decider_registry import create_decider_registry
from .ui import readable_scenario, prep_for_state
from ..utils.utils import get_id, readable, debounce
from .prompt_logic import (
    build_prompt_context,
    compute_possible_attributes,
    filter_valid_attributes,
    select_initial_decider,
    get_max_alignment_attributes,
    get_llm_backbones_from_config,
)

# Maximum number of choices allowed (limited by ADM code)
MAX_CHOICES = 2

COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME = 0.1

# Messages
DECISION_ATTRIBUTE_ERROR = (
    "Decider requires alignment attributes. Please add at least one."
)
DECIDER_NOT_SUPPORTED_FOR_DATASET = (
    "The selected decider is not supported for the current dataset."
)


# Data transformation functions
def readable_items(items: List) -> List[Dict]:
    """Transform items to readable format for UI."""

    def _item(item):
        if isinstance(item, dict):
            value = item["value"]
            return {
                "value": value,
                "title": readable(value),
                "possible_scores": item.get("possible_scores", []),
                "description": item.get("description", ""),
            }
        return {"value": item, "title": readable(item)}

    return [_item(item) for item in items]


def map_ui_to_align_attributes(attributes: List[Dict]) -> List[Dict]:
    """Map UI attribute representation to backend format."""
    return [{"type": a["value"], "score": a["score"]} for a in attributes]


def build_scenario_items(scenarios: Dict) -> List[Dict]:
    """Transform scenarios dict to UI items list."""
    return [
        {"value": id, "title": f"{id} - {s['state']}"} for id, s in scenarios.items()
    ]


# State manipulation helpers
def update_alignment_attribute_in_list(
    attributes: List[Dict], attribute_id: str, patch: Dict
) -> List[Dict]:
    """Update an attribute in the list with the given patch."""
    updated = []
    for attr in attributes:
        if attr["id"] == attribute_id:
            updated_attr = {**attr, **patch}
            updated.append(updated_attr)
        else:
            updated.append(attr)
    return updated


def remove_attribute_from_list(attributes: List[Dict], attribute_id: str) -> List[Dict]:
    """Remove an attribute from the list."""
    return [a for a in attributes if a["id"] != attribute_id]


def add_attribute_to_list(attributes: List[Dict], new_item: Dict) -> List[Dict]:
    """Add a new attribute to the list."""
    return [*attributes, {**new_item, "id": get_id(), "score": 0}]


def update_decider_messages(
    current_messages: List[str], add: bool, message: str
) -> List[str]:
    """Update decider validation messages."""
    messages = current_messages or []
    if add:
        if message not in messages:
            return [*messages, message]
        return messages
    return [m for m in messages if m != message]


def update_edited_choices(choices: List[str], index: int, value: str) -> List[str]:
    """Update choice at the given index."""
    updated = list(choices)
    if index < len(updated):
        updated[index] = value
    return updated


@TrameApp()
class PromptController:
    def __init__(self, server, config_paths=None):
        self.server = server
        self.server.state.max_choices = MAX_CHOICES
        self.decider_api = create_decider_registry(config_paths or [])
        self.server.state.change(
            "alignment_attributes", "decider", "prompt_scenario_id"
        )(
            debounce(COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME, self.server.state)(
                self.compute_system_prompt
            )
        )
        self.server.state.change(
            "alignment_attributes", "decider", "prompt_scenario_id"
        )(
            debounce(COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME, self.server.state)(
                self.compute_alignment_descriptions
            )
        )
        self.init_state()

    def update_scenarios(self):
        """Update the scenarios list in state."""
        items = build_scenario_items(scenarios)
        self.server.state.scenarios = items
        if items:
            self.server.state.prompt_scenario_id = items[0]["value"]

    def _initialize_edited_fields(self, scenario):
        """Initialize edited fields from scenario."""
        self.server.state.edited_scenario_text = scenario.get("display_state", "")
        self.server.state.edited_choices = [
            choice.get("unstructured", "") for choice in scenario.get("choices", [])
        ]

    def update_deciders(self):
        """Update the deciders list - useful after registering experiment configs."""
        all_deciders = self.decider_api.get_all_deciders()
        self.server.state.deciders = readable_items(list(all_deciders.keys()))

        selected = select_initial_decider(
            self.server.state.deciders, self.server.state.decider
        )
        if selected:
            self.server.state.decider = selected

    def init_state(self):
        self.server.state.decider = ""
        self.server.state.decider_messages = []
        self.server.state.alignment_attributes = []
        self.server.state.system_prompt = ""
        self.server.state.send_button_disabled = False
        self.server.state.edited_scenario_text = ""
        self.server.state.edited_choices = []
        self.server.state.prompt_scenario = {}
        self.server.state.attribute_targets = []
        self.server.state.possible_alignment_attributes = []
        self.server.state.max_alignment_attributes = 0
        self.server.state.scenarios = []
        self.server.state.deciders = []
        self.server.state.llm_backbones = []
        self.server.state.prompt_scenario_id = ""
        self.server.state.llm_backbone = ""

        self.update_scenarios()
        self.update_deciders()
        self.update_decider_params()

        if self.server.state.llm_backbones:
            self.server.state.llm_backbone = self.server.state.llm_backbones[0]
        if self.server.state.scenarios:
            first_scenario_id = self.server.state.scenarios[0]["value"]
            first_scenario = scenarios[first_scenario_id]
            self._initialize_edited_fields(first_scenario)

    def update_decider_message(self, add, message):
        """Update decider validation messages."""
        self.server.state.decider_messages = update_decider_messages(
            self.server.state.decider_messages, add, message
        )

    @change("prompt_scenario_id")
    def on_scenario_change(self, prompt_scenario_id, **_):
        s = scenarios[prompt_scenario_id]
        self.server.state.prompt_scenario = readable_scenario(s)
        self._initialize_edited_fields(s)

    def get_prompt(self):
        """Build complete prompt context with edited values."""
        return build_prompt_context(
            scenario_id=self.server.state.prompt_scenario_id,
            llm_backbone=self.server.state.llm_backbone,
            decider=self.server.state.decider,
            attributes=self.server.state.alignment_attributes,
            system_prompt=self.server.state.system_prompt,
            edited_text=self.server.state.edited_scenario_text,
            edited_choices=self.server.state.edited_choices,
            decider_registry=self.decider_api,
        )

    @controller.add("add_choice")
    def add_choice(self):
        # Note: This method is currently disabled in UI when MAX_CHOICES=2
        # because the alignment system only supports exactly 2 choices.
        # Kept for future compatibility if MAX_CHOICES increases.
        if len(self.server.state.edited_choices) < MAX_CHOICES:
            self.server.state.edited_choices = [
                *self.server.state.edited_choices,
                "",
            ]

    @controller.add("update_choice")
    def update_choice(self, index, value):
        """Update choice text at given index."""
        self.server.state.edited_choices = update_edited_choices(
            self.server.state.edited_choices, index, value
        )

    @controller.add("delete_choice")
    def delete_choice(self, index):
        # Note: This method is currently disabled in UI when MAX_CHOICES=2
        # because the alignment system requires exactly 2 choices.
        # Kept for future compatibility if MAX_CHOICES increases.
        if len(self.server.state.edited_choices) > MAX_CHOICES:
            self.server.state.edited_choices = [
                choice
                for i, choice in enumerate(self.server.state.edited_choices)
                if i != index
            ]

    @controller.add("add_alignment_attribute")
    def add_alignment_attribute(self):
        """Add a new alignment attribute."""
        if self.server.state.possible_alignment_attributes:
            item = self.server.state.possible_alignment_attributes[0]
            self.server.state.alignment_attributes = add_attribute_to_list(
                self.server.state.alignment_attributes, item
            )

    @controller.add("update_value_alignment_attribute")
    def update_value_alignment_attribute(self, alignment_attribute_id, value):
        """Update the value of an alignment attribute."""
        prompt = self.get_prompt()
        descriptions = get_alignment_descriptions_map(prompt)
        description = descriptions.get(value, {}).get(
            "description", f"No description available for {value}"
        )

        patch = {"value": value, "title": readable(value), "description": description}
        self.server.state.alignment_attributes = update_alignment_attribute_in_list(
            self.server.state.alignment_attributes, alignment_attribute_id, patch
        )
        self.server.state.dirty("alignment_attributes")

    @controller.add("update_score_alignment_attribute")
    def update_score_alignment_attribute(self, alignment_attribute_id, score):
        """Update the score of an alignment attribute."""
        self.server.state.alignment_attributes = update_alignment_attribute_in_list(
            self.server.state.alignment_attributes,
            alignment_attribute_id,
            {"score": score},
        )
        self.server.state.dirty("alignment_attributes")

    @controller.add("delete_alignment_attribute")
    def delete_alignment_attribute(self, alignment_attribute_id):
        """Delete an alignment attribute."""
        self.server.state.alignment_attributes = remove_attribute_from_list(
            self.server.state.alignment_attributes, alignment_attribute_id
        )

    @change("decider", "prompt_scenario_id")
    def update_max_alignment_attributes(self, **_):
        """Update max alignment attributes from decider config."""
        decider_configs = self.decider_api.get_dataset_decider_configs(
            self.server.state.prompt_scenario_id,
            self.server.state.decider,
        )
        self.server.state.max_alignment_attributes = get_max_alignment_attributes(
            decider_configs
        )

    @change("max_alignment_attributes")
    def clamp_attributes(self, max_alignment_attributes, **_):
        """Clamp attributes to max allowed."""
        if len(self.server.state.alignment_attributes) > max_alignment_attributes:
            self.server.state.alignment_attributes = (
                self.server.state.alignment_attributes[:max_alignment_attributes]
            )

    @change("decider", "alignment_attributes", "prompt_scenario_id")
    def validate_alignment_attribute(self, **_):
        """Validate alignment attributes are present when required."""
        decider_configs = self.decider_api.get_dataset_decider_configs(
            self.server.state.prompt_scenario_id,
            self.server.state.decider,
        )

        needs_attributes = (
            decider_configs
            and "baseline" not in decider_configs.get("postures", {})
            and len(self.server.state.alignment_attributes) == 0
        )

        self.update_decider_message(needs_attributes, DECISION_ATTRIBUTE_ERROR)

    @change("decider", "prompt_scenario_id")
    def validate_decider_exists_for_dataset(self, **_):
        """Validate decider is supported for the dataset."""
        decider_configs = self.decider_api.get_dataset_decider_configs(
            self.server.state.prompt_scenario_id,
            self.server.state.decider,
        )

        self.update_decider_message(
            not decider_configs, DECIDER_NOT_SUPPORTED_FOR_DATASET
        )

    @change("decider_messages")
    def gate_send_button(self, **_):
        """Disable send button if there are validation messages."""
        self.server.state.send_button_disabled = bool(
            self.server.state.decider_messages
        )

    @change("prompt_scenario_id", "decider")
    def update_decider_params(self, **_):
        decider_configs = self.decider_api.get_dataset_decider_configs(
            self.server.state.prompt_scenario_id,
            self.server.state.decider,
        )

        self.server.state.llm_backbones = get_llm_backbones_from_config(decider_configs)

        if self.server.state.llm_backbone not in self.server.state.llm_backbones:
            self.server.state.llm_backbone = (
                self.server.state.llm_backbones[0]
                if self.server.state.llm_backbones
                else "N/A"
            )

    @change("prompt_scenario_id", "decider")
    def limit_to_dataset_alignment_attributes(self, **_):
        valid_attributes = get_attributes(
            self.server.state.prompt_scenario_id, self.server.state.decider
        )
        self.server.state.alignment_attributes = filter_valid_attributes(
            self.server.state.alignment_attributes, valid_attributes
        )

    @change("alignment_attributes", "prompt_scenario_id", "decider")
    def compute_possible_alignment_attributes(self, **_):
        attrs = get_attributes(
            self.server.state.prompt_scenario_id,
            self.server.state.decider,
        )

        # Get alignment descriptions
        prompt = self.get_prompt()
        descriptions = get_alignment_descriptions_map(prompt)

        used = {a["value"] for a in self.server.state.alignment_attributes}
        possible = compute_possible_attributes(attrs, used, descriptions)
        self.server.state.possible_alignment_attributes = readable_items(possible)

    def compute_system_prompt(self, **_):
        mapped_attributes = map_ui_to_align_attributes(
            self.server.state.alignment_attributes
        )
        sys_prompt = self.decider_api.get_system_prompt(
            self.server.state.decider,
            mapped_attributes,
            self.server.state.prompt_scenario_id,
        )
        self.server.state.system_prompt = sys_prompt

    def compute_alignment_descriptions(self, **_):
        readable_prompt = prep_for_state(self.get_prompt())
        self.server.state.attribute_targets = readable_prompt.get(
            "alignment_target", {}
        ).get("kdma_values", [])
