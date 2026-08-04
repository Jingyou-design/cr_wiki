"""Scan source directories visible to the current department manager."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.api.schema import (
    AuthenticatedUserContext,
    ManagerDirectoryCreateResponse,
    ManagerFileContentResponse,
    ManagerFileNode,
    ManagerFileTreeResponse,
    ManagerFileWriteResponse,
    ManagerPathMoveResponse,
    WorkflowContext,
)
from app.workflows.auth import department_for


class ManagerDirectoryAccessError(RuntimeError):
    """Raised when a manager has no valid company-handbook directory scope."""


class ManagerDirectoryScanError(RuntimeError):
    """Raised when an authorized directory cannot be scanned."""


class ManagerFileNotFoundError(RuntimeError):
    """Raised when a requested manager-owned path does not exist."""


class ManagerFileConflictError(RuntimeError):
    """Raised when a requested filesystem operation conflicts with state."""


class ManagerFileOperationError(RuntimeError):
    """Raised when an authorized filesystem operation cannot be completed."""


_SOURCE_PREFIX = PurePosixPath("/company-handbook")
_SOURCE_RULE_PREFIX = "/company-handbook/"
_RECURSIVE_SUFFIX = "/**"


def scan_manager_file_tree(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
) -> ManagerFileTreeResponse:
    """Return trees below recursive company-handbook paths for one manager."""

    roots = manager_source_roots(context, user)
    nodes: list[ManagerFileNode] = []
    for virtual_root in roots:
        physical_root = _physical_path(context, virtual_root)
        if not physical_root.exists():
            continue
        if not physical_root.is_dir() or physical_root.is_symlink():
            raise ManagerDirectoryScanError(
                f"授权资料目录无效：{_display_path(virtual_root)}"
            )
        nodes.append(_scan_directory(physical_root, virtual_root))
    return ManagerFileTreeResponse(roots=nodes)


def manager_source_roots(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
) -> tuple[PurePosixPath, ...]:
    """Derive company source roots from the current department read paths."""

    department = department_for(user)
    roots: list[PurePosixPath] = []
    for rule in department.read_paths:
        normalized = "/" + rule.strip().lstrip("/")
        if not normalized.startswith(_SOURCE_RULE_PREFIX):
            continue
        if not normalized.endswith(_RECURSIVE_SUFFIX):
            continue

        department_path = (
            normalized.removeprefix(_SOURCE_RULE_PREFIX)
            .removesuffix("**")
            .strip("/")
        )
        root = _SOURCE_PREFIX / department_path
        _physical_path(context, root)
        if root not in roots:
            roots.append(root)

    return tuple(roots)


def resolve_manager_path(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
    requested_path: str,
) -> Path:
    """Resolve one requested path inside the current department source roots."""

    requested = PurePosixPath("/" + requested_path.lstrip("/"))
    physical = _physical_path(context, requested)
    resolved = physical.resolve(strict=False)
    allowed_roots = (
        _physical_path(context, root).resolve()
        for root in manager_source_roots(context, user)
    )

    if not any(
        resolved == root or resolved.is_relative_to(root)
        for root in allowed_roots
    ):
        raise ManagerDirectoryAccessError(
            "该文件不属于当前经理的部门目录。"
        )
    return resolved


def read_manager_file(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
    requested_path: str,
) -> ManagerFileContentResponse:
    """Read one authorized UTF-8 source file."""

    physical = resolve_manager_path(context, user, requested_path)
    if not physical.exists() or not physical.is_file():
        raise ManagerFileNotFoundError("请求的文件不存在。")

    try:
        content = physical.read_text(encoding="utf-8")
        size = physical.stat().st_size
    except OSError as exc:
        raise ManagerFileOperationError("无法读取请求的文件。") from exc

    return ManagerFileContentResponse(
        path=_physical_display_path(context, physical),
        content=content,
        size=size,
    )


def write_manager_file(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
    requested_path: str,
    content: str,
) -> ManagerFileWriteResponse:
    """Create or atomically replace one authorized UTF-8 source file."""

    physical = resolve_manager_path(context, user, requested_path)
    existed = physical.exists()
    if existed and not physical.is_file():
        raise ManagerFileConflictError("目标路径不是文件。")
    _require_parent_directory(physical)

    temporary = physical.with_name(f".{physical.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(physical)
        size = physical.stat().st_size
    except OSError as exc:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
        raise ManagerFileOperationError("无法保存请求的文件。") from exc

    return ManagerFileWriteResponse(
        status="updated" if existed else "created",
        path=_physical_display_path(context, physical),
        size=size,
    )


def create_manager_directory(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
    requested_path: str,
) -> ManagerDirectoryCreateResponse:
    """Create one authorized source directory."""

    physical = resolve_manager_path(context, user, requested_path)
    if physical.exists():
        raise ManagerFileConflictError("目标路径已经存在。")
    _require_parent_directory(physical)

    try:
        physical.mkdir()
    except OSError as exc:
        raise ManagerFileOperationError("无法创建请求的目录。") from exc

    return ManagerDirectoryCreateResponse(
        path=_physical_display_path(context, physical),
    )


def move_manager_path(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
    source_path: str,
    target_path: str,
) -> ManagerPathMoveResponse:
    """Rename or move one authorized source file or directory."""

    source = resolve_manager_path(context, user, source_path)
    target = resolve_manager_path(context, user, target_path)
    if not source.exists():
        raise ManagerFileNotFoundError("需要移动的文件或目录不存在。")
    if target.exists():
        raise ManagerFileConflictError("目标路径已经存在。")

    source_roots = (
        _physical_path(context, root).resolve()
        for root in manager_source_roots(context, user)
    )
    if any(source == root for root in source_roots):
        raise ManagerFileConflictError("不能移动部门授权根目录。")
    if source.is_dir() and target.is_relative_to(source):
        raise ManagerFileConflictError("不能把目录移动到它自身内部。")
    _require_parent_directory(target)

    path_type = "directory" if source.is_dir() else "file"
    try:
        source.rename(target)
    except OSError as exc:
        raise ManagerFileOperationError(
            "无法重命名或移动请求的路径。"
        ) from exc

    return ManagerPathMoveResponse(
        source_path=_physical_display_path(context, source),
        target_path=_physical_display_path(context, target),
        type=path_type,
    )


def _scan_directory(
    physical: Path,
    virtual: PurePosixPath,
) -> ManagerFileNode:
    try:
        items = [
            item
            for item in physical.iterdir()
            if not item.is_symlink() and not item.name.startswith(".")
        ]
    except OSError as exc:
        raise ManagerDirectoryScanError(
            f"无法扫描授权资料目录：{_display_path(virtual)}"
        ) from exc

    items.sort(
        key=lambda item: (
            0 if item.is_dir() else 1,
            item.name.casefold(),
        )
    )
    children: list[ManagerFileNode] = []
    for item in items:
        child_virtual = virtual / item.name
        if item.is_dir():
            children.append(_scan_directory(item, child_virtual))
        elif item.is_file():
            children.append(
                ManagerFileNode(
                    name=item.name,
                    path=_display_path(child_virtual),
                    type="file",
                    size=item.stat().st_size,
                )
            )

    return ManagerFileNode(
        name=physical.name,
        path=_display_path(virtual),
        type="directory",
        children=children,
    )


def _physical_path(
    context: WorkflowContext,
    virtual: PurePosixPath,
) -> Path:
    root = context.project_root.expanduser().resolve()
    source_root = (root / "company-handbook").resolve()
    relative = virtual.relative_to("/")
    physical = root.joinpath(*relative.parts)

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ManagerDirectoryAccessError(
                "授权资料路径中不允许包含符号链接。"
            )

    if not physical.resolve(strict=False).is_relative_to(source_root):
        raise ManagerDirectoryAccessError(
            "授权资料路径越出 company-handbook。"
        )
    return physical


def _display_path(path: PurePosixPath) -> str:
    return path.as_posix().lstrip("/")


def _require_parent_directory(path: Path) -> None:
    if not path.parent.exists() or not path.parent.is_dir():
        raise ManagerFileNotFoundError("目标路径的上级目录不存在。")


def _physical_display_path(
    context: WorkflowContext,
    physical: Path,
) -> str:
    root = context.project_root.expanduser().resolve()
    return physical.resolve(strict=False).relative_to(root).as_posix()
