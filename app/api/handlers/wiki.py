"""HTTP handling for Wiki status and update endpoints."""

from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.api.schema import (
    UpdateChangesResponse,
    UpdateWikiRequest,
    UpdateWikiResponse,
    WikiStatusResponse,
    WorkflowContext,
)
from app.config.settings import settings
from app.workflows.source_manifest import SourceManifestError
from app.workflows.update_wiki import (
    UpdateExecutionError,
    UpdateSourceNotReadyError,
    WikiNotInitializedError,
    preview_update,
    run_update,
)
from app.workflows.wiki_status import get_wiki_status


async def handle_wiki_status() -> WikiStatusResponse:
    context = _workflow_context()
    return await run_in_threadpool(get_wiki_status, context)


async def handle_update_changes() -> UpdateChangesResponse:
    context = _workflow_context()
    try:
        return await run_in_threadpool(preview_update, context)
    except (WikiNotInitializedError, UpdateSourceNotReadyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except SourceManifestError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_update_wiki(
    request: UpdateWikiRequest,
) -> UpdateWikiResponse:
    context = _workflow_context()
    try:
        return await run_in_threadpool(
            run_update,
            context,
            message=request.message,
        )
    except (
        WikiNotInitializedError,
        UpdateSourceNotReadyError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except UpdateExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _workflow_context() -> WorkflowContext:
    return WorkflowContext(project_root=settings.wiki_project_root.resolve())
