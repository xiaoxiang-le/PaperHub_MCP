# PaperHub MCP

PaperHub 是通过 MCP 客户端操作的本地论文管理服务，支持 PDF、DOCX、Markdown 和 LaTeX 文献的扫描、检索、分类、格式转换、翻译和写作大纲生成。需要 Python 3.11+。

日常操作顺序是：**准备论文目录 → 安装并配置服务 → 接入 MCP 客户端 → 扫描建库 → 检索和核对元数据 → 分类预览并应用 → 按需转换、翻译或生成大纲 → 打开输出文件**。扫描、检索和分类可在本地完成；使用翻译功能时才需要配置外部模型服务。

## 1. 首次安装：准备项目和论文目录

以下以 Windows PowerShell 为例，假设项目放在 `C:/Projects/PaperHub_MCP`，论文放在 `D:/Papers`。请将示例路径换成自己的真实路径。

如果已下载本项目，直接进入已有项目目录；否则先克隆：

```powershell
git clone https://github.com/xiaoxiang-le/PaperHub_MCP.git C:/Projects/PaperHub_MCP
Set-Location C:/Projects/PaperHub_MCP
```

将几篇论文放到 `D:/Papers`，也可以按年份或研究方向建立子目录。首次建议用少量文献跑通流程，再扫描完整文献库。支持的扫描扩展名为 `.pdf`、`.docx`、`.md`、`.tex`。

在项目根目录执行：

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,conversion]"
Copy-Item examples/config.toml paperhub.toml
```

`dev` 安装测试和检查工具，`conversion` 安装可由服务自动发现的 Pandoc 二进制。仅使用扫描、检索和分类时，可以改为 `pip install -e .`。复制配置模板只需在首次安装时执行，已有配置时请直接编辑，避免覆盖自己的设置。

macOS/Linux 对应使用 `python3 -m venv .venv`、`.venv/bin/python`、`.venv/bin/paperhub-mcp`，复制文件使用 `cp examples/config.toml paperhub.toml`。也可在项目目录执行 `uv sync --locked --extra dev --extra conversion` 安装锁定依赖，再通过 `uv run paperhub-mcp --config paperhub.toml` 启动。

## 2. 配置：区分原文、服务数据和输出目录

打开刚复制的 `paperhub.toml`，修改以下字段。这里是配置片段；请在模板中修改已有字段，不要重复添加同名表。

```toml
data_dir = "C:/PaperHubData"

[library]
paths = ["D:/Papers"]
file_types = ["pdf", "docx", "md", "tex"]
default_apply_mode = "index"

[convert]
output_dir = "C:/PaperHubOutput"
timeout = 120
pandoc_path = "auto"
```

| 配置项 | 用途 | 示例 |
|---|---|---|
| `library.paths` | 允许读取和扫描的论文目录，可填写多个目录 | `["D:/Papers", "E:/Research"]` |
| `data_dir` | 保存数据库、任务记录、翻译检查点和已安装插件 | `C:/PaperHubData` |
| `convert.output_dir` | 保存转换、翻译、引用、大纲和分类文件操作的输出 | `C:/PaperHubOutput` |
| `library.default_apply_mode` | 未指定模式时的分类方式，初次使用建议保留 `index` | `index` |

Windows 的 TOML 路径建议使用 `/`。使用绝对路径可以避免客户端工作目录不同带来的歧义。论文目录需事先存在；数据和输出目录由程序按需创建。建议将三个目录分开，便于管理和备份。

只有授权目录内的原文才能被读取。术语表、DOCX 模板和 CSL 样式文件也应放在授权目录内。所有新输出写入 `output_dir`，不会覆盖已有同名文件。`paperhub.toml` 是本机配置，已被 Git 忽略。

运行诊断：

```powershell
.\.venv\Scripts\paperhub-mcp --config paperhub.toml --doctor
```

核对输出中的 `library_paths` 是否指向自己的论文目录且 `exists` 为 `true`；核对 `data_dir` 和 `output_dir`。`engines` 显示转换引擎路径，`api_keys` 仅显示密钥是否配置。首次只扫描和检索时，没有翻译密钥、LibreOffice 或 XeLaTeX 不影响这些操作。

## 3. 接入 MCP 客户端并确认服务可用

PaperHub 的业务操作由支持 MCP 的聊天客户端调用。终端用于安装、配置和诊断；下文的工具参数 JSON 是 **MCP 工具的输入参数，不是 PowerShell 命令**。你可以在客户端直接用自然语言提出请求，由助手调用对应工具。

### 3.1 默认方式：客户端启动 stdio 服务

在客户端的 MCP 服务配置中添加以下内容；已有 `mcpServers` 时，将 `paperhub` 合并进去即可。参考 [客户端配置示例](examples/mcp-client.json)。

```json
{
  "mcpServers": {
    "paperhub": {
      "command": "C:/Projects/PaperHub_MCP/.venv/Scripts/paperhub-mcp.exe",
      "args": ["--config", "C:/Projects/PaperHub_MCP/paperhub.toml"]
    }
  }
}
```

将 `command` 和 `--config` 后面的路径换成自己的绝对路径，保存后重新加载客户端的 MCP 连接或重启客户端。使用此方式时，客户端负责启动服务，无需提前在终端运行另一个 stdio 服务。

在客户端发送：

> 请调用 PaperHub 的 ping 和 doctor，确认服务连接正常，并告诉我当前授权的论文目录和输出目录。

成功后，`ping` 返回服务名称和版本，`doctor` 返回当前配置和依赖诊断。确认工具可用，再进入扫描步骤。

如果手工执行下面的命令，服务会等待 MCP 的标准输入；终端没有交互菜单属于正常现象，可按 `Ctrl+C` 停止。

```powershell
.\.venv\Scripts\paperhub-mcp --config paperhub.toml
```

### 3.2 可选方式：本机 HTTP 服务

如果客户端支持连接已有的 MCP HTTP 服务，在终端执行：

```powershell
.\.venv\Scripts\paperhub-mcp --config paperhub.toml --transport streamable-http --port 8765
```

保持该终端运行，在客户端连接 `http://127.0.0.1:8765/mcp`，再调用 `ping`。服务只监听本机，面向单用户使用。具体连接入口取决于客户端。

## 4. 第一次完整操作：扫描、查找并整理论文

### 4.1 扫描建库，等待任务完成

向客户端发送：

> 请扫描 D:/Papers，包括子目录。拿到任务 ID 后继续查询进度，完成后告诉我新增、更新、跳过、缺失和失败的文件数。

助手调用 `scan_library`，参数为：

```json
{"path": "D:/Papers", "recursive": true}
```

成功提交任务的返回示例：

```json
{"ok": true, "data": {"task_id": "<task-id>", "status": "pending"}}
```

接着调用 `get_task_status`：

```json
{"task_id": "<task-id>"}
```

把 `<task-id>` 换成实际返回的 `data.task_id`。看到 `data.status` 为 `done` 才表示任务完成；扫描报告位于 `data.result`，包含 `added`、`updated`、`skipped`、`missing`、`failed`、`denied`。即使任务完成，也要查看失败和拒绝读取的文件列表。

再次扫描相同目录时会进行增量处理：未变化的文件会跳过，新增或变化的文件会更新索引。扫描只建库，不会自动移动论文或生成翻译文件。

### 4.2 检索文献并保存论文 ID

发送：

> 请在文献库中搜索 transformer，最多返回 10 篇，展示标题、年份、摘要、文件路径和论文 ID。

对应 `search_papers`：

```json
{"query": "transformer", "limit": 10, "semantic": false}
```

成功结果位于 `data` 数组，每篇论文的 `id` 就是后续使用的 `paper_id`。工具不会把文件名自动当作论文 ID。需要限制年份时，可增加 `"year_range": [2020, 2026]`。

查看某篇详情，调用 `get_paper_info`：

```json
{"paper_id": "<paper-id>"}
```

自动提取的元数据可能不完整。若标题或年份有误，可让助手调用 `update_paper_metadata`：

```json
{"paper_id": "<paper-id>", "fields": {"title": "Corrected Paper Title", "year": 2024}}
```

这会修正数据库中的元数据，不修改原文。查重可调用 `find_duplicates`，它返回疑似重复论文及原因，由你决定后续如何处理。

### 4.3 先生成分类预览，再决定是否应用

发送：

> 请将已索引论文分成 3 个主题，先展示每个主题的名称和包含的论文，等我看完再应用。

对应 `classify_papers`：

```json
{"num_topics": 3}
```

此步骤生成草案，不改原文件。成功结果的 **`data.id` 是分类方案 ID**，不是 `task_id`；后续作为 `plan_id` 传入。指定部分论文时，增加 `"scope": ["<paper-id-1>", "<paper-id-2>"]`，否则默认处理全部可用论文。

想调整方案，可以让助手重命名、合并、拆分或调整论文归属。对应 `adjust_classification` 的 `topics` 必须包含完整新分组，原方案中的每篇论文恰好出现一次：

```json
{
  "plan_id": "<plan-id>",
  "topics": [
    {"name": "主题 A", "paper_ids": ["<paper-id-1>"]},
    {"name": "主题 B", "paper_ids": ["<paper-id-2>"]}
  ]
}
```

以上只演示两篇论文的情况；实际操作需包含原方案的全部论文。可调用 `get_classification` 查看调整后的方案。

### 4.4 应用分类，必要时撤销

确认分组后，首次建议发送：

> 使用 index 模式应用刚才的分类方案。

对应 `apply_classification`：

```json
{"plan_id": "<plan-id>", "mode": "index"}
```

| 模式 | 实际效果 | 使用前提 |
|---|---|---|
| `index` | 在数据库建立主题归属，原文位置不变 | 适合先跑通流程 |
| `symlink` | 在输出目录的 `classified` 下按主题创建链接 | 系统需允许创建符号链接 |
| `move` | 将原文移动到输出目录的 `classified` 下 | 先查看移动预览并确认 |

应用后，可将方案中主题的 `id` 作为 `search_papers` 的 `topic` 参数，查询该主题内的论文。

使用 `move` 时，首次调用会返回 `ok: false`、`error.code: E_CONFIRM_REQUIRED`，以及 `error.preview`、`error.confirm_token`。这是待确认状态。助手应展示源路径和目标路径；你同意后，才使用相同参数并增加令牌再次调用：

```json
{"plan_id": "<plan-id>", "mode": "move", "confirm_token": "<confirm-token>"}
```

不满意已应用的方案，可调用 `undo_classification`：

```json
{"plan_id": "<plan-id>"}
```

它撤销主题归属、移除分类链接或恢复移动的原文。若文件内容已变化或原路径出现冲突，会停止并报告问题。需要重新分类时，撤销后生成新的方案。

## 5. 按需操作：导出引用和转换格式

### 5.1 导出参考文献

发送：

> 请把刚才找到的论文导出成 BibTeX，并告诉我输出文件路径。

对应 `export_bibtex`：

```json
{"scope": ["<paper-id-1>", "<paper-id-2>"], "style": "bibtex"}
```

不传 `scope` 时导出全部可用论文；`style` 也可为 `csl-json`。返回的 `data.path` 是文件路径，`data.count` 是导出的文献数。请核对元数据再用于正式引用。

### 5.2 单篇转换

例如把某篇 PDF 转成 Markdown，调用 `convert_format`：

```json
{"paper_id": "<paper-id>", "target_format": "md"}
```

也可以直接指定授权目录内的文件：

```json
{"path": "D:/Papers/example.pdf", "target_format": "md"}
```

`paper_id` 与 `path` 必须二选一。返回 `data.task_id` 后，调用 `get_task_status` 等待完成，从 `data.result.path` 获取输出路径，并查看 `warnings`。

### 5.3 批量转换及引擎选择

将指定论文批量转成 DOCX，调用 `batch_convert`：

```json
{"scope": ["<paper-id-1>", "<paper-id-2>"], "target_format": "docx"}
```

任务完成后检查 `data.result.results` 和 `data.result.failed`。批量任务可能显示 `done`，同时包含失败文件；应逐项查看原因。

| 转换需求 | 依赖和说明 |
|---|---|
| PDF → MD | 内置 pypdf 抽取文本 |
| PDF → DOCX/TEX/HTML | 先抽取为 MD，再调用 Pandoc |
| MD/DOCX/TEX/HTML 之间转换 | Pandoc |
| DOCX → PDF | LibreOffice，需能找到 `soffice` |
| 其他支持格式 → PDF | Pandoc 和 XeLaTeX |

`.[conversion]` 提供 Pandoc，LibreOffice 和 PDF 渲染引擎仍需单独安装。安装后重新运行 `--doctor` 核对引擎路径。扫描版 PDF 可能需要先用其他 OCR 工具处理；项目会给出 OCR 提示，不自动完成 OCR。PDF 转换不保证原有排版、公式和图片完整恢复，请检查输出。

## 6. 翻译流程：配置模型、确认外发、查看结果和续译

### 6.1 配置翻译后端

在 `paperhub.toml` 中找到对应后端表，将 `model` 改为自己账户可用的模型名称。例如：

```toml
[translate.backends.openai]
model = "替换为实际模型名称"
```

使用 OpenAI 时，在启动服务的 PowerShell 中设置：

```powershell
$env:OPENAI_API_KEY = "替换为自己的 API Key"
```

使用 Anthropic 时，改为设置 `ANTHROPIC_API_KEY`，并填写 `[translate.backends.anthropic]` 下的 `model`。模型也可通过 `PAPERHUB_OPENAI_MODEL` 或 `PAPERHUB_ANTHROPIC_MODEL` 指定。

环境变量只对当前进程及其之后启动的子进程生效。如果服务由桌面客户端启动，需要让该客户端及服务进程能够继承密钥环境变量；仅在另一个 PowerShell 中设置不会更新已运行的客户端。重新启动客户端或服务后，调用 `doctor` 确认对应 `api_keys` 为 `true`。不要将真实密钥写入 TOML 或提交到仓库。

若配置了 `input_per_million` 和 `output_per_million`，预览会估算金额；未配置时金额为 `null`，仍会估算 tokens。这不表示翻译免费。

### 6.2 先试译摘要

发送：

> 请把这篇论文的标题和摘要翻译成中文，先告诉我使用的后端、外发内容和费用估算，等我确认再执行。

对应 `translate_abstract`：

```json
{"paper_id": "<paper-id>", "target_lang": "zh-CN", "backend": "openai"}
```

首次返回 `E_CONFIRM_REQUIRED`。你看过预览并同意后，助手用原参数加上返回的 `error.confirm_token` 再次调用。成功后直接返回原文和译文，**摘要翻译不返回后台任务 ID**。

### 6.3 全文或双语翻译

调用 `translate_paper`：

```json
{
  "paper_id": "<paper-id>",
  "target_lang": "zh-CN",
  "backend": "openai",
  "mode": "bilingual",
  "glossary": {"attention": "注意力", "transformer": "Transformer"}
}
```

`mode: "full"` 输出译文，`mode: "bilingual"` 输出原文和译文对照。首次同样先确认外发；同意后携带令牌再次调用，拿到 `data.task_id`，再用 `get_task_status` 查询。完成后从 `data.result.path` 打开 Markdown 文件，检查术语警告和公式、代码、引用结构。

术语较多时，可在授权目录中保存 UTF-8 CSV 文件：

```csv
source,target
attention,注意力
neural network,神经网络
```

先调用 `load_glossary`，参数为 `{"path": "D:/Papers/glossary.csv"}`，再将返回的 `data` 字典作为翻译工具的 `glossary` 参数。

### 6.4 失败、取消和续译

长任务可用 `cancel_task` 申请取消：

```json
{"task_id": "<task-id>"}
```

通过 `get_task_status` 确认最终状态。遇到 `failed`，先查看报告、修复密钥、模型、超时或源文件等问题。状态为 `failed`、`cancelled` 或 `interrupted` 时，可调用 `resume_task`：

```json
{"task_id": "<task-id>"}
```

续译使用同一个任务 ID，复用已成功保存的分块。`pending`、`running` 和 `done` 状态的任务不能这样恢复。源文件或关键配置变化时，应按错误提示重新扫描或重新发起任务。

## 7. 大纲流程：安装插件、生成、检查和导出

发送：

> 请列出大纲插件。我想使用 outline-survey，根据选中的论文生成综述大纲，先展示插件权限供我确认。

先调用 `list_plugins`，再调用 `install_plugin`：

```json
{"plugin_name": "outline-survey"}
```

首次返回权限预览和确认令牌。你同意后再次调用：

```json
{"plugin_name": "outline-survey", "confirm_token": "<confirm-token>"}
```

确认插件已安装且启用；如果被停用，调用 `enable_plugin`。然后调用 `generate_outline`：

```json
{
  "plugin": "outline-survey",
  "scope": ["<paper-id-1>", "<paper-id-2>"],
  "options": {"title": "Transformer 研究综述"}
}
```

不传 `scope` 时使用全部可用论文。返回 `data.id` 作为 `outline_id`；先检查章节、要点和引用建议，可通过 `edit_outline` 修改标题和完整章节列表，再调用 `export_outline`：

```json
{"outline_id": "<outline-id>", "target_format": "md"}
```

返回的 `data.path` 是输出文件。`md` 原生可用，`docx`、`tex` 需要 Pandoc。内置插件生成的是结构化大纲和引用建议，不是已经核验的完整综述正文。第三方本地 wheel 插件的安装与开发方法见 [插件开发文档](docs/plugins.md)。

## 8. 日常使用、返回值和排查

以后使用时无需重新安装：启动 MCP 客户端，新增论文后扫描对应目录，再检索或执行其他操作即可。

### 返回值和 ID 对照

| 操作 | 下一步需要的字段 | 后续用途 |
|---|---|---|
| 扫描、转换、全文翻译 | `data.task_id` | 查询、取消和恢复任务 |
| 搜索论文 | `data` 数组中各论文的 `id` | 作为 `paper_id` 或 `scope` 元素 |
| 生成分类方案 | `data.id` | 作为 `plan_id` 查看、调整、应用或撤销 |
| 生成大纲 | `data.id` | 作为 `outline_id` 编辑或导出 |
| 待确认操作 | `error.confirm_token` | 用户同意后用相同参数再次调用 |
| 文件输出 | `data.path` 或任务的 `data.result.path` | 打开实际生成的文件 |

普通成功响应是 `{"ok": true, "data": ...}`，业务错误是 `{"ok": false, "error": ...}`。查询任务时，工具返回成功只表示查询成功，仍需检查 `data.status`。`progress` 为 0～1。

任务状态通常是 `pending → running → done / failed / cancelled`。服务异常退出后，下次启动会将未完成任务标记为 `interrupted`，需显式恢复。服务运行时请保留它的进程，尤其是在长任务执行期间。

确认令牌默认有效期为 300 秒且只能使用一次，并绑定操作参数及相关文件/方案内容。过期或参数变化后，需要重新取得预览并确认。

### 输出在哪里

所有文件以返回的实际路径为准，通常位于 `output_dir` 的以下子目录：

| 子目录 | 内容 |
|---|---|
| `converted` | 单篇和批量转换文件 |
| `translations` | 全文或双语翻译 Markdown |
| `references` | BibTeX 和 CSL JSON |
| `outlines` | 大纲 Markdown；其他格式转换输出见返回路径 |
| `classified` | 分类链接或移动后的原文；index 模式只更新数据库 |

备份时建议同时保留论文原文和 `data_dir`；后者包含数据库、任务、方案、操作日志及翻译检查点。不要在任务执行期间删除数据目录。

### 常见问题

| 现象 | 排查步骤 |
|---|---|
| 客户端看不到工具或连接失败 | 核对可执行文件和配置文件绝对路径，先在终端运行 `--doctor`，再重新加载 MCP 连接 |
| 终端启动后一直等待 | stdio 服务在等待 MCP 输入；使用客户端连接，或选择 HTTP 模式 |
| 扫描路径被拒绝 | 将原文目录加入 `library.paths`，核对实际路径并重载配置 |
| 找不到新放入的论文 | 重新扫描对应目录，等待完成并查看 `failed` 和 `denied` |
| 转换报告缺少引擎 | 按转换依赖表安装引擎，重新运行 `doctor` 核对路径 |
| PDF 没有可提取正文 | 检查是否为扫描件，先进行 OCR 再扫描或转换 |
| Windows 无法创建分类链接 | 检查符号链接权限，或使用 `index` 模式 |
| 返回 `E_CONFIRM_REQUIRED` | 查看预览，用户同意后携带令牌再次调用 |
| 翻译提示密钥或模型未配置 | 检查服务进程继承的环境变量与后端 `model`，通过 `doctor` 确认 |
| 分类提示源文件变化 | 重新扫描并生成方案，使用新的方案 ID |
| 批量任务完成但有文件失败 | 查看 `result.failed`，按失败原因处理对应文件 |

修改 TOML 后，在没有活动任务时调用 `reload_config`。修改 `data_dir` 需重启服务。运行中的进程无法通过重载获得另一个终端中新设置的环境变量，这类变化需要重新启动并正确继承环境。

### 可选：启用本地语义模型

默认 `tfidf` 是离线词法基线。需要句子模型的语义检索时，安装：

```powershell
.\.venv\Scripts\python -m pip install -e ".[semantic]"
```

在 `[embedding]` 中设置 `engine = "sentence-transformers"`，将 `model` 设置为已下载好的本地模型目录，重载配置或重启后使用 `search_papers` 的 `semantic: true`。运行时使用 `local_files_only=True`，不会自动下载模型。

## 9. 开发验证和进一步阅读

在项目根目录执行：

```powershell
.\.venv\Scripts\python -m pytest --cov=paperhub --cov-report=term-missing
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\python -m build
```

开发测试使用模拟翻译后端，不调用付费 API。本项目尚未发布到 PyPI；使用本地源码安装，也可使用 `uvx --from /absolute/path/to/project paperhub-mcp` 启动本地项目。

更多说明：[工具参数手册](docs/tools.md)、[交付范围与需求映射](docs/delivery.md)、[验证记录](docs/validation.md)、[插件开发](docs/plugins.md)、[隐私与安全](docs/security.md)。原始产品与需求文档保留在项目根目录。
