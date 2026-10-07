# PaperHub MCP —— 论文资料管理 MCP 产品文档

> 版本:v0.1(草案)  
> 项目代号:PaperHub MCP  
> 文档目的:明确产品定位、功能范围、技术架构、插件体系与外部 API 依赖,作为开发与迭代的基准。

---

## 1. 产品概述

### 1.1 背景与痛点

研究者的文献通常散落在本地各个文件夹(下载目录、桌面、各类项目文件夹),存在以下问题:

- 文件名混乱(如 `1706.03762.pdf`、`paper(3).pdf`),难以检索
- 同一研究方向的论文无法自动归类,整理靠手工
- 投稿或阅读时经常需要在 PDF / Word / Markdown / LaTeX 等格式间转换
- 写综述或新论文时缺少快速的大纲辅助
- 阅读外文文献时需要在多个翻译工具间来回切换

### 1.2 产品定位

PaperHub MCP 是一个基于 **Model Context Protocol(MCP)** 的论文资料管理服务。它让 Claude Desktop、Cursor、Claude Code 等任何 MCP 客户端,都能通过自然语言直接操作用户本地的论文库:扫描、分类、转换、生成大纲、翻译。

### 1.3 目标用户

| 用户类型 | 典型场景 |
|---|---|
| 研究生 / 博士生 | 整理几百篇文献,写开题报告、综述 |
| 科研人员 | 跟踪领域进展,按主题管理论文 |
| 跨语言研究者 | 阅读并翻译外文论文,或将中文论文转为英文投稿 |
| 论文写作者 | 快速生成大纲,统一文档格式 |

### 1.4 核心价值

1. **零迁移成本**:直接读取本地文件系统,不要求用户把文献导入某个封闭数据库
2. **自然语言驱动**:通过 MCP 让 AI 助手调用工具,而不是学习新的软件界面
3. **可扩展**:大纲生成等能力以插件形式提供,按需安装
4. **模型无关**:翻译等能力可自由切换 GPT、Claude 或其他服务

---

## 2. 产品目标与非目标

### 2.1 目标

- 一键扫描指定目录,自动提取论文元数据(标题、作者、年份、摘要、DOI)
- 按研究主题自动聚类,并支持用户手动调整
- 一键在主流文档格式间转换
- 通过插件体系提供论文大纲生成及后续扩展能力
- 通过外部 LLM 接口实现论文级语言转换,并尽量保留公式、图表、引用结构

### 2.2 非目标(v1 阶段不做)

- 不做云端文献存储或多人协作
- 不做完整的引用管理器(如 Zotero 的全部功能),但保留导出 BibTeX 的接口
- 不做论文全文检索的商业级搜索引擎
- 不提供图形化桌面客户端(依赖 MCP 客户端作为交互界面)

---

## 3. 功能需求

### 3.1 模块一:本地文献扫描与智能分类(核心)

#### 功能描述

读取用户授权的本地目录,识别论文文件,抽取元数据,并将相同研究方向的论文自动归为一组。

#### 功能点

| 编号 | 功能 | 说明 | 优先级 |
|---|---|---|---|
| F1.1 | 目录扫描 | 递归扫描授权目录,识别 PDF / DOCX / MD / TEX / EPUB 等 | P0 |
| F1.2 | 增量更新 | 通过文件哈希与修改时间,仅处理新增或变更文件 | P0 |
| F1.3 | 元数据提取 | 提取标题、作者、年份、摘要、关键词、DOI | P0 |
| F1.4 | 元数据补全 | 通过 DOI/标题调用学术 API 补全缺失信息 | P1 |
| F1.5 | 主题聚类 | 基于语义向量对论文自动聚类,并生成主题名称 | P0 |
| F1.6 | 分类应用 | 预览分类结果后,可选择「仅建索引」「创建软链接」或「实际移动文件」 | P0 |
| F1.7 | 手动调整 | 用户可通过对话移动论文、合并/拆分主题 | P1 |
| F1.8 | 重复检测 | 基于 DOI、标题相似度、文件哈希识别重复论文 | P1 |
| F1.9 | 目录监听 | 监听文件夹变化,自动入库新论文 | P2 |

#### 分类流程

```
扫描文件 → 文本抽取 → 元数据解析 → 向量化(标题+摘要)
   → 聚类(HDBSCAN) → LLM 命名主题 → 生成分类方案(预览)
   → 用户确认 → 应用(索引 / 软链接 / 移动)
```

#### 关键设计原则

- **默认非破坏性**:分类默认只建立索引与虚拟分组,不移动用户文件;移动文件须显式确认
- **可解释**:每个主题展示关键词与代表论文,便于用户判断聚类是否合理
- **本地优先**:向量计算默认使用本地模型,无需上传论文内容

---

### 3.2 模块二:一键格式转换

#### 功能描述

在常见论文格式之间快速转换,并尽量保持排版、公式、参考文献完整。

#### 支持的转换矩阵(规划)

| 源格式 \ 目标格式 | PDF | DOCX | Markdown | LaTeX | HTML | TXT |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| **PDF** | — | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| **DOCX** | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| **Markdown** | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| **LaTeX** | ✅ | ✅ | ✅ | — | ✅ | ✅ |

> ✅ 完整支持  ⚠️ 受限(PDF → LaTeX 为尽力还原,复杂公式需人工校对)

#### 功能点

| 编号 | 功能 | 说明 | 优先级 |
|---|---|---|---|
| F2.1 | 单文件转换 | 指定文件与目标格式即可转换 | P0 |
| F2.2 | 批量转换 | 对一个主题分组或整个目录批量转换 | P0 |
| F2.3 | 转换前备份 | 默认保留原文件,输出到独立目录 | P0 |
| F2.4 | 模板套用 | 套用期刊/学校模板(如 IEEE、ACM、学位论文模板) | P1 |
| F2.5 | 参考文献样式转换 | 通过 CSL 切换 APA / IEEE / GB/T 7714 等样式 | P1 |
| F2.6 | 扫描件 OCR | 对扫描版 PDF 先 OCR 再转换 | P1 |
| F2.7 | 转换质量报告 | 输出转换告警(公式丢失、图片缺失、表格错位) | P1 |

---

### 3.3 模块三:论文大纲生成(插件化)

#### 功能描述

大纲生成作为**可选插件**提供,用户按需安装。核心服务只提供插件宿主能力,不内置具体大纲逻辑。

#### 插件化的原因

- 不同学科、不同论文类型(综述 / 实验类 / 理论类 / 学位论文)大纲结构差异很大
- 不同用户偏好不同的生成模型或写作风格
- 便于社区贡献新的大纲模板与生成策略

#### 官方大纲插件规划

| 插件名 | 功能 | 输入 | 输出 |
|---|---|---|---|
| `outline-survey` | 综述论文大纲 | 某主题分组下的多篇论文 | 分章节大纲 + 每节对应参考文献 |
| `outline-empirical` | 实验类论文大纲 | 研究问题、方法、数据说明 | IMRaD 结构大纲 |
| `outline-thesis` | 学位论文大纲 | 研究方向、已有材料 | 章节级大纲及字数建议 |
| `outline-from-draft` | 从草稿反推大纲 | 已有草稿文档 | 结构化大纲 + 逻辑缺口提示 |

#### 功能点

| 编号 | 功能 | 优先级 |
|---|---|---|
| F3.1 | 插件发现、安装、卸载、启用、停用 | P0 |
| F3.2 | 基于所选主题分组生成大纲 | P0 |
| F3.3 | 大纲导出为 Markdown / DOCX / LaTeX 骨架 | P1 |
| F3.4 | 大纲与文献关联(每个小节挂载建议引用的论文) | P1 |
| F3.5 | 大纲迭代修改(对话式调整) | P1 |

---

### 3.4 模块四:论文语言转换(外部 MCP / API 接入)

#### 功能描述

将论文翻译成目标语言,通过**可插拔的翻译后端**调用外部 LLM 服务(GPT、Claude 等)。

#### 接入方式

提供三种后端,用户可在配置中切换或设置优先级:

| 方式 | 说明 | 适用场景 |
|---|---|---|
| **A. 直连 API** | 服务端直接调用 OpenAI / Anthropic API | 批量、自动化翻译 |
| **B. MCP Sampling** | 服务端通过 MCP 的 sampling 能力,请求宿主客户端的模型完成翻译(需客户端支持) | 不想额外配置 API Key |
| **C. 外部 MCP Server** | 服务端作为 MCP Client,连接其他翻译类 MCP Server | 复用已有翻译生态 |

#### 功能点

| 编号 | 功能 | 说明 | 优先级 |
|---|---|---|---|
| F4.1 | 全文翻译 | 整篇论文翻译为指定语言 | P0 |
| F4.2 | 分段翻译 | 按章节/段落翻译,支持断点续译 | P0 |
| F4.3 | 结构保护 | 保护公式、代码、图表编号、引用标记不被翻译或破坏 | P0 |
| F4.4 | 术语表 | 用户自定义术语对照,保证全文术语一致 | P1 |
| F4.5 | 双语对照输出 | 原文/译文逐段对照 | P1 |
| F4.6 | 摘要翻译 | 仅翻译标题与摘要,低成本快速浏览 | P0 |
| F4.7 | 学术润色 | 目标语言的学术风格润色(如中译英后润色) | P2 |
| F4.8 | 成本预估 | 翻译前估算 token 数与费用,用户确认后执行 | P1 |
| F4.9 | 模型路由 | 按任务选择模型(如摘要用小模型,全文用强模型) | P2 |

#### 翻译处理流水线

```
读取文档 → 结构解析(章节/段落/公式/图表) → 占位符保护(公式、引用)
   → 术语表注入 → 分块(按语义边界) → 调用翻译后端
   → 占位符还原 → 一致性检查 → 输出(原格式 / 双语 / Markdown)
```

---

## 4. MCP 接口设计

### 4.1 Tools(工具)

| 工具名 | 说明 | 主要参数 |
|---|---|---|
| `scan_library` | 扫描目录并建立索引 | `path`, `recursive`, `file_types` |
| `get_paper_info` | 获取单篇论文元数据 | `paper_id` |
| `search_papers` | 按关键词/语义检索论文 | `query`, `topic`, `year_range` |
| `classify_papers` | 生成主题分类方案(预览) | `scope`, `num_topics`(可选) |
| `apply_classification` | 应用分类方案 | `plan_id`, `mode`(index / symlink / move) |
| `find_duplicates` | 查找重复论文 | `scope` |
| `convert_format` | 格式转换 | `paper_id / path`, `target_format`, `template` |
| `batch_convert` | 批量转换 | `scope`, `target_format` |
| `translate_paper` | 翻译论文 | `paper_id`, `target_lang`, `backend`, `mode` |
| `translate_abstract` | 仅翻译摘要 | `paper_id`, `target_lang` |
| `list_plugins` | 列出已安装与可用插件 | `installed_only` |
| `install_plugin` | 安装插件 | `plugin_name`, `version` |
| `generate_outline` | 调用大纲插件生成大纲 | `plugin`, `scope`, `options` |
| `export_bibtex` | 导出参考文献 | `scope`, `style` |

### 4.2 Resources(资源)

| URI | 说明 |
|---|---|
| `paperhub://library/index` | 整个论文库索引 |
| `paperhub://topics/{topic_id}` | 某主题下的论文列表 |
| `paperhub://paper/{paper_id}` | 单篇论文元数据与摘要 |
| `paperhub://plugins/installed` | 已安装插件清单 |

### 4.3 Prompts(提示模板)

| 名称 | 用途 |
|---|---|
| `organize_my_library` | 引导用户完成「扫描 → 预览 → 确认分类」 |
| `write_survey_outline` | 引导生成综述大纲 |
| `translate_with_glossary` | 引导带术语表的翻译 |

### 4.4 交互示例

```
用户:帮我整理 ~/Papers 里的文献,按研究方向分类
Claude:[调用 scan_library → classify_papers]
        发现 312 篇论文,建议分为 8 个主题:
        1. 大语言模型推理优化(47 篇)……
        是否应用?我建议先用「软链接」模式,不改动原文件。
用户:可以,应用
Claude:[调用 apply_classification(mode=symlink)]
```

---

## 5. 系统架构

### 5.1 总体架构

```
┌─────────────────────────────────────────────────┐
│     MCP 客户端 (Claude Desktop / Cursor / ...)   │
└───────────────────────┬─────────────────────────┘
                        │ MCP (stdio / Streamable HTTP)
┌───────────────────────▼─────────────────────────┐
│               PaperHub MCP Server                │
│  ┌───────────┬───────────┬───────────┬────────┐ │
│  │ 扫描分类  │ 格式转换  │ 翻译调度  │ 插件宿主│ │
│  └─────┬─────┴─────┬─────┴─────┬─────┴───┬────┘ │
│        │           │           │         │      │
│  ┌─────▼───────────▼───────────▼─────────▼────┐ │
│  │   核心服务层:索引库 / 任务队列 / 配置 / 日志 │ │
│  └─────┬───────────┬───────────┬──────────────┘ │
└────────┼───────────┼───────────┼────────────────┘
         │           │           │
   本地文件系统   转换引擎    外部服务
                (Pandoc 等)  (GPT / Claude / 学术 API / 外部 MCP)
```

### 5.2 分层说明

| 层 | 职责 |
|---|---|
| 协议层 | MCP Server 实现,暴露 Tools / Resources / Prompts |
| 业务层 | 扫描、分类、转换、翻译、插件管理 |
| 基础设施层 | SQLite 索引、向量库、任务队列、配置、日志 |
| 适配层 | 各类外部引擎与 API 的统一适配接口 |

### 5.3 插件架构

**插件接口(伪代码)**

```python
class OutlinePlugin(Protocol):
    name: str
    version: str
    supported_types: list[str]   # survey / empirical / thesis ...

    def generate(self, context: OutlineContext, options: dict) -> Outline: ...
```

**插件清单 `plugin.json`**

```json
{
  "name": "outline-survey",
  "version": "0.1.0",
  "type": "outline",
  "entry": "outline_survey.plugin:SurveyOutlinePlugin",
  "permissions": ["read_library", "call_llm"],
  "min_core_version": "0.1.0",
  "description": "为某一研究主题生成综述论文大纲"
}
```

**插件生命周期**:发现 → 下载 → 校验(签名/哈希) → 安装 → 注册 → 启用/停用 → 卸载

**实现方案**:v1 使用 Python 包 + `entry_points` 机制,并通过 PyPI 或官方插件索引(一个 JSON 清单托管在 GitHub)分发;后续再考虑独立的插件市场。

---

## 6. 技术选型

### 6.1 开发语言与框架

| 项 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.11+ | PDF 解析、NLP、学术工具生态最完整 |
| MCP SDK | 官方 Python SDK(`mcp`,可用 `FastMCP`) | 快速定义 tools/resources/prompts |
| 传输方式 | stdio(本地)为主,可选 Streamable HTTP | 本地文件访问场景以 stdio 最简单安全 |
| 包管理 | `uv` | 安装与分发简便,支持 `uvx` 一键运行 |
| 数据模型 | Pydantic | 参数校验与结构化输出 |

> 备选:若团队更熟悉 TypeScript,可使用官方 TypeScript SDK,但 PDF/NLP 生态需额外桥接。

### 6.2 存储

| 用途 | 选型 |
|---|---|
| 元数据索引 | SQLite(含 FTS5 全文检索) |
| 向量存储 | `sqlite-vec` 或 ChromaDB(本地持久化) |
| 配置 | TOML / YAML + 环境变量 |
| 任务状态 | SQLite 任务表(断点续译、批量转换) |

---

## 7. 预期使用的库、插件与外部 API

### 7.1 文件读取与元数据提取

| 工具/库 | 用途 | 备注 |
|---|---|---|
| **PyMuPDF (fitz)** | PDF 文本与图片抽取、速度快 | 注意 AGPL 许可 |
| **pdfplumber / pypdf** | PDF 表格、元信息补充 | 宽松许可备选 |
| **GROBID** | 学术 PDF 结构化解析(标题、作者、参考文献) | 需本地运行服务(Docker) |
| **python-docx** | 读取 DOCX | |
| **Tesseract / OCRmyPDF** | 扫描件 OCR | |
| **watchdog** | 目录变化监听 | F1.9 |
| **python-magic** | 文件类型识别 | |

### 7.2 分类与语义处理

| 工具/库 | 用途 |
|---|---|
| **sentence-transformers** | 本地文本向量化(可选 SPECTER2 等学术专用模型) |
| **scikit-learn / hdbscan** | 聚类(HDBSCAN 无需预设聚类数) |
| **BERTopic**(可选) | 主题建模与关键词提取 |
| **rapidfuzz** | 标题模糊匹配、重复检测 |
| **LLM(经翻译后端同一适配层)** | 为每个聚类生成可读的主题名称 |

### 7.3 格式转换

| 工具/库 | 用途 |
|---|---|
| **Pandoc + pypandoc** | Markdown / DOCX / LaTeX / HTML 之间的主力转换引擎 |
| **LaTeX 发行版(TeX Live / MiKTeX)** | LaTeX → PDF 编译 |
| **LibreOffice(headless)** | DOCX → PDF,保真度较好 |
| **marker / Nougat / MinerU**(可选) | PDF → Markdown/LaTeX,对公式与版面还原更好 |
| **CSL 样式库** | 参考文献样式切换(APA、IEEE、GB/T 7714 等) |
| **WeasyPrint**(可选) | HTML → PDF |

### 7.4 学术元数据 API(补全与去重)

| API | 用途 | 说明 |
|---|---|---|
| **Crossref REST API** | 通过 DOI/标题获取元数据 | 免费,建议带邮箱进入 polite pool |
| **Semantic Scholar API** | 摘要、引用关系、相关论文 | 建议申请 API Key 提高限额 |
| **OpenAlex API** | 开放学术图谱、主题标签 | 免费开放 |
| **arXiv API** | arXiv 论文元数据与全文链接 | |
| **Unpaywall API**(可选) | 查找开放获取全文 | |

### 7.5 语言转换与大模型接入

| 接入对象 | 方式 | 备注 |
|---|---|---|
| **OpenAI(GPT 系列)** | 官方 API / Python SDK | 需用户自备 API Key |
| **Anthropic(Claude 系列)** | 官方 API / Python SDK | 需用户自备 API Key |
| **MCP Sampling** | 经宿主客户端调用其模型 | 依赖客户端支持,无需额外 Key |
| **外部翻译类 MCP Server** | 本服务作为 MCP Client 连接 | 通过配置文件声明服务器地址 |
| **DeepL API**(可选) | 传统高质量机器翻译,成本更低 | 可用于摘要或初稿翻译 |
| **LiteLLM**(可选) | 统一多家模型接口,简化「模型无关」实现 | 减少自行适配的工作量 |

> 具体模型名称与定价会变化,实现时请以各家官方文档为准,并把模型名放入配置而非硬编码。

### 7.6 插件体系与分发

| 项 | 方案 |
|---|---|
| 插件加载 | Python `entry_points` / `importlib.metadata` |
| 插件分发 | PyPI + 官方插件索引 JSON(GitHub 托管) |
| 校验 | 哈希校验;后续支持签名 |
| 权限声明 | 插件清单声明所需权限,安装时展示给用户 |

### 7.7 工程与质量保障

| 工具 | 用途 |
|---|---|
| pytest | 单元与集成测试 |
| MCP Inspector | 调试与验证 MCP 工具 |
| ruff / mypy | 代码风格与类型检查 |
| GitHub Actions | CI 与发布 |
| structlog | 结构化日志 |

---

## 8. 安全与隐私

| 风险 | 对策 |
|---|---|
| 越权读取文件 | 仅访问用户配置的**白名单目录**;可结合 MCP roots 能力声明范围 |
| 误改/误删原文件 | 默认非破坏性;移动/覆盖需二次确认;转换输出到独立目录;可选操作日志与撤销 |
| 论文内容外泄 | 向量化默认本地运行;调用外部 LLM 前明确提示「将上传内容」,并允许仅翻译摘要 |
| API Key 泄露 | 通过环境变量或系统钥匙串存储,不写入日志与索引 |
| 恶意插件 | 权限声明 + 哈希校验 + 官方索引审核;插件默认无文件写权限 |
| 路径穿越 | 所有路径做规范化与白名单校验 |
| 版权合规 | 提示用户翻译/转换仅限个人学习研究范围使用 |

---

## 9. 非功能需求

| 指标 | 目标(v1) |
|---|---|
| 扫描性能 | 1000 篇 PDF 首次索引 ≤ 15 分钟(普通笔记本,不含 OCR) |
| 增量扫描 | 无变化时 ≤ 10 秒 |
| 可用性 | macOS / Windows / Linux 全平台 |
| 离线能力 | 扫描、分类、格式转换可完全离线;翻译与元数据补全需联网 |
| 可观测性 | 每个长任务有进度、可取消、可恢复 |
| 安装体验 | `uvx paperhub-mcp` 一条命令启动,并提供 Claude Desktop 配置示例 |

---

## 10. 路线图

### Phase 1:MVP(约 4–6 周)

- 目录扫描、元数据提取、SQLite 索引
- 语义聚类与分类预览(仅索引/软链接模式)
- Pandoc 基础格式转换(MD / DOCX / PDF / LaTeX)
- 摘要翻译 + 直连 OpenAI / Anthropic API
- 完整的 MCP Tools 与基础文档

### Phase 2:插件与完善(约 4–6 周)

- 插件宿主与插件安装机制
- 官方插件:`outline-survey`、`outline-empirical`
- 全文翻译(结构保护、术语表、断点续译)
- Crossref / Semantic Scholar 元数据补全
- 重复检测、批量转换、转换质量报告

### Phase 3:生态扩展

- MCP Sampling 与外部 MCP Server 翻译后端
- 插件索引与社区贡献流程
- 目录监听自动入库
- 期刊/学校模板库、GB/T 7714 等引用样式
- 引用关系图谱、相关论文推荐(插件形式)

---

## 11. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| PDF 解析质量不稳定(双栏、扫描件、公式) | 元数据与分类不准 | 多引擎兜底(GROBID + PyMuPDF),提供人工修正入口 |
| PDF → LaTeX/DOCX 保真度有限 | 用户期望落差 | 明确标注支持程度,输出转换质量报告 |
| 全文翻译成本高、耗时长 | 用户体验差 | 成本预估、分段断点续译、模型路由 |
| LLM 翻译破坏公式/引用 | 结果不可用 | 占位符保护 + 还原后校验 |
| MCP Sampling 客户端支持不一 | 功能不可用 | 作为可选后端,默认回退到直连 API |
| 插件质量与安全不可控 | 安全风险 | 权限声明、审核、官方索引 |
| 大模型 API 变动 | 接口失效 | 适配层隔离,模型名与参数走配置 |

---

## 12. 待确认的问题

1. 目标主要用户的论文语言以哪几种为主?(决定翻译优先支持的语言对)
2. 分类默认是否允许实际移动文件,还是始终仅建索引/软链接?
3. 是否需要与 Zotero / EndNote 等现有工具互通?
4. 插件是否计划开放给第三方开发者,是否需要审核机制?
5. 是否面向团队部署(Streamable HTTP + 鉴权),还是仅限个人本地使用?
6. 项目是否开源,选择何种许可证?(会影响 PyMuPDF 等 AGPL 依赖的取舍)

---

## 附录 A:Claude Desktop 配置示例

```json
{
  "mcpServers": {
    "paperhub": {
      "command": "uvx",
      "args": ["paperhub-mcp"],
      "env": {
        "PAPERHUB_LIBRARY_PATHS": "/Users/me/Papers",
        "OPENAI_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

## 附录 B:配置文件示例(`paperhub.toml`)

```toml
[library]
paths = ["~/Papers", "~/Downloads/papers"]
file_types = ["pdf", "docx", "md", "tex"]
classification_mode = "index"   # index | symlink | move

[convert]
output_dir = "~/Papers/_converted"
keep_original = true

[translate]
default_backend = "anthropic"   # openai | anthropic | sampling | external_mcp
default_target_lang = "zh-CN"
glossary = "~/Papers/glossary.csv"

[translate.backends.openai]
model = "<在此填写模型名>"

[translate.backends.anthropic]
model = "<在此填写模型名>"

[plugins]
index_url = "https://example.com/paperhub-plugins/index.json"
enabled = ["outline-survey"]
```
