"""
Client API for making decisions with singleton pattern.
Provides a convenient get_decision() function that manages a singleton MultiprocessDecider.
"""

import atexit
from align_utils.models import ADMResult
from .decider import MultiprocessDecider
from .types import DeciderParams

_decider = None


def _get_process_manager():
    """Get or create the process manager singleton"""
    global _decider
    if _decider is None:
        _decider = MultiprocessDecider()
    return _decider


async def get_decision(params: DeciderParams) -> ADMResult:
    """Get a decision using DeciderParams.

    Args:
        params: DeciderParams with scenario_input, alignment_target, resolved_config

    Returns:
        ADMResult with decision and choice_info
    """
    process_manager = _get_process_manager()
    return await process_manager.get_decision(params)


def cleanup():
    """Clean up resources when the module is unloaded"""
    if _decider is not None:
        _decider.shutdown()


atexit.register(cleanup)
