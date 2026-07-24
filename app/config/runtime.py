"""Resolve and validate the init workflow filesystem context."""

from __future__ import annotations

from pathlib import Path

from app.api.schema import WorkflowContext


def load_workflow_context(project_root: str | Path | None = None) -> WorkflowContext:
    """Resolve the project root used by one workflow run."""

    root = Path(project_root or Path.cwd())
    root = root.expanduser().resolve()
    return WorkflowContext(project_root=root)


def validate_layout(context: WorkflowContext) -> None:
    """Validate filesystem assumptions without mixing I/O into the schema."""

    if not context.project_root.is_dir():
        raise ValueError(f"项目目录不存在：{context.project_root}")
    source_dir = context.project_root / "company-handbook"
    if not source_dir.is_dir():
        raise ValueError(f"原始资料目录不存在：{source_dir}")
