"""Discovery of built-in ADM configurations from align-system."""

from pathlib import Path
from typing import Dict, List, Any
import align_system


def get_system_adm_configs_dir() -> Path:
    """Get the path to align-system's ADM configs directory."""
    return Path(align_system.__file__).parent / "configs" / "adm"


def categorize_adm(name: str) -> str:
    """Categorize an ADM by its filename prefix."""
    if name.startswith("phase2_"):
        return "phase2"
    elif name.startswith("pipeline_"):
        return "pipeline"
    elif name.startswith("tagging_"):
        return "tagging"
    elif name.startswith("single_kdma_"):
        return "single_kdma"
    elif name.startswith("outlines_"):
        return "outlines"
    elif name.startswith("hybrid_"):
        return "hybrid"
    else:
        return "other"


def discover_system_adms() -> Dict[str, List[Dict[str, Any]]]:
    """Scan align-system ADM configs and return categorized list.

    Returns:
        Dict mapping category names to lists of ADM info dicts.
        Each ADM dict has: name, config_path, title
    """
    adm_dir = get_system_adm_configs_dir()

    categories: Dict[str, List[Dict[str, Any]]] = {}

    for yaml_file in sorted(adm_dir.glob("*.yaml")):
        name = yaml_file.stem
        config_path = f"adm/{yaml_file.name}"
        title = name.replace("_", " ").title()

        category = categorize_adm(name)
        if category not in categories:
            categories[category] = []

        categories[category].append(
            {
                "name": name,
                "config_path": config_path,
                "title": title,
            }
        )

    return categories
