from __future__ import annotations

import uuid

import jwt
from fastapi import HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_access_header,
    set_refresh_cookies,
)
from app.core.enums import UserRole
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    verify_password,
)
from app.crud import auth, user
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)


async def register_user(db: AsyncSession, payload: RegisterRequest) -> RegisterResponse:
    """Create a new USER account or raise if the account already exists.

    Args:
        db: Async SQLAlchemy session.
        payload: Registration body (account, password, name).

    Returns:
        ``RegisterResponse`` with account, name, role, and success message.

    Raises:
        HTTPException: 409 if an account with the same ``account`` already exists.
    """
    existing_user = await user.get_user_by_account(db, payload.account)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
        )

    try:
        created_user = await user.create_user(
            db,
            account_id=payload.account,
            name=payload.name,
            password=payload.password,
            role=UserRole.USER,
            must_change_password=False,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
        ) from None

    return RegisterResponse(
        account=created_user.account_id,
        name=created_user.name,
        role=UserRole(created_user.role),
        message="Registration successful",
    )


async def login_user(
    db: AsyncSession,
    payload: LoginRequest,
    response: Response,
) -> LoginResponse:
    """Authenticate; set refresh cookies and Bearer access header.

    Args:
        db: Async SQLAlchemy session.
        payload: Login body (account, password).
        response: Used for Set-Cookie and ``Authorization`` header.

    Returns:
        ``LoginResponse`` profile fields (no tokens in JSON).

    Raises:
        HTTPException: 401 if the account is missing or the password is wrong.
    """
    current_user = await user.get_user_by_account(db, payload.account)
    if current_user is None or current_user.password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account or password",
        )
    if not verify_password(payload.password, current_user.password.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account or password",
        )

    role = UserRole(current_user.role)
    access_token = create_access_token(subject=current_user.id, role=role)
    refresh_raw = await auth.create_refresh_token(db, current_user.id)
    csrf = generate_opaque_token()
    set_refresh_cookies(
        response,
        refresh_token=refresh_raw,
        csrf_token=csrf,
    )
    set_access_header(response, access_token)
    return LoginResponse(
        account=current_user.account_id,
        name=current_user.name,
        role=role,
        preferred_language=user.preferred_language_code(current_user),
        must_change_password=current_user.password.must_change_password,
    )


async def logout_user(
    db: AsyncSession,
    request: Request,
    response: Response,
) -> None:
    """Revoke refresh tokens for the cookie session and clear cookies.

    Uses the refresh cookie only (no Bearer required) so expired access can
    still log out. CSRF is enforced by middleware on this path.
    """
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        user_id = await auth.get_active_user_id_for_refresh(db, raw)
        if user_id is not None:
            await auth.revoke_all_for_user(db, user_id)
    clear_auth_cookies(response)


async def get_current_user_profile(current_user: User) -> CurrentUserResponse:
    """Build the ``/users/me`` response for an authenticated user.

    Args:
        current_user: Authenticated user with password relation loaded.

    Returns:
        ``CurrentUserResponse`` with account, name, role, and preferred language.

    Raises:
        HTTPException: 401 if the user has no password row.
    """
    if current_user.password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or token expired",
        )
    return CurrentUserResponse(
        account=current_user.account_id,
        name=current_user.name,
        role=UserRole(current_user.role),
        preferred_language=user.preferred_language_code(current_user),
    )


def parse_user_id_from_token(token: str) -> uuid.UUID:
    """Decode a JWT and return the subject user id.

    Args:
        token: Raw access JWT string.

    Returns:
        UUID parsed from the token ``sub`` claim.

    Raises:
        HTTPException: 401 if the token is invalid, expired, or ``sub`` is bad.
    """
    try:
        payload = decode_access_token(token)
        return uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or token expired",
        ) from exc
