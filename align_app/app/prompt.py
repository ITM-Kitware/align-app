from typing import List, Dict
from trame.decorators import TrameApp, change, controller
from rapidfuzz import fuzz, process, utils
from ..adm.decider_registry import create_decider_registry
from ..adm.probe_registry import create_probe_registry
from ..adm.probe import Probe
from .ui import readable_probe, prep_for_state
from ..utils.utils import get_id, readable, debounce
from .prompt_logic import (
    build_prompt_context,
    compute_possible_attributes,
    filter_valid_attributes,
    select_initial_decider,
    get_max_alignment_attributes,
    get_llm_backbones_from_config,
    find_probe_by_base_and_scene,
    get_alignment_descriptions_map,
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


# state transformation functions
def readable_items(items: List) -> List[Dict]:
    return [
        {
            "value": item["value"],
            "title": readable(item["value"]),
            "possible_scores": item.get("possible_scores", []),
            "description": item.get("description", ""),
        }
        if isinstance(item, dict)
        else {"value": item, "title": readable(item)}
        for item in items
    ]


def extract_base_scenarios(probes: Dict[str, Probe]) -> List[Dict]:
    """Extract unique base scenario IDs from all probes."""
    unique_bases = sorted(set(probe.scenario_id for probe in probes.values()))
    return [{"value": id, "title": id} for id in unique_bases]


def get_scenes_for_base_scenario(
    probes: Dict[str, Probe], scenario_id: str
) -> List[Dict]:
    scene_map = {
        probe.scene_id: (probe.display_state or "").split("\n")[0]
        for probe in probes.values()
        if probe.scenario_id == scenario_id
    }

    return [
        {
            "value": scene_id,
            "title": f"{scene_id} - {text[:50]}{'...' if len(text) > 50 else ''}",
        }
        for scene_id, text in scene_map.items()
    ]


def map_ui_to_align_attributes(attributes: List[Dict]) -> List[Dict]:
    """Map UI attribute representation to backend format."""
    return [{"type": a["value"], "score": a["score"]} for a in attributes]


def build_probe_items(probes: Dict) -> List[Dict]:
    """Transform probes dict to UI items list."""
    return [{"value": id, "title": f"{id} - {s.state}"} for id, s in probes.items()]


# state manipulation helpers
def update_alignment_attribute_in_list(
    attributes: List[Dict], attribute_id: str, patch: Dict
) -> List[Dict]:
    return [
        {**attr, **patch} if attr["id"] == attribute_id else attr for attr in attributes
    ]


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
    def __init__(self, server, config_paths=None, scenarios_paths=None):
        self.server = server
        self.server.state.max_choices = MAX_CHOICES
        self.probe_registry = create_probe_registry(scenarios_paths)
        self.decider_api = create_decider_registry(
            config_paths or [], self.probe_registry
        )
        self.server.state.change("decider", "prompt_probe_id")(
            debounce(COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME, self.server.state)(
                self.compute_system_prompt
            )
        )
        self.server.state.change("decider", "prompt_probe_id")(
            debounce(COMPUTE_SYSTEM_PROMPT_DEBOUNCE_TIME, self.server.state)(
                self.compute_alignment_descriptions
            )
        )
        self.search_controller = SearchController(server, self.probe_registry)
        self.init_state()

    def update_scenarios(self):
        """Update the scenarios list in state."""
        probes = self.probe_registry.get_probes()
        items = build_probe_items(probes)
        self.server.state.scenarios = items

        base_scenarios = extract_base_scenarios(probes)
        self.server.state.base_scenarios = base_scenarios

        if base_scenarios:
            self.server.state.scenario_id = base_scenarios[0]["value"]
            scene_items = get_scenes_for_base_scenario(
                probes, self.server.state.scenario_id
            )
            self.server.state.scene_items = scene_items

            if scene_items:
                self.server.state.scene_id = scene_items[0]["value"]
                self.server.state.prompt_probe_id = find_probe_by_base_and_scene(
                    probes,
                    self.server.state.scenario_id,
                    self.server.state.scene_id,
                )

    def _initialize_edited_fields(self, probe: Probe):
        """Initialize edited fields from probe."""
        self.server.state.edited_probe_text = probe.display_state or ""
        self.server.state.edited_choices = [
            choice.get("unstructured", "") for choice in (probe.choices or [])
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
        self.server.state.edited_probe_text = ""
        self.server.state.edited_choices = []
        self.server.state.prompt_probe = {}
        self.server.state.attribute_targets = []
        self.server.state.possible_alignment_attributes = []
        self.server.state.max_alignment_attributes = 0
        self.server.state.scenarios = []
        self.server.state.deciders = []
        self.server.state.llm_backbones = []
        self.server.state.prompt_probe_id = ""
        self.server.state.llm_backbone = ""
        self.server.state.base_scenarios = []
        self.server.state.scenario_id = ""
        self.server.state.scene_items = []
        self.server.state.scene_id = ""

        self.update_scenarios()
        self.update_deciders()
        self.update_decider_params()

        if self.server.state.llm_backbones:
            self.server.state.llm_backbone = self.server.state.llm_backbones[0]
        if self.server.state.prompt_probe_id:
            first_probe = self.probe_registry.get_probe(
                self.server.state.prompt_probe_id
            )
            self._initialize_edited_fields(first_probe)

        # Initialize computed values
        self.compute_possible_alignment_attributes()
        self.compute_system_prompt()
        self.compute_alignment_descriptions()

    def update_decider_message(self, add, message):
        """Update decider validation messages."""
        self.server.state.decider_messages = update_decider_messages(
            self.server.state.decider_messages, add, message
        )

    @change("scenario_id")
    def on_base_scenario_change(self, scenario_id, **_):
        """Handle base scenario selection change."""
        probes = self.probe_registry.get_probes()
        scene_items = get_scenes_for_base_scenario(probes, scenario_id)
        self.server.state.scene_items = scene_items
        self.server.state.scene_id = scene_items[0]["value"]
        self.server.state.prompt_probe_id = find_probe_by_base_and_scene(
            probes, scenario_id, self.server.state.scene_id
        )

    @change("scene_id")
    def on_scene_change(self, scene_id, **_):
        """Handle scene selection change."""
        probes = self.probe_registry.get_probes()
        self.server.state.prompt_probe_id = find_probe_by_base_and_scene(
            probes, self.server.state.scenario_id, scene_id
        )

    @change("prompt_probe_id")
    def on_scenario_change(self, prompt_probe_id, **_):
        probe = self.probe_registry.get_probe(prompt_probe_id)
        self.server.state.prompt_probe = readable_probe(probe)
        self._initialize_edited_fields(probe)

    def get_prompt(self):
        """Build complete prompt context with edited values."""
        return build_prompt_context(
            probe_id=self.server.state.prompt_probe_id,
            llm_backbone=self.server.state.llm_backbone,
            decider=self.server.state.decider,
            attributes=self.server.state.alignment_attributes,
            system_prompt=self.server.state.system_prompt,
            edited_text=self.server.state.edited_probe_text,
            edited_choices=self.server.state.edited_choices,
            decider_registry=self.decider_api,
            probe_registry=self.probe_registry,
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

    def _update_after_attribute_change(self):
        """Helper to update state after attribute changes (not score changes)."""
        self.compute_possible_alignment_attributes()
        self.validate_alignment_attribute()
        self.compute_system_prompt()
        self.compute_alignment_descriptions()

    @controller.add("add_alignment_attribute")
    def add_alignment_attribute(self):
        """Add a new alignment attribute."""
        if self.server.state.possible_alignment_attributes:
            item = self.server.state.possible_alignment_attributes[0]
            self.server.state.alignment_attributes = add_attribute_to_list(
                self.server.state.alignment_attributes, item
            )
            self._update_after_attribute_change()

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
        self._update_after_attribute_change()

    @controller.add("update_score_alignment_attribute")
    def update_score_alignment_attribute(self, alignment_attribute_id, score):
        """Update the score of an alignment attribute."""
        self.server.state.alignment_attributes = update_alignment_attribute_in_list(
            self.server.state.alignment_attributes,
            alignment_attribute_id,
            {"score": score},
        )

    @controller.add("delete_alignment_attribute")
    def delete_alignment_attribute(self, alignment_attribute_id):
        """Delete an alignment attribute."""
        self.server.state.alignment_attributes = remove_attribute_from_list(
            self.server.state.alignment_attributes, alignment_attribute_id
        )
        self._update_after_attribute_change()

    @change("decider", "prompt_probe_id")
    def update_max_alignment_attributes(self, **_):
        """Update max alignment attributes from decider config."""
        metadata = self.decider_api.get_decider_options(
            self.server.state.prompt_probe_id,
            self.server.state.decider,
        )
        self.server.state.max_alignment_attributes = get_max_alignment_attributes(
            metadata
        )

    @change("max_alignment_attributes")
    def clamp_attributes(self, max_alignment_attributes, **_):
        """Clamp attributes to max allowed."""
        if len(self.server.state.alignment_attributes) > max_alignment_attributes:
            self.server.state.alignment_attributes = (
                self.server.state.alignment_attributes[:max_alignment_attributes]
            )
            self._update_after_attribute_change()

    @change("decider", "prompt_probe_id")
    def validate_alignment_attribute(self, **_):
        """Validate alignment attributes are present when required."""
        metadata = self.decider_api.get_decider_options(
            self.server.state.prompt_probe_id,
            self.server.state.decider,
        )

        # Baseline and random deciders don't need alignment attributes
        decider_needs_alignment = self.server.state.decider not in [
            "pipeline_baseline",
            "pipeline_random",
        ]
        needs_attributes = (
            metadata
            and decider_needs_alignment
            and len(self.server.state.alignment_attributes) == 0
        )

        self.update_decider_message(needs_attributes, DECISION_ATTRIBUTE_ERROR)

    @change("decider", "prompt_probe_id")
    def validate_decider_exists_for_dataset(self, **_):
        """Validate decider is supported for the dataset."""
        metadata = self.decider_api.get_decider_options(
            self.server.state.prompt_probe_id,
            self.server.state.decider,
        )

        self.update_decider_message(not metadata, DECIDER_NOT_SUPPORTED_FOR_DATASET)

    @change("decider_messages")
    def gate_send_button(self, **_):
        """Disable send button if there are validation messages."""
        self.server.state.send_button_disabled = bool(
            self.server.state.decider_messages
        )

    @change("prompt_probe_id", "decider")
    def update_decider_params(self, **_):
        metadata = self.decider_api.get_decider_options(
            self.server.state.prompt_probe_id,
            self.server.state.decider,
        )

        self.server.state.llm_backbones = get_llm_backbones_from_config(metadata)

        if self.server.state.llm_backbone not in self.server.state.llm_backbones:
            self.server.state.llm_backbone = (
                self.server.state.llm_backbones[0]
                if self.server.state.llm_backbones
                else "N/A"
            )

    @change("prompt_probe_id", "decider")
    def limit_to_dataset_alignment_attributes(self, **_):
        valid_attributes = self.probe_registry.get_attributes(
            self.server.state.prompt_probe_id
        )
        self.server.state.alignment_attributes = filter_valid_attributes(
            self.server.state.alignment_attributes, valid_attributes
        )

    @change("prompt_probe_id", "decider")
    def compute_possible_alignment_attributes(self, **_):
        attrs = self.probe_registry.get_attributes(self.server.state.prompt_probe_id)

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
            self.server.state.prompt_probe_id,
        )
        self.server.state.system_prompt = sys_prompt

    def compute_alignment_descriptions(self, **_):
        readable_prompt = prep_for_state(self.get_prompt())
        self.server.state.attribute_targets = readable_prompt.get(
            "alignment_target", {}
        ).get("kdma_values", [])


@TrameApp()
class SearchController:
    """Controller for search functionality with dropdown menu."""

    def __init__(self, server, probe_registry):
        self.server = server
        self.probe_registry = probe_registry
        self.server.state.search_query = ""
        self.server.state.search_results = []
        self.server.state.search_menu_open = False
        self.server.state.change("search_query")(
            debounce(0.2, self.server.state)(self.update_search_results)
        )

    def _create_search_result(self, probe_id, probe: Probe):
        display_state = probe.display_state or ""
        display_text = display_state.split("\n")[0] if display_state else ""
        display_text = f"{display_text[:60]}{'...' if len(display_text) > 60 else ''}"
        return {
            "id": probe_id,
            "scenario_id": probe.scenario_id,
            "scene_id": probe.scene_id,
            "display_text": display_text,
        }

    def update_search_results(self, search_query, **_):
        if not search_query:
            self.server.state.search_results = []
            self.server.state.search_menu_open = False
            return

        probes = self.probe_registry.get_probes()

        searchable_items = {
            probe_id: (
                f"{probe.scenario_id} "
                f"{probe.scene_id} "
                f"{probe.display_state or ''} "
                f"{' '.join(choice.get('unstructured', '') for choice in (probe.choices or []))}"
            )
            for probe_id, probe in probes.items()
        }

        matches = process.extract(
            search_query,
            searchable_items,
            scorer=fuzz.token_set_ratio,
            processor=utils.default_process,
            limit=200,
            score_cutoff=80,
        )

        results = [
            self._create_search_result(probe_id, probes[probe_id])
            for _, _, probe_id in matches
        ]

        self.server.state.search_results = results or [
            {
                "id": None,
                "scenario_id": "",
                "scene_id": "",
                "display_text": "No results found",
            }
        ]
        self.server.state.search_menu_open = True

    @controller.add("select_search_result")
    def select_search_result(self, index):
        if 0 <= index < len(self.server.state.search_results):
            result = self.server.state.search_results[index]
            if result.get("id") is not None:
                self.server.state.update(
                    {
                        "scenario_id": result.get("scenario_id"),
                        "scene_id": result.get("scene_id"),
                    }
                )
