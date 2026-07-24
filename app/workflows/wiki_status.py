from app.api.schema import WikiStatusResponse, WorkflowContext


def get_wiki_status(context: WorkflowContext) -> WikiStatusResponse:
    root = context.project_root.resolve()
    source_root = root / "company-handbook"
    draft_root = root / "generated-wiki" / "drafts"
    source_files = (
        [path for path in source_root.rglob("*") if path.is_file()]
        if source_root.is_dir()
        else []
    )
    wiki_pages = (
        [path for path in draft_root.rglob("*.md") if path.is_file()]
        if draft_root.is_dir()
        else []
    )
    initialized = bool(wiki_pages)
    return WikiStatusResponse(
        status="ready" if initialized else "empty",
        initialized=initialized,
        source_file_count=len(source_files),
        wiki_page_count=len(wiki_pages),
        message=(
            "Wiki 已存在，可以进行问答或增量更新。"
            if initialized
            else "尚未生成 Wiki，请先上传公司资料包。"
        ),
    )
