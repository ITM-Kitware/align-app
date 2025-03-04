from trame.decorators import TrameApp, change
from ..adm.adm_core import get_scenarios, get_prompt, LLM_BACKBONES, deciders


@TrameApp()
class PromptController:
    def __init__(self, server):
        self.server = server
        self.reset()

    def update_scenarios(self):
        scenarios = get_scenarios()
        items = [
            {"value": id, "title": f"{id} - {s['state']}"}
            for id, s in scenarios.items()
        ]
        self.server.state.scenarios = items
        self.server.state.prompt_scenario_id = self.server.state.scenarios[0]["value"]

    def reset(self):
        self.update_scenarios()
        self.server.state.llm_backbones = LLM_BACKBONES
        self.server.state.llm_backbone = LLM_BACKBONES[0]
        self.server.state.decision_makers = deciders
        self.server.state.decision_maker = deciders[0]

    @change("prompt_scenario_id")
    def on_scenario_change(self, prompt_scenario_id, **kwargs):
        s = get_scenarios()[prompt_scenario_id]
        self.server.state.prompt_scenario = s

    def get_prompt(self):
        return get_prompt(
            self.server.state.prompt_scenario_id,
            self.server.state.llm_backbone,
            self.server.state.decision_maker,
        )
