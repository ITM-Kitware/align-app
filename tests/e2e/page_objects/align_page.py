from playwright.sync_api import Page, expect, Locator

from ..conftest import (
    DECISION_TIMEOUT,
    DEFAULT_WAIT_TIMEOUT,
    SPINNER_APPEAR_TIMEOUT,
)


class AlignPage:
    def __init__(self, page: Page):
        self.page = page

    @property
    def decider_dropdown(self) -> Locator:
        return (
            self.page.locator(".v-card-text .v-select").filter(has_text="Decider").first
        )

    @property
    def send_button(self) -> Locator:
        return self.page.locator(".v-card-actions button:has(i.mdi-send)")

    @property
    def spinner(self) -> Locator:
        return self.page.locator(".v-progress-circular")

    @property
    def decision_text(self) -> Locator:
        return self.page.locator("text=/^[A-Z].+/").first

    @property
    def scenario_dropdown(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panel-text .v-select")
            .filter(has_text="Scenario")
            .first
        )

    @property
    def scene_dropdown(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panel-text .v-select")
            .filter(has_text="Scene")
            .first
        )

    @property
    def results_decider_dropdown(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panels .v-expansion-panel-title .v-select")
            .filter(has_text="Decider")
            .first
        )

    @property
    def results_llm_dropdown(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panels .v-expansion-panel-title .v-select")
            .filter(has_text="LLM")
            .first
        )

    @property
    def decision_send_button(self) -> Locator:
        return self.page.get_by_role("button", name="Choose", exact=True).first

    def goto(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")

    def select_decider(self, decider_name: str) -> None:
        self.decider_dropdown.click()
        self.page.locator(f".v-list-item:has-text('{decider_name}')").click()

    def click_send_button(self) -> None:
        self.send_button.click()

    def wait_for_decision(self, timeout: int = DECISION_TIMEOUT) -> None:
        expect(self.decision_text).to_be_visible(timeout=timeout)

    def get_decision_text(self) -> str:
        text = self.decision_text.text_content()
        if text is None:
            raise RuntimeError("Decision text is None")
        return text

    def is_send_button_enabled(self) -> bool:
        return self.send_button.is_enabled()

    def wait_for_spinner_to_appear(self, timeout: int = SPINNER_APPEAR_TIMEOUT) -> None:
        expect(self.spinner).to_be_visible(timeout=timeout)

    def wait_for_spinner_to_disappear(
        self, timeout: int = DEFAULT_WAIT_TIMEOUT
    ) -> None:
        expect(self.spinner).not_to_be_visible(timeout=timeout)

    def select_scenario(self, scenario_id: str) -> None:
        self.scenario_dropdown.click()
        self.page.locator(f".v-list-item:has-text('{scenario_id}')").click()

    def select_scene(self, scene_id: str) -> None:
        self.scene_dropdown.click()
        self.page.locator(f".v-list-item:has-text('{scene_id}')").click()

    def get_scene_dropdown_value(self) -> str:
        value = self.scene_dropdown.locator("input").input_value()
        if value is None:
            raise RuntimeError("Scene dropdown value is None")
        return value

    def click_decision_send_button(self) -> None:
        self.decision_send_button.click()

    def wait_for_decision_send_button(
        self, timeout: int = DEFAULT_WAIT_TIMEOUT
    ) -> None:
        expect(self.decision_send_button).to_be_visible(timeout=timeout)

    def select_results_decider(self, decider_name: str) -> None:
        expect(self.results_decider_dropdown).to_be_visible()
        self.results_decider_dropdown.click()
        menu_item = self.page.locator(f".v-list-item:has-text('{decider_name}')")
        expect(menu_item).to_be_visible()
        menu_item.click()

    def get_results_llm_value(self) -> str:
        value = self.results_llm_dropdown.locator("input").input_value()
        if value is None:
            raise RuntimeError("LLM dropdown value is None")
        return value

    def select_results_llm(self, llm_name: str) -> None:
        expect(self.results_llm_dropdown).to_be_visible()
        self.results_llm_dropdown.click()
        menu_item = self.page.locator(f".v-list-item:has-text('{llm_name}')")
        expect(menu_item).to_be_visible()
        menu_item.click()

    @property
    def alignment_panel_title(self) -> Locator:
        return self.page.get_by_role("button").filter(has_text="Alignment").filter(
            has=self.page.locator(".v-expansion-panel-title__overlay")
        )

    @property
    def alignment_panel_content(self) -> Locator:
        return self.page.locator(".v-expansion-panel").filter(
            has=self.page.get_by_role("button").filter(has_text="Alignment")
        ).locator(".v-expansion-panel-text")

    def expand_alignment_panel(self) -> None:
        expect(self.alignment_panel_title).to_be_visible()
        is_expanded = self.alignment_panel_title.get_attribute("aria-expanded") == "true"
        if not is_expanded:
            self.alignment_panel_title.click()
        expect(self.alignment_panel_title).to_have_attribute("aria-expanded", "true")
        expect(self.alignment_panel_content).to_be_visible()

    @property
    def add_alignment_button(self) -> Locator:
        return self.alignment_panel_content.get_by_role("button", name="Add Alignment")

    def get_alignment_count(self) -> int:
        return self.alignment_panel_content.locator(".v-select").count()

    def get_alignment_dropdown(self, index: int = 0) -> Locator:
        return self.alignment_panel_content.locator(".v-select").nth(index)

    def get_alignment_delete_button(self, index: int = 0) -> Locator:
        return self.alignment_panel_content.locator("button:has(.mdi-delete)").nth(index)

    def click_add_alignment(self) -> None:
        expect(self.add_alignment_button).to_be_visible()
        self.add_alignment_button.click()

    def delete_alignment(self, index: int = 0) -> None:
        delete_btn = self.get_alignment_delete_button(index)
        expect(delete_btn).to_be_visible()
        delete_btn.click()

    def get_alignment_value(self, index: int = 0) -> str:
        dropdown = self.get_alignment_dropdown(index)
        value = dropdown.locator("input").input_value()
        if value is None:
            return ""
        return value

    def select_alignment(self, index: int, alignment_name: str) -> None:
        dropdown = self.get_alignment_dropdown(index)
        expect(dropdown).to_be_visible()
        dropdown.click()
        menu_item = self.page.locator(f".v-list-item:has-text('{alignment_name}')")
        expect(menu_item).to_be_visible()
        menu_item.click()
