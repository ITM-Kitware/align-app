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


def test_pipeline_random_scenario_change_rerun(page: Page, align_app_server: str):
    align_page = AlignPage(page)

    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Random")

    align_page.click_send_button()

    align_page.wait_for_decision()

    page.get_by_role("button").filter(has_text="Scenario").click()

    align_page.scenario_dropdown.click()
    scenario_items = page.locator(".v-list-item")
    scenario_count = scenario_items.count()

    assert scenario_count >= 2, "Test requires at least 2 scenarios"

    second_scenario = scenario_items.nth(1)
    second_scenario_text = second_scenario.text_content()
    second_scenario.click()

    page.wait_for_timeout(500)

    current_scenario = align_page.scenario_dropdown.locator("input").input_value()
    assert second_scenario_text in current_scenario, (
        f"Expected scenario to be '{second_scenario_text}' but got '{current_scenario}'"
    )

    align_page.wait_for_decision_send_button()
    expect(align_page.decision_send_button).to_be_visible()

    align_page.click_decision_send_button()
    align_page.wait_for_decision()

    expect(align_page.decision_text).to_be_visible()
    expect(align_page.decision_text).to_have_text(decision_starts_with_choice_letter())
