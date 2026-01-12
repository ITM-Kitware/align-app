from .page_objects.align_page import AlignPage
# from .conftest import DEFAULT_DECIDER, ALIGNMENT_DECIDER

DEFAULT_DECIDER = "pipeline_random"
ALIGNMENT_DECIDER = "phase2_pipeline_zeroshot_comparative_regression"


def test_decider_switch_replaces_draft_run(page, align_app_server):
    print("DEBUG: Starting test_decider_switch_replaces_draft_run")
    align_page = AlignPage(page)
    align_page.goto(align_app_server)
    align_page.wait_for_spinner_to_disappear()
    print("DEBUG: Navigated and spinner gone")

    initial_count = align_page.get_run_columns().count()
    print(f"DEBUG: Initial count: {initial_count}")
    assert initial_count >= 1, "Expected at least 1 run"

    # Switch decider (Draft Run -> Replacement)
    target_decider = ALIGNMENT_DECIDER
    current_decider = align_page.get_decider_dropdown_value()
    print(f"DEBUG: Current decider: {current_decider}")
    if current_decider == target_decider:
        target_decider = DEFAULT_DECIDER

    print(f"DEBUG: Switching to {target_decider}")
    align_page.select_decider(target_decider)
    align_page.wait_for_spinner_to_disappear()

    # Verify count unchanged
    new_count = align_page.get_run_columns().count()
    print(f"DEBUG: New count: {new_count}")
    align_page.expect_run_count(initial_count)
    print("DEBUG: Count verified")

    # Switch back
    align_page.select_decider(current_decider)
    align_page.wait_for_spinner_to_disappear()

    # Verify count unchanged
    align_page.expect_run_count(initial_count)


def test_decider_switch_replaces_after_decision(page, align_app_server):
    """After a decision, switching decider still REPLACES in UI.
    Old run is preserved in registry for history/export but replaced in view."""
    print("DEBUG: Starting test_decider_switch_replaces_after_decision")
    align_page = AlignPage(page)
    align_page.goto(align_app_server)
    align_page.wait_for_spinner_to_disappear()
    print("DEBUG: Navigated and spinner gone")

    initial_count = align_page.get_run_columns().count()
    print(f"DEBUG: Initial count: {initial_count}")

    # Get a decision on the run
    print("DEBUG: Getting decision...")
    align_page.click_and_wait_for_decision()
    print("DEBUG: Decision obtained")

    # Run count should stay same (decision adds result to same run)
    count_after_decision = align_page.get_run_columns().count()
    print(f"DEBUG: Count after decision: {count_after_decision}")
    align_page.expect_run_count(initial_count)

    # Now switch decider (Run has decision -> Still REPLACES in UI)
    target_decider = ALIGNMENT_DECIDER
    current_decider = align_page.get_decider_dropdown_value()
    print(f"DEBUG: Current decider: {current_decider}")
    if current_decider == target_decider:
        target_decider = DEFAULT_DECIDER

    print(f"DEBUG: Switching to {target_decider}")
    align_page.select_decider(target_decider)
    align_page.wait_for_spinner_to_disappear()

    # Verify count STAYS THE SAME (always replace in UI)
    new_count = align_page.get_run_columns().count()
    print(f"DEBUG: New count after switch: {new_count}")
    print(f"DEBUG: Expected count: {initial_count}")
    align_page.expect_run_count(initial_count)
    print("DEBUG: Replacement verified!")
