from align_app.app.runs_table_filter import compute_filter_options, filter_rows


def test_compute_filter_options_extracts_unique_values():
    rows = [
        {
            "scenario_id": "scenario_a",
            "scene_id": "scene_1",
            "decider_name": "decider_x",
            "llm_backbone_name": "llm_1",
            "alignment_summary": "aligned",
            "decision_text": "choice A",
        },
        {
            "scenario_id": "scenario_b",
            "scene_id": "scene_2",
            "decider_name": "decider_y",
            "llm_backbone_name": "llm_2",
            "alignment_summary": "not aligned",
            "decision_text": "choice B",
        },
    ]

    options = compute_filter_options(rows)

    assert options["runs_table_scenario_options"] == ["scenario_a", "scenario_b"]
    assert options["runs_table_scene_options"] == ["scene_1", "scene_2"]
    assert options["runs_table_decider_options"] == ["decider_x", "decider_y"]
    assert options["runs_table_llm_options"] == ["llm_1", "llm_2"]
    assert options["runs_table_alignment_options"] == ["aligned", "not aligned"]
    assert options["runs_table_decision_options"] == ["choice A", "choice B"]


def test_compute_filter_options_sorts_values():
    rows = [
        {
            "scenario_id": "zebra",
            "scene_id": "1",
            "decider_name": "x",
            "llm_backbone_name": "l",
            "alignment_summary": "a",
            "decision_text": "d",
        },
        {
            "scenario_id": "alpha",
            "scene_id": "2",
            "decider_name": "y",
            "llm_backbone_name": "l",
            "alignment_summary": "a",
            "decision_text": "d",
        },
    ]

    options = compute_filter_options(rows)

    assert options["runs_table_scenario_options"] == ["alpha", "zebra"]


def test_compute_filter_options_deduplicates_values():
    rows = [
        {
            "scenario_id": "same",
            "scene_id": "1",
            "decider_name": "x",
            "llm_backbone_name": "l",
            "alignment_summary": "a",
            "decision_text": "d",
        },
        {
            "scenario_id": "same",
            "scene_id": "2",
            "decider_name": "y",
            "llm_backbone_name": "l",
            "alignment_summary": "a",
            "decision_text": "d",
        },
    ]

    options = compute_filter_options(rows)

    assert options["runs_table_scenario_options"] == ["same"]


def test_filter_rows_empty_filters_returns_all():
    rows = [
        {"scenario_id": "a", "scene_id": "1"},
        {"scenario_id": "b", "scene_id": "2"},
    ]

    filters = [([], "scenario_id"), ([], "scene_id")]
    result = filter_rows(rows, filters)

    assert len(result) == 2


def test_filter_rows_single_filter():
    rows = [
        {"scenario_id": "a", "scene_id": "1"},
        {"scenario_id": "b", "scene_id": "2"},
        {"scenario_id": "a", "scene_id": "3"},
    ]

    filters = [(["a"], "scenario_id")]
    result = filter_rows(rows, filters)

    assert len(result) == 2
    assert all(r["scenario_id"] == "a" for r in result)


def test_filter_rows_multiple_values_in_filter():
    rows = [
        {"scenario_id": "a", "scene_id": "1"},
        {"scenario_id": "b", "scene_id": "2"},
        {"scenario_id": "c", "scene_id": "3"},
    ]

    filters = [(["a", "b"], "scenario_id")]
    result = filter_rows(rows, filters)

    assert len(result) == 2
    scenarios = {r["scenario_id"] for r in result}
    assert scenarios == {"a", "b"}


def test_filter_rows_multiple_filters_combine_with_and():
    rows = [
        {"scenario_id": "a", "scene_id": "1"},
        {"scenario_id": "a", "scene_id": "2"},
        {"scenario_id": "b", "scene_id": "1"},
    ]

    filters = [(["a"], "scenario_id"), (["1"], "scene_id")]
    result = filter_rows(rows, filters)

    assert len(result) == 1
    assert result[0]["scenario_id"] == "a"
    assert result[0]["scene_id"] == "1"


def test_filter_rows_no_matches_returns_empty():
    rows = [
        {"scenario_id": "a", "scene_id": "1"},
        {"scenario_id": "b", "scene_id": "2"},
    ]

    filters = [(["nonexistent"], "scenario_id")]
    result = filter_rows(rows, filters)

    assert len(result) == 0


def test_filter_rows_handles_missing_keys():
    rows = [
        {"scenario_id": "a"},
        {"scenario_id": "b", "scene_id": "1"},
    ]

    filters = [(["1"], "scene_id")]
    result = filter_rows(rows, filters)

    assert len(result) == 1
    assert result[0]["scenario_id"] == "b"
