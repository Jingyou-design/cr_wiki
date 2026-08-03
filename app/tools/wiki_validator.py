"""Deterministic validation for one-source-one-page Wiki trees."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from app.api.schema import ValidationReport, WorkflowContext
from app.workflows.source_manifest import build_source_manifest


COMMON_FIELDS = {
    "type",
    "title",
    "description",
    "status",
    "related_pages",
    "tags",
    "uncertainties",
}
DOCUMENT_FIELDS = COMMON_FIELDS | {"source_path", "source_sha256"}
ALLOWED_TYPES = {"company-policy", "external-policy", "guide", "reference"}
LINK_RE = re.compile(r"\[[^\]]+\]\(((?:[^()]|\([^()]*\))*)\)")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
NUMBER_RE = re.compile(
    r"(?<![A-Za-z])\d+(?:\.\d+)?(?:%|元|日|天|个月|年|小时|公里)?"
)


def validate_page(
    project_root: Path,
    page: str | Path,
    *,
    allow_pending_indexes: bool = False,
    lightweight: bool = False,
) -> ValidationReport:
    """Validate one generated page without following paths outside the project.

    ``lightweight`` is used after each Agent write. It checks the page boundary,
    Front Matter, and source identity, while deferring cross-page links and
    evidence-quality diagnostics until an explicit tree diagnostic.
    """

    root = project_root.resolve()
    draft_root = (root / "generated-wiki" / "drafts").resolve()
    page_path = _resolve_page(root, draft_root, page)
    report = ValidationReport(checked_files=1)
    display_path = _display(root, page_path)
    if not _is_within(page_path, draft_root):
        report.add(
            "error", "path.outside_drafts", "页面不在草稿目录中。", display_path
        )
        return report
    if page_path.suffix.lower() != ".md":
        report.add(
            "error", "path.not_markdown", "Wiki 页面必须是 Markdown 文件。", display_path
        )
        return report
    if not page_path.is_file():
        report.add("error", "file.missing", "页面不存在。", display_path)
        return report

    text = page_path.read_text(encoding="utf-8")
    if page_path.name == "index.md":
        _validate_links(
            page_path,
            draft_root,
            text,
            display_path,
            report,
            allow_pending_indexes=allow_pending_indexes,
        )
        return report
    if page_path.name == "quickstart.md" and page_path.parent != draft_root:
        report.add(
            "error",
            "tree.nested_quickstart",
            "quickstart.md 只能存在于 Wiki 根目录。",
            display_path,
        )

    metadata, body, error = _parse_front_matter(text)
    if error:
        report.add("error", "front_matter.invalid", error, display_path)
        return report
    required = COMMON_FIELDS if page_path.name == "quickstart.md" else DOCUMENT_FIELDS
    missing = sorted(required - metadata.keys())
    if missing:
        report.add(
            "error",
            "front_matter.missing_fields",
            f"缺少字段：{', '.join(missing)}。",
            display_path,
        )
    page_type = metadata.get("type")
    if page_type and page_type not in ALLOWED_TYPES:
        report.add(
            "error",
            "front_matter.type",
            f"不支持的 type：{page_type}。",
            display_path,
        )
    if metadata.get("status") != "draft":
        report.add(
            "error",
            "front_matter.status",
            "Wiki 草稿页面状态必须为 draft。",
            display_path,
        )
    for field_name in ("title", "description"):
        if not str(metadata.get(field_name, "")).strip():
            report.add(
                "error",
                f"front_matter.{field_name}",
                f"{field_name} 不能为空。",
                display_path,
            )

    if page_path.name != "quickstart.md":
        source = metadata.get("source_path")
        digest = str(metadata.get("source_sha256", "")).strip()
        if not isinstance(source, str) or not source.strip():
            report.add(
                "error",
                "sources.empty",
                "文档页必须且只能对应一个 source_path。",
                display_path,
            )
        else:
            _validate_source(root, source, digest, display_path, report)
        if not SHA256_RE.fullmatch(digest):
            report.add(
                "error",
                "sources.invalid_hash",
                "source_sha256 必须是 64 位小写 SHA-256。",
                display_path,
            )

    if not lightweight:
        _validate_links(
            page_path,
            draft_root,
            body,
            display_path,
            report,
            allow_pending_indexes=allow_pending_indexes,
        )
        if NUMBER_RE.search(body) and "来源依据" not in body:
            report.add(
                "warning",
                "evidence.numbers_without_section",
                "正文包含数字，但没有“来源依据”章节。",
                display_path,
            )
    return report


def validate_tree(project_root: Path) -> ValidationReport:
    """Validate the full Wiki structure and exact source/page coverage."""

    root = project_root.resolve()
    draft_root = root / "generated-wiki" / "drafts"
    report = ValidationReport()
    if not draft_root.is_dir():
        report.add(
            "error",
            "tree.missing",
            "草稿目录不存在。",
            "generated-wiki/drafts",
        )
        return report

    pages = sorted(draft_root.rglob("*.md"))
    report.checked_files = len(pages)
    quickstarts = [path for path in pages if path.name == "quickstart.md"]
    root_quickstart = draft_root / "quickstart.md"
    if not root_quickstart.is_file():
        report.add(
            "error",
            "tree.quickstart_missing",
            "缺少根目录入口 quickstart.md。",
            _display(root, root_quickstart),
        )
    for nested in quickstarts:
        if nested != root_quickstart:
            report.add(
                "error",
                "tree.nested_quickstart",
                "子目录不得生成 quickstart.md。",
                _display(root, nested),
            )

    manifest = build_source_manifest(WorkflowContext(project_root=root))
    expected_sources = {item.path: item for item in manifest.files}
    actual_documents = {
        path.relative_to(draft_root).as_posix(): path
        for path in pages
        if path.name not in {"index.md", "quickstart.md"}
    }
    pages_by_source: dict[str, list[tuple[str, Path]]] = {}
    for relative, page_path in actual_documents.items():
        metadata, _, error = _parse_front_matter(
            page_path.read_text(encoding="utf-8")
        )
        if error:
            continue
        source_path = metadata.get("source_path")
        if not isinstance(source_path, str) or source_path not in expected_sources:
            report.add(
                "error",
                "tree.unmapped_page",
                "页面不对应任何当前源文件。",
                f"generated-wiki/drafts/{relative}",
            )
            continue
        pages_by_source.setdefault(source_path, []).append((relative, page_path))
        if metadata.get("source_sha256") != expected_sources[source_path].sha256:
            report.add(
                "error",
                "tree.source_hash_mismatch",
                "页面记录的 source_sha256 与当前资料不一致。",
                _display(root, page_path),
            )

    for source_path in sorted(expected_sources, key=str.casefold):
        source_pages = pages_by_source.get(source_path, [])
        if not source_pages:
            report.add(
                "error",
                "tree.source_page_missing",
                f"源文件尚未生成对应页面：{source_path}。",
                f"generated-wiki/drafts/{source_path}",
            )
        elif len(source_pages) > 1:
            for relative, _ in source_pages:
                report.add(
                    "error",
                    "tree.source_page_duplicate",
                    f"源文件对应了多个页面：{source_path}。",
                    f"generated-wiki/drafts/{relative}",
                )

    expected_index_directories = {PurePosixPath(".")}
    for relative in actual_documents:
        parent = PurePosixPath(relative).parent
        while parent.as_posix() != ".":
            expected_index_directories.add(parent)
            parent = parent.parent
    expected_indexes = {
        "index.md"
        if directory.as_posix() == "."
        else f"{directory.as_posix()}/index.md"
        for directory in expected_index_directories
    }
    actual_indexes = {
        path.relative_to(draft_root).as_posix()
        for path in pages
        if path.name == "index.md"
    }
    for relative in sorted(expected_indexes - actual_indexes):
        report.add(
            "error",
            "tree.index_missing",
            "资料目录缺少自动索引。",
            f"generated-wiki/drafts/{relative}",
        )
    for relative in sorted(actual_indexes - expected_indexes):
        report.add(
            "error",
            "tree.stale_index",
            "索引目录已没有对应文档。",
            f"generated-wiki/drafts/{relative}",
        )

    for page_path in pages:
        report.issues.extend(validate_page(root, page_path).issues)
    return report


def diagnose_tree(project_root: Path) -> ValidationReport:
    """Return best-effort tree diagnostics without blocking a workflow."""

    try:
        return validate_tree(project_root)
    except Exception as exc:
        report = ValidationReport()
        report.add(
            "warning",
            "diagnostics.failed",
            f"未能完成 Wiki 全量诊断：{exc}",
            "generated-wiki/drafts",
        )
        return report


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str, str | None]:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "文件必须以 YAML Front Matter 的 --- 开始。"
    try:
        closing = next(
            i for i in range(1, len(lines)) if lines[i].strip() == "---"
        )
    except StopIteration:
        return {}, text, "Front Matter 缺少结束分隔符 ---。"
    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw_line in lines[1:closing]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")) and raw_line.strip().startswith("-"):
            if current_list is None:
                return {}, text, f"无法识别的列表项：{raw_line.strip()}"
            data[current_list].append(_unquote(raw_line.strip()[1:].strip()))
            continue
        if ":" not in raw_line:
            return {}, text, f"无法识别的 Front Matter 行：{raw_line}"
        key, raw_value = raw_line.split(":", 1)
        key, value = key.strip(), raw_value.strip()
        current_list = None
        if not value:
            data[key] = []
            current_list = key
        elif value == "[]":
            data[key] = []
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = (
                []
                if not inner
                else [_unquote(item.strip()) for item in inner.split(",")]
            )
        else:
            data[key] = _unquote(value)
    return data, "\n".join(lines[closing + 1 :]).strip(), None


def _validate_source(
    root: Path,
    source: str,
    expected_digest: str,
    page: str,
    report: ValidationReport,
) -> None:
    normalized = PurePosixPath(source.replace("\\", "/").lstrip("/"))
    if (
        not normalized.parts
        or normalized.parts[0] != "company-handbook"
        or ".." in normalized.parts
    ):
        report.add(
            "error",
            "sources.outside_handbook",
            f"非法来源路径：{source}。",
            page,
        )
        return
    source_path = (root / Path(*normalized.parts)).resolve()
    handbook = (root / "company-handbook").resolve()
    if not _is_within(source_path, handbook) or not source_path.is_file():
        report.add(
            "error",
            "sources.missing",
            f"来源文件不存在：{source}。",
            page,
        )
        return
    if SHA256_RE.fullmatch(expected_digest) and _hash_file(source_path) != expected_digest:
        report.add(
            "error",
            "sources.hash_mismatch",
            f"来源内容哈希不一致：{source}。",
            page,
        )


def _validate_links(
    page_path: Path,
    draft_root: Path,
    body: str,
    display: str,
    report: ValidationReport,
    *,
    allow_pending_indexes: bool = False,
) -> None:
    for target in LINK_RE.findall(body):
        target = unquote(target.strip().split("#", 1)[0])
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        resolved = (
            (draft_root / target.lstrip("/"))
            if target.startswith("/")
            else (page_path.parent / target)
        ).resolve()
        if not _is_within(resolved, draft_root):
            report.add(
                "error",
                "links.outside_drafts",
                f"链接越出草稿目录：{target}。",
                display,
            )
        elif not resolved.exists() and not (
            allow_pending_indexes
            and PurePosixPath(target.replace("\\", "/")).name == "index.md"
        ):
            report.add(
                "error",
                "links.missing",
                f"链接目标不存在：{target}。",
                display,
            )


def _resolve_page(root: Path, draft_root: Path, page: str | Path) -> Path:
    value = str(page).replace("\\", "/")
    if value.startswith("/generated-wiki/drafts/"):
        return (root / value.lstrip("/")).resolve()
    path = Path(page)
    if path.is_absolute():
        return path.resolve()
    if value.startswith("generated-wiki/drafts/"):
        return (root / path).resolve()
    return (draft_root / path).resolve()


def _unquote(value: str) -> str:
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        return value[1:-1]
    return value


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
