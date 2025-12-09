from typing import Optional, Any, Dict
from pydantic import BaseModel
from align_utils.models import InputOutputItem


def get_probe_id(item: InputOutputItem) -> str:
    """Extract probe_id from InputOutputItem in format '{scenario_id}.{scene_id}'."""
    if not item.input or not item.input.full_state:
        raise ValueError("InputOutputItem must have input and full_state")

    full_state = item.input.full_state
    if "meta_info" not in full_state or "scene_id" not in full_state["meta_info"]:
        raise ValueError("InputOutputItem missing required meta_info.scene_id")

    scene_id = full_state["meta_info"]["scene_id"]
    return f"{item.input.scenario_id}.{scene_id}"


class Probe(BaseModel):
    """
    Wrapper around InputOutputItem that adds derived fields for convenient access.

    This model combines the original align-utils InputOutputItem with application-specific
    derived fields like probe_id, scene_id, and display_state. It provides type-safe access
    to scenario data throughout the application.

    Attributes:
        item: The original InputOutputItem from align-utils containing input/output data
        probe_id: Unique identifier combining scenario_id and scene_id (e.g., "DryRunEval-MJ2-eval.MJ2-1")
        scene_id: The scene identifier extracted from full_state.meta_info.scene_id
        display_state: Optional display text from full_state.unstructured
    """

    item: InputOutputItem
    probe_id: str
    scene_id: str
    display_state: Optional[str] = None

    model_config = {"extra": "forbid"}

    @classmethod
    def from_input_output_item(cls, item: InputOutputItem) -> "Probe":
        """
        Factory method to create a Probe from an InputOutputItem.

        Automatically derives probe_id, scene_id, and display_state from the input data.

        Args:
            item: InputOutputItem from align-utils

        Returns:
            Probe instance with derived fields populated

        Raises:
            ValueError: If required fields are missing from the input data
        """
        probe_id = get_probe_id(item)
        full_state = item.input.full_state
        assert full_state is not None
        scene_id = full_state["meta_info"]["scene_id"]

        display_state = full_state.get("unstructured")

        return cls(
            item=item,
            probe_id=probe_id,
            scene_id=scene_id,
            display_state=display_state,
        )

    @property
    def scenario_id(self) -> str:
        """Convenience property to access scenario_id from the input."""
        return self.item.input.scenario_id

    @property
    def full_state(self) -> Optional[Dict[str, Any]]:
        """Convenience property to access full_state from the input."""
        return self.item.input.full_state

    @property
    def state(self) -> Optional[str]:
        """Convenience property to access state from the input."""
        return self.item.input.state

    @property
    def choices(self) -> Optional[list]:
        """Convenience property to access choices from the input."""
        return self.item.input.choices

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Probe to dictionary representation for serialization.

        Returns a dict with all probe fields suitable for JSON serialization
        or passing to hydration functions.
        """
        return {
            "probe_id": self.probe_id,
            "scene_id": self.scene_id,
            "scenario_id": self.scenario_id,
            "display_state": self.display_state,
            "full_state": self.full_state,
            "state": self.state,
            "choices": self.choices,
        }
