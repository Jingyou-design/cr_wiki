"""Run JSON-backed authentication, sessions, and authorization workflows."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from pathlib import Path
from threading import RLock
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.schema import (
    AccessControlConfig,
    AuthenticatedUserContext,
    CurrentUserResponse,
    DepartmentConfig,
    UserConfig,
)
from app.config.settings import settings


class AccessControlConfigurationError(RuntimeError):
    """Raised when the JSON access-control configuration is invalid."""


_CONFIG_LOCK = RLock()
_CONFIG_SIGNATURE: tuple[str, int, int] | None = None
_CONFIG: AccessControlConfig | None = None
_CONFIG_REVISION = ""

_SESSION_LOCK = RLock()
_SESSIONS: dict[str, tuple[str, float]] = {}


def load_access_control() -> tuple[AccessControlConfig, str]:
    """Load and cache the validated JSON configuration."""

    global _CONFIG_SIGNATURE, _CONFIG, _CONFIG_REVISION

    path = _access_control_path()
    try:
        stat = path.stat()
    except OSError as exc:
        raise AccessControlConfigurationError(
            f"访问控制配置不存在或无法读取：{path}"
        ) from exc
    signature = (str(path), stat.st_mtime_ns, stat.st_size)
    with _CONFIG_LOCK:
        if _CONFIG is not None and signature == _CONFIG_SIGNATURE:
            return _CONFIG, _CONFIG_REVISION
        try:
            content = path.read_bytes()
            config = AccessControlConfig.model_validate_json(content)
        except (OSError, UnicodeError, ValidationError, ValueError) as exc:
            raise AccessControlConfigurationError(
                f"访问控制配置格式无效：{path}"
            ) from exc
        _validate_access_control(config)
        _CONFIG = config
        _CONFIG_SIGNATURE = signature
        _CONFIG_REVISION = hashlib.sha256(content).hexdigest()[:16]
        return config, _CONFIG_REVISION


def authenticate(username: str, password: str) -> AuthenticatedUserContext | None:
    """Validate plaintext prototype credentials from the JSON configuration."""

    config, revision = load_access_control()
    normalized = username.strip()
    user = next(
        (item for item in config.users if item.username == normalized),
        None,
    )
    supplied = password.encode("utf-8")
    expected = (user.password if user else "invalid-user-password").encode(
        "utf-8"
    )
    password_matches = hmac.compare_digest(supplied, expected)
    if user is None or not user.is_active or not password_matches:
        return None
    return _identity(config, revision, user)


def create_session(user_id: str) -> str:
    """Create an opaque in-memory browser session."""

    token = secrets.token_urlsafe(32)
    expires_at = time.time() + settings.auth_session_ttl_seconds
    with _SESSION_LOCK:
        _remove_expired_sessions()
        _SESSIONS[token] = (user_id, expires_at)
    return token


def delete_session(token: str | None) -> None:
    if not token:
        return
    with _SESSION_LOCK:
        _SESSIONS.pop(token, None)


def get_current_user(
    session_token: Annotated[
        str | None,
        Cookie(alias=settings.auth_cookie_name),
    ] = None,
) -> AuthenticatedUserContext:
    """Return the current active user or raise HTTP 401/503."""

    if not session_token:
        _unauthorized()
    with _SESSION_LOCK:
        session = _SESSIONS.get(session_token)
        if session is None or session[1] <= time.time():
            _SESSIONS.pop(session_token, None)
            _unauthorized()
        user_id = session[0]
    try:
        config, revision = load_access_control()
    except AccessControlConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    user = next((item for item in config.users if item.id == user_id), None)
    if user is None or not user.is_active:
        delete_session(session_token)
        _unauthorized()
    return _identity(config, revision, user)


def require_admin(
    user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> AuthenticatedUserContext:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号没有 Wiki 管理权限。",
        )
    return user


def current_user_response(
    user: AuthenticatedUserContext,
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.user_id,
        username=user.username,
        department_code=user.department_code,
        role=user.role,
        config_revision=user.config_revision,
    )


def department_for(
    user: AuthenticatedUserContext,
) -> DepartmentConfig:
    config, revision = load_access_control()
    if revision != user.config_revision:
        current = next(
            (item for item in config.users if item.id == user.user_id),
            None,
        )
        if current is None:
            raise AccessControlConfigurationError("当前用户已从配置中删除。")
        user = _identity(config, revision, current)
    department = next(
        (
            item
            for item in config.departments
            if item.code == user.department_code
        ),
        None,
    )
    if department is None:
        raise AccessControlConfigurationError(
            f"用户所属部门不存在：{user.department_code}"
        )
    return department


def _identity(
    config: AccessControlConfig,
    revision: str,
    user: UserConfig,
) -> AuthenticatedUserContext:
    department = next(
        (
            item
            for item in config.departments
            if item.code == user.department_code
        ),
        None,
    )
    if department is None:
        raise AccessControlConfigurationError(
            f"用户 {user.username} 引用了不存在的部门。"
        )
    return AuthenticatedUserContext(
        user_id=user.id,
        username=user.username,
        department_code=department.code,
        role=user.role,
        config_revision=revision,
    )


def _validate_access_control(config: AccessControlConfig) -> None:
    department_codes = [item.code for item in config.departments]
    user_ids = [item.id for item in config.users]
    usernames = [item.username for item in config.users]
    if len(department_codes) != len(set(department_codes)):
        raise AccessControlConfigurationError("部门 code 不能重复。")
    if len(user_ids) != len(set(user_ids)):
        raise AccessControlConfigurationError("用户 id 不能重复。")
    if len(usernames) != len(set(usernames)):
        raise AccessControlConfigurationError("用户名不能重复。")
    known_departments = set(department_codes)
    for user in config.users:
        if user.department_code not in known_departments:
            raise AccessControlConfigurationError(
                f"用户 {user.username} 引用了不存在的部门。"
            )
    for department in config.departments:
        for path in department.read_paths:
            if not path.startswith("/") or ".." in Path(path).parts:
                raise AccessControlConfigurationError(
                    f"部门 {department.code} 包含无效权限路径：{path}"
                )


def _access_control_path() -> Path:
    path = settings.access_control_file.expanduser()
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def _remove_expired_sessions() -> None:
    now = time.time()
    expired = [
        token
        for token, (_, expires_at) in _SESSIONS.items()
        if expires_at <= now
    ]
    for token in expired:
        _SESSIONS.pop(token, None)


def _unauthorized() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请先登录。",
    )
