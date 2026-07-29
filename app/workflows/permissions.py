"""Build and cache Deep Agent permissions for each access workflow."""

from __future__ import annotations

from threading import RLock

from deepagents import FilesystemPermission

from app.api.schema import AuthenticatedUserContext, DepartmentConfig


_SENSITIVE_PATHS = [
    "/.env",
    "/.env.*",
    "/**/.env",
    "/**/.env.*",
    "/access-control.json",
    "/**/access-control.json",
]
_NAVIGATION_PATHS = [
    "/",
    "/company-handbook",
    "/company-handbook/公司管理制度",
    "/generated-wiki",
    "/generated-wiki/drafts",
    "/generated-wiki/drafts/公司管理制度",
    "/wiki-instructions.md",
]
_PERMISSION_LOCK = RLock()
_PERMISSION_CACHE: dict[
    tuple[str, str],
    tuple[FilesystemPermission, ...],
] = {}


def get_chat_permissions(
    user: AuthenticatedUserContext,
    department: DepartmentConfig,
) -> tuple[FilesystemPermission, ...]:
    """Return cached filesystem rules for an admin or department."""

    scope = "admin" if user.role == "admin" else department.code
    key = (user.config_revision, scope)
    with _PERMISSION_LOCK:
        cached = _PERMISSION_CACHE.get(key)
        if cached is not None:
            return cached
        if user.role == "admin":
            permissions = (
                FilesystemPermission(
                    operations=["read", "write"],
                    paths=_SENSITIVE_PATHS,
                    mode="deny",
                ),
                FilesystemPermission(
                    operations=["read", "write"],
                    paths=["/**"],
                    mode="allow",
                ),
            )
        else:
            readable = list(
                dict.fromkeys(
                    [
                        *_NAVIGATION_PATHS,
                        *department.read_paths,
                    ]
                )
            )
            permissions = (
                FilesystemPermission(
                    operations=["read", "write"],
                    paths=_SENSITIVE_PATHS,
                    mode="deny",
                ),
                FilesystemPermission(
                    operations=["read"],
                    paths=readable,
                    mode="allow",
                ),
                FilesystemPermission(
                    operations=["read"],
                    paths=["/**"],
                    mode="deny",
                ),
                FilesystemPermission(
                    operations=["write"],
                    paths=["/**"],
                    mode="deny",
                ),
            )
        _remove_old_revisions(user.config_revision)
        _PERMISSION_CACHE[key] = permissions
        return permissions


def _remove_old_revisions(current_revision: str) -> None:
    stale = [
        key
        for key in _PERMISSION_CACHE
        if key[0] != current_revision
    ]
    for key in stale:
        _PERMISSION_CACHE.pop(key, None)
