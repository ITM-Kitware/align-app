from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


class UnorderedObject(html.Ul):
    def __init__(self, obj, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(v_for=(f"[key, value] in Object.entries({obj})",)):
                html.Span("{{key}}: ", style="font-weight: bold")
                html.Span("{{value}}")


class Scenario(vuetify3.VExpansionPanel):
    def __init__(self, scenario, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanelTitle():
                with html.Div(classes="text-h6 text-no-wrap text-truncate"):
                    html.Span("Scenario: ", classes="font-weight-bold")
                    html.Span(
                        f"{{{{{scenario}.scenario_id}}}} - "
                        f"{{{{{scenario}.full_state.unstructured}}}}",
                    )
            with vuetify3.VExpansionPanelText():
                html.P(
                    f"{{{{{scenario}.full_state.unstructured}}}}",
                    classes=" text-subtitle-1 pb-4",
                )
                html.H3("Choices")
                with html.Ul(
                    v_for=(f"choice in {scenario}.choices"),
                    classes="ml-4",
                ):
                    html.Li("{{choice.unstructured}}")


class DeciderParams(vuetify3.VExpansionPanel):
    def __init__(self, params, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanelTitle():
                with vuetify3.VRow(classes="text-h6 text-no-wrap text-truncate"):
                    with vuetify3.VCol():
                        html.Span("LLM Backbone: ", classes="font-weight-bold")
                        html.Span(f"{{{{{params}.llm_backbone}}}}")
                    with vuetify3.VCol():
                        html.Span("Decision Maker: ", classes="font-weight-bold")
                        html.Span(f"{{{{{params}.decider}}}}")
            with vuetify3.VExpansionPanelText():
                UnorderedObject(params)


class AlignmentTargets(vuetify3.VExpansionPanel):
    def __init__(self, alignment_targets, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanelTitle():
                with html.Div(classes="text-h6 text-no-wrap text-truncate"):
                    html.Span("Alignment Targets: ", classes="font-weight-bold")
                    html.Span(
                        f"{{{{ {alignment_targets}.length ? "
                        f"{alignment_targets}.map(att => att.id).join(', ') : "
                        f"'No Alignment' }}}}"
                    )
            with vuetify3.VExpansionPanelText():
                with html.Div(
                    v_for=(f"attribute in {alignment_targets}",),
                    classes="mb-4",
                ):
                    html.H3("{{attribute.id}}")
                    UnorderedObject("attribute", classes="ml-4")
                html.Div(
                    "No Alignment",
                    v_if=(f"{alignment_targets}.length === 0",),
                )


class Prompt:
    def __init__(self, prompt):
        DeciderParams(f"{prompt}.decider_params")
        AlignmentTargets(f"{prompt}.alignment_targets")
        Scenario(f"{prompt}.scenario")


class Decision:
    def __init__(self, decision):
        with vuetify3.VExpansionPanel():
            with vuetify3.VExpansionPanelTitle():
                with html.Div(classes="text-h6 text-no-wrap text-truncate"):
                    html.Span("Decision: ", classes="font-weight-bold")
                    html.Span(
                        f"{{{{{decision}.unstructured}}}}",
                        v_if=(f"{decision}",),
                    )
                    vuetify3.VProgressCircular(v_else=True, indeterminate=True)
            with vuetify3.VExpansionPanelText(v_if=(f"{decision}",)):
                html.H3("Justification")
                html.P(f"{{{{{decision}.justification}}}}")
                html.H3("KDMA Association")
                UnorderedObject(f"{decision}.kdma_association", classes="ml-4")


class Result(vuetify3.VCard):
    def __init__(self, result, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VCardText():
                with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                    Prompt(f"{result}.prompt")
                    Decision(f"{result}.decision")


class PromptInput(vuetify3.VCard):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VCardText():
                with vuetify3.VRow():
                    with vuetify3.VCol():
                        vuetify3.VSelect(
                            label="LLM Backbone",
                            items=("llm_backbones",),
                            v_model=("llm_backbone",),
                            hide_details="auto",
                        )
                    with vuetify3.VCol():
                        vuetify3.VSelect(
                            label="Decision Maker",
                            items=("decision_makers",),
                            v_model=("decision_maker",),
                            hide_details="auto",
                        )
                with vuetify3.VRow(
                    v_for=("alignment_attribute in alignment_attributes",),
                    key=("alignment_attribute.id",),
                ):
                    with vuetify3.VCol():
                        vuetify3.VSelect(
                            label="Alignment Target",
                            items=("possible_alignment_attributes",),
                            model_value=("alignment_attribute.type",),
                            update_modelValue=(
                                self.server.controller.update_type_alignment_attribute,
                                r"[$event, alignment_attribute.id]",
                            ),
                            no_data_text="No available alignment targets",
                            hide_details="auto",
                        )
                    with vuetify3.VCol():
                        with vuetify3.VRow(no_gutters=True):
                            vuetify3.VSlider(
                                label="Alignment Score",
                                model_value=("alignment_attribute.score",),
                                update_modelValue=(
                                    self.server.controller.update_score_alignment_attribute,
                                    r"[$event, alignment_attribute.id]",
                                ),
                            )
                            with vuetify3.VBtn(
                                classes="ml-2",
                                icon=True,
                                click=(
                                    self.server.controller.delete_alignment_attribute,
                                    "[alignment_attribute.id]",
                                ),
                            ):
                                vuetify3.VIcon("mdi-delete")

                with vuetify3.VRow(v_if=("possible_alignment_attributes.length > 0",)):
                    with vuetify3.VCol():
                        vuetify3.VBtn(
                            "Add Alignment Attribute",
                            click=self.server.controller.add_alignment_attribute,
                        )
                with vuetify3.VRow():
                    with vuetify3.VCol(
                        cols=4,
                    ):
                        vuetify3.VSelect(
                            label="Scenario",
                            items=("scenarios",),
                            v_model=("prompt_scenario_id",),
                            hide_details="auto",
                        )
                    with vuetify3.VCol(cols=8):
                        with vuetify3.VExpansionPanels(
                            multiple=True, variant="accordion"
                        ):
                            Scenario("prompt_scenario")

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

        self.content.height = "100vh"

        with self as layout:
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                with vuetify3.VBtn(icon=True, click=self.server.controller.reset_state):
                    vuetify3.VIcon("mdi-undo")

            with layout.content:
                with vuetify3.VContainer(classes="fill-height"):
                    with vuetify3.VCol(classes="fill-height d-flex flex-column"):
                        with html.Div(
                            classes="overflow-y-auto flex-grow-0 flex-shrink-1 mb-4 d-flex flex-column ga-4 pa-1",
                            style="min-height: 10rem",
                        ):
                            # need this div for overflow to work =/
                            with html.Div(v_for=("result in output",)):
                                Result("result", key=("result.id",))
                        PromptInput(classes="mt-auto flex-shrink-0")
