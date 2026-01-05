"""Discovery of built-in ADM configurations from align-system."""

from pathlib import Path
from typing import Dict, List, Any, Set
import align_system

ADM_BLACKLIST: Set[str] = {
    "hybrid_kaleido",
    "hybrid_regression",
    "oracle",
    "outlines_persona",
    "outlines_regression_aligned",
    "outlines_regression_aligned_comparative",
    "outlines_transformers_structured_aligned",
    "outlines_transformers_structured_baseline",
    "persona",
    "random",
    "relevance_oracle",
    "single_kdma_aligned",
    "single_kdma_baseline",
    "tagging_aligned",
    "tagging_baseline",
    "tagging_fewshot_aligned",
}


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


def _add_adm(
    categories: Dict[str, List[Dict[str, Any]]],
    name: str,
    config_path: str,
) -> None:
    """Add an ADM to the categories dict if not blacklisted."""
    if name in ADM_BLACKLIST:
        return

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


def discover_system_adms() -> Dict[str, List[Dict[str, Any]]]:
    """Scan align-system ADM configs and return categorized list.

    Returns:
        Dict mapping category names to lists of ADM info dicts.
        Each ADM dict has: name, config_path, title
    """
    adm_dir = get_system_adm_configs_dir()
    categories: Dict[str, List[Dict[str, Any]]] = {}

    top_level_names: Set[str] = set()
    for yaml_file in sorted(adm_dir.glob("*.yaml")):
        name = yaml_file.stem
        top_level_names.add(name)
        _add_adm(categories, name, f"adm/{yaml_file.name}")

    for subdir in sorted(adm_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name in top_level_names:
            continue
        for yaml_file in sorted(subdir.glob("*.yaml")):
            name = yaml_file.stem
            config_path = f"adm/{subdir.name}/{yaml_file.name}"
            _add_adm(categories, name, config_path)

    return categories
