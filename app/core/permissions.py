"""Reusable authorization guards."""

from collections.abc import Collection

from app.schemas.auth import CurrentUser

PRIVILEGED_ROLES = frozenset({"owner", "manager"})


def require_role(current_user: CurrentUser, roles: Collection[str], action: str) -> None:
    """Ensure the current user has one of the required roles."""
    if current_user.role not in roles:
        raise PermissionError(f"Role '{current_user.role}' cannot {action}")
