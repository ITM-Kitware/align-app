from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


class AlignLayout(SinglePageLayout):
    def __init__(
        self,
        server,
        reload=None,
        **kwargs,
    ):
        super().__init__(server, **kwargs)

        self.state.trame__title = "align-app"

        with SinglePageLayout(self.server) as layout:
            # Toolbar
            layout.title.set_text("Align App")
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                with vuetify3.VBtn(icon=True, click=self.controller.reset_state):
                    vuetify3.VIcon("mdi-undo")

            # Main content
            with layout.content:
                with vuetify3.VContainer(fluid=True, classes="pa-0 fill-height"):
                    with vuetify3.VRow(classes="fill-height"):
                        with vuetify3.VCol(cols=12, classes="pa-0 fill-height"):
                            vuetify3.VTextarea(
                                v_model=("prompt",),
                                label="Prompt",
                            )
