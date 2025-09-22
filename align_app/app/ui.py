from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html
from ..adm.adm_core import serialize_prompt, Prompt, get_alignment_descriptions_map
from ..utils.utils import noop, readable, readable_sentence, sentence_lines
from .unordered_object import UnorderedObject, ValueWithProgressBar


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


SENTENCE_KEYS = ["intent", "unstructured"]  # Keys to apply sentence function to

CHOICE_INFO_DESCRIPTIONS = {
    "Predicted KDMA values": "Key Decision-Making Attributes associated with each choice",
    "ICL example responses": (
        "Training examples with annotated KDMA scores used to guide model alignment through similarity matching"
    ),
    "True KDMA values": "Ground-truth KDMA scores from annotations in the training dataset",
    "True relevance": "Ground-truth relevance labels indicating how much a KDMA applies to the scenario",
}


def readable_scenario(scenario):
    characters = scenario["full_state"]["characters"]
    readable_characters = [
        {**c, **{key: sentence_lines(c[key]) for key in SENTENCE_KEYS if key in c}}
        for c in characters
    ]

    return {
        **scenario,
        "full_state": {**scenario["full_state"], "characters": readable_characters},
    }


def readable_attribute(kdma_value, descriptions):
    return {
        **kdma_value,
        "description": descriptions.get(kdma_value.get("kdma"), {}).get(
            "description",
            f"No description for {kdma_value.get('kdma')}",
        ),
        "kdma": readable(kdma_value.get("kdma")),
        "value": round(kdma_value.get("value"), 2),
    }


def prep_for_state(prompt: Prompt):
    descriptions = get_alignment_descriptions_map(prompt)
    p = serialize_prompt(prompt)
    p["alignment_target"] = {
        **p["alignment_target"],
        "kdma_values": [
            readable_attribute(a, descriptions)
            for a in p["alignment_target"]["kdma_values"]
        ],
    }
    p["decider_params"]["decider"] = readable(p["decider_params"]["decider"])
    p["scenario"] = readable_scenario(p["scenario"])
    return p


def make_keys_readable(obj, max_depth=2, current_depth=0):
    if current_depth >= max_depth or not isinstance(obj, dict):
        return obj

    result = {}
    for key, value in obj.items():
        readable_key = readable_sentence(key)
        if isinstance(value, dict):
            result[readable_key] = make_keys_readable(
                value, max_depth, current_depth + 1
            )
        elif isinstance(value, list):
            result[readable_key] = [
                make_keys_readable(item, max_depth, current_depth + 1)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[readable_key] = value
    return result


def prep_decision_for_state(decision_data):
    choice_info_keys = list(decision_data["choice_info"].keys())
    return {
        **decision_data,
        "choice_info_readable_keys": [readable(key) for key in choice_info_keys],
        "choice_info_readable": make_keys_readable(decision_data["choice_info"]),
    }


class TooltipIcon(vuetify3.VTooltip):
    """Question mark icon with tooltip for showing descriptions."""

    def __init__(self, description_expression, **kwargs):
        super().__init__(location="top", max_width="400px", **kwargs)
        with self:
            with vuetify3.Template(v_slot_activator=("{ props }",)):
                vuetify3.VIcon(
                    "mdi-help-circle-outline",
                    size="small",
                    v_bind="props",
                    classes="ml-2 text-grey",
                )
            html.Div(
                "{{ " + description_expression + " }}",
                style="white-space: normal; word-wrap: break-word;",
            )


class IclExampleListRenderer(html.Ul):
    def __init__(self, icl_data, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(
                v_for=(f"[kdma, examples] in Object.entries({icl_data})",),
                key=("kdma",),
            ):
                html.Span("{{kdma}}: ")
                with html.Ul(classes="ml-4"):
                    with html.Li(
                        v_for=("(example, index) in examples",),
                        key=("index",),
                    ):
                        html.Span("Example {{index + 1}}: ")
                        with html.Ul(classes="ml-4"):
                            with html.Li(
                                v_if=(
                                    "example.similarity_score !== null && example.similarity_score !== undefined",
                                )
                            ):
                                html.Span("Similarity: ")
                                ValueWithProgressBar("example.similarity_score")
                            with html.Li(
                                v_else_if=("example.similarity_score === null",)
                            ):
                                html.Span("Random")
                            with html.Li():
                                html.Span("Prompt: {{example.prompt}}")
                            html.Li(
                                "Reasoning: {{example.response.reasoning}}",
                                v_if=("example.response.reasoning",),
                            )
                            with html.Li(
                                v_for=(
                                    "([choice, responseData]) in Object.entries(example.response)"
                                    ".filter(([key]) => key !== 'reasoning')"
                                ),
                                key=("choice",),
                            ):
                                html.Span("{{choice}}: Score ")
                                ValueWithProgressBar(
                                    "responseData.score", decimals=0, max_value=100
                                )


class PanelSection(vuetify3.VExpansionPanel):
    def __init__(self, child, **kwargs):
        super().__init__(**kwargs)

        has_text = hasattr(child, "Text")
        with self:
            # set icons to blank to keep column alignment.  hide-actions changes width of available space.
            icon_kwargs = (
                {"expand_icon": "", "collapse_icon": ""} if not has_text else {}
            )
            with vuetify3.VExpansionPanelTitle(static=not has_text, **icon_kwargs):
                child.Title()
            if has_text:
                with vuetify3.VExpansionPanelText():
                    child.Text()


class RowWithLabel:
    def __init__(self, run_content=noop, label="", no_runs=None):
        title = bool(label)
        with vuetify3.VRow(style="max-width: 100%;"):
            with vuetify3.VCol(cols=2, classes="align-self-center"):
                html.Span(label, classes="text-h6")
            with vuetify3.VCol(
                v_for=("(id, column) in runs_to_compare",),
                key=("id",),
                v_if=("runs_to_compare.length > 0",),
                classes=(
                    "text-subtitle-1 text-no-wrap text-truncate align-self-center"
                    if title
                    else ""
                ),
            ):
                run_content()
            with vuetify3.VCol(
                v_else=True,
                classes=(
                    "text-subtitle-1 text-no-wrap text-truncate align-self-center"
                    if title
                    else ""
                ),
            ):
                if no_runs:
                    no_runs()


class LlmBackbone:
    class Title:
        def __init__(self):
            def run_content():
                html.Span("{{runs[id].prompt.decider_params.llm_backbone}}")

            RowWithLabel(run_content=run_content, label="LLM")


class Decider:
    class Title:
        def __init__(self):
            def run_content():
                html.Span("{{runs[id].prompt.decider_params.decider}}")

            RowWithLabel(run_content=run_content, label="Decider")


class Alignment:
    class Title:
        def __init__(self):
            def run_content():
                html.Span(
                    "{{ runs[id].prompt.alignment_target.kdma_values.length ? "
                    "runs[id].prompt.alignment_target.kdma_values.map(att => `${att.kdma} ${att.value}`).join(', ') : "
                    "'No Alignment' }}"
                )

            RowWithLabel(run_content=run_content, label="Alignment")

    class Text:
        def __init__(self):
            def run_content():
                with html.Div(
                    v_for=(
                        "kdma_value in runs[id].prompt.alignment_target.kdma_values",
                    ),
                    key=("kdma_value.kdma",),
                ):
                    with html.Div(
                        style="display: flex; align-items: center; gap: 8px;"
                    ):
                        html.Span("{{kdma_value.kdma}}")
                        ValueWithProgressBar("kdma_value.value")
                    html.Div("{{kdma_value.description}}", classes="ml-8")
                html.Div(
                    "",
                    v_if=("runs[id].prompt.alignment_target.kdma_values.length === 0",),
                )

            RowWithLabel(run_content=run_content)


class SystemPrompt:
    class Title:
        def __init__(self):
            def run_content():
                html.Span(
                    "{{runs[id].prompt.system_prompt}}",
                )

            RowWithLabel(run_content=run_content, label="System Prompt")

    class Text:
        def __init__(self):
            def run_content():
                html.Div("{{runs[id].prompt.system_prompt}}")

            RowWithLabel(run_content=run_content)


class ScenarioLayout:
    def __init__(self, scenario):
        html.Div("Situation", classes="text-h6")
        html.P(f"{{{{{scenario}.display_state}}}}", style="white-space: pre-wrap;")
        html.Div("Choices", classes="text-h6 pt-4")
        with html.Ol(classes="ml-8", type="A"):
            html.Li("{{choice.unstructured}}", v_for=(f"choice in {scenario}.choices"))


class EditableScenarioLayout(html.Div):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            html.Div("Situation", classes="text-h6")
            vuetify3.VTextarea(
                v_model=("edited_scenario_text",),
                auto_grow=True,
                rows=3,
                hide_details="auto",
            )
            html.Div("Choices", classes="text-h6 pt-4")
            with html.Div(classes="ml-4"):
                with html.Ul(classes="pa-0", style="list-style: none"):
                    with html.Li(
                        v_for=("(choice, index) in edited_choices",),
                        key=("index",),
                        classes="d-flex align-center mb-2",
                    ):
                        html.Span(
                            "{{String.fromCharCode(65 + index)}}.", classes="mr-2"
                        )
                        vuetify3.VTextarea(
                            model_value=("edited_choices[index]",),
                            update_modelValue=(
                                self.server.controller.update_choice,
                                "[index, $event]",
                            ),
                            auto_grow=True,
                            rows=1,
                            hide_details="auto",
                            density="compact",
                            classes="flex-grow-1",
                        )
                        with vuetify3.VBtn(
                            icon=True,
                            size="small",
                            classes="ml-2",
                            disabled=("edited_choices.length <= 2",),
                            click=(
                                self.server.controller.delete_choice,
                                "[index]",
                            ),
                            v_if=("max_choices > 2",),
                        ):
                            vuetify3.VIcon("mdi-close", size="small")
                vuetify3.VBtn(
                    "Add Choice",
                    click=self.server.controller.add_choice,
                    variant="outlined",
                    size="small",
                    classes="mt-2",
                    v_if=("edited_choices.length < max_choices && max_choices > 2",),
                )


class Scenario:
    class Title:
        def __init__(self):
            def run_content():
                html.Span(
                    "{{runs[id].prompt.scenario.scenario_id}} - "
                    "{{runs[id].prompt.scenario.full_state.unstructured}}",
                )

            RowWithLabel(run_content=run_content, label="Scenario")

    class Text:
        def __init__(self):
            def run_content():
                ScenarioLayout("runs[id].prompt.scenario")

            RowWithLabel(run_content=run_content)


class Decision:
    class Title:
        def __init__(self):
            def render_run_decision():
                html.Span(
                    "{{runs[id].decision.unstructured}}", v_if=("runs[id].decision",)
                )
                vuetify3.VProgressCircular(v_else=True, indeterminate=True, size=20)

            RowWithLabel(run_content=render_run_decision, label="Decision")

    class Text:
        def __init__(self):
            def render_run_decision_text():
                with html.Template(v_if=("runs[id].decision",)):
                    html.Div("Justification", classes="text-h6")
                    html.P("{{runs[id].decision.justification}}")

            RowWithLabel(run_content=render_run_decision_text)


class ChoiceInfo:
    class Title:
        def __init__(self):
            def render_choice_info():
                html.Span(
                    "{{runs[id].decision.choice_info_readable_keys.join(', ')}}",
                    v_if=(
                        "runs[id].decision && runs[id].decision.choice_info_readable_keys",
                    ),
                )
                vuetify3.VProgressCircular(v_else=True, indeterminate=True, size=20)

            RowWithLabel(run_content=render_choice_info, label="Choice Info")

    class Text:
        def __init__(self):
            def render_choice_info_text():
                with html.Template(
                    v_if=(
                        "runs[id].decision && runs[id].decision.choice_info_readable",
                    )
                ):
                    with html.Div(
                        v_for=(
                            "[key, value] in Object.entries(runs[id].decision.choice_info_readable)",
                        ),
                        key=("key",),
                        classes="mb-4",
                    ):
                        with html.Div(classes="text-h6 d-flex align-center"):
                            html.Span("{{key}}")
                            TooltipIcon(
                                "choiceInfoDescriptions[key] || 'No description available'",
                                v_if=("choiceInfoDescriptions[key]",),
                            )
                        with html.Div(classes="ml-4"):
                            with html.Template(
                                v_if=("key === 'ICL example responses'",)
                            ):
                                IclExampleListRenderer("value")
                            with html.Template(v_else=True):
                                UnorderedObject("value")

            RowWithLabel(run_content=render_choice_info_text)


class RunNumber:
    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                vuetify3.VSelect(
                    items=("Object.keys(runs).map((_, i) => i + 1)",),
                    model_value=("Object.keys(runs).indexOf(id) + 1",),
                    update_modelValue=(
                        self.server.controller.update_run_to_compare,
                        r"[$event, column]",
                    ),
                    hide_details="auto",
                )

            def no_runs():
                html.Div("No Runs")

            RowWithLabel(run_content=run_content, label="Run Number", no_runs=no_runs)


class ResultsComparison(html.Div):
    def __init__(self, **kwargs):
        super().__init__(classes="d-flex flex-wrap ga-4 pa-1", **kwargs)
        with self:
            with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                PanelSection(child=RunNumber)
                PanelSection(child=Scenario)
                PanelSection(child=Decider)
                PanelSection(child=Alignment)
                PanelSection(child=SystemPrompt)
                PanelSection(child=LlmBackbone)
                PanelSection(child=Decision)
                PanelSection(child=ChoiceInfo)


class ScenarioPanel(vuetify3.VExpansionPanel):
    def __init__(self, scenario, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanelTitle():
                with html.Div(classes="text-subtitle-1 text-no-wrap text-truncate"):
                    html.Span(
                        f"{{{{{scenario}.scenario_id}}}} - "
                        f"{{{{{scenario}.full_state.unstructured}}}}",
                    )
            with vuetify3.VExpansionPanelText():
                ScenarioLayout(scenario)


class EditableScenarioPanel(vuetify3.VExpansionPanel):
    def __init__(self, scenario, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanelTitle():
                with html.Div(classes="text-subtitle-1 text-no-wrap text-truncate"):
                    html.Span(
                        f"{{{{{scenario}.scenario_id}}}} - "
                        f"{{{{{scenario}.full_state.unstructured}}}}",
                    )
            with vuetify3.VExpansionPanelText():
                EditableScenarioLayout()


class PromptInput(html.Div):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VCardText():
                vuetify3.VSelect(
                    label="Scenario",
                    items=("scenarios",),
                    v_model=("prompt_scenario_id",),
                )
                with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                    EditableScenarioPanel("prompt_scenario")

                vuetify3.VSelect(
                    classes="mt-6",
                    label="Decider",
                    items=("deciders",),
                    v_model=("decider",),
                    error_messages=("decider_messages",),
                )
                with html.Template(
                    v_for=("alignment_attribute in alignment_attributes",),
                    key=("alignment_attribute.id",),
                ):
                    with vuetify3.VRow(no_gutters=True):
                        with vuetify3.VSelect(
                            label="Alignment",
                            items=("possible_alignment_attributes",),
                            model_value=("alignment_attribute",),
                            update_modelValue=(
                                self.server.controller.update_value_alignment_attribute,
                                r"[alignment_attribute.id, $event]",
                            ),
                            no_data_text="No available alignments",
                            hide_details="auto",
                        ):
                            with vuetify3.Template(v_slot_append_inner=""):
                                TooltipIcon("alignment_attribute.description")
                        with vuetify3.VBtn(
                            classes="ml-2 mt-1",
                            icon=True,
                            click=(
                                self.server.controller.delete_alignment_attribute,
                                "[alignment_attribute.id]",
                            ),
                        ):
                            vuetify3.VIcon("mdi-delete")

                    with vuetify3.VRow(
                        v_if=("alignment_attribute.possible_scores.length > 1",),
                        align="center",
                        justify="center",
                        classes="mb-2",
                    ):
                        with html.Template(
                            v_if=(
                                "alignment_attribute.possible_scores === 'continuous'",
                            )
                        ):
                            html.Span("0")
                            vuetify3.VSlider(
                                classes="px-4",
                                style="max-width: 300px",
                                model_value=("alignment_attribute.score",),
                                update_modelValue=(
                                    self.server.controller.update_score_alignment_attribute,
                                    r"[alignment_attribute.id, $event]",
                                ),
                                max=(1,),
                                thumb_label=True,
                                hide_details="auto",
                            )
                            html.Span("1")
                        vuetify3.VSlider(
                            v_else=True,
                            style="max-width: 300px",
                            model_value=("alignment_attribute.score",),
                            update_modelValue=(
                                self.server.controller.update_score_alignment_attribute,
                                r"[alignment_attribute.id, $event]",
                            ),
                            max=("alignment_attribute.possible_scores.length - 1",),
                            ticks=(
                                r"Object.fromEntries(alignment_attribute.possible_scores.map((s, i) => [i, s]))",
                            ),
                            show_ticks="always",
                            step="1",
                            tick_size="4",
                            hide_details="auto",
                        )

                vuetify3.VBtn(
                    "Add Alignment Attribute",
                    click=self.server.controller.add_alignment_attribute,
                    v_if=(
                        "alignment_attributes.length < max_alignment_attributes"
                        " && possible_alignment_attributes.length > 0"
                    ),
                    classes="my-2",
                )

                with vuetify3.VExpansionPanels(
                    classes="mb-6 mt-4", multiple=True, variant="accordion"
                ):
                    with vuetify3.VExpansionPanel():
                        with vuetify3.VExpansionPanelTitle():
                            with html.Div(
                                classes="text-subtitle-1 text-no-wrap text-truncate"
                            ):
                                html.Span("System Prompt:")
                                html.Span("{{system_prompt}}")
                        with vuetify3.VExpansionPanelText():
                            html.Div("{{system_prompt}}")

                vuetify3.VSelect(
                    disabled=("llm_backbones.length <= 1",),
                    label="LLM Backbone",
                    items=("llm_backbones",),
                    v_model=("llm_backbone",),
                    hide_details="auto",
                )

            with vuetify3.VCardActions():
                with vuetify3.VBtn(
                    click=self.server.controller.submit_prompt,
                    disabled=("send_button_disabled",),
                ):
                    vuetify3.VIcon("mdi-send")


class AlignLayout(SinglePageLayout):
    def __init__(
        self,
        server,
        reload=None,
        **kwargs,
    ):
        super().__init__(server, **kwargs)

        self.state.trame__title = "align-app"
        self.state.choiceInfoDescriptions = CHOICE_INFO_DESCRIPTIONS
        self.title.set_text("Align App")
        self.icon.hide()

        with self as layout:
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                with vuetify3.VBtn(
                    icon=True,
                    click="utils.download('align-app-runs.json', runs_json || '[]', 'application/json')",
                    disabled=("Object.keys(runs).length === 0",),
                ):
                    vuetify3.VIcon("mdi-download")
                with vuetify3.VBtn(icon=True, click=self.server.controller.reset_state):
                    vuetify3.VIcon("mdi-undo")

            with layout.content:
                with vuetify3.VContainer(fluid=True, classes="overflow-y-auto"):
                    with vuetify3.VRow():
                        with vuetify3.VCol(cols=8):
                            ResultsComparison()
                        with vuetify3.VCol(cols=4):
                            PromptInput(classes="")
