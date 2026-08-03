"""Load and render prompts for the company-wiki Deep Agent.

Prompt wording lives beside this loader in ``app/prompt/*.md`` so it can be reviewed and
edited independently of Python code.  This module only validates inputs,
selects the command-specific template, and substitutes runtime values.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from app.api.schema import PromptPaths


SYSTEM_PROMPT_VERSION = "0.7.0"
PROMPT_DIR = Path(__file__).parent


def create_system_prompt(
    paths: PromptPaths | None = None,
) -> str:
    """Render the common system prompt plus init instructions."""

    prompt_paths = paths or PromptPaths()
    mode_instructions = _render_template("init.md", _path_values(prompt_paths))
    values = {
        **_path_values(prompt_paths),
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "mode_instructions": mode_instructions,
    }
    return _render_template("common.md", values)


def create_user_prompt(
    runtime_root: str,
    *,
    sources_json: str,
    paths: PromptPaths | None = None,
) -> str:
    """Render concrete context for a single init run."""

    prompt_paths = paths or PromptPaths()

    return _render_template(
        "user.md",
        {
            **_path_values(prompt_paths),
            "runtime_root": runtime_root,
            "sources": sources_json,
        },
    )


def create_chat_system_prompt(
    paths: PromptPaths | None = None,
) -> str:
    """Render the read-only grounded chat system prompt."""

    prompt_paths = paths or PromptPaths()
    return _render_template(
        "chat.md",
        {
            **_path_values(prompt_paths),
            "prompt_version": SYSTEM_PROMPT_VERSION,
        },
    )


def create_chat_user_prompt(question: str) -> str:
    """Render one employee question for the grounded chat agent."""

    return _render_template(
        "chat_user.md",
        {"question": question.strip()},
    )


def create_update_system_prompt(
    paths: PromptPaths | None = None,
) -> str:
    """Render the common system prompt plus incremental-update instructions."""

    prompt_paths = paths or PromptPaths()
    mode_instructions = _render_template("update.md", _path_values(prompt_paths))
    values = {
        **_path_values(prompt_paths),
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "mode_instructions": mode_instructions,
    }
    return _render_template("common.md", values)


def create_update_user_prompt(
    runtime_root: str,
    *,
    update_context_json: str,
    user_message: str | None = None,
    paths: PromptPaths | None = None,
) -> str:
    """Render the deterministic source-change context for one update run."""

    prompt_paths = paths or PromptPaths()
    return _render_template(
        "update_user.md",
        {
            **_path_values(prompt_paths),
            "runtime_root": runtime_root,
            "update_context": update_context_json,
            "user_message": (
                user_message.strip()
                if user_message and user_message.strip()
                else "无。"
            ),
        },
    )


def _render_template(name: str, values: dict[str, str]) -> str:
    template_path = PROMPT_DIR / name
    if not template_path.is_file():
        raise FileNotFoundError(f"Prompt template does not exist: {template_path}")
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.substitute(values).strip()


def _path_values(paths: PromptPaths) -> dict[str, str]:
    return {
        "source_dir": paths.source_dir,
        "draft_dir": paths.draft_dir,
        "instructions_file": paths.instructions_file,
        "plan_file": paths.plan_file,
    }
