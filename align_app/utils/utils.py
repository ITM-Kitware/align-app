import asyncio
from functools import wraps
import copy
from trame.app import asynchronous
import re

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


def readable(snake_or_kebab_or_camel: str):
    """
    Converts a snake_case, kebab-case, or camelCase string to a human-readable format.

    Args:
        snake_or_kebab_or_camel (str): The input string in snake_case, kebab-case, or camelCase.

    Returns:
        str: The human-readable string.
    """
    # Handle camelCase by inserting spaces before capital letters
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", snake_or_kebab_or_camel)
    # Handle snake_case and kebab-case
    result = s.replace("_", " ").replace("-", " ").title()
    # Fix specific acronyms
    result = result.replace("Icl", "ICL")
    return result


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


def merge_dicts(base_dict, override_dict):
    """
    Recursively merge two dictionaries, with the override_dict values taking precedence.
    """
    result = copy.deepcopy(base_dict)

    for key, override_value in override_dict.items():
        if key not in result:
            result[key] = copy.deepcopy(override_value)
            continue

        base_value = result[key]

        if isinstance(base_value, dict) and isinstance(override_value, dict):
            result[key] = merge_dicts(base_value, override_value)
        else:
            result[key] = copy.deepcopy(override_value)

    return result


def create_nested_dict_from_path(path_keys, value):
    """
    Creates a nested dictionary from a list of keys with the specified value at the leaf.

    Example:
    create_nested_dict_from_path(["instance", "model_name"], "my_model") returns
    {"instance": {"model_name": "my_model"}}
    """
    result = {}
    current = result

    # Build the nested structure
    for key in path_keys[:-1]:
        current[key] = {}
        current = current[key]

    # Set the leaf value
    if path_keys:
        current[path_keys[-1]] = value

    return result


def sentence_lines(text: str):
    """Convert newline-separated text into sentences with capital first letter and period ending."""
    lines = text.split("\n")
    processed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Capitalize first letter, add period if missing
        line = line[0].upper() + line[1:]
        if not line.endswith("."):
            line += "."
        processed.append(line)
    return " ".join(processed)
