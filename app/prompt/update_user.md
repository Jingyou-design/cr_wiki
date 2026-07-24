运行根目录：`$runtime_root`

资料源：`$source_dir`

现有 Wiki 草稿：`$draft_dir`

本次确定性更新上下文：

```json
$update_context
```

管理员补充要求：

$user_message

严格遵循 `current_sources` 和 `source_changes`。页面必须通过其 front matter 的
`source_path` 与当前资料对应。
