from trame.app import get_server, asynchronous
from trame.decorators import TrameApp, controller
from . import ui
from ..adm.decider import get_prompt, get_decision, readable_scenario, serialize_prompt


@TrameApp()
class AlignApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue3")
        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)
        self._build_ui()

        self.reset_state()

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    def update_prompt(self):
        self._prompt = get_prompt()
        self.state.prompt = readable_scenario(self._prompt["scenario"])

    @controller.set("reset_state")
    def reset_state(self):
        self.update_prompt()
        self.state.output = []

    async def make_decision(self):
        prompt = {"prompt": serialize_prompt(self._prompt)}
        with self.state:
            self.state.output = [
                *self.state.output,
                prompt,
            ]
        await self.server.network_completion  # let spinner be shown

        decision = get_decision(self._prompt)
        result = {"prompt": prompt["prompt"], "decision": decision}
        with self.state:
            self.state.output = [
                *self.state.output[:-1],
                result,
            ]
            self.update_prompt()

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.make_decision())

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
