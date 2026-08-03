"""Execute the init Wiki workflow and deterministic post-processing."""

from __future__ import annotations

import json
import shutil
from typing import Any

from app.api.schema import InitWikiResponse, WorkflowContext

from app.prompt.loader import create_user_prompt
from app.tools.wiki_validator import diagnose_tree
from app.workflows.agent_factory import create_init_agent
from app.workflows.source_manifest import build_source_manifest, save_source_manifest


class WikiAlreadyInitializedError(RuntimeError):
    """Raised when init would overwrite existing Wiki drafts."""


class WorkflowExecutionError(RuntimeError):
    """Raised when the Agent fails during the init workflow."""


def run_init(context: WorkflowContext) -> InitWikiResponse:
    draft_root = context.project_root / "generated-wiki" / "drafts"
    if draft_root.is_dir() and any(draft_root.iterdir()):
        raise WikiAlreadyInitializedError(
            "草稿目录已经包含文件；init 不允许覆盖现有结果。"
        )
    draft_root.mkdir(parents=True, exist_ok=True)
    manifest = build_source_manifest(context)
    agent = create_init_agent(context)
    user_prompt = create_user_prompt(
        str(context.project_root),
        sources_json=json.dumps(
            [item.model_dump() for item in manifest.files],
            ensure_ascii=False,
            indent=2,
        ),
    )
    plan_path = context.project_root / "generated-wiki" / "_plan.json"
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_prompt}]}
        )
    except Exception as exc:
        if draft_root.is_dir():
            shutil.rmtree(draft_root, ignore_errors=True)
        raise WorkflowExecutionError("Wiki Agent 执行失败。") from exc
    finally:
        if plan_path.is_file():
            plan_path.unlink()

    validation = diagnose_tree(context.project_root)
    try:
        save_source_manifest(context)
    except Exception as exc:
        shutil.rmtree(draft_root, ignore_errors=True)
        raise WorkflowExecutionError("无法保存 Wiki 资料变更基线。") from exc
    return InitWikiResponse(
        summary=_final_message_text(result),
        output_dir=draft_root,
        validation=validation,
    )


def _final_message_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        return str(result)
    content = getattr(messages[-1], "content", "")
    return content if isinstance(content, str) else str(content)
