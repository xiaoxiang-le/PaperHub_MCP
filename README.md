# PaperHub MCP

基于官方 MCP Python SDK 的本地论文管理服务。支持扫描 PDF/DOCX/Markdown/LaTeX、检索与分类预览、分类应用与撤销、格式转换、分块翻译与续译，以及可安装的大纲插件。Python 3.11+。

## 安装与启动

### 1、创建Python虚拟环境
```powershell
python -m venv .venv
```
### 2、安装项目和开发依赖
```
.\.venv\Scripts\python -m pip install -e ".[dev]"
```
### 3、复制配置模板
```
Copy-Item examples/config.toml paperhub.toml
```
### 4、编辑 paperhub.toml：设置 library.paths、data_dir 和 convert.output_dir
+ library.paths：文献库所在路径。
+ data_dir：程序存储数据的目录。
+ convert.output_dir：文件转换结果的输出目录。
### 5、运行诊断检查
```
.\.venv\Scripts\paperhub-mcp --config paperhub.toml --doctor
```
### 6、启动MCP服务
```
.\.venv\Scripts\paperhub-mcp --config paperhub.toml
```

macOS/Linux 使用 `.venv/bin/python` 和 `.venv/bin/paperhub-mcp`。也可使用 `uv run paperhub-mcp --config paperhub.toml`；本项目尚未发布到 PyPI，当前使用 `uvx --from /absolute/path/to/project paperhub-mcp`，而非直接假定 `uvx paperhub-mcp` 已可用。

无授权路径时拒绝扫描。所有输出进入配置的 `output_dir`，不覆盖已有文件。默认分类模式为 `index`。默认 TF-IDF 为离线基线，不具备句子模型的语义能力；真正的语义检索需安装 `.[semantic]`，将 `embedding.engine` 设置为 `sentence-transformers`，`embedding.model` 设置为已经下载好的本地模型目录。运行时使用 `local_files_only=True`，不会自动下载模型。

## MCP 客户端配置

参考 [客户端配置](examples/mcp-client.json)，替换绝对路径。Claude Desktop、Cursor 等客户端可使用以下服务配置：

```json
{
  "mcpServers": {
    "paperhub": {
      "command": "C:/path/to/project/.venv/Scripts/paperhub-mcp.exe",
      "args": ["--config", "C:/path/to/project/paperhub.toml"]
    }
  }
}
```

可选 `--transport streamable-http --port 8765`，只监听 `127.0.0.1`，地址为 `http://127.0.0.1:8765/mcp`。当前面向单用户本机运行。

## 工作流程

1. `scan_library(path)` → 返回 `task_id`，用 `get_task_status` 查询完成报告。
2. `classify_papers(num_topics=3)` → 返回分类方案 `id`；预览不改文件。
3. `apply_classification(plan_id, mode="index")` 建立主题索引。`symlink` 创建链接；`move` 首次返回 `E_CONFIRM_REQUIRED` 和预览，用户确认后再携带 `confirm_token` 调用。
4. `undo_classification(plan_id)` 恢复文件或移除链接；冲突时停止，不覆盖文件。
5. `convert_format(path=..., target_format="docx")` 或 `batch_convert(...)` 返回转换任务；缺外部引擎时任务报告给出安装提示。
6. `translate_paper` / `translate_abstract` 先返回外发告知与费用估算。用户确认后提交令牌。全文任务失败后 `resume_task` 复用已完成分块。
7. `install_plugin("outline-survey")` → 展示权限 → 确认安装 → `generate_outline` → `export_outline`。

令牌与参数、方案/文件哈希绑定，短期有效且只能使用一次。MCP 助手应向用户展示预览并等待其同意后再使用令牌。

## 转换与翻译依赖

PDF 采用 pypdf 抽取文本；扫描件返回 OCR 提示。PDF→MD 原生可用；PDF→DOCX/TEX/HTML 经 MD 再调用 Pandoc。MD/DOCX/TEX/HTML 互转需要 Pandoc；DOCX→PDF 需要 LibreOffice (`soffice`)；其他 PDF 输出需 Pandoc 与 XeLaTeX。不保证 PDF 原排版、公式和图片恢复，输出包含质量告警。Pandoc 使用 `--sandbox`，PDF 引擎禁用 shell escape。

翻译后端为 OpenAI/Anthropic 官方 SDK。通过 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 设置密钥，模型名由配置或 `PAPERHUB_OPENAI_MODEL` / `PAPERHUB_ANTHROPIC_MODEL` 指定。密钥不写入配置或日志。单价由配置提供；未配置时金额显示 `null`，只估算 tokens。开发测试全部使用模拟后端，运行测试不调用付费 API。

可选 `python -m pip install -e ".[conversion]"` 在 Python 环境内安装 Pandoc 二进制，服务会自动发现。PDF 渲染引擎仍需单独安装。配置中的翻译后端/目标语言和分类模式会作为工具的默认值；修改配置后可在空闲时调用 `reload_config`。

使用 `uv sync --locked --extra dev --extra conversion` 可按仓库的 `uv.lock` 安装锁定依赖。完整本机验证结果见 [验证记录](docs/validation.md)。

## 验证

```powershell
.\.venv\Scripts\python -m pytest --cov=paperhub --cov-report=term-missing
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\python -m build
```

参阅 [工具手册](docs/tools.md)、[交付范围与需求映射](docs/delivery.md)、[插件开发](docs/plugins.md)、[隐私与安全](docs/security.md)。原始产品与需求文档保留在项目根目录。

