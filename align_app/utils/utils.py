import asyncio
from functools import wraps
from trame.app import asynchronous

_id_counter = 0


def get_id():
    """
    Returns a unique ID.

    Returns:
        str: A unique ID
    """
    global _id_counter
    _id_counter += 1
    return str(_id_counter)


def readable(snake_or_kebab: str):
    """
    Converts a snake_case or kebab-case string to a human-readable format.

    Args:
        snake_or_kebab (str): The input string in snake_case or kebab-case.

    Returns:
        str: The human-readable string.
    """
    return snake_or_kebab.replace("_", " ").replace("-", " ").title()


def sentence(text: str):
    return text[0].upper() + text[1:]


def noop():
    """
    A no-operation function.

    Returns:
        None
    """
    return


def debounce(wait, state=None):
    """Pass Trame state as arg if function modifies state"""

    def decorator(func):
        task = None

        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal task
            if task:
                task.cancel()

            async def debounced():
                await asyncio.sleep(wait)
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
                if state:
                    state.flush()

            task = asynchronous.create_task(debounced())

        return wrapper

    return decorator
