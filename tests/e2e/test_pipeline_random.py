import re

from playwright.sync_api import Page, expect

from .page_objects.align_page import AlignPage


def decision_starts_with_choice_letter():
    return re.compile(r"^[A-Z].+")


def test_pipeline_random_decision_flow(page: Page, align_app_server: str):
    align_page = AlignPage(page)

    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Random")

    align_page.click_send_button()

    align_page.wait_for_decision()

    expect(align_page.decision_text).to_have_text(decision_starts_with_choice_letter())


def test_pipeline_random_scene_change_rerun(page: Page, align_app_server: str):
    align_page = AlignPage(page)

    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Random")

    align_page.click_send_button()

    align_page.wait_for_decision()

    first_decision = align_page.get_decision_text()

    page.get_by_role("button").filter(has_text="Scenario").click()

    align_page.scene_dropdown.click()
    scene_items = page.locator(".v-list-item")
    second_scene = scene_items.nth(1)
    second_scene.click()

    align_page.wait_for_decision_send_button()
    expect(align_page.decision_send_button).to_be_visible()

    align_page.click_decision_send_button()
    align_page.wait_for_decision()

    expect(align_page.decision_text).to_be_visible()
    expect(align_page.decision_text).to_have_text(decision_starts_with_choice_letter())
