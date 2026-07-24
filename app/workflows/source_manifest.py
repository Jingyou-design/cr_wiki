"""Fingerprint normalized sources and persist the update baseline."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.api.schema import (
    SourceChangeSet,
    SourceFileFingerprint,
    SourceManifest,
    WorkflowContext,
)


_HASH_CHUNK_BYTES = 1024 * 1024
_MANIFEST_RELATIVE_PATH = Path("generated-wiki") / ".source-manifest.json"
_AGENT_READABLE_SUFFIXES = {
    ".csv", ".htm", ".html", ".json", ".markdown", ".md", ".txt", ".yaml", ".yml",
}


class SourceManifestError(RuntimeError):
    """Raised when the persisted update baseline cannot be read or written."""


def detect_source_changes(context: WorkflowContext) -> SourceChangeSet:
    """Compare normalized sources with the last successful Wiki baseline."""

    current = build_source_manifest(context)
    previous = load_source_manifest(context)
    if previous is None:
        return SourceChangeSet(
            baseline_exists=False,
            added=[item.path for item in current.files],
        )

    current_by_path = {item.path: item for item in current.files}
    previous_by_path = {item.path: item for item in previous.files}
    current_paths = set(current_by_path)
    previous_paths = set(previous_by_path)
    return SourceChangeSet(
        baseline_exists=True,
        added=sorted(current_paths - previous_paths, key=str.casefold),
        modified=sorted(
            (
                path
                for path in current_paths & previous_paths
                if current_by_path[path].sha256 != previous_by_path[path].sha256
            ),
            key=str.casefold,
        ),
        deleted=sorted(previous_paths - current_paths, key=str.casefold),
    )


def build_source_manifest(context: WorkflowContext) -> SourceManifest:
    """Hash every normalized source file in deterministic path order."""

    source_root = (context.project_root / "company-handbook").resolve()
    if not source_root.is_dir():
        raise SourceManifestError(f"公司资料目录不存在：{source_root}")
    files = sorted(
        (
            path
            for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in _AGENT_READABLE_SUFFIXES
        ),
        key=lambda path: path.relative_to(source_root).as_posix().casefold(),
    )
    fingerprints = [
        SourceFileFingerprint(
            path=f"company-handbook/{path.relative_to(source_root).as_posix()}",
            sha256=_hash_file(path),
            size=path.stat().st_size,
        )
        for path in files
    ]
    return SourceManifest(files=fingerprints)


def load_source_manifest(context: WorkflowContext) -> SourceManifest | None:
    """Load the persisted baseline, returning None before the first snapshot."""

    path = manifest_path(context)
    if not path.is_file():
        return None
    try:
        return SourceManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError, ValueError) as exc:
        raise SourceManifestError("Wiki 资料变更基线损坏，无法安全执行 update。") from exc


def save_source_manifest(context: WorkflowContext) -> Path:
    """Atomically replace the baseline after a successful Wiki run."""

    manifest = build_source_manifest(context)
    target = manifest_path(context)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            manifest.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise SourceManifestError("无法保存 Wiki 资料变更基线。") from exc
    return target


def manifest_path(context: WorkflowContext) -> Path:
    """Return the private deterministic baseline location."""

    return context.project_root.resolve() / _MANIFEST_RELATIVE_PATH


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
