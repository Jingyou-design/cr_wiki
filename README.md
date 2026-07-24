# 创然公司 Wiki（Python 版）

这是一个基于 LangChain Deep Agents 的公司 Wiki 生成器。目前实现管理员上传
公司资料 ZIP、通过 MinerU 将 PDF/Office/图片转换为 Markdown，以及读取
`company-handbook/` 生成待人工审核的 Wiki 草稿。

## 当前数据流

```text
POST /api/wiki/sources/upload
  -> 直接解压到 company-handbook/
  -> 同步等待 MinerU 解析完成
  -> 文本文件保留原样
  -> PDF / Word / Excel / PPT / 图片批量提交 MinerU
  -> 轮询 MinerU 并下载 full.md
  -> company-handbook/
  -> 对每个 company-handbook 文件计算确定性页面路径和 SHA-256
  -> 动态镜像上传资料的全部目录层级
  -> create_deep_agent
  -> langchain-deepseek / ChatDeepSeek
  -> DeepSeek API
  -> Deep Agent 内置 ls/glob/grep/read_file/write_file/edit_file
  -> 一个源文件生成一个 generated-wiki/drafts/.../*.md
  -> 根目录只生成一个 quickstart.md
  -> Middleware 写后自动校验
  -> Middleware 为根目录和每级资料目录递归生成 index.md
  -> init 工作流执行整体验收

POST /api/wiki/chat
  -> 加载只读问答提示词和有限轮次的会话上下文
  -> quickstart -> 根 index -> 目录 index -> Wiki 文档页
  -> Wiki 缺失、含糊、冲突或用户要求核对原文时才回读 company-handbook
  -> 返回有依据的回答、Wiki 页面路径和必要的原文路径

GET /api/wiki/update/changes
  -> 对 company-handbook 文件计算 SHA-256
  -> 与上次成功 init/update 的资料基线比较
  -> 返回新增、修改、删除文件，不改动 Wiki

POST /api/wiki/update
  -> 把源文件变化直接映射到唯一 Wiki 页面
  -> 新增文件创建页面、修改文件更新页面、删除文件删除页面
  -> Middleware 自动校验并递归重建各级 index.md
  -> 整体验收失败自动恢复更新前草稿
  -> 成功后原子保存新的资料基线
```

  `company-handbook/` 保留解压后的原始资料；其中原生文本和 MinerU 生成的
Markdown 会进入后续 Agent 的资料清单，并被权限规则设为只读。临时上传的 ZIP 在
任务结束后自动清理。
Agent 只能把内容写进
`generated-wiki/drafts/` 和临时的 `generated-wiki/_plan.json`，不能读取 `.env`，
也没有本地命令执行能力。

## 代码结构

- `app/api/schema.py`：统一的 Pydantic 数据模型；
- `app/config/settings.py`：基于 `BaseSettings` 的 DeepSeek 模型配置；
- `app/config/runtime.py`：init 工作目录解析和目录校验；
- `app/prompt/`：系统提示词、模式提示词和模板加载器；
- `app/tools/`：确定性的 Wiki 校验和索引生成函数；
- `app/workflows/mineru_parser.py`：MinerU 精准批量解析客户端；
- `app/workflows/`：异步资料处理、Middleware、Agent 工厂和 init 工作流；
- `app/api/router.py`：FastAPI 路由；
- `app/main.py`：FastAPI 应用入口。

## 环境准备

项目统一使用 Python 3.12，并由 `uv` 管理解释器、虚拟环境和依赖：

```powershell
uv sync --python 3.12
Copy-Item .env.example .env
```

`uv` 会自动创建项目内的 `.venv`，不需要手工激活。然后编辑 `.env`，只替换
`DEEPSEEK_API_KEY`。真实密钥不会提交到仓库，Agent 的文件权限也禁止读取它。

同时确认 `WIKI_PROJECT_ROOT` 指向包含 `company-handbook/` 的项目根目录。若资料
包包含 PDF、Word、Excel、PPT 或图片，还必须配置：

```env
MINERU_API_TOKEN=从MinerU API管理页面创建的Token
MINERU_BASE_URL=https://mineru.net
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=ch
MINERU_ENABLE_TABLE=true
MINERU_ENABLE_FORMULA=false
MINERU_IS_OCR=true
```

公司原件会发送给 MinerU 云端解析。上传内部敏感资料前，应先确认公司的第三方
数据处理和保密要求。MinerU 接口说明见
[官方文档](https://mineru.net/apiManage/docs)。

## 启动 API

开发环境可用 Uvicorn 启动 FastAPI：

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后：

- 测试控制台：`http://127.0.0.1:8000/`
- 健康检查：`GET http://127.0.0.1:8000/api/health`
- 接口文档：`http://127.0.0.1:8000/docs`
- 上传并生成 Wiki：`POST http://127.0.0.1:8000/api/wiki/sources/upload`
- 预览资料变化：`GET http://127.0.0.1:8000/api/wiki/update/changes`
- Wiki 增量更新：`POST http://127.0.0.1:8000/api/wiki/update`
- 公司问答：`POST http://127.0.0.1:8000/api/wiki/chat`
- 清空会话：`DELETE http://127.0.0.1:8000/api/wiki/chat/{conversation_id}`

## Docker 部署

Docker 版本使用 Linux 容器，避免 Windows 文件路径兼容问题。先将
`.env.example` 复制为 `.env`，填写 `DEEPSEEK_API_KEY`；如需解析 PDF、Office
或图片，再填写 MinerU 配置。然后在项目根目录执行：

```powershell
docker compose up -d --build
```

访问地址为 `http://127.0.0.1:8000/`，也可将 `.env` 中的 `WIKI_PORT` 改为其他
宿主机端口。容器代码目录为 `/app`，可变数据统一保存于宿主机的 `./data/`：

```text
data/
  company-handbook/       # 管理员上传并转换后的可读资料
  generated-wiki/         # 生成的 Wiki、索引和资料变更基线
  wiki-instructions.md    # 可选的管理员 Wiki 说明
```

`./data` 必须定期备份；删除容器或重新构建镜像不会删除这个目录。公网部署时请在
容器前配置 HTTPS 反向代理和身份认证，当前应用本身尚未提供员工登录功能。

常用 Docker 命令：

```powershell
docker compose ps       # 查看运行和健康状态
docker compose logs -f  # 查看服务日志
docker compose down     # 停止并删除容器，不删除 ./data
```

## 上传公司资料

首次部署时 `company-handbook/` 为空。管理员先上传一个 ZIP。支持 PDF、DOC、
DOCX、PPT、PPTX、XLS、XLSX、常见图片、Markdown、TXT、CSV、JSON、YAML 和
HTML：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/wiki/sources/upload" `
  -Method Post `
  -Form @{ file = Get-Item "F:\资料\company-handbook.zip" }
```

上传接口会同步完成解压、MinerU 转换和 Wiki 初始化；成功响应中直接包含 Wiki
生成摘要与校验报告。

上传后会直接清空并重建 `company-handbook/`，再将 ZIP 内容解压进去。普通文本保持
原样；二进制文档由 MinerU 生成同名 `.md` 可读文件。后续 init
和 update 只会读取文本和 Markdown，不会将 PDF、Word 等二进制原件交给 Agent。新的
ZIP 会替换已有资料包，并清空旧的 Wiki 草稿与变更基线，避免新资料被旧 Wiki 回答。

## Wiki 生成结构

系统不写死业务目录名称，而是按照上传 ZIP 解压后的实际目录动态生成。例如：

```text
company-handbook/
  公司管理制度/
    财务/
      报销制度.md
  对外发布文档/
    政策通知.docx.mineru.md

generated-wiki/drafts/
  quickstart.md
  index.md
  公司管理制度/
    index.md
    财务/
      index.md
      报销制度.md
  对外发布文档/
    index.md
    政策通知.md
```

`quickstart.md` 只在 Wiki 根目录存在，用于说明覆盖范围和使用方法。每级
`index.md` 都由程序生成，只列当前目录的文档和子目录。每个普通 Wiki 页面在
Front Matter 中记录唯一 `source_path` 和 `source_sha256`，因此 update 可以
精确定位页面，不需要让模型猜影响范围。

## 调用 init 接口

确认资料状态为 `ready` 后执行初始化：

```powershell
$body = @{
  scope = "全部公司资料"
  message = "财务制度优先突出报销时间、审批流程和票据要求"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/wiki/init" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

草稿位于 `generated-wiki/drafts/`。接口响应中的 `validation.valid: true` 只代表
格式、来源路径、内部链接和重复标题等机械规则通过，不代替人工核对制度内容。

同一时间只允许执行一个 init。已有任务运行中或草稿已经存在时，接口返回 HTTP 409，避免重复生成和互相覆盖。

## 调用 update 接口

成功执行 init 后，系统会在 `generated-wiki/.source-manifest.json` 保存资料文件
路径、大小和 SHA-256。管理员修改 `company-handbook/` 中的转换稿后，可以先
只读预览变化：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/wiki/update/changes"
```

确认 `added`、`modified` 和 `deleted` 清单后执行更新：

```powershell
$body = @{
  message = "重点核对变更制度中的金额、日期和审批流程"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/wiki/update" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

没有内容变化时，接口直接返回 `no_changes`，不会调用模型。更新期间会备份草稿；
Agent 失败或整体验收不通过时自动恢复，且不会推进资料基线。

当前 update 检测的是已经放入 `company-handbook/` 的可读资料变化。重新上传完整 ZIP
会先替换资料包并清空旧 Wiki；随后必须执行 init 重新生成 Wiki，而不是对旧 Wiki
直接 update。

## 调用 chat 接口

资料状态为 `ready`，并且 init 或 update 已成功生成与资料同步的 Wiki 后才能
提问。第一次请求只提交问题：

```powershell
$body = @{
  question = "公司报销日是哪几天？"
} | ConvertTo-Json

$result = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/wiki/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

响应包含 `answer`、`sources` 和 `conversation_id`。继续追问时，把同一个
`conversation_id` 带回请求体：

```powershell
$followUp = @{
  question = "审批流程呢？"
  conversation_id = $result.conversation_id
} | ConvertTo-Json
```

问答 Agent 只有读取权限，并严格采用 Wiki-first：先通过 quickstart 和递归索引
定位一源一页的 Wiki 文档；只有 Wiki 缺失、含糊、冲突、信息不足，或用户明确要求
核对原文时，才读取页面记录的 `company-handbook/` 来源。只要资料有待 update 或
Wiki 校验失败，Chat 会拒绝回答，避免用过期页面。当前会话只保存在单个 API 进程
的内存中，服务重启后会丢失；生产部署时应改用 Redis 或数据库，并在接口前增加
登录和访问控制。

## 尚未实现

- 草稿审核、发布和回滚；
- 登录、权限和企业微信接入；
- 上传任务的数据库持久化和多进程调度；
- MinerU 解析失败后的单文件重试和人工跳过。
