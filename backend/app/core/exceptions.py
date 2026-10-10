"""App-level exceptions (handled in ``main`` or raised into FastAPI)."""

from app.core.auth_policies import AUTH_UNAUTHORIZED_DETAIL


class AuthRequired(Exception):
    """Raised when authentication fails; handler clears cookies on the 401."""

    def __init__(self, detail: str = AUTH_UNAUTHORIZED_DETAIL) -> None:
        self.detail = detail
        super().__init__(detail)
