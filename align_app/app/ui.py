from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


class Decision(html.Div):
    def __init__(self, decision, **kwargs):
        super().__init__(**kwargs)
        with self:
            html.H3(f"{{{{{decision}.unstructured}}}}")
            html.Pre(f"{{{{{decision}}}}}")


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
                                v_for=("decision in output",),
                            ):
                                Decision("decision")
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
