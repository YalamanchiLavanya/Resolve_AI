from functools import wraps

from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

STAFF_ROLES = ("SUPPORT_AGENT", "TEAM_LEAD", "ADMIN")


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def current_user():
    """Return (user_id, role) from the verified JWT."""
    return int(get_jwt_identity()), get_jwt().get("role")


def role_required(*roles):
    """Require a valid JWT. If roles are given, the user's role must match."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            _, role = current_user()
            if roles and role not in roles:
                raise ApiError("You do not have permission for this action", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
