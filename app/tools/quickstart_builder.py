"""Build the single root quickstart without duplicating directory indexes."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


def build_root_quickstart(project_root: Path) -> Path:
    """Create one high-level entry page from actual first-level Wiki folders."""

    draft_root = project_root.resolve() / "generated-wiki" / "drafts"
    draft_root.mkdir(parents=True, exist_ok=True)
    document_pages = [
        path
        for path in draft_root.rglob("*.md")
        if path.name not in {"index.md", "quickstart.md"}
    ]
    first_level_directories = sorted(
        {
            page.relative_to(draft_root).parts[0]
            for page in document_pages
            if len(page.relative_to(draft_root).parts) > 1
        },
        key=str.casefold,
    )
    root_page_count = sum(page.parent == draft_root for page in document_pages)

    lines = [
        "---",
        "type: guide",
        "title: 公司知识库使用说明",
        "description: 公司知识库的使用入口和一级资料目录导航。",
        "status: draft",
        "related_pages: []",
        "tags:",
        "  - 入口",
        "  - 导航",
        "uncertainties: []",
        "---",
        "",
        "# 公司知识库使用说明",
        "",
        "本知识库按照管理员上传资料包的实际目录组织。每个源文件对应一个独立",
        "Wiki 页面；目录中的完整文件清单由各级 `index.md` 自动维护。",
        "",
        "## 如何查找",
        "",
        "1. 从下面的一级资料目录进入；",
        "2. 沿目录中的 `index.md` 逐级缩小范围；",
        "3. 打开具体文档页查看规则、流程、条件和来源依据；",
        "4. 也可以直接使用知识库问答，由 Agent 按相同顺序检索。",
        "",
        "## 一级资料目录",
        "",
    ]
    if first_level_directories:
        lines.extend(["| 目录 | 文档数量 |", "| --- | ---: |"])
        for directory in first_level_directories:
            count = sum(
                page.relative_to(draft_root).parts[0] == directory
                for page in document_pages
            )
            link = quote(directory, safe="-._~")
            lines.append(f"| [{directory}]({link}/index.md) | {count} |")
        lines.append("")
    else:
        lines.extend(["当前没有一级资料目录。", ""])

    if root_page_count:
        lines.extend(
            [
                f"另有 {root_page_count} 个文档直接位于知识库根目录，"
                "可通过 [根目录索引](index.md) 查看。",
                "",
            ]
        )
    lines.extend(
        [
            "## 使用提醒",
            "",
            "- Wiki 页面用于快速检索和理解，页面中的 `source_path` 指向唯一源文件；",
            "- 外部政策可能存在时效性，页面标注不确定或冲突时应核对原文；",
            "- Wiki 与资料尚未同步时，系统会暂停问答并要求管理员先执行 update。",
            "",
        ]
    )
    target = draft_root / "quickstart.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
