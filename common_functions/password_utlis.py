"""This module provides utility functions for hashing and checking passwords using bcrypt."""

import bcrypt


def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Args:
        plain_password (str): The raw password to hash.

    Returns:
        str: The hashed password.
    """
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def check_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against the hashed version.

    Args:
        plain_password (str): The input password to check.
        hashed_password (str): The stored hashed password from DB.

    Returns:
        bool: True if match, else False.
    """
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


