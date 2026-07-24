这是已有 Wiki 的增量更新工作流。

- 先读取 `$instructions_file`、根 `quickstart.md`、根 `index.md`、当前资料清单和
  资料变更清单。
- 每个当前源文件必须且只能保留一个页面；不得把多个文件合并。
- `added`：读取源文件并在镜像目录中创建页面。
- `modified`：用 `grep` 根据页面 front matter 中的 `source_path` 找到对应页面，读取
  源文件后重写或精确编辑，并更新 `source_sha256`。
- `deleted`：用 `grep` 找到记录该 `source_path` 的页面，再使用 `delete_wiki_page` 删除。
- 不创建、编辑或删除 `quickstart.md` 和 `index.md`；Middleware 会根据实际
  一级目录重建唯一根 quickstart，并递归重建全部目录索引。
- 先在 `$plan_file` 写入影响计划。完成后核对每个当前资料都有且只有一个页面，
  所有页面仍为 `draft`，然后结束。
