import secrets


def generate_session_id(length=32):
    """
    Generate a random session ID with the specified length.

    Args:
        length (int): The length of the session ID (default is 32).

    Returns:
        str: The randomly generated session ID.
    """
    return secrets.token_hex(length)
