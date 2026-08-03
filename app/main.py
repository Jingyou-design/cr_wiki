"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router


FRONTEND_ROOT = Path(__file__).resolve().parent / "frontend"


app = FastAPI(
    title="CR Wiki API",
    version="0.1.0",
    description="基于 Deep Agents 的公司 Wiki 生成服务。",
)
app.include_router(router, prefix="/api")
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_ROOT),
    name="frontend-assets",
)


@app.get("/", include_in_schema=False)
async def login_page() -> FileResponse:
    """Serve the login page."""

    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    """Serve the administrator console."""

    return FileResponse(FRONTEND_ROOT / "admin.html")


@app.get("/manager", include_in_schema=False)
async def manager_page() -> FileResponse:
    """Serve the department manager console."""

    return FileResponse(FRONTEND_ROOT / "admin.html")


@app.get("/chat", include_in_schema=False)
async def chat_page() -> FileResponse:
    """Serve the employee knowledge chat."""

    return FileResponse(FRONTEND_ROOT / "chat.html")


@app.get("/book", include_in_schema=False)
async def book_page() -> FileResponse:
    """Serve the employee Wiki browser."""

    return FileResponse(FRONTEND_ROOT / "book.html")
