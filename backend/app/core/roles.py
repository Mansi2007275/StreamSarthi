"""Role-based access control for expert-only endpoints.

The frontend hides UI based on role too, but that is UX only - this dependency
is the real gate, since the frontend check can always be bypassed.
"""

from fastapi import Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError
from app.services.db import RepoProtocol, get_repo


def require_role(*roles: str):
    def _dep(
        user: CurrentUser = Depends(get_current_user),
        repo: RepoProtocol = Depends(get_repo),
    ) -> CurrentUser:
        profile = repo.get_profile(user.id)
        if not profile or profile.get("role") not in roles:
            raise AppError(403, "FORBIDDEN", "Expert access required")
        return user

    return _dep
