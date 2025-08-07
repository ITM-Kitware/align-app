from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html
from ..adm.adm_core import serialize_prompt, Prompt, get_alignment_descriptions_map
from ..utils.utils import noop, readable, sentence_lines

MAX_ALIGNMENT_ATTRIBUTES = 1


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


SENTENCE_KEYS = ["intent", "unstructured"]  # Keys to apply sentence function to


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
        readable_key = readable(key)
        if isinstance(value, dict):
            result[readable_key] = make_keys_readable(
                value, max_depth, current_depth + 1
            )
        elif isinstance(value, list):
            result[readable_key] = value
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


class ValueWithProgressBar(html.Span):
    def __init__(self, value_expression, decimals=2, **kwargs):
        super().__init__(**kwargs)
        with self:
            vuetify3.VProgressLinear(
                model_value=(f"{value_expression} * 100",),
                height="10",
                readonly=True,
                style=("display: inline-block; width: 100px;"),
            )
            html.Span(
                f"{{{{{value_expression}.toFixed({decimals})}}}}",
                style="display: inline-block; margin-left: 8px;",
            )


class UnorderedObject(html.Ul):
    def __init__(self, obj, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(
                v_if=f"{obj}", v_for=(f"[key, value] in Object.entries({obj})",)
            ):
                html.Span("{{key}}: ")

                with html.Template(
                    v_if=(
                        "typeof value === 'object' && value !== null && !Array.isArray(value)",
                    )
                ):
                    html.Br()
                    with html.Ul(classes="ml-4"):
                        with html.Li(v_for=("[k, v] in Object.entries(value)",)):
                            html.Span("{{k}}: ")
                            with html.Template(v_if=("Array.isArray(v)",)):
                                html.Span("{{v.join(', ')}}")
                            with html.Template(v_else=True):
                                html.Span("{{v}}")

                with html.Template(v_else_if=("Array.isArray(value)",)):
                    html.Span("{{value.join(', ')}}")

                with html.Template(v_else=True):
                    html.Span("{{value}}")

            html.Div("No Object", v_else=True)


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
                                html.Span("{{choice}}: Score {{responseData.score}}")


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
                    with html.Ul(classes="ml-8"):
                        html.Li("{{kdma_value.description}}")
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
        html.P(f"{{{{{scenario}.display_state}}}}")
        html.Div(
            "Characters",
            classes="text-h6 pt-4",
            v_if=f"{scenario}.full_state.characters && {scenario}.full_state.characters.length",
        )
        with html.Div(
            v_for=(f"character in {scenario}.full_state.characters",), classes="pt-2"
        ):
            html.Div("{{character.name}}")
            with html.Div(classes="ml-8"):
                html.P("{{character.unstructured}}", classes="my-2")
                html.P("{{character.intent}}")
        html.Div("Choices", classes="text-h6 pt-4")
        with html.Ol(classes="ml-8", type="A"):
            html.Li("{{choice.unstructured}}", v_for=(f"choice in {scenario}.choices"))


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
                        html.Div("{{key}}", classes="text-h6")
                        with html.Div(classes="ml-4"):
                            with html.Template(
                                v_if=("key === 'ICL Example Responses'",)
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


class PromptInput(vuetify3.VCard):
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
                    ScenarioPanel("prompt_scenario")

                vuetify3.VSelect(
                    classes="mt-6",
                    label="Decision Maker",
                    items=("decision_makers",),
                    v_model=("decision_maker",),
                    error_messages=("decider_messages",),
                )
                with html.Template(
                    v_for=("alignment_attribute in alignment_attributes",),
                    key=("alignment_attribute.id",),
                ):
                    with vuetify3.VRow(no_gutters=True):
                        vuetify3.VSelect(
                            label="Alignment",
                            items=("possible_alignment_attributes",),
                            model_value=("alignment_attribute",),
                            update_modelValue=(
                                self.server.controller.update_value_alignment_attribute,
                                r"[alignment_attribute.id, $event]",
                            ),
                            no_data_text="No available alignments",
                            hide_details="auto",
                        )
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
                                html.Span("Alignment:")
                                html.Span(
                                    "{{attribute_targets.length ? "
                                    "attribute_targets.map(att => `${att.kdma} ${att.value}`).join(', ')"
                                    ": 'No Alignments'}}"
                                )
                        with vuetify3.VExpansionPanelText():
                            with html.Div(
                                "{{kdma_value.kdma}}",
                                v_for=("kdma_value in attribute_targets",),
                                key=("kdma_value.kdma",),
                            ):
                                with html.Ul(classes="ml-8"):
                                    with html.Li():
                                        html.Span("Value: {{kdma_value.value}} ")
                                        vuetify3.VProgressLinear(
                                            model_value=("kdma_value.value * 100",),
                                            height="10",
                                            readonly=True,
                                            style="display: inline-block; width: 100px; vertical-align: middle;",
                                        )
                                    html.Li("{{kdma_value.description}}")
                            html.Div(
                                "",
                                v_if=("attribute_targets.length === 0",),
                            )

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
        self.title.set_text("Align App")
        self.icon.hide()

        with self as layout:
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                with vuetify3.VBtn(icon=True, click=self.server.controller.reset_state):
                    vuetify3.VIcon("mdi-undo")

            with layout.content:
                with vuetify3.VContainer(fluid=True, classes="overflow-y-auto"):
                    with vuetify3.VRow():
                        with vuetify3.VCol(cols=8):
                            ResultsComparison()
                        with vuetify3.VCol(cols=4):
                            PromptInput(classes="")
