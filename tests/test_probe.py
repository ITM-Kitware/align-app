import pytest
from align_app.adm.probe import Probe
from align_app.adm.state_builder import probe_to_dict
from align_utils.models import InputOutputItem, InputData


def create_test_input_output_item(
    scenario_id="test-scenario",
    scene_id="scene-1",
    include_unstructured=True,
    full_state=None,
    original_index=0,
):
    if full_state is None:
        full_state = {
            "meta_info": {"scene_id": scene_id},
        }
        if include_unstructured:
            full_state["unstructured"] = "Test scenario description"

    input_data = InputData(
        scenario_id=scenario_id,
        full_state=full_state,
        state="Test state",
        choices=[
            {"unstructured": "Choice 1"},
            {"unstructured": "Choice 2"},
        ],
    )

    return InputOutputItem(input=input_data, output=None, original_index=original_index)


class TestProbeFactoryMethod:
    def test_from_input_output_item_success(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.probe_id == "test-scenario.scene-1"
        assert probe.scene_id == "scene-1"
        assert probe.scenario_id == "test-scenario"
        assert probe.display_state == "Test scenario description"
        assert probe.item == item

    def test_from_input_output_item_without_unstructured(self):
        item = create_test_input_output_item(include_unstructured=False)
        probe = Probe.from_input_output_item(item)

        assert probe.probe_id == "test-scenario.scene-1"
        assert probe.display_state is None

    def test_from_input_output_item_missing_input(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InputOutputItem(input=None, output=None, original_index=0)

    def test_from_input_output_item_missing_full_state(self):
        input_data = InputData(scenario_id="test", full_state=None)
        item = InputOutputItem(input=input_data, output=None, original_index=0)

        with pytest.raises(
            ValueError, match="InputOutputItem must have input and full_state"
        ):
            Probe.from_input_output_item(item)

    def test_from_input_output_item_missing_meta_info(self):
        full_state = {"some_field": "value"}
        item = create_test_input_output_item(full_state=full_state)

        with pytest.raises(ValueError, match="missing required meta_info.scene_id"):
            Probe.from_input_output_item(item)

    def test_from_input_output_item_missing_scene_id(self):
        full_state = {"meta_info": {}}
        item = create_test_input_output_item(full_state=full_state)

        with pytest.raises(ValueError, match="missing required meta_info.scene_id"):
            Probe.from_input_output_item(item)


class TestProbeProperties:
    def test_scenario_id_property(self):
        item = create_test_input_output_item(scenario_id="custom-scenario")
        probe = Probe.from_input_output_item(item)

        assert probe.scenario_id == "custom-scenario"

    def test_full_state_property(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.full_state is not None
        assert "meta_info" in probe.full_state
        assert probe.full_state["meta_info"]["scene_id"] == "scene-1"

    def test_state_property(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.state == "Test state"

    def test_choices_property(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert len(probe.choices) == 2
        assert probe.choices[0]["unstructured"] == "Choice 1"


class TestProbeAttributeAccess:
    def test_attribute_probe_id(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.probe_id == "test-scenario.scene-1"

    def test_attribute_scene_id(self):
        item = create_test_input_output_item(scene_id="custom-scene")
        probe = Probe.from_input_output_item(item)

        assert probe.scene_id == "custom-scene"

    def test_attribute_scenario_id(self):
        item = create_test_input_output_item(scenario_id="custom-scenario")
        probe = Probe.from_input_output_item(item)

        assert probe.scenario_id == "custom-scenario"

    def test_attribute_display_state(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.display_state == "Test scenario description"

    def test_attribute_full_state(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.full_state["meta_info"]["scene_id"] == "scene-1"

    def test_attribute_state(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert probe.state == "Test state"

    def test_attribute_choices(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        assert len(probe.choices) == 2

    def test_attribute_invalid_key(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        with pytest.raises(AttributeError):
            _ = probe.invalid


class TestProbeValidation:
    def test_extra_fields_forbidden(self):
        item = create_test_input_output_item()

        with pytest.raises(ValueError):
            Probe(
                item=item,
                probe_id="test.scene-1",
                scene_id="scene-1",
                display_state=None,
                extra_field="not allowed",
            )

    def test_required_fields(self):
        item = create_test_input_output_item()

        with pytest.raises(ValueError):
            Probe(item=item, probe_id="test.scene-1")


class TestProbeToDictFunction:
    def test_probe_to_dict_includes_all_fields(self):
        item = create_test_input_output_item()
        probe = Probe.from_input_output_item(item)

        probe_dict = probe_to_dict(probe)

        assert probe_dict["probe_id"] == "test-scenario.scene-1"
        assert probe_dict["scene_id"] == "scene-1"
        assert probe_dict["scenario_id"] == "test-scenario"
        assert probe_dict["display_state"] == "Test scenario description"
        assert probe_dict["full_state"]["meta_info"]["scene_id"] == "scene-1"
        assert probe_dict["state"] == "Test state"
        assert len(probe_dict["choices"]) == 2

    def test_probe_to_dict_without_display_state(self):
        item = create_test_input_output_item(include_unstructured=False)
        probe = Probe.from_input_output_item(item)

        probe_dict = probe_to_dict(probe)

        assert "display_state" in probe_dict
        assert probe_dict["display_state"] is None
