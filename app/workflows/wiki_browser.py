"""Read generated Wiki pages through the current access-control rules."""

from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status

from app.api.schema import (
    AuthenticatedUserContext,
    WikiPageResponse,
    WikiTreeNode,
    WikiTreeResponse,
)
from app.config.settings import settings
from app.workflows.auth import department_for


_WIKI_PREFIX = "/generated-wiki/drafts"


def get_wiki_tree(user: AuthenticatedUserContext) -> WikiTreeResponse:
    draft_root = _draft_root()
    roots = (
        [PurePosixPath(".")]
        if user.role == "admin"
        else _allowed_roots(user)
    )
    nodes = []
    for root in roots:
        folder = (
            draft_root
            if root == PurePosixPath(".")
            else draft_root.joinpath(*root.parts).resolve()
        )
        if folder.is_relative_to(draft_root) and folder.is_dir():
            nodes.append(_tree_node(folder, draft_root))
    return WikiTreeResponse(roots=nodes)


def get_wiki_page(
    path: str,
    user: AuthenticatedUserContext,
) -> WikiPageResponse:
    draft_root = _draft_root()
    relative = _relative_path(path)
    page = draft_root.joinpath(*relative.parts).resolve()
    virtual_path = f"{_WIKI_PREFIX}/{relative.as_posix()}"

    if not _can_read(user, virtual_path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号没有权限读取该页面。",
        )
    if (
        not page.is_relative_to(draft_root)
        or page.suffix.lower() != ".md"
        or not page.is_file()
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wiki页面不存在。",
        )
    return WikiPageResponse(
        path=relative.as_posix(),
        content=page.read_text(encoding="utf-8"),
    )


def _tree_node(folder: Path, draft_root: Path) -> WikiTreeNode:
    children = []
    for item in sorted(folder.iterdir(), key=lambda value: value.name):
        if item.is_symlink() or item.name.startswith("."):
            continue
        if item.is_dir():
            children.append(_tree_node(item, draft_root))
        elif item.suffix.lower() == ".md" and item.name != "index.md":
            children.append(
                WikiTreeNode(
                    name=item.stem,
                    type="page",
                    path=item.relative_to(draft_root).as_posix(),
                )
            )

    index = folder / "index.md"
    return WikiTreeNode(
        name=folder.name,
        type="directory",
        path=(
            index.relative_to(draft_root).as_posix()
            if index.is_file()
            else None
        ),
        children=children,
    )


def _allowed_roots(
    user: AuthenticatedUserContext,
) -> list[PurePosixPath]:
    prefix = f"{_WIKI_PREFIX}/"
    roots = {
        PurePosixPath(rule[len(prefix):-3])
        for rule in department_for(user).read_paths
        if rule.startswith(prefix) and rule.endswith("/**")
    }
    return sorted(roots, key=lambda value: value.as_posix())


def _can_read(
    user: AuthenticatedUserContext,
    virtual_path: str,
) -> bool:
    if user.role == "admin":
        return True
    for rule in department_for(user).read_paths:
        if rule.endswith("/**"):
            root = rule[:-3]
            if virtual_path.startswith(f"{root}/"):
                return True
        elif virtual_path == rule:
            return True
    return False


def _relative_path(path: str) -> PurePosixPath:
    value = path.strip().replace("\\", "/").lstrip("/")
    prefix = f"{_WIKI_PREFIX.lstrip('/')}/"
    if value.startswith(prefix):
        value = value[len(prefix):]
    return PurePosixPath(value)


def _draft_root() -> Path:
    project_root = settings.wiki_project_root.expanduser().resolve()
    if not (project_root / "generated-wiki").exists():
        project_root = project_root / "data"
    return (project_root / "generated-wiki" / "drafts").resolve()
