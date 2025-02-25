from trame.app import get_server, asynchronous
from trame.decorators import TrameApp, controller
from . import ui
from ..adm.decider import get_decision, serialize_prompt
from .prompt import PromptController


@TrameApp()
class AlignApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue3")
        self._promptController = PromptController(self.server)
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

    @controller.set("reset_state")
    def reset_state(self):
        self._promptController.reset()
        self.state.output = []

    async def make_decision(self):
        prompt = self._promptController.get_prompt()
        run = {"prompt": serialize_prompt(prompt)}
        with self.state:
            self.state.output = [
                *self.state.output,
                run,
            ]
        await self.server.network_completion  # let spinner be shown

        decision = get_decision(prompt)
        run = {"prompt": run["prompt"], "decision": decision}
        with self.state:
            self.state.output = [
                *self.state.output[:-1],
                run,
            ]

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.make_decision())

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
