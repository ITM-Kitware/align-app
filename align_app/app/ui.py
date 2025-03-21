from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html
from ..utils.utils import noop

MAX_ALIGNMENT_ATTRIBUTES = 1


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


class UnorderedObject(html.Ul):
    def __init__(self, obj, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(
                v_if=f"{obj}", v_for=(f"[key, value] in Object.entries({obj})",)
            ):
                html.Span("{{key}}: ")
                html.Span("{{value}}")
            html.Div("No Object", v_else=True)


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
    def __init__(self, run_content=noop, label="", title=True):
        with vuetify3.VRow(style="max-width: 100%;"):
            with vuetify3.VCol(cols=2):
                html.Span(label, classes="text-h6")
            with vuetify3.VCol(
                v_for=("id in runs_to_compare",),
                key=("id",),
                classes=(
                    "text-subtitle-1 text-no-wrap text-truncate align-self-center"
                    if title
                    else ""
                ),
            ):
                run_content()


class LlmBackbone:
    class Title:
        def __init__(self):
            def run_content():
                html.Span("{{runs[id].prompt.decider_params.llm_backbone}}")

            RowWithLabel(run_content=run_content, label="LLM Backbone")


class DecisionMaker:
    class Title:
        def __init__(self):
            def run_content():
                html.Span("{{runs[id].prompt.decider_params.decider}}")

            RowWithLabel(run_content=run_content, label="Decision Maker")


class AlignmentTargets:
    class Title:
        def __init__(self):
            def run_content():
                html.Span(
                    "{{ runs[id].prompt.alignment_targets.length ? "
                    "runs[id].prompt.alignment_targets.map(att => att.id).join(', ') : "
                    "'No Alignment Targets' }}"
                )

            RowWithLabel(run_content=run_content, label="Alignment Target")

    class Text:
        def __init__(self):
            def run_content():
                with html.Div(
                    v_for=("attribute in runs[id].prompt.alignment_targets",),
                    key=("attribute.id",),
                    classes="mb-4",
                ):
                    with html.Ul(classes="ml-8"):
                        with html.Li(v_for=("value in attribute.kdma_values",)):
                            html.Span("{{value.kdma}}: ")
                            html.Span("{{value.value}}")
                html.Div("", v_if=("runs[id].prompt.alignment_targets.length === 0",))

            RowWithLabel(run_content=run_content, title=False)


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
                html.P(
                    "{{runs[id].prompt.scenario.full_state.unstructured}}",
                    classes="pb-4",
                )
                html.Div("Choices", classes="text-h6")
                with html.Ul(
                    v_for=("choice in runs[id].prompt.scenario.choices",),
                    classes="ml-8",
                ):
                    html.Li("{{choice.unstructured}}")

            RowWithLabel(run_content=run_content, title=False)


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
                    html.Div("KDMA Association", classes="text-h6 mt-4")
                    UnorderedObject(
                        "runs[id].decision.kdma_association",
                        v_if="runs[id].decision.kdma_association",
                        classes="ml-8",
                    )
                    html.Div(
                        "No KDMA Association",
                        v_else=True,
                    )

            RowWithLabel(run_content=render_run_decision_text, title=False)


class ResultsComparison(html.Div):
    def __init__(self, **kwargs):
        super().__init__(classes="d-flex flex-wrap ga-4 pa-1", **kwargs)
        with self:
            with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                PanelSection(child=DecisionMaker)
                PanelSection(child=LlmBackbone)
                PanelSection(child=AlignmentTargets)
                PanelSection(child=Scenario)
                PanelSection(child=Decision)


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
                html.P(
                    f"{{{{{scenario}.full_state.unstructured}}}}",
                    classes="text-subtitle-1 pb-4",
                )
                html.Div("Choices", classes="text-h6")
                with html.Ul(
                    v_for=(f"choice in {scenario}.choices"),
                    classes="ml-8",
                ):
                    html.Li("{{choice.unstructured}}")


class PromptInput(vuetify3.VCard):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VCardText():
                vuetify3.VSelect(
                    label="Decision Maker",
                    items=("decision_makers",),
                    v_model=("decision_maker",),
                )
                vuetify3.VSelect(
                    label="LLM Backbone",
                    items=("llm_backbones",),
                    v_model=("llm_backbone",),
                )
                with html.Template(
                    v_for=("alignment_attribute in alignment_attributes",),
                    key=("alignment_attribute.id",),
                ):
                    with vuetify3.VRow(no_gutters=True):
                        vuetify3.VSelect(
                            label="Alignment Target",
                            items=("possible_alignment_attributes",),
                            model_value=("alignment_attribute",),
                            update_modelValue=(
                                self.server.controller.update_value_alignment_attribute,
                                r"[$event, alignment_attribute.id]",
                            ),
                            no_data_text="No available alignment targets",
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
                    vuetify3.VSlider(
                        model_value=("alignment_attribute.score",),
                        update_modelValue=(
                            self.server.controller.update_score_alignment_attribute,
                            r"[$event, alignment_attribute.id]",
                        ),
                    )

                vuetify3.VBtn(
                    "Add Alignment Attribute",
                    click=self.server.controller.add_alignment_attribute,
                    v_if=(f"alignment_attributes.length < {MAX_ALIGNMENT_ATTRIBUTES}",),
                )

                vuetify3.VSelect(
                    classes="mt-6",
                    label="Scenario",
                    items=("scenarios",),
                    v_model=("prompt_scenario_id",),
                )
                with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                    ScenarioPanel("prompt_scenario")

            with vuetify3.VCardActions():
                with vuetify3.VBtn(click=self.server.controller.submit_prompt):
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
