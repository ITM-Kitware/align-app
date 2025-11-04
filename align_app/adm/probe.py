from typing import Optional, Any, Dict
from pydantic import BaseModel
from align_utils.models import InputOutputItem


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
            KeyError: If required fields are missing from the input data
        """
        if not item.input or not item.input.full_state:
            raise ValueError("InputOutputItem must have input and full_state")

        scene_id = item.input.full_state["meta_info"]["scene_id"]
        probe_id = f"{item.input.scenario_id}.{scene_id}"

        display_state = None
        if "unstructured" in item.input.full_state:
            display_state = item.input.full_state["unstructured"]

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

    def __getitem__(self, key: str) -> Any:
        """
        Support dictionary-style access for backward compatibility during migration.

        This allows both probe.field and probe["field"] syntax to work.
        """
        if key == "probe_id":
            return self.probe_id
        elif key == "scene_id":
            return self.scene_id
        elif key == "display_state":
            return self.display_state
        elif key == "scenario_id":
            return self.scenario_id
        elif key == "full_state":
            return self.full_state
        elif key == "state":
            return self.state
        elif key == "choices":
            return self.choices
        else:
            raise KeyError(f"Key '{key}' not found in Probe")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Support dict.get() pattern for backward compatibility.
        """
        try:
            return self[key]
        except KeyError:
            return default
