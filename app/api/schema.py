"""Pydantic data models shared across the company Wiki application."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class WorkflowContext(BaseModel):
    """Filesystem context for one Wiki workflow run."""

    model_config = ConfigDict(frozen=True)

    project_root: Path


class MinerUConfig(BaseModel):
    """Configuration used by the MinerU document parsing client."""

    model_config = ConfigDict(frozen=True)

    api_token: str = Field(repr=False)
    base_url: str
    model_version: str
    language: str
    enable_table: bool
    enable_formula: bool
    is_ocr: bool
    request_timeout_seconds: float
    poll_interval_seconds: float
    poll_timeout_seconds: float


class MinerUDocument(BaseModel):
    """One binary source document submitted to MinerU."""

    model_config = ConfigDict(frozen=True)

    source_path: Path
    original_relative_path: str
    target_relative_path: str
    upload_name: str
    data_id: str


class PromptPaths(BaseModel):
    """Virtual paths exposed by Deep Agents' filesystem backend."""

    model_config = ConfigDict(frozen=True)

    source_dir: str = "/company-handbook"
    draft_dir: str = "/generated-wiki/drafts"
    instructions_file: str = "/wiki-instructions.md"
    plan_file: str = "/generated-wiki/_plan.json"


class ValidationIssue(BaseModel):
    """One deterministic Wiki validation finding."""

    model_config = ConfigDict(frozen=True)

    level: str
    code: str
    message: str
    path: str


class ValidationReport(BaseModel):
    """Aggregate result returned by page and tree validators."""

    issues: list[ValidationIssue] = Field(default_factory=list)
    checked_files: int = 0

    @computed_field
    @property
    def valid(self) -> bool:
        return not any(item.level == "error" for item in self.issues)

    @computed_field
    @property
    def errors(self) -> int:
        return sum(item.level == "error" for item in self.issues)

    @computed_field
    @property
    def warnings(self) -> int:
        return sum(item.level == "warning" for item in self.issues)

    def add(self, level: str, code: str, message: str, path: str) -> None:
        self.issues.append(
            ValidationIssue(level=level, code=code, message=message, path=path)
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class InitWikiResponse(BaseModel):
    """Completed Wiki initialization result."""

    status: Literal["completed"] = "completed"
    summary: str
    output_dir: Path
    validation: ValidationReport


class WikiStatusResponse(BaseModel):
    """Current persisted Wiki availability."""

    status: Literal["ready", "empty"]
    initialized: bool
    source_file_count: int = Field(ge=0)
    wiki_page_count: int = Field(ge=0)
    message: str


class SourceFileFingerprint(BaseModel):
    """Stable content fingerprint for one normalized source file."""

    model_config = ConfigDict(frozen=True)

    path: str
    sha256: str
    size: int = Field(ge=0)


class SourceManifest(BaseModel):
    """Persisted source baseline used by the update workflow."""

    model_config = ConfigDict(frozen=True)

    version: Literal[1] = 1
    files: list[SourceFileFingerprint] = Field(default_factory=list)


class WikiPageMapping(BaseModel):
    """Deterministic one-to-one mapping from a source file to a Wiki page."""

    model_config = ConfigDict(frozen=True)

    source_path: str
    source_sha256: str
    page_path: str


class WikiPageChange(BaseModel):
    """One source change together with its deterministic Wiki page target."""

    model_config = ConfigDict(frozen=True)

    change: Literal["added", "modified", "deleted"]
    source_path: str
    page_path: str
    source_sha256: str | None = None


class SourceChangeSet(BaseModel):
    """Source files changed since the last successful init or update."""

    model_config = ConfigDict(frozen=True)

    baseline_exists: bool
    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

    @computed_field
    @property
    def total(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)


class UpdateChangesResponse(BaseModel):
    """Read-only preview of pending normalized-source changes."""

    status: Literal["changes_detected", "no_changes"]
    changes: SourceChangeSet


class UpdateWikiRequest(BaseModel):
    """Optional administrator guidance for an incremental Wiki update."""

    message: str | None = Field(default=None, max_length=2000)


class UpdateWikiResponse(BaseModel):
    """Result of one incremental Wiki maintenance run."""

    status: Literal["completed", "no_changes"]
    summary: str
    output_dir: Path
    changes: SourceChangeSet
    updated_pages: list[str] = Field(default_factory=list)
    deleted_pages: list[str] = Field(default_factory=list)
    validation: ValidationReport


class ChatRequest(BaseModel):
    """One employee question with an optional conversation continuation ID."""

    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class ChatTurn(BaseModel):
    """One retained user or assistant message in a chat conversation."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: str


class ChatResponse(BaseModel):
    """Grounded answer returned by the company Wiki chat workflow."""

    status: Literal["completed"] = "completed"
    conversation_id: str
    answer: str
    sources: list[str] = Field(default_factory=list)


class ChatResetResponse(BaseModel):
    """Result of forgetting one in-memory chat conversation."""

    status: Literal["reset"] = "reset"
    conversation_id: str
    existed: bool


class HealthResponse(BaseModel):
    """Service health response."""

    status: Literal["ok"] = "ok"
    service: str = "company-wiki"
