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


class Prompt(html.Div):
    def __init__(self, prompt, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                with vuetify3.VExpansionPanel():
                    with vuetify3.VExpansionPanelTitle():
                        with html.Div(classes="text-h5 text-no-wrap text-truncate"):
                            html.Span("Scenario ID: ", classes="font-weight-bold")
                            html.Span(
                                f"{{{{{prompt}.scenario.scenario_id}}}} - "
                                f"{{{{{prompt}.scenario.full_state.unstructured}}}}",
                            )
                    with vuetify3.VExpansionPanelText():
                        html.P(
                            f"{{{{{prompt}.scenario.full_state.unstructured}}}}",
                            classes=" text-subtitle-1 pb-4",
                        )
                        UnorderedObject(f"{prompt}.scenario")
                with vuetify3.VExpansionPanel():
                    with vuetify3.VExpansionPanelTitle():
                        with html.Div(classes="text-h5 text-no-wrap text-truncate"):
                            html.Span("Alignment Target: ", classes="font-weight-bold")
                            html.Span(f"{{{{{prompt}.alignment_target.id}}}}")
                    with vuetify3.VExpansionPanelText():
                        UnorderedObject(f"{prompt}.alignment_target")


class Decision(html.Div):
    def __init__(self, decision, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanels(
                multiple=True,
                variant="accordion",
            ):
                with vuetify3.VExpansionPanel():
                    with vuetify3.VExpansionPanelTitle():
                        with html.Div(classes="text-h5 text-no-wrap text-truncate"):
                            html.Span("Decision: ", classes="font-weight-bold")
                            html.Span(
                                f"{{{{{decision}.unstructured}}}}",
                                v_if=(f"{decision}",),
                            )
                            vuetify3.VProgressCircular(v_else=True, indeterminate=True)
                    with vuetify3.VExpansionPanelText(v_if=(f"{decision}",)):
                        UnorderedObject(decision)


class Result(vuetify3.VCard):
    def __init__(self, result, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VCardText():
                Prompt(f"{result}.prompt", classes="pb-4")
                Decision(f"{result}.decision")


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
                with vuetify3.VBtn(icon=True, click=self.controller.reset_state):
                    vuetify3.VIcon("mdi-undo")

            with layout.content:
                with vuetify3.VContainer(fluid=True, classes="fill-height"):
                    with vuetify3.VCol(
                        cols=12, classes="fill-height d-flex flex-column"
                    ):
                        with html.Div(classes="flex-grow-1 d-flex flex-column ga-4"):
                            with html.Div(
                                v_for=("result in output",),
                            ):
                                Result("result")
                        with html.Div(classes="mt-auto"):
                            with vuetify3.VCard():
                                with vuetify3.VCardText():
                                    vuetify3.VTextarea(
                                        v_model=("prompt",),
                                        placeholder="Enter prompt",
                                        variant="underlined",
                                        auto_grow=True,
                                        max_rows=10,
                                        hide_details="auto",
                                    )
                                with vuetify3.VCardActions():
                                    with vuetify3.VBtn(
                                        click=self.controller.submit_prompt
                                    ):
                                        vuetify3.VIcon("mdi-send")
