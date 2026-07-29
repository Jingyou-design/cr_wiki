"""Detect normalized-source changes and incrementally maintain Wiki drafts."""

from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from app.api.schema import (
    UpdateChangesResponse,
    UpdateWikiResponse,
    ValidationReport,
    SourceChangeSet,
    WorkflowContext,
)
from app.prompt.loader import create_update_user_prompt
from app.tools.wiki_validator import validate_tree
from app.workflows.agent_factory import create_update_agent
from app.workflows.source_manifest import (
    SourceManifestError,
    build_source_manifest,
    detect_source_changes,
    save_source_manifest,
)


class WikiNotInitializedError(RuntimeError):
    """Raised when update is requested before a usable Wiki exists."""


class UpdateSourceNotReadyError(RuntimeError):
    """Raised when normalized company sources are not ready."""


class UpdateExecutionError(RuntimeError):
    """Raised when the incremental Agent cannot complete safely."""


class UpdateValidationError(RuntimeError):
    """Raised after invalid update output has been rolled back."""

    def __init__(self, message: str, report: ValidationReport) -> None:
        super().__init__(message)
        self.report = report


def preview_update(context: WorkflowContext) -> UpdateChangesResponse:
    """Return pending source changes without mutating drafts or the baseline."""

    _ensure_update_ready(context)
    changes = detect_source_changes(context)
    return UpdateChangesResponse(
        status="changes_detected" if changes.has_changes else "no_changes",
        changes=changes,
    )


def run_update(
    context: WorkflowContext,
    *,
    message: str | None,
) -> UpdateWikiResponse:
    _ensure_update_ready(context)
    changes = detect_source_changes(context)
    draft_root = context.project_root.resolve() / "generated-wiki" / "drafts"
    if not changes.has_changes:
        return UpdateWikiResponse(
            status="no_changes",
            summary="公司资料与上次成功运行时一致，没有需要更新的 Wiki 页面。",
            output_dir=draft_root,
            changes=changes,
            validation=validate_tree(context.project_root),
        )

    current_manifest = build_source_manifest(context)
    update_context = {
        "source_changes": changes.model_dump(),
        "current_sources": [
            item.model_dump() for item in current_manifest.files
        ],
    }
    before = _snapshot_pages(draft_root)
    backup_root = (
        context.project_root.resolve()
        / "generated-wiki"
        / f".update-backup-{uuid4().hex}"
    )
    plan_path = context.project_root.resolve() / "generated-wiki" / "_plan.json"
    shutil.copytree(draft_root, backup_root)
    committed = False
    try:
        agent = create_update_agent(context)
        prompt = create_update_user_prompt(
            str(context.project_root),
            update_context_json=json.dumps(
                update_context,
                ensure_ascii=False,
                indent=2,
            ),
            user_message=message,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]}
        )
        validation = validate_tree(context.project_root)
        if not validation.valid:
            raise UpdateValidationError(
                "增量更新结果未通过整体验收，已经恢复更新前草稿。",
                validation,
            )
        save_source_manifest(context)
        after = _snapshot_pages(draft_root)
        committed = True
        return UpdateWikiResponse(
            status="completed",
            summary=_final_message_text(result),
            output_dir=draft_root,
            changes=changes,
            updated_pages=sorted(
                (
                    path
                    for path, digest in after.items()
                    if PurePosixPath(path).name != "index.md"
                    and before.get(path) != digest
                ),
                key=str.casefold,
            ),
            deleted_pages=sorted(
                (
                    path
                    for path in before.keys() - after.keys()
                    if PurePosixPath(path).name != "index.md"
                ),
                key=str.casefold,
            ),
            validation=validation,
        )
    except UpdateValidationError:
        raise
    except SourceManifestError as exc:
        raise UpdateExecutionError(str(exc)) from exc
    except Exception as exc:
        raise UpdateExecutionError("Wiki 增量更新 Agent 执行失败。") from exc
    finally:
        if plan_path.is_file():
            plan_path.unlink()
        if not committed:
            _restore_drafts(draft_root, backup_root)
        shutil.rmtree(backup_root, ignore_errors=True)


def _ensure_update_ready(context: WorkflowContext) -> None:
    if not (context.project_root / "company-handbook").is_dir():
        raise UpdateSourceNotReadyError(
            "公司资料尚未处理完成，暂时不能执行 update。"
        )
    draft_root = context.project_root.resolve() / "generated-wiki" / "drafts"
    if not (draft_root / "quickstart.md").is_file():
        raise WikiNotInitializedError(
            "尚未找到可维护的 Wiki 草稿，请先成功执行 init。"
        )


def _snapshot_pages(draft_root: Path) -> dict[str, str]:
    return {
        path.relative_to(draft_root).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(draft_root.rglob("*.md"))
        if path.is_file()
    }


def _restore_drafts(draft_root: Path, backup_root: Path) -> None:
    if not backup_root.is_dir():
        return
    shutil.rmtree(draft_root, ignore_errors=True)
    shutil.copytree(backup_root, draft_root)


def _final_message_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        return str(result)
    content = getattr(messages[-1], "content", "")
    return content if isinstance(content, str) else str(content)
