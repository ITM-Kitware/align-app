import re

from playwright.sync_api import expect

from .page_objects.align_page import AlignPage


def decision_starts_with_choice_letter():
    return re.compile(r"^[A-Z].+")


def test_pipeline_random_decision_flow(align_page_with_decision: AlignPage):
    expect(align_page_with_decision.decision_text).to_have_text(
        decision_starts_with_choice_letter()
    )


def test_pipeline_random_scene_change_rerun(align_page_with_decision: AlignPage):
    align_page = align_page_with_decision
    page = align_page.page

    align_page.expand_scenario_panel()

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


def test_pipeline_random_scenario_change_rerun(align_page_with_decision: AlignPage):
    align_page = align_page_with_decision
    page = align_page.page

    align_page.scenario_dropdown.click()
    page.wait_for_selector(".v-list-item", state="visible")
    scenario_items = page.locator(".v-list-item")
    scenario_count = scenario_items.count()

    assert scenario_count >= 2, "Test requires at least 2 scenarios"

    second_scenario = scenario_items.nth(1)
    second_scenario_text = second_scenario.text_content()
    second_scenario.click()

    listbox = page.get_by_role("listbox", name="Scenario-list")
    expect(listbox).not_to_be_visible()

    current_scenario = align_page.get_scenario_dropdown_value()
    assert second_scenario_text in current_scenario, (
        f"Expected scenario to be '{second_scenario_text}' but got '{current_scenario}'"
    )

    align_page.wait_for_decision_send_button()
    expect(align_page.decision_send_button).to_be_visible()

    align_page.click_decision_send_button()
    align_page.wait_for_decision()

    expect(align_page.decision_text).to_be_visible()
    expect(align_page.decision_text).to_have_text(decision_starts_with_choice_letter())


def test_pipeline_random_decider_change_restores_cache(
    align_page_with_decision: AlignPage,
):
    """Test that cached decision is restored when changing decider back.

    Reproduces bug where:
    1. Run pipeline_random -> decision cached
    2. Change to different decider -> decision cleared
    3. Change back to pipeline_random -> decision should be restored from cache

    Expected: Decision is restored (no Choose button)
    Actual (bug): Choose button shows (cache not found)
    """
    align_page = align_page_with_decision
    page = align_page.page

    original_decision_text = align_page.get_decision_text()

    align_page.results_decider_dropdown.click()
    page.wait_for_selector(".v-list-item", state="visible")

    non_random_decider, _ = align_page.find_decider_in_open_list(
        exclude=["pipeline_random"]
    )
    assert non_random_decider is not None, (
        "Test requires at least one non-pipeline_random decider"
    )

    non_random_decider.click()

    align_page.wait_for_decision_send_button()
    expect(align_page.decision_send_button).to_be_visible()

    align_page.results_decider_dropdown.click()
    page.wait_for_selector(".v-list-item", state="visible")

    pipeline_random_option = page.get_by_role("option", name="pipeline_random")
    expect(pipeline_random_option).to_be_visible()
    pipeline_random_option.click()

    expect(align_page.decision_text).to_be_visible()
    expect(align_page.decision_text).to_have_text(original_decision_text)
    expect(align_page.decision_send_button).not_to_be_visible()
