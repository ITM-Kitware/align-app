from .page_objects.align_page import AlignPage


def test_config_edit_creates_new_decider(page, align_app_server):
    """Test that editing config YAML creates a new decider with edit suffix."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.expand_decider_panel()

    original_decider = align_page.get_decider_dropdown_value()
    original_config = align_page.get_config_yaml()
    assert original_config, "Config should not be empty"
    assert " - edit " not in original_decider, "Should start with non-edited decider"

    modified_config = original_config + "\ntest_key: test_value"
    align_page.set_config_yaml(modified_config)
    align_page.blur_config_textarea()

    page.wait_for_timeout(500)

    new_decider = align_page.get_decider_dropdown_value()
    assert " - edit " in new_decider, (
        f"Expected decider to have ' - edit ' suffix after config change. "
        f"Original: {original_decider}, New: {new_decider}"
    )
    assert new_decider.startswith(original_decider.split(" - edit ")[0]), (
        f"New decider should be based on original. "
        f"Original: {original_decider}, New: {new_decider}"
    )


def test_config_edit_revert_restores_original_decider(page, align_app_server):
    """Test that reverting config to original restores the original decider."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.expand_decider_panel()

    original_decider = align_page.get_decider_dropdown_value()
    original_config = align_page.get_config_yaml()
    assert original_config, "Config should not be empty"

    modified_config = original_config + "\ntest_key: test_value"
    align_page.set_config_yaml(modified_config)
    align_page.blur_config_textarea()

    page.wait_for_timeout(500)

    edited_decider = align_page.get_decider_dropdown_value()
    assert " - edit " in edited_decider, (
        "Decider should have edit suffix after modification"
    )

    align_page.set_config_yaml(original_config)
    align_page.blur_config_textarea()

    page.wait_for_timeout(500)

    reverted_decider = align_page.get_decider_dropdown_value()
    assert reverted_decider == original_decider, (
        f"Expected decider to revert to original after restoring config. "
        f"Original: {original_decider}, Reverted: {reverted_decider}"
    )


def test_config_edit_to_existing_config_reuses_decider(page, align_app_server):
    """Test that editing config to match an existing config reuses that decider."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.expand_decider_panel()

    original_config = align_page.get_config_yaml()

    modified_config_1 = original_config + "\nfirst_key: first_value"
    align_page.set_config_yaml(modified_config_1)
    align_page.blur_config_textarea()
    page.wait_for_timeout(500)

    first_edited_decider = align_page.get_decider_dropdown_value()
    assert " - edit 1" in first_edited_decider, (
        "First edit should create '- edit 1' decider"
    )

    modified_config_2 = original_config + "\nsecond_key: second_value"
    align_page.set_config_yaml(modified_config_2)
    align_page.blur_config_textarea()
    page.wait_for_timeout(500)

    second_edited_decider = align_page.get_decider_dropdown_value()
    assert " - edit 2" in second_edited_decider, (
        "Second edit should create '- edit 2' decider"
    )

    align_page.set_config_yaml(modified_config_1)
    align_page.blur_config_textarea()
    page.wait_for_timeout(500)

    reused_decider = align_page.get_decider_dropdown_value()
    assert reused_decider == first_edited_decider, (
        f"Expected decider to reuse first edited decider. "
        f"First edit: {first_edited_decider}, Reused: {reused_decider}"
    )
