"""FastAPI routes for company Wiki sources and workflows."""

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from starlette.concurrency import run_in_threadpool

from app.api.schema import (
    ChatRequest,
    ChatResetResponse,
    ChatResponse,
    HealthResponse,
    InitWikiResponse,
    MinerUConfig,
    UpdateChangesResponse,
    UpdateWikiRequest,
    UpdateWikiResponse,
    WorkflowContext,
    WikiStatusResponse,
)
from app.config.settings import settings
from app.workflows.init_wiki import (
    WikiAlreadyInitializedError,
    WorkflowExecutionError,
    run_init,
)
from app.workflows.chat import (
    ChatExecutionError,
    ChatSourceNotReadyError,
    ChatWikiNotInitializedError,
    clear_chat,
    run_chat,
)
from app.workflows.source_upload import (
    InvalidSourceArchiveError,
    process_source_archive,
)
from app.workflows.mineru_parser import MinerUConfigurationError
from app.workflows.source_manifest import SourceManifestError
from app.workflows.update_wiki import (
    UpdateExecutionError,
    UpdateSourceNotReadyError,
    UpdateValidationError,
    WikiNotInitializedError,
    preview_update,
    run_update,
)
from app.workflows.wiki_status import get_wiki_status


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/wiki/status",
    response_model=WikiStatusResponse,
    tags=["wiki"],
)
async def wiki_status() -> WikiStatusResponse:
    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
    return await run_in_threadpool(
        get_wiki_status,
        context,
    )


@router.post(
    "/wiki/sources/upload",
    response_model=InitWikiResponse,
    tags=["wiki-sources"],
)
async def upload_sources(
    file: UploadFile = File(..., description="公司资料 ZIP 压缩包"),
    scope: str = Form("全部公司资料"),
    message: str | None = Form(None),
) -> InitWikiResponse:
    """Upload sources, convert them, and initialize Wiki in one request."""

    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
    mineru_config = _mineru_config()
    try:
        await run_in_threadpool(
            process_source_archive,
            context,
            filename=file.filename or "",
            stream=file.file,
            mineru_config=mineru_config,
        )
        return await run_in_threadpool(
            run_init,
            context,
            scope=scope,
            message=message or None,
        )
    except (InvalidSourceArchiveError, WikiAlreadyInitializedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except MinerUConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except WorkflowExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()


@router.post(
    "/wiki/chat",
    response_model=ChatResponse,
    tags=["wiki-chat"],
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer one grounded employee question."""

    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
    try:
        return await run_in_threadpool(
            run_chat,
            context,
            question=request.question,
            conversation_id=request.conversation_id,
        )
    except (ChatSourceNotReadyError, ChatWikiNotInitializedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ChatExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete(
    "/wiki/chat/{conversation_id}",
    response_model=ChatResetResponse,
    tags=["wiki-chat"],
)
async def reset_chat(conversation_id: str) -> ChatResetResponse:
    """Forget one server-side in-memory conversation."""

    return ChatResetResponse(
        conversation_id=conversation_id,
        existed=await run_in_threadpool(clear_chat, conversation_id),
    )


@router.get(
    "/wiki/update/changes",
    response_model=UpdateChangesResponse,
    tags=["wiki"],
)
async def update_changes() -> UpdateChangesResponse:
    """Preview normalized-source changes without modifying Wiki drafts."""

    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
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


@router.post(
    "/wiki/update",
    response_model=UpdateWikiResponse,
    tags=["wiki"],
)
async def update_wiki(request: UpdateWikiRequest) -> UpdateWikiResponse:
    """Update only Wiki pages affected by normalized-source changes."""

    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
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
    except UpdateValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": str(exc),
                "validation": exc.report.model_dump(),
            },
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


def _mineru_config() -> MinerUConfig:
    return MinerUConfig(
        api_token=settings.mineru_api_token,
        base_url=settings.mineru_base_url,
        model_version=settings.mineru_model_version,
        language=settings.mineru_language,
        enable_table=settings.mineru_enable_table,
        enable_formula=settings.mineru_enable_formula,
        is_ocr=settings.mineru_is_ocr,
        request_timeout_seconds=settings.mineru_request_timeout_seconds,
        poll_interval_seconds=settings.mineru_poll_interval_seconds,
        poll_timeout_seconds=settings.mineru_poll_timeout_seconds,
    )
