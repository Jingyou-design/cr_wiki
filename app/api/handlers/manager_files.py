"""HTTP handling for manager-owned source file operations."""

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.api.schema import (
    AuthenticatedUserContext,
    ManagerDirectoryCreateRequest,
    ManagerDirectoryCreateResponse,
    ManagerFileContentResponse,
    ManagerFileTreeResponse,
    ManagerFileWriteRequest,
    ManagerFileWriteResponse,
    ManagerPathMoveRequest,
    ManagerPathMoveResponse,
    WorkflowContext,
)
from app.config.settings import settings
from app.workflows.auth import AccessControlConfigurationError
from app.workflows.manager_files import (
    ManagerFileConflictError,
    ManagerDirectoryAccessError,
    ManagerDirectoryScanError,
    ManagerFileNotFoundError,
    ManagerFileOperationError,
    create_manager_directory,
    move_manager_path,
    read_manager_file,
    scan_manager_file_tree,
    write_manager_file,
)

_Result = TypeVar("_Result")


async def handle_manager_file_tree(
    user: AuthenticatedUserContext,
) -> ManagerFileTreeResponse:
    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
    try:
        return await run_in_threadpool(scan_manager_file_tree, context, user)
    except ManagerDirectoryAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except AccessControlConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ManagerDirectoryScanError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_manager_file_content(
    path: str,
    user: AuthenticatedUserContext,
) -> ManagerFileContentResponse:
    return await _run_file_operation(read_manager_file, user, path)


async def handle_manager_file_write(
    request: ManagerFileWriteRequest,
    user: AuthenticatedUserContext,
) -> ManagerFileWriteResponse:
    return await _run_file_operation(
        write_manager_file,
        user,
        request.path,
        request.content,
    )


async def handle_manager_directory_create(
    request: ManagerDirectoryCreateRequest,
    user: AuthenticatedUserContext,
) -> ManagerDirectoryCreateResponse:
    return await _run_file_operation(
        create_manager_directory,
        user,
        request.path,
    )


async def handle_manager_path_move(
    request: ManagerPathMoveRequest,
    user: AuthenticatedUserContext,
) -> ManagerPathMoveResponse:
    return await _run_file_operation(
        move_manager_path,
        user,
        request.source_path,
        request.target_path,
    )


async def _run_file_operation(
    operation: Callable[..., _Result],
    user: AuthenticatedUserContext,
    *args: Any,
) -> _Result:
    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
    try:
        return await run_in_threadpool(operation, context, user, *args)
    except ManagerDirectoryAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ManagerFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ManagerFileConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except AccessControlConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ManagerFileOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
