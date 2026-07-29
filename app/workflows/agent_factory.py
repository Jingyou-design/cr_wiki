"""Build the init Deep Agent with workflow filesystem guardrails."""

from __future__ import annotations

from collections.abc import Sequence

from deepagents import FilesystemPermission
from langgraph.types import Checkpointer

from app.api.schema import AuthenticatedUserContext, DepartmentConfig, WorkflowContext
from app.config.settings import settings

from app.prompt.loader import create_system_prompt
from app.workflows.validation_middleware import WikiValidationMiddleware
from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from app.prompt.loader import create_chat_system_prompt
from langchain_deepseek import ChatDeepSeek

_READABLE_DIRECTORY_PATHS = [
    "/",
    "/company-handbook",
    "/company-handbook/**",
    "/generated-wiki",
    "/generated-wiki/drafts",
    "/generated-wiki/drafts/**",
    "/wiki-instructions.md",
]


def create_init_agent(context: WorkflowContext):
    """Create the only currently enabled agent mode: Wiki initialization."""

    model = _create_deepseek_model()
    backend = FilesystemBackend(root_dir=context.project_root, virtual_mode=True)
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/.env", "/.env.*", "/**/.env", "/**/.env.*"],
            mode="deny",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=[
                *_READABLE_DIRECTORY_PATHS,
                "/generated-wiki/_plan.json",
            ],
            mode="allow",
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="deny"),
        FilesystemPermission(
            operations=["write"],
            paths=["/generated-wiki/drafts/**", "/generated-wiki/_plan.json"],
            mode="allow",
        ),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    return create_deep_agent(
        model=model,
        system_prompt=create_system_prompt(),
        middleware=[WikiValidationMiddleware(context.project_root)],
        backend=backend,
        permissions=permissions,
        name="company-wiki-init",
    )


def create_chat_agent(
    context: WorkflowContext,
    *,
    checkpointer: Checkpointer,
    permissions: Sequence[FilesystemPermission],
    user: AuthenticatedUserContext,
    department: DepartmentConfig,
):
    """Create a department-scoped Deep Agent."""
    backend = FilesystemBackend(root_dir=context.project_root, virtual_mode=True)
    access_prompt = (
        "\n\n## 当前登录身份与访问范围\n"
        f"- 用户：{user.username}\n"
        f"- 部门：{user.department_code}\n"
    )
    if user.role == "admin":
        access_prompt += "- 角色：管理员。\n"
    else:
        allowed = "\n".join(f"  - `{path}`" for path in department.read_paths)
        access_prompt += (
            "- 角色：普通员工，只读。\n"
            "- 不读取全局 quickstart.md 或根 index.md；"
            "直接在以下授权目录内使用 ls、glob、grep 和 read_file：\n"
            f"{allowed}\n"
            "- 其他部门目录不可访问，不得猜测其中内容。\n"
        )
    return create_deep_agent(
        model=_create_deepseek_model(),
        system_prompt=create_chat_system_prompt() + access_prompt,
        backend=backend,
        permissions=list(permissions),
        checkpointer=checkpointer,
        name=(
            "company-wiki-chat-admin"
            if user.role == "admin"
            else f"company-wiki-chat-{department.code}"
        ),
    )


def create_update_agent(context: WorkflowContext):
    """Create an incremental Wiki maintenance Agent with narrow page deletion."""

    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import FilesystemBackend

    from app.prompt.loader import create_update_system_prompt
    from app.tools.wiki_files import create_delete_wiki_page_tool

    backend = FilesystemBackend(root_dir=context.project_root, virtual_mode=True)
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/.env", "/.env.*", "/**/.env", "/**/.env.*"],
            mode="deny",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=[
                *_READABLE_DIRECTORY_PATHS,
                "/generated-wiki/_plan.json",
            ],
            mode="allow",
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="deny"),
        FilesystemPermission(
            operations=["write"],
            paths=["/generated-wiki/drafts/**", "/generated-wiki/_plan.json"],
            mode="allow",
        ),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    return create_deep_agent(
        model=_create_deepseek_model(),
        tools=[create_delete_wiki_page_tool(context.project_root)],
        system_prompt=create_update_system_prompt(),
        middleware=[WikiValidationMiddleware(context.project_root)],
        backend=backend,
        permissions=permissions,
        name="company-wiki-update",
    )


def _create_deepseek_model():

    if not settings.deepseek_api_key.strip():
        raise ValueError(
            "缺少 DEEPSEEK_API_KEY。请在项目根目录的 .env 中配置，"
            "不要把真实密钥提交到仓库。"
        )
    return ChatDeepSeek(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_base_url,
        temperature=settings.deepseek_temperature,
        max_retries=2,
        timeout=120,
    )
