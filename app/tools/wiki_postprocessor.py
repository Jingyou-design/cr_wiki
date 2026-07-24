"""Deterministic finishing steps for Agent-generated document pages."""

from __future__ import annotations

from pathlib import Path

from app.tools.wiki_validator import _parse_front_matter


def ensure_source_sections(project_root: Path) -> list[Path]:
    """Append the canonical source path when a document page omitted it."""

    draft_root = project_root.resolve() / "generated-wiki" / "drafts"
    changed: list[Path] = []
    for page in sorted(
        draft_root.rglob("*.md"),
        key=lambda path: path.relative_to(draft_root).as_posix().casefold(),
    ):
        if page.name in {"index.md", "quickstart.md"}:
            continue
        text = page.read_text(encoding="utf-8")
        metadata, body, error = _parse_front_matter(text)
        if error or "来源依据" in body:
            continue
        source_path = metadata.get("source_path")
        if not isinstance(source_path, str) or not source_path.strip():
            continue
        finished = (
            text.rstrip()
            + "\n\n## 来源依据\n\n"
            + f"- `{source_path.strip()}`\n"
        )
        page.write_text(finished, encoding="utf-8")
        changed.append(page)
    return changed
