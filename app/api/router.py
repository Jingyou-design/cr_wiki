"""FastAPI route declarations for the company Wiki."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Response,
    UploadFile,
    status,
)
from starlette.responses import StreamingResponse

from app.api.handlers.auth import (
    handle_current_user,
    handle_login,
    handle_logout,
)
from app.api.handlers.chat import handle_chat
from app.api.handlers.wiki import (
    handle_update_changes,
    handle_update_wiki,
    handle_wiki_status,
)
from app.api.schema import (
    AuthenticatedUserContext,
    ChatRequest,
    CurrentUserResponse,
    InitWikiResponse,
    LoginRequest,
    UpdateChangesResponse,
    UpdateWikiRequest,
    UpdateWikiResponse,
    WikiPageResponse,
    WikiStatusResponse,
    WikiTreeResponse,
)
from app.workflows.auth import (
    get_current_user,
    require_admin,
    require_manager,
)
from app.config.settings import settings
from app.workflows.source_upload import upload_and_initialize
from app.workflows.wiki_browser import get_wiki_page, get_wiki_tree


router = APIRouter()
CurrentUser = Annotated[AuthenticatedUserContext, Depends(get_current_user)]
AdminUser = Annotated[AuthenticatedUserContext, Depends(require_admin)]
ManagerUser = Annotated[AuthenticatedUserContext, Depends(require_manager)]
SessionCookie = Annotated[
    str | None,
    Cookie(alias=settings.auth_cookie_name),
]


@router.post(
    "/auth/login",
    response_model=CurrentUserResponse,
    tags=["auth"],
)
async def login(
    request: LoginRequest,
    response: Response,
) -> CurrentUserResponse:
    """Authenticate a configured user and create a browser session."""

    return await handle_login(request, response)


@router.post(
    "/auth/me",
    response_model=CurrentUserResponse,
    tags=["auth"],
)
async def me(user: CurrentUser) -> CurrentUserResponse:
    """Return the current active user without exposing the password."""

    return handle_current_user(user)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
)
async def logout(
    response: Response,
    session_token: SessionCookie = None,
) -> None:
    """Delete the server session and browser cookie."""

    handle_logout(response, session_token)


@router.post(
    "/wiki/status",
    response_model=WikiStatusResponse,
    tags=["wiki"],
)
async def wiki_status(_user: CurrentUser) -> WikiStatusResponse:
    return await handle_wiki_status()


@router.post(
    "/wiki/sources/upload",
    response_model=InitWikiResponse,
    tags=["wiki-sources"],
)
async def upload_sources(
    _user: AdminUser,
    file: UploadFile = File(..., description="公司资料 ZIP 压缩包"),
) -> InitWikiResponse:
    """Upload sources, convert them, and initialize Wiki in one request."""

    return await upload_and_initialize(file)


@router.post(
    "/wiki/chat",
    tags=["wiki-chat"],
)
async def chat(
    request: ChatRequest,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream one grounded employee answer using Server-Sent Events."""

    return await handle_chat(request, user)


@router.get(
    "/wiki/tree",
    response_model=WikiTreeResponse,
    tags=["wiki"],
)
def wiki_tree(user: CurrentUser) -> WikiTreeResponse:
    return get_wiki_tree(user)


@router.get(
    "/wiki/page",
    response_model=WikiPageResponse,
    tags=["wiki"],
)
def wiki_page(path: str, user: CurrentUser) -> WikiPageResponse:
    return get_wiki_page(path, user)


@router.post(
    "/wiki/update/changes",
    response_model=UpdateChangesResponse,
    tags=["wiki"],
)
async def update_changes(_user: ManagerUser) -> UpdateChangesResponse:
    """Preview normalized-source changes without modifying Wiki drafts."""

    return await handle_update_changes()


@router.post(
    "/wiki/update",
    response_model=UpdateWikiResponse,
    tags=["wiki"],
)
async def update_wiki(
    request: UpdateWikiRequest,
    _user: ManagerUser,
) -> UpdateWikiResponse:
    """Update only Wiki pages affected by normalized-source changes."""

    return await handle_update_wiki(request)
