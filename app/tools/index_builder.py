"""Build deterministic recursive indexes for generated Wiki drafts."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from app.tools.wiki_validator import _parse_front_matter


def build_draft_indexes(project_root: Path) -> list[Path]:
    """Rebuild root and directory indexes from the current document pages."""

    root = project_root.resolve()
    draft_root = root / "generated-wiki" / "drafts"
    draft_root.mkdir(parents=True, exist_ok=True)

    for stale_index in draft_root.rglob("index.md"):
        if stale_index.is_file():
            stale_index.unlink()

    document_pages = sorted(
        (
            path
            for path in draft_root.rglob("*.md")
            if path.name not in {"index.md", "quickstart.md"}
        ),
        key=lambda path: path.relative_to(draft_root).as_posix().casefold(),
    )
    indexed_directories = {draft_root}
    for page in document_pages:
        current = page.parent
        while current != draft_root:
            indexed_directories.add(current)
            current = current.parent

    created: list[Path] = []
    for directory in sorted(
        indexed_directories,
        key=lambda path: (
            len(path.relative_to(draft_root).parts),
            path.relative_to(draft_root).as_posix().casefold(),
        ),
        reverse=True,
    ):
        index_path = directory / "index.md"
        index_path.write_text(
            _render_directory_index(
                directory=directory,
                draft_root=draft_root,
                document_pages=document_pages,
                indexed_directories=indexed_directories,
            ),
            encoding="utf-8",
        )
        created.append(index_path)
    return sorted(
        created,
        key=lambda path: path.relative_to(draft_root).as_posix().casefold(),
    )


def build_draft_index(project_root: Path) -> Path:
    """Backward-compatible helper returning the rebuilt root index."""

    build_draft_indexes(project_root)
    return project_root.resolve() / "generated-wiki" / "drafts" / "index.md"


def _render_directory_index(
    *,
    directory: Path,
    draft_root: Path,
    document_pages: list[Path],
    indexed_directories: set[Path],
) -> str:
    relative_directory = directory.relative_to(draft_root)
    title = "公司知识库" if directory == draft_root else directory.name
    lines = [
        f"# {title}",
        "",
        "> 此索引由程序根据资料目录自动生成，请勿手工编辑。",
        "",
    ]

    if directory == draft_root and (draft_root / "quickstart.md").is_file():
        lines.extend(
            [
                "## 开始使用",
                "",
                "- [知识库使用说明](quickstart.md)",
                "",
            ]
        )

    child_directories = sorted(
        (
            child
            for child in indexed_directories
            if child.parent == directory and child != directory
        ),
        key=lambda path: path.name.casefold(),
    )
    if child_directories:
        lines.extend(["## 目录", "", "| 目录 | 内容 |", "| --- | --- |"])
        for child in child_directories:
            page_count = sum(
                page.is_relative_to(child) for page in document_pages
            )
            lines.append(
                f"| [{child.name}]({_link(child.name)}/index.md) | "
                f"{page_count} 个文档页面 |"
            )
        lines.append("")

    direct_pages = [page for page in document_pages if page.parent == directory]
    if direct_pages:
        lines.extend(["## 文档", "", "| 页面 | 说明 |", "| --- | --- |"])
        for page in direct_pages:
            metadata, _, error = _parse_front_matter(
                page.read_text(encoding="utf-8")
            )
            title_value = page.stem if error else str(
                metadata.get("title") or page.stem
            )
            description = "" if error else str(
                metadata.get("description") or ""
            )
            lines.append(
                f"| [{_cell(title_value)}]({_link(page.name)}) | "
                f"{_cell(description)} |"
            )
        lines.append("")

    if not child_directories and not direct_pages:
        lines.extend(["当前目录还没有文档页面。", ""])

    if relative_directory.parts:
        lines.extend(["[返回上级目录](../index.md)", ""])
    return "\n".join(lines)


def _cell(value: str) -> str:
    return value.replace("|", "｜").replace("\r", " ").replace("\n", " ").strip()


def _link(value: str) -> str:
    return quote(value.replace("\\", "/"), safe="/-._~")
