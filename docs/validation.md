# 验证记录

日期：2026-10-08（Asia/Shanghai）。环境：Windows、Python 3.14.5。

| 检查 | 结果 |
|---|---|
| `python -m pytest --cov=paperhub --cov-report=term --cov-report=xml --cov-fail-under=70 -q` | **65 passed, 2 skipped**；整体覆盖率 **89.82%** |
| `python -m ruff check .` | 通过 |
| `python -m mypy` | 35 个核心源码文件通过 |
| `python -m build` | 生成核心 wheel 与 sdist |
| `python -m build plugins/outline-example` | 生成示例插件 wheel 与 sdist |
| `python scripts/smoke_wheel.py dist/paperhub_mcp-0.1.0-py3-none-any.whl` | 临时环境离线安装真实 wheel，确认导入安装包而非 editable 源码，CLI doctor 启动通过 |
| MCP 真实 stdio | 官方 ClientSession 初始化、ping、异步扫描、任务轮询、检索和资源读取通过 |
| Pandoc 真实转换 | 12 种 MD/DOCX/TEX/HTML 格式对及 3 种 PDF→MD→目标格式，15 项通过 |
| 第三方 wheel | 实际 venv 离线安装、entry point 加载、结果校验、异常/超时隔离、卸载通过 |
| 翻译 | 模拟 OpenAI/Anthropic SDK；确认前无后端调用；公式/代码/引用保留；取消及失败分块续译通过 |

两个跳过项为真实符号链接逃逸和应用/撤销测试：当前 Windows 权限不能创建符号链接。实际移动/撤销、输出覆盖拒绝、路径穿越拒绝测试已通过。

本机未检测到 LibreOffice、XeLaTeX、OCRmyPDF、Tesseract，未验证 PDF 渲染和 OCR。未安装真实句子模型，严格离线加载行为使用模型替身验证。未提供 API Key，未进行付费翻译或真实翻译质量验收。macOS/Linux 三平台 CI 矩阵已编写，尚未在 GitHub Actions 上执行。

运行时依赖已通过 `uv.lock` 锁定。核心验证版本包含 MCP 1.30.0、pypdf 6.19.0、python-docx 1.2.0、scikit-learn 1.9.1、OpenAI SDK 2.54.0、Anthropic SDK 0.125.0。

产物位置：`dist/paperhub_mcp-0.1.0-py3-none-any.whl`、`dist/paperhub_mcp-0.1.0.tar.gz`。示例插件产物位于 `plugins/outline-example/dist/`。可使用 `python scripts/smoke_wheel.py dist/paperhub_mcp-0.1.0-py3-none-any.whl` 验证离线安装和 CLI；脚本使用临时环境并复用开发环境的依赖，不访问网络。

