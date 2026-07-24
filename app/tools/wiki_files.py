"""Narrow file mutations that Deep Agents' built-in tools do not provide."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Callable


_DRAFT_PREFIX = PurePosixPath("/generated-wiki/drafts")
_PROTECTED_PAGES = {"index.md", "quickstart.md"}


def create_delete_wiki_page_tool(project_root: Path) -> Callable[[str], str]:
    """Create a project-bound tool that can delete only non-entry Wiki pages."""

    resolved_root = project_root.resolve()
    draft_root = (resolved_root / "generated-wiki" / "drafts").resolve()

    def delete_wiki_page(file_path: str) -> str:
        """Delete one obsolete Wiki Markdown page after its sources were removed."""

        normalized = PurePosixPath(
            "/" + file_path.strip().replace("\\", "/").lstrip("/")
        )
        if (
            normalized.suffix.lower() != ".md"
            or normalized.name.lower() in _PROTECTED_PAGES
            or ".." in normalized.parts
            or not normalized.is_relative_to(_DRAFT_PREFIX)
        ):
            return (
                "Error: delete_wiki_page 只允许删除 "
                "/generated-wiki/drafts 下非 quickstart、非 index 的 Markdown 页面。"
            )
        target = (
            resolved_root / Path(*normalized.relative_to("/").parts)
        ).resolve()
        try:
            target.relative_to(draft_root)
        except ValueError:
            return "Error: 页面路径越出 Wiki 草稿目录。"
        if not target.is_file():
            return f"Error: 页面不存在：{normalized.as_posix()}"
        target.unlink()
        return f"Deleted obsolete Wiki page: {normalized.as_posix()}"

    return delete_wiki_page
