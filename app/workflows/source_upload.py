from __future__ import annotations

import shutil
from errno import ENAMETOOLONG
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4
from zipfile import BadZipFile, LargeZipFile, ZipFile

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.schema import (
    InitWikiResponse,
    MinerUConfig,
    MinerUDocument,
    WorkflowContext,
)
from app.config.settings import settings
from app.workflows.init_wiki import run_init
from app.workflows.mineru_parser import parse_documents


_MINERU_SUFFIXES = {
    ".bmp", ".doc", ".docx", ".gif", ".jpeg", ".jpg", ".jp2", ".pdf",
    ".png", ".ppt", ".pptx", ".webp", ".xls", ".xlsx",
}
_AGENT_READABLE_SUFFIXES = {
    ".csv", ".htm", ".html", ".json", ".markdown", ".md", ".txt", ".yaml", ".yml",
}


class InvalidSourceArchiveError(RuntimeError):
    pass


async def upload_and_initialize(file: UploadFile) -> InitWikiResponse:
    """Process one uploaded archive and initialize its Wiki."""

    try:
        context = WorkflowContext(
            project_root=settings.wiki_project_root.resolve()
        )
        mineru_config = _mineru_config()
        await run_in_threadpool(
            process_source_archive,
            context,
            filename=file.filename or "",
            stream=file.file,
            mineru_config=mineru_config,
        )
        return await run_in_threadpool(run_init, context)
    finally:
        await file.close()


def process_source_archive(
    context: WorkflowContext,
    *,
    filename: str,
    stream: BinaryIO,
    mineru_config: MinerUConfig,
) -> None:
    if not filename.lower().endswith(".zip"):
        raise InvalidSourceArchiveError("只允许上传 .zip 格式的公司资料包。")

    root = context.project_root.expanduser().resolve()
    source_dir = root / "company-handbook"
    draft_root = root / "generated-wiki" / "drafts"
    if draft_root.is_dir() and any(draft_root.rglob("*.md")):
        raise InvalidSourceArchiveError(
            "已有已生成的 Wiki，不能直接上传新资料包。"
            "如需替换全部资料，请先清空现有 Wiki。"
        )
    processing_root = root / f".source-processing-{uuid4().hex}"
    extracted_dir = processing_root / "extracted"
    prepared_dir = processing_root / "company-handbook"
    try:
        extracted_dir.mkdir(parents=True)
        prepared_dir.mkdir()
        with ZipFile(stream, metadata_encoding="gbk") as archive:
            archive.extractall(extracted_dir)

        _copy_readable_sources(extracted_dir, prepared_dir)
        parse_documents(
            mineru_config,
            _build_mineru_documents(extracted_dir),
            prepared_dir,
        )
        if not any(path.is_file() for path in prepared_dir.rglob("*")):
            raise InvalidSourceArchiveError(
                "资料包处理后没有可供 Agent 读取的文本或 Markdown 文件。"
            )

        shutil.rmtree(source_dir, ignore_errors=True)
        prepared_dir.replace(source_dir)
        _clear_previous_wiki(root)
    except (BadZipFile, LargeZipFile) as exc:
        raise InvalidSourceArchiveError("ZIP 文件损坏或格式不受支持。") from exc
    except OSError as exc:
        if exc.errno == ENAMETOOLONG:
            message = "ZIP 内存在过长的文件名，请缩短后重新压缩上传。"
        else:
            message = "ZIP 文件无法解压，请检查压缩包内容。"
        raise InvalidSourceArchiveError(message) from exc
    finally:
        shutil.rmtree(processing_root, ignore_errors=True)


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


def _build_mineru_documents(source_root: Path) -> list[MinerUDocument]:
    documents: list[MinerUDocument] = []
    for source in sorted(source_root.rglob("*"), key=lambda path: path.as_posix().casefold()):
        if not source.is_file() or source.suffix.lower() not in _MINERU_SUFFIXES:
            continue
        relative_path = source.relative_to(source_root)
        documents.append(
            MinerUDocument(
                source_path=source,
                target_relative_path=relative_path.with_suffix(".md").as_posix(),
                upload_name=f"doc_{uuid4().hex}{source.suffix.lower()}",
                data_id=f"doc_{uuid4().hex}",
            )
        )
    return documents


def _copy_readable_sources(source_root: Path, target_root: Path) -> None:
    for source in source_root.rglob("*"):
        if not source.is_file() or source.suffix.lower() not in _AGENT_READABLE_SUFFIXES:
            continue
        target = target_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _clear_previous_wiki(project_root: Path) -> None:
    wiki_root = project_root / "generated-wiki"
    shutil.rmtree(wiki_root / "drafts", ignore_errors=True)
    (wiki_root / ".source-manifest.json").unlink(missing_ok=True)
    (wiki_root / "_plan.json").unlink(missing_ok=True)
