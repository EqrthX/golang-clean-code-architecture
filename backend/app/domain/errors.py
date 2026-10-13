class DuplicateEmailError(Exception):
    """Registration cannot use an email already stored in the database."""


class PasswordVerifyError(Exception):
    """Login verify password not match"""


class InvalidTokenError(Exception):
    """Token is invalid, expired, revoked, or belongs to a missing user."""


class ResourceNotFoundError(Exception):
    """A requested public resource is unavailable to this user."""
