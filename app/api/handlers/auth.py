"""HTTP handling for authentication endpoints."""

from fastapi import HTTPException, Response, status
from starlette.concurrency import run_in_threadpool

from app.api.schema import (
    AuthenticatedUserContext,
    CurrentUserResponse,
    LoginRequest,
)
from app.workflows.auth import (
    AccessControlConfigurationError,
    authenticate,
    create_session,
    current_user_response,
    delete_session,
)
from app.config.settings import settings


async def handle_login(
    request: LoginRequest,
    response: Response,
) -> CurrentUserResponse:
    try:
        user = await run_in_threadpool(
            authenticate,
            request.username,
            request.password,
        )
    except AccessControlConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误。",
        )

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_session(user.user_id),
        max_age=settings.auth_session_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )
    return current_user_response(user)


def handle_current_user(
    user: AuthenticatedUserContext,
) -> CurrentUserResponse:
    return current_user_response(user)


def handle_logout(
    response: Response,
    session_token: str | None,
) -> None:
    delete_session(session_token)
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
