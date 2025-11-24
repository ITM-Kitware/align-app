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
        return self.page.locator(".v-select").filter(has_text="Decider")

    @property
    def send_button(self) -> Locator:
        return self.page.locator("button:has(i.mdi-send)")

    @property
    def spinner(self) -> Locator:
        return self.page.locator(".v-progress-circular")

    @property
    def decision_text(self) -> Locator:
        return self.page.locator("text=/^[A-Z].+/").first

    @property
    def scene_dropdown(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panel-text .v-select")
            .filter(has_text="Scene")
            .first
        )

    @property
    def decision_send_button(self) -> Locator:
        return self.page.get_by_role("button", name="Choose", exact=True)

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

    def select_scene(self, scene_id: str) -> None:
        self.scene_dropdown.click()
        self.page.locator(f".v-list-item:has-text('{scene_id}')").click()

    def click_decision_send_button(self) -> None:
        self.decision_send_button.click()

    def wait_for_decision_send_button(
        self, timeout: int = DEFAULT_WAIT_TIMEOUT
    ) -> None:
        expect(self.decision_send_button).to_be_visible(timeout=timeout)
