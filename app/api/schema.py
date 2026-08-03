"""Pydantic data models shared across the company Wiki application."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class WorkflowContext(BaseModel):
    """Filesystem context for one Wiki workflow run."""

    project_root: Path


class MinerUConfig(BaseModel):
    """Configuration used by the MinerU document parsing client."""

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

    source_path: Path
    target_relative_path: str
    upload_name: str
    data_id: str


class PromptPaths(BaseModel):
    """Virtual paths exposed by Deep Agents' filesystem backend."""

    source_dir: str = "/company-handbook"
    draft_dir: str = "/generated-wiki/drafts"
    instructions_file: str = "/wiki-instructions.md"
    plan_file: str = "/generated-wiki/_plan.json"


class DepartmentConfig(BaseModel):
    """One department and the virtual paths its employees may read."""

    code: str = Field(min_length=1,max_length=50,pattern=r"^[a-z][a-z0-9_-]*$",)
    name: str = Field(min_length=1, max_length=100)
    read_paths: list[str] = Field(default_factory=list)


class UserConfig(BaseModel):
    """One user loaded from the JSON access-control configuration."""

    id: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)
    department_code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    role: Literal["admin", "manager", "employee"] = "employee"
    is_active: bool = True


class AccessControlConfig(BaseModel):
    """Validated structure of access-control.json."""

    version: Literal[1] = 1
    departments: list[DepartmentConfig] = Field(default_factory=list)
    users: list[UserConfig] = Field(default_factory=list)


class LoginRequest(BaseModel):
    """Credentials submitted to create a login session."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)


class AuthenticatedUserContext(BaseModel):
    """Password-free identity used by backend authorization."""

    user_id: str
    username: str
    department_code: str
    role: Literal["admin", "manager", "employee"]
    config_revision: str


class CurrentUserResponse(BaseModel):
    """Safe current-user information returned to the frontend."""

    id: str
    username: str
    department_code: str
    role: Literal["admin", "manager", "employee"]
    config_revision: str


class ValidationIssue(BaseModel):
    """One deterministic Wiki validation finding."""

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

    path: str
    sha256: str
    size: int = Field(ge=0)


class SourceManifest(BaseModel):
    """Persisted source baseline used by the update workflow."""

    version: Literal[1] = 1
    files: list[SourceFileFingerprint] = Field(default_factory=list)


class SourceChangeSet(BaseModel):
    """Source files changed since the last successful init or update."""

    baseline_exists: bool
    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

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


class WikiTreeNode(BaseModel):
    """One directory or Markdown page in the readable Wiki tree."""

    name: str
    type: Literal["directory", "page"]
    path: str | None = None
    children: list["WikiTreeNode"] = Field(default_factory=list)


class WikiTreeResponse(BaseModel):
    """Wiki roots visible to the current user."""

    roots: list[WikiTreeNode] = Field(default_factory=list)


class WikiPageResponse(BaseModel):
    """Markdown content of one readable Wiki page."""

    path: str
    content: str
