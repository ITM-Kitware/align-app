"""
Decider module for Alignment App.
Provides process management for ADM models.
"""

import atexit
from .multiprocess_decider import MultiprocessDecider

_decider = None


def _get_process_manager():
    """Get or create the process manager singleton"""
    global _decider
    if _decider is None:
        _decider = MultiprocessDecider()
    return _decider


async def get_decision(prompt):
    """Get a decision for a prompt"""
    process_manager = _get_process_manager()
    return await process_manager.get_decision(prompt)


# Ensure the subprocess is cleaned up
def cleanup():
    """Clean up resources when the module is unloaded"""
    if _decider is not None:
        _decider.shutdown()


atexit.register(cleanup)
