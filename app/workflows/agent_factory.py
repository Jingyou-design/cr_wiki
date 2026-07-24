"""Build the init Deep Agent with workflow filesystem guardrails."""

from __future__ import annotations

from app.api.schema import WorkflowContext
from app.config.settings import settings
from app.config.runtime import validate_layout

from app.prompt.loader import create_system_prompt
from app.workflows.validation_middleware import WikiValidationMiddleware


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

    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import FilesystemBackend

    validate_layout(context)
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


def create_chat_agent(context: WorkflowContext):
    """Create a read-only Deep Agent for grounded employee questions."""

    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import FilesystemBackend

    from app.prompt.loader import create_chat_system_prompt

    validate_layout(context)
    backend = FilesystemBackend(root_dir=context.project_root, virtual_mode=True)
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/.env", "/.env.*", "/**/.env", "/**/.env.*"],
            mode="deny",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=_READABLE_DIRECTORY_PATHS,
            mode="allow",
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="deny"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    return create_deep_agent(
        model=_create_deepseek_model(),
        system_prompt=create_chat_system_prompt(),
        backend=backend,
        permissions=permissions,
        name="company-wiki-chat",
    )


def create_update_agent(context: WorkflowContext):
    """Create an incremental Wiki maintenance Agent with narrow page deletion."""

    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import FilesystemBackend

    from app.prompt.loader import create_update_system_prompt
    from app.tools.wiki_files import create_delete_wiki_page_tool

    validate_layout(context)
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
    from langchain_deepseek import ChatDeepSeek

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
