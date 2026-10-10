from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    OkResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """Register a new user account.

    Args:
        payload: Registration body (account, password, name).
        db: Async SQLAlchemy session (injected).

    Returns:
        ``RegisterResponse`` for the created account.

    Raises:
        HTTPException: 409 if the account already exists.
    """
    return await auth_service.register_user(db, payload)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Log in; set refresh cookies and Bearer access header.

    Args:
        payload: Login body (account, password).
        response: Used for Set-Cookie and ``Authorization``.
        db: Async SQLAlchemy session (injected).

    Returns:
        ``LoginResponse`` profile fields (tokens are not in JSON).

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    return await auth_service.login_user(db, payload, response)


@router.post("/logout", response_model=OkResponse)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OkResponse:
    """Revoke refresh tokens for the cookie session and clear cookies.

    CSRF is required (middleware). Bearer is not required so expired access
    can still log out.
    """
    await auth_service.logout_user(db, request, response)
    return OkResponse()
