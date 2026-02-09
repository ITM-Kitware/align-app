from playwright.sync_api import expect
from .page_objects.align_page import AlignPage


def test_situation_text_edit_creates_new_scene(page, align_app_server):
    """Test that editing situation text creates a new scene with edit suffix."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.expand_scenario_panel()

    original_scene = align_page.get_scene_dropdown_value_from_panel()
    original_text = align_page.get_situation_text()
    assert original_text, "Situation text should not be empty"
    assert " edit " not in original_scene, "Should start with non-edited scene"

    modified_text = original_text + " [test modification]"
    align_page.set_situation_text(modified_text)
    expect(align_page.save_probe_button).to_be_visible()
    page.wait_for_timeout(2000)
    align_page.click_save_probe_button()

    page.wait_for_timeout(500)

    new_scene = align_page.get_scene_dropdown_value_from_panel()
    assert " edit " in new_scene, (
        f"Expected scene to have ' edit ' suffix after text change. "
        f"Original: {original_scene}, New: {new_scene}"
    )


def test_situation_text_revert_restores_original_scene(page, align_app_server):
    """Test that reverting situation text to original restores the original scene."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.expand_scenario_panel()

    original_scene = align_page.get_scene_dropdown_value_from_panel()
    original_text = align_page.get_situation_text()
    assert original_text, "Situation text should not be empty"

    modified_text = original_text + " [test modification]"
    align_page.set_situation_text(modified_text)
    expect(align_page.save_probe_button).to_be_visible()
    page.wait_for_timeout(2000)
    align_page.click_save_probe_button()

    page.wait_for_timeout(500)

    edited_scene = align_page.get_scene_dropdown_value_from_panel()
    assert " edit " in edited_scene, "Scene should have edit suffix after modification"

    # Revert text to original - save button should appear since text differs from edited
    align_page.set_situation_text(original_text)
    expect(align_page.save_probe_button).to_be_visible()
    page.wait_for_timeout(2000)
    align_page.click_save_probe_button()

    page.wait_for_timeout(500)

    reverted_scene = align_page.get_scene_dropdown_value_from_panel()
    assert reverted_scene == original_scene, (
        f"Expected scene to revert to original after restoring text. "
        f"Original: {original_scene}, Reverted: {reverted_scene}"
    )


def test_situation_textarea_cursor_position_preserved(page, align_app_server):
    """Regression test: typing in situation textarea should not jump cursor to end."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)
    align_page.expand_scenario_panel()

    textarea = align_page.situation_textarea
    expect(textarea).to_be_visible()
    textarea.click()
    page.keyboard.press("Control+Home")
    page.wait_for_timeout(200)

    page.keyboard.type("X", delay=50)
    page.wait_for_timeout(1500)

    cursor_position = textarea.evaluate("el => el.selectionStart")
    assert cursor_position <= 2, (
        f"Cursor jumped to position {cursor_position} after typing at start. "
        f"Expected near position 1."
    )
