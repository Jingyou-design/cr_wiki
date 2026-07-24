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
async def frontend() -> FileResponse:
    """Serve the local Wiki initialization console."""

    return FileResponse(FRONTEND_ROOT / "index.html")
