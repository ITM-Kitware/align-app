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
