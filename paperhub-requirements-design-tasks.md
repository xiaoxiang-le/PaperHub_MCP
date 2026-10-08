# PaperHub MCP —— 需求规格、设计方案与总任务清单

> 版本:v0.1  
> 配套文档:《PaperHub MCP 产品文档》(产品定位、功能概览、技术选型)  
> 本文档用途:把产品文档落到可开发、可验收、可排期的层面。

**目录**

1. 需求规格
2. 设计方案
3. 总任务清单(WBS)
4. 里程碑与排期
5. 测试与验收计划
6. 风险与依赖
7. 开发规范与协作约定

---

# 第一部分:需求规格

## 1.1 角色与用户故事

| 编号 | 角色 | 用户故事 | 对应模块 |
|---|---|---|---|
| US-01 | 研究生 | 我想让 AI 扫描我的论文文件夹,告诉我里面有哪些论文 | 扫描 |
| US-02 | 研究生 | 我想把同一研究方向的论文自动分到一组,并看到每组的主题名 | 分类 |
| US-03 | 研究生 | 我想在分类前先预览结果,满意后才真正整理文件 | 分类 |
| US-04 | 科研人员 | 我想一句话把某篇/某组论文转成 DOCX 或 Markdown | 转换 |
| US-05 | 论文作者 | 我想基于某个主题下的论文生成综述大纲 | 大纲插件 |
| US-06 | 论文作者 | 我只想安装自己需要的大纲类型,不要臃肿 | 插件 |
| US-07 | 跨语言研究者 | 我想快速看英文论文的中文摘要 | 翻译 |
| US-08 | 跨语言研究者 | 我想翻译全文,且公式和引用不被破坏 | 翻译 |
| US-09 | 跨语言研究者 | 我想自己选择用 GPT 还是 Claude 翻译 | 翻译后端 |
| US-10 | 所有用户 | 我担心文件被误改,希望所有破坏性操作可确认、可撤销 | 安全 |

## 1.2 功能需求(FR)

优先级:**P0** 必须(MVP)/ **P1** 重要(v1.0)/ **P2** 增强。

### A. 扫描与索引

| 编号 | 需求描述 | 验收标准 | 优先级 |
|---|---|---|---|
| FR-A1 | 递归扫描授权目录,识别 PDF、DOCX、MD、TEX | 对含 4 种格式的测试目录,识别率 100%;非授权目录请求被拒绝 | P0 |
| FR-A2 | 为每个文件计算内容哈希并入库 | 同一文件重复扫描不产生重复记录 | P0 |
| FR-A3 | 增量扫描,仅处理新增/变更/删除的文件 | 无变化时二次扫描不触发解析;删除的文件在索引中标记为 missing | P0 |
| FR-A4 | 提取元数据:标题、作者、年份、摘要、关键词、DOI | 在 50 篇标注样本上,标题准确率 ≥ 85%,摘要提取率 ≥ 80% | P0 |
| FR-A5 | 元数据缺失时,通过 DOI/标题调用学术 API 补全 | 命中时补全字段并标记来源;API 失败不影响主流程 | P1 |
| FR-A6 | 扫描失败文件(加密、损坏、扫描件)单独记录原因,不中断整体任务 | 扫描报告列出失败文件与原因 | P0 |
| FR-A7 | 长任务提供进度回报并可取消 | 扫描 100+ 文件时可收到进度;取消后任务在 5 秒内停止 | P1 |
| FR-A8 | 目录监听,自动入库新文件 | 新文件放入后 30 秒内进入索引 | P2 |

### B. 检索与分类

| 编号 | 需求描述 | 验收标准 | 优先级 |
|---|---|---|---|
| FR-B1 | 对标题+摘要生成语义向量,本地计算 | 默认不发生任何外部网络请求 | P0 |
| FR-B2 | 自动聚类并输出分类方案(含主题名、关键词、代表论文) | 在含 3 个明确主题的 30 篇样本上,聚类纯度 ≥ 80% | P0 |
| FR-B3 | 分类方案为「预览」状态,需显式调用才会应用 | 未应用前文件系统无任何改动 | P0 |
| FR-B4 | 应用方案支持三种模式:仅索引 / 软链接 / 移动 | 三种模式均可执行;移动模式需二次确认并记录日志 | P0 |
| FR-B5 | 用户可通过对话调整:移动论文、合并/拆分/重命名主题 | 调整后分类方案同步更新并可再次预览 | P1 |
| FR-B6 | 关键词 + 语义混合检索 | 检索「Transformer 加速」能返回语义相关但不含该词的论文 | P1 |
| FR-B7 | 重复论文检测(DOI、哈希、标题相似度) | 在含 5 组重复的样本中检出率 ≥ 90% | P1 |
| FR-B8 | 导出 BibTeX / CSL-JSON | 导出文件可被 Zotero 正确导入 | P1 |
| FR-B9 | 操作日志与撤销(针对软链接/移动) | 可撤销最近一次分类应用,文件恢复原位 | P1 |

### C. 格式转换

| 编号 | 需求描述 | 验收标准 | 优先级 |
|---|---|---|---|
| FR-C1 | 单文件转换:MD / DOCX / LaTeX / HTML / PDF 之间(PDF 作为目标或源按支持矩阵) | 支持矩阵内的转换均可成功执行 | P0 |
| FR-C2 | 默认保留原文件,输出到独立目录 | 转换后原文件哈希不变 | P0 |
| FR-C3 | 批量转换(按主题或目录) | 批量中单个失败不影响其余,最终给出汇总报告 | P0 |
| FR-C4 | 转换质量报告(公式、图片、表格、引用告警) | 报告至少包含告警类型与位置 | P1 |
| FR-C5 | 扫描版 PDF 先 OCR 后转换 | 对清晰扫描件文字识别率达到可读水平 | P1 |
| FR-C6 | 套用期刊/学校模板 | 提供至少 2 个内置模板并支持自定义模板路径 | P1 |
| FR-C7 | 参考文献样式切换(CSL) | 支持 APA、IEEE、GB/T 7714 | P1 |
| FR-C8 | 外部转换引擎缺失时给出明确安装指引 | 缺少 Pandoc 等时返回可操作的错误提示 | P0 |

### D. 插件与大纲

| 编号 | 需求描述 | 验收标准 | 优先级 |
|---|---|---|---|
| FR-D1 | 插件宿主:发现、安装、卸载、启用、停用 | 全流程可通过 MCP 工具完成,无需重启核心服务(或明确提示重启) | P0 |
| FR-D2 | 插件清单声明版本、类型、入口、权限、最低核心版本 | 清单校验不通过则拒绝安装 | P0 |
| FR-D3 | 安装时展示权限并要求确认 | 未确认则不安装 | P0 |
| FR-D4 | 插件异常不影响核心服务 | 插件抛出异常时核心继续可用,错误被记录 | P0 |
| FR-D5 | 官方插件 `outline-survey`:基于主题分组生成综述大纲 | 输出含章节层级、每节要点、每节建议引用的论文 | P0 |
| FR-D6 | 大纲导出为 Markdown / DOCX / LaTeX 骨架 | 三种格式均可导出 | P1 |
| FR-D7 | 大纲对话式迭代修改 | 可对某节进行增删改并保留其余内容 | P1 |
| FR-D8 | 官方插件 `outline-empirical`、`outline-thesis`、`outline-from-draft` | 各自通过示例输入验证 | P1 |
| FR-D9 | 插件索引(JSON)与版本兼容性检查 | 不兼容的插件不可安装并提示原因 | P1 |

### E. 翻译与语言转换

| 编号 | 需求描述 | 验收标准 | 优先级 |
|---|---|---|---|
| FR-E1 | 翻译后端抽象接口,支持注册多个后端 | 新增一个后端无需修改业务代码 | P0 |
| FR-E2 | 直连 OpenAI API 后端 | 配置 Key 后可完成摘要翻译 | P0 |
| FR-E3 | 直连 Anthropic API 后端 | 同上 | P0 |
| FR-E4 | 摘要/标题翻译 | 1 次调用内完成,返回双语结果 | P0 |
| FR-E5 | 全文翻译:按语义分块、逐块翻译、合并 | 50 页论文可完整输出 | P0 |
| FR-E6 | 结构保护:公式、代码、图表编号、引用标记以占位符保护并还原 | 在含公式样本上,还原后公式 100% 与原文一致 | P0 |
| FR-E7 | 断点续译:任务中断后可从上次进度继续 | 中断后恢复不重复翻译已完成块 | P1 |
| FR-E8 | 术语表(CSV)注入 | 术语表中的词在译文中一致出现 ≥ 95% | P1 |
| FR-E9 | 双语对照输出 | 输出段落一一对应 | P1 |
| FR-E10 | 翻译前成本预估并要求确认 | 全文翻译前展示预估 token 与费用区间 | P1 |
| FR-E11 | MCP Sampling 后端 | 客户端支持时可用;不支持时自动回退并提示 | P2 |
| FR-E12 | 外部 MCP Server 后端(本服务作为 MCP Client) | 可通过配置接入至少 1 个外部翻译 MCP | P2 |
| FR-E13 | 翻译前提示「内容将发送至外部服务」 | 首次使用某后端时提示并记录用户确认 | P0 |
| FR-E14 | 学术润色 | 可对译文做目标语言润色 | P2 |

### F. 通用能力

| 编号 | 需求描述 | 优先级 |
|---|---|---|
| FR-F1 | 配置文件(TOML)+ 环境变量,支持热读取关键项 | P0 |
| FR-F2 | 结构化日志,敏感信息(API Key、全文内容)脱敏 | P0 |
| FR-F3 | 统一错误码与可读错误信息(便于 AI 助手向用户解释) | P0 |
| FR-F4 | 一条命令启动(`uvx paperhub-mcp`)及客户端配置示例 | P0 |
| FR-F5 | 自检工具 `doctor`:检查 Pandoc、LaTeX、GROBID、API Key 等依赖状态 | P1 |

## 1.3 非功能需求(NFR)

| 编号 | 类别 | 要求 |
|---|---|---|
| NFR-1 | 性能 | 1000 篇文本型 PDF 首次索引 ≤ 15 分钟(不含 OCR/GROBID);无变化的增量扫描 ≤ 10 秒 |
| NFR-2 | 资源 | 常驻内存 ≤ 1 GB(不含向量模型加载峰值);向量模型按需加载 |
| NFR-3 | 兼容性 | macOS、Windows、Linux;Python 3.11+ |
| NFR-4 | 安全 | 路径白名单、路径穿越防护、API Key 不落盘明文日志、破坏性操作二次确认 |
| NFR-5 | 隐私 | 默认本地处理;任何外发内容的操作须明示 |
| NFR-6 | 可靠性 | 长任务可取消、可恢复;单文件失败不中断批任务 |
| NFR-7 | 可维护性 | 核心模块单元测试覆盖率 ≥ 70%;类型检查通过 |
| NFR-8 | 可扩展性 | 新增文件格式、转换器、翻译后端、插件均通过接口注册,不改核心代码 |
| NFR-9 | 可观测性 | 每个长任务有 task_id、状态、进度、错误明细 |
| NFR-10 | 国际化 | 工具说明与错误信息以中英双语为目标,至少保证中文可用 |

## 1.4 约束与假设

- 用户需自备 OpenAI / Anthropic 的 API Key 才能使用直连翻译后端。
- 外部引擎(Pandoc、LaTeX、LibreOffice、GROBID、Tesseract)由用户安装,项目提供检测与指引,不强制捆绑。
- PDF → LaTeX / DOCX 为「尽力还原」,不承诺排版完全一致。
- MVP 阶段不提供图形界面,交互依赖 MCP 客户端。
- PyMuPDF 为 AGPL 许可,是否采用取决于项目是否开源(待决策,见 §6)。

---

# 第二部分:设计方案

## 2.1 设计原则

1. **非破坏性优先**:默认只读与旁路输出,破坏性操作显式确认。
2. **两阶段操作**:「生成方案(预览)→ 用户确认 → 应用」,适用于分类与批量转换。
3. **适配器模式**:解析器、转换器、翻译后端、插件均通过统一接口注册。
4. **长任务异步化**:耗时操作返回 `task_id`,通过状态工具查询,避免客户端超时。
5. **本地优先、外发明示**:任何会把论文内容发到外部的行为必须提示。
6. **失败隔离**:单文件/单插件/单块失败不拖垮整体。

## 2.2 总体架构

```
┌────────────────────────────────────────────────────────┐
│  MCP 客户端(Claude Desktop / Cursor / Claude Code …)  │
└───────────────────────────┬────────────────────────────┘
                            │ stdio / Streamable HTTP
┌───────────────────────────▼────────────────────────────┐
│ ① 协议层  server.py:Tools / Resources / Prompts 注册   │
├────────────────────────────────────────────────────────┤
│ ② 服务层                                                │
│  LibraryService │ ClassifyService │ ConvertService      │
│  TranslateService │ PluginService │ TaskService         │
├────────────────────────────────────────────────────────┤
│ ③ 适配层(接口 + 多实现)                               │
│  Parser:PyMuPDF / GROBID / docx / md / tex             │
│  Converter:Pandoc / LibreOffice / marker               │
│  Embedder:sentence-transformers                        │
│  TranslateBackend:OpenAI / Anthropic / Sampling / MCP  │
│  MetadataSource:Crossref / SemanticScholar / OpenAlex  │
├────────────────────────────────────────────────────────┤
│ ④ 基础设施层                                            │
│  SQLite(元数据+FTS5) │ 向量库 │ 任务队列 │ 配置 │ 日志 │
│  安全守卫(路径白名单 / 确认机制 / 操作日志)           │
└────────────────────────────────────────────────────────┘
```

## 2.3 项目目录结构

```
paperhub-mcp/
├── pyproject.toml
├── README.md
├── docs/
├── src/paperhub/
│   ├── server.py              # MCP 入口,注册 tools/resources/prompts
│   ├── config.py              # 配置加载与校验
│   ├── errors.py              # 统一错误码
│   ├── security/
│   │   ├── path_guard.py      # 路径白名单与规范化
│   │   ├── confirm.py         # 二次确认令牌
│   │   └── oplog.py           # 操作日志与撤销
│   ├── core/
│   │   ├── db.py              # SQLite 连接与迁移
│   │   ├── models.py          # Pydantic 数据模型
│   │   ├── tasks.py           # 任务队列/状态
│   │   └── events.py          # 进度事件
│   ├── library/
│   │   ├── scanner.py
│   │   ├── parsers/           # base.py, pdf.py, docx.py, md.py, tex.py
│   │   ├── metadata.py        # 提取与补全
│   │   └── dedupe.py
│   ├── classify/
│   │   ├── embedder.py
│   │   ├── cluster.py
│   │   ├── naming.py          # LLM 命名主题
│   │   └── applier.py         # index / symlink / move
│   ├── convert/
│   │   ├── base.py
│   │   ├── pandoc.py
│   │   ├── libreoffice.py
│   │   ├── pdf_extract.py     # marker 等
│   │   └── report.py          # 质量报告
│   ├── translate/
│   │   ├── base.py            # TranslateBackend 接口
│   │   ├── backends/          # openai.py, anthropic.py, sampling.py, mcp_client.py
│   │   ├── segmenter.py       # 语义分块
│   │   ├── protector.py       # 占位符保护/还原
│   │   ├── glossary.py
│   │   └── pipeline.py
│   ├── plugins/
│   │   ├── host.py            # 加载/注册/生命周期
│   │   ├── manifest.py        # 清单校验
│   │   ├── registry.py        # 索引与版本检查
│   │   └── api.py             # 提供给插件的受限上下文
│   └── tools/                 # 各 MCP tool 的薄封装
├── plugins/                   # 官方插件(独立包)
│   ├── outline-survey/
│   └── outline-empirical/
└── tests/
    ├── fixtures/              # 测试用 PDF/DOCX 样本
    ├── unit/
    └── integration/
```

## 2.4 数据模型(SQLite)

```sql
-- 论文主表
CREATE TABLE paper (
  id            TEXT PRIMARY KEY,          -- uuid
  file_path     TEXT NOT NULL UNIQUE,
  file_hash     TEXT NOT NULL,
  file_type     TEXT NOT NULL,
  file_mtime    INTEGER NOT NULL,
  status        TEXT NOT NULL,             -- ok | failed | missing
  fail_reason   TEXT,
  title         TEXT,
  authors       TEXT,                      -- JSON 数组
  year          INTEGER,
  abstract      TEXT,
  keywords      TEXT,                      -- JSON 数组
  doi           TEXT,
  meta_source   TEXT,                      -- parsed | crossref | s2 | manual
  language      TEXT,
  created_at    INTEGER,
  updated_at    INTEGER
);
CREATE INDEX idx_paper_hash ON paper(file_hash);
CREATE INDEX idx_paper_doi  ON paper(doi);
CREATE VIRTUAL TABLE paper_fts USING fts5(title, abstract, keywords, content='paper');

-- 向量(若使用 sqlite-vec,则为虚拟表;此处示意)
CREATE TABLE paper_embedding (
  paper_id  TEXT PRIMARY KEY REFERENCES paper(id),
  model     TEXT NOT NULL,
  vector    BLOB NOT NULL
);

-- 主题与分类方案
CREATE TABLE topic (
  id         TEXT PRIMARY KEY,
  plan_id    TEXT NOT NULL,
  name       TEXT NOT NULL,
  keywords   TEXT,                         -- JSON
  is_manual  INTEGER DEFAULT 0
);
CREATE TABLE plan (
  id         TEXT PRIMARY KEY,
  status     TEXT NOT NULL,                -- draft | applied | reverted
  mode       TEXT,                         -- index | symlink | move
  created_at INTEGER,
  applied_at INTEGER
);
CREATE TABLE paper_topic (
  paper_id   TEXT REFERENCES paper(id),
  topic_id   TEXT REFERENCES topic(id),
  score      REAL,
  PRIMARY KEY (paper_id, topic_id)
);

-- 异步任务
CREATE TABLE task (
  id          TEXT PRIMARY KEY,
  type        TEXT NOT NULL,               -- scan | convert | translate | outline
  status      TEXT NOT NULL,               -- pending | running | done | failed | cancelled
  progress    REAL DEFAULT 0,
  payload     TEXT,                        -- JSON 入参
  result      TEXT,                        -- JSON 结果/错误
  created_at  INTEGER,
  updated_at  INTEGER
);

-- 翻译断点
CREATE TABLE translate_chunk (
  task_id     TEXT REFERENCES task(id),
  idx         INTEGER,
  source_text TEXT,
  target_text TEXT,
  status      TEXT,                        -- pending | done | failed
  PRIMARY KEY (task_id, idx)
);

-- 操作日志(支撑撤销)
CREATE TABLE oplog (
  id         TEXT PRIMARY KEY,
  plan_id    TEXT,
  op         TEXT,                         -- symlink | move
  src        TEXT,
  dst        TEXT,
  created_at INTEGER,
  reverted   INTEGER DEFAULT 0
);

-- 插件
CREATE TABLE plugin (
  name       TEXT PRIMARY KEY,
  version    TEXT,
  enabled    INTEGER,
  permissions TEXT,                        -- JSON
  installed_at INTEGER
);
```

## 2.5 关键流程设计

### 2.5.1 扫描与解析

```
scan_library(path)
  → path_guard 校验白名单
  → 创建 task,返回 task_id
  → 遍历文件 → 比对 (path, mtime, hash)
       ├ 未变化:跳过
       ├ 新增/变更:加入解析队列
       └ 已删除:标记 missing
  → 解析器链(按文件类型选择,失败则降级到下一个解析器)
       PDF:GROBID(可用时) → PyMuPDF 首页文本 + 启发式 → 失败记录
  → 元数据归一化 → 写入 paper / paper_fts
  → 异步:元数据补全(Crossref/S2),失败忽略
  → 任务完成,输出扫描报告(成功/失败/跳过数量)
```

### 2.5.2 分类(两阶段)

```
classify_papers(scope)
  → 取 title + abstract(缺摘要则取首页前 N 字)
  → Embedder 生成向量并缓存
  → HDBSCAN 聚类;噪声点归入「未分类」
  → 每个簇:TF-IDF 关键词 + 代表论文(离质心最近)
  → LLM 为簇命名(可选,失败则用关键词拼接)
  → 写入 plan(status=draft),返回预览
apply_classification(plan_id, mode)
  → mode=move 时要求 confirm_token
  → 逐文件执行,写 oplog
  → plan.status=applied
undo_classification(plan_id)
  → 按 oplog 逆序还原
```

### 2.5.3 格式转换

```
convert_format(src, target, template?)
  → 路径校验;选择转换路线(路由表)
       md→docx            : Pandoc
       docx→pdf           : LibreOffice
       tex→pdf            : latexmk
       pdf→md             : marker/PyMuPDF(扫描件先 OCR)
       pdf→docx           : pdf→md→docx(两段式)+ 质量告警
  → 输出到 output_dir,原文件不动
  → 生成质量报告(告警列表)
```

**转换路由表**由配置驱动,便于后续替换更优引擎。

### 2.5.4 翻译流水线

```
translate_paper(paper_id, target_lang, backend, mode)
  → 首次使用该后端:外发提示 + 用户确认
  → 解析为结构(章节/段落/公式/代码/图表/引用)
  → protector:公式、代码、引用标记 → 占位符 {{M1}} {{C3}} …
  → segmenter:按语义边界分块(控制 token 上限,保留前后文摘要)
  → 成本预估 → 用户确认
  → 逐块调用 backend(并发度受限、带重试与退避)
       每块完成即写 translate_chunk(支撑断点续译)
  → 术语表注入(提示词内联 + 事后一致性检查)
  → 合并 → protector 还原 → 校验(占位符数量与顺序是否一致)
  → 输出:原格式 / Markdown / 双语对照
```

**翻译提示词要点**:保持学术语气、保留占位符不变、遵循术语表、不增删内容、输出仅含译文。

**校验失败策略**:占位符缺失或多出 → 该块自动重试(最多 2 次)→ 仍失败则标记为 failed,保留原文并在报告中列出。

### 2.5.5 插件生命周期

```
install_plugin(name)
  → 从插件索引获取清单 → 校验兼容性(min_core_version)
  → 展示权限,获取确认
  → pip 安装到独立目录/虚拟环境(隔离核心依赖)
  → 校验哈希 → 写入 plugin 表
  → host.load(): 通过 entry_points 加载,调用 register(api)
generate_outline(plugin, scope, options)
  → host 构造受限 PluginContext(只含授权能力)
  → 插件 generate() 在受保护的调用中执行(超时 + 异常隔离)
```

## 2.6 接口契约

### 2.6.1 适配器接口(Python Protocol)

```python
class Parser(Protocol):
    file_types: list[str]

    def parse(self, path: Path) -> ParsedDocument: ...


class Converter(Protocol):
    def can_convert(self, src_fmt: str, dst_fmt: str) -> bool: ...
    def convert(self, src: Path, dst: Path, opts: ConvertOptions) -> ConvertResult: ...


class TranslateBackend(Protocol):
    name: str

    async def translate(self, req: TranslateRequest) -> TranslateResponse: ...
    def estimate_cost(self, tokens: int) -> CostEstimate: ...


class OutlinePlugin(Protocol):
    def generate(self, ctx: PluginContext, options: dict) -> Outline: ...
```

### 2.6.2 PluginContext(插件可用能力,按权限授予)

| 能力 | 权限名 | 说明 |
|---|---|---|
| 读取论文元数据与摘要 | `read_library` | 只读 |
| 读取主题分组 | `read_topics` | 只读 |
| 调用大模型 | `call_llm` | 经核心的翻译/LLM 适配层,统一计费与日志 |
| 写入输出文件 | `write_output` | 仅限输出目录 |
| 联网 | `network` | 默认不授予 |

### 2.6.3 统一返回与错误码

```json
{
  "ok": false,
  "error": {
    "code": "E_CONVERTER_MISSING",
    "message": "未检测到 Pandoc",
    "hint": "请安装 Pandoc 后运行 doctor 重新检测"
  }
}
```

| 错误码 | 含义 |
|---|---|
| `E_PATH_DENIED` | 路径不在授权目录 |
| `E_NOT_FOUND` | 论文/任务/插件不存在 |
| `E_PARSE_FAILED` | 文件解析失败(含原因) |
| `E_CONVERTER_MISSING` | 缺少外部转换引擎 |
| `E_CONFIRM_REQUIRED` | 需要用户二次确认 |
| `E_BACKEND_AUTH` | 翻译后端鉴权失败(Key 无效/缺失) |
| `E_BACKEND_RATE` | 触发限流,已进入退避 |
| `E_PLACEHOLDER_MISMATCH` | 翻译后占位符不一致 |
| `E_PLUGIN_INCOMPATIBLE` | 插件与核心版本不兼容 |
| `E_TASK_CANCELLED` | 任务被取消 |

### 2.6.4 长任务工具约定

| 工具 | 说明 |
|---|---|
| `get_task_status(task_id)` | 返回状态、进度、已完成/失败明细 |
| `cancel_task(task_id)` | 请求取消 |
| `resume_task(task_id)` | 恢复可恢复的任务(翻译、批量转换) |

## 2.7 配置设计

```toml
[library]
paths = ["~/Papers"]
file_types = ["pdf", "docx", "md", "tex"]
default_apply_mode = "index"

[security]
require_confirm_for_move = true
allow_network_metadata = true

[embedding]
model = "<本地向量模型名>"
cache_dir = "~/.paperhub/cache"

[convert]
output_dir = "~/Papers/_converted"
pandoc_path = "auto"
routes = { "pdf->docx" = ["pdf_extract", "pandoc"] }

[translate]
default_backend = "anthropic"
default_target_lang = "zh-CN"
concurrency = 3
max_retries = 3

[translate.backends.openai]
model = "<模型名>"
[translate.backends.anthropic]
model = "<模型名>"

[plugins]
index_url = "<插件索引地址>"
install_dir = "~/.paperhub/plugins"
enabled = []
```

API Key 仅通过环境变量(`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`)或系统钥匙串读取,不写入配置文件。

## 2.8 安全设计要点

- **路径守卫**:所有入口路径先 `resolve()` 再比对白名单前缀;拒绝符号链接逃逸。
- **确认令牌**:破坏性操作先返回预览与一次性 `confirm_token`,携带令牌再次调用才执行,令牌短时过期。
- **日志脱敏**:不记录 API Key,不记录论文全文;记录文件路径、哈希、操作类型。
- **插件隔离**:插件安装于独立目录;默认无网络与写权限;调用设置超时。
- **提示注入防护**:论文内容是「数据」而非「指令」。翻译与大纲提示词中以明确分隔符包裹论文文本,并声明其中的指令性文字不得执行;返回给 MCP 客户端的论文内容同样视为不可信数据。

## 2.9 设计决策记录(ADR 摘要)

| 编号 | 决策 | 备选 | 理由 |
|---|---|---|---|
| ADR-1 | Python + 官方 MCP SDK | TypeScript | PDF/NLP 生态成熟 |
| ADR-2 | SQLite 单文件存储 | PostgreSQL | 本地工具,零运维 |
| ADR-3 | HDBSCAN 聚类 | KMeans | 无需预设簇数,能识别噪声 |
| ADR-4 | 分类两阶段(预览→应用) | 一步到位 | 降低误操作风险 |
| ADR-5 | 长任务异步 + task_id | 同步阻塞 | 避免客户端超时,支持取消/恢复 |
| ADR-6 | 翻译后端接口化 | 写死单一模型 | 满足 GPT/Claude/外部 MCP 并存 |
| ADR-7 | 插件走 Python entry_points | 自定义脚本系统 | 复用成熟打包与依赖管理 |
| ADR-8 | 转换路由表可配置 | 写死转换链 | 便于替换更优引擎 |

---

# 第三部分:总任务清单(WBS)

> 估算单位:人天(PD)。按 1 名全职开发者估算,含自测;AI 辅助编码可适当缩减。  
> 优先级与阶段对应:M1/M2 = P0,M3 = P1,M4 = P2。

## 3.1 工作分解总览

| 工作包 | 内容 | 估算(PD) |
|---|---|---|
| WP0 | 项目启动与工程基础 | 4 |
| WP1 | 扫描与索引 | 10 |
| WP2 | 检索与分类 | 12 |
| WP3 | 格式转换 | 11 |
| WP4 | 翻译与语言转换 | 16 |
| WP5 | 插件体系与大纲 | 12 |
| WP6 | 安全、任务与通用能力 | 8 |
| WP7 | 测试与质量 | 8 |
| WP8 | 文档与发布 | 5 |
| | **合计** | **约 86 PD** |

## 3.2 详细任务表

状态列用于跟踪:☐ 未开始 / ◐ 进行中 / ☑ 完成。

### WP0 项目启动与工程基础(4 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T0.1 | 初始化仓库、`pyproject.toml`、`uv` 环境、目录骨架 | 0.5 | — | 可运行空项目 | ☐ |
| T0.2 | 配置 ruff / mypy / pytest / pre-commit | 0.5 | T0.1 | 质量门禁 | ☐ |
| T0.3 | CI(GitHub Actions):lint + test + 多平台矩阵 | 1 | T0.2 | CI 流水线 | ☐ |
| T0.4 | MCP Server 骨架:注册一个 `ping` 工具,MCP Inspector 联调 | 1 | T0.1 | Hello World | ☐ |
| T0.5 | 配置加载模块(TOML + 环境变量)与校验 | 1 | T0.1 | `config.py` | ☐ |

### WP1 扫描与索引(10 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T1.1 | SQLite 初始化与迁移机制;`paper`、`paper_fts` 表 | 1 | T0.1 | `db.py` | ☐ |
| T1.2 | 路径守卫(白名单、规范化、符号链接处理) | 1 | T0.5 | `path_guard.py` | ☐ |
| T1.3 | 文件遍历 + 哈希 + 增量比对 | 1.5 | T1.1, T1.2 | `scanner.py` | ☐ |
| T1.4 | 解析器接口与 PDF 解析器(PyMuPDF:文本、首页启发式取标题/摘要) | 2 | T1.3 | `parsers/pdf.py` | ☐ |
| T1.5 | DOCX / MD / TEX 解析器 | 1.5 | T1.4 | 其余解析器 | ☐ |
| T1.6 | 元数据归一化(DOI 正则、年份、作者拆分) | 1 | T1.4 | `metadata.py` | ☐ |
| T1.7 | 工具:`scan_library`、`get_paper_info`、`search_papers`(关键词) | 1 | T1.3~T1.6 | 3 个 MCP 工具 | ☐ |
| T1.8 | 失败文件记录与扫描报告 | 0.5 | T1.3 | 报告输出 | ☐ |
| T1.9 | (P1)GROBID 解析器适配与降级链 | 1.5 | T1.4 | `parsers/grobid.py` | ☐ |
| T1.10 | (P1)Crossref / Semantic Scholar 元数据补全 | 1.5 | T1.6 | `MetadataSource` 实现 | ☐ |
| T1.11 | (P2)目录监听 `watchdog` 自动入库 | 1 | T1.3 | 监听器 | ☐ |

### WP2 检索与分类(12 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T2.1 | Embedder 接口与本地向量模型实现,向量缓存 | 1.5 | T1.1 | `embedder.py` | ☐ |
| T2.2 | HDBSCAN 聚类、噪声处理、簇关键词(TF-IDF) | 2 | T2.1 | `cluster.py` | ☐ |
| T2.3 | 主题命名(LLM 适配,失败回退关键词) | 1 | T2.2, T4.1 | `naming.py` | ☐ |
| T2.4 | `plan/topic/paper_topic` 表与方案预览输出 | 1 | T2.2 | 数据模型 + 预览 | ☐ |
| T2.5 | 应用器:index / symlink / move + oplog | 2 | T2.4, T6.2 | `applier.py` | ☐ |
| T2.6 | 撤销机制 `undo_classification` | 1 | T2.5 | 撤销工具 | ☐ |
| T2.7 | 工具:`classify_papers`、`apply_classification`、`undo_classification` | 1 | T2.4~T2.6 | MCP 工具 | ☐ |
| T2.8 | (P1)手动调整:移动/合并/拆分/重命名主题 | 1.5 | T2.4 | 调整工具 | ☐ |
| T2.9 | (P1)语义+关键词混合检索 | 1 | T2.1, T1.7 | 检索增强 | ☐ |
| T2.10 | (P1)重复检测 `find_duplicates` | 1 | T1.6 | `dedupe.py` | ☐ |
| T2.11 | (P1)BibTeX / CSL-JSON 导出 | 1 | T1.6 | `export_bibtex` | ☐ |

### WP3 格式转换(11 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T3.1 | 转换器接口 + 路由表 + 外部引擎检测 | 1.5 | T0.5 | `convert/base.py` | ☐ |
| T3.2 | Pandoc 转换器(MD/DOCX/LaTeX/HTML 互转) | 2 | T3.1 | `pandoc.py` | ☐ |
| T3.3 | LibreOffice(DOCX→PDF)与 latexmk(TEX→PDF) | 1.5 | T3.1 | PDF 输出 | ☐ |
| T3.4 | PDF→Markdown(PyMuPDF 基础版;marker 可选增强) | 2 | T3.1 | `pdf_extract.py` | ☐ |
| T3.5 | 工具:`convert_format`、`batch_convert`,输出目录与备份 | 1 | T3.2~T3.4 | MCP 工具 | ☐ |
| T3.6 | (P1)转换质量报告(公式/图片/表格告警) | 1.5 | T3.5 | `report.py` | ☐ |
| T3.7 | (P1)OCR 预处理(OCRmyPDF/Tesseract) | 1 | T3.4 | 扫描件支持 | ☐ |
| T3.8 | (P1)模板套用与 CSL 引用样式切换 | 1.5 | T3.2 | 模板/样式 | ☐ |

### WP4 翻译与语言转换(16 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T4.1 | `TranslateBackend` 接口、后端注册表、统一错误映射 | 1 | T0.5 | `translate/base.py` | ☐ |
| T4.2 | OpenAI 后端(重试、退避、限流处理) | 1.5 | T4.1 | `backends/openai.py` | ☐ |
| T4.3 | Anthropic 后端 | 1.5 | T4.1 | `backends/anthropic.py` | ☐ |
| T4.4 | 摘要/标题翻译工具 `translate_abstract` | 0.5 | T4.2, T4.3 | MCP 工具 | ☐ |
| T4.5 | 结构解析 + 占位符保护/还原(公式、代码、引用、图表编号) | 3 | T1.4 | `protector.py` | ☐ |
| T4.6 | 语义分块与上下文衔接 | 1.5 | T4.5 | `segmenter.py` | ☐ |
| T4.7 | 翻译流水线 + 校验 + 失败块重试 | 2 | T4.5, T4.6 | `pipeline.py` | ☐ |
| T4.8 | 工具 `translate_paper`(异步任务) | 1 | T4.7, T6.3 | MCP 工具 | ☐ |
| T4.9 | (P1)断点续译(`translate_chunk` 表与 `resume_task`) | 1.5 | T4.8 | 可恢复 | ☐ |
| T4.10 | (P1)术语表注入与一致性检查 | 1 | T4.7 | `glossary.py` | ☐ |
| T4.11 | (P1)双语对照输出;成本预估与确认 | 1.5 | T4.7 | 输出与预估 | ☐ |
| T4.12 | (P2)MCP Sampling 后端(含能力探测与回退) | 1.5 | T4.1 | `sampling.py` | ☐ |
| T4.13 | (P2)外部 MCP Server 后端(MCP Client 连接配置) | 2 | T4.1 | `mcp_client.py` | ☐ |

### WP5 插件体系与大纲(12 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T5.1 | 插件清单规范、校验器、`plugin` 表 | 1 | T1.1 | `manifest.py` | ☐ |
| T5.2 | 插件宿主:entry_points 加载、生命周期、异常隔离、超时 | 2 | T5.1 | `host.py` | ☐ |
| T5.3 | PluginContext 与权限模型 | 1.5 | T5.2 | `api.py` | ☐ |
| T5.4 | 插件安装/卸载(独立目录)、权限确认、哈希校验 | 2 | T5.2, T6.2 | 安装器 | ☐ |
| T5.5 | 工具:`list_plugins`、`install_plugin`、`enable/disable_plugin` | 0.5 | T5.4 | MCP 工具 | ☐ |
| T5.6 | 官方插件 `outline-survey`(MVP 版)+ `generate_outline` 工具 | 2 | T5.3, T2.4 | 首个插件 | ☐ |
| T5.7 | (P1)大纲导出 MD/DOCX/LaTeX;对话式修改 | 1 | T5.6 | 导出/迭代 | ☐ |
| T5.8 | (P1)`outline-empirical`、`outline-thesis`、`outline-from-draft` | 1.5 | T5.6 | 3 个插件 | ☐ |
| T5.9 | (P1)插件索引与版本兼容性检查 | 0.5 | T5.4 | 索引 JSON | ☐ |

### WP6 安全、任务与通用能力(8 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T6.1 | 统一错误码与返回结构 | 0.5 | T0.4 | `errors.py` | ☐ |
| T6.2 | 确认令牌机制 + 操作日志 | 1.5 | T1.1 | `confirm.py`、`oplog.py` | ☐ |
| T6.3 | 异步任务框架(task 表、进度、取消、恢复) | 2.5 | T1.1 | `tasks.py` | ☐ |
| T6.4 | 结构化日志与敏感信息脱敏 | 1 | T0.1 | 日志模块 | ☐ |
| T6.5 | 外发内容提示与用户确认记录 | 0.5 | T6.2 | 隐私提示 | ☐ |
| T6.6 | (P1)`doctor` 自检工具 | 1 | T3.1, T4.1 | 依赖检测 | ☐ |
| T6.7 | 提示注入防护:提示词分隔与不可信数据标注 | 1 | T4.7, T5.6 | 防护规范 | ☐ |

### WP7 测试与质量(8 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T7.1 | 构建测试样本集(50 篇多格式论文,含双栏、扫描件、公式密集、中英文) | 2 | — | `fixtures/` | ☐ |
| T7.2 | 元数据提取标注集与准确率评测脚本 | 1.5 | T7.1, T1.6 | 评测脚本 | ☐ |
| T7.3 | 聚类评测(纯度)与阈值调参 | 1 | T7.1, T2.2 | 评测报告 | ☐ |
| T7.4 | 翻译占位符还原测试(含 mock 后端) | 1 | T4.7 | 单元测试 | ☐ |
| T7.5 | 核心流程集成测试(经 MCP 协议端到端) | 1.5 | 各 WP | 集成测试 | ☐ |
| T7.6 | 跨平台(macOS/Windows/Linux)冒烟与路径兼容测试 | 1 | T0.3 | CI 矩阵结果 | ☐ |

### WP8 文档与发布(5 PD)

| ID | 任务 | 估算 | 依赖 | 产出 | 状态 |
|---|---|---|---|---|---|
| T8.1 | README、快速开始、Claude Desktop/Cursor 配置示例 | 1 | M1 | README | ☐ |
| T8.2 | 各 MCP 工具的参数与示例文档 | 1 | M2 | 工具手册 | ☐ |
| T8.3 | 插件开发指南与模板仓库 | 1.5 | M3 | 开发者文档 | ☐ |
| T8.4 | 打包发布:PyPI、`uvx` 验证、版本号策略、CHANGELOG | 1 | M3 | 发布流程 | ☐ |
| T8.5 | 隐私与安全说明页 | 0.5 | M3 | 说明文档 | ☐ |

---

# 第四部分:里程碑与排期

## 4.1 里程碑

| 里程碑 | 目标 | 包含任务 | 预计周期 | 退出标准 |
|---|---|---|---|---|
| **M0 启动** | 工程可跑 | WP0 | 第 1 周 | CI 绿,MCP Inspector 能调用 `ping` |
| **M1 可扫描可分类**(MVP-α) | 本地论文入库并预览分类 | T1.1–T1.8、T2.1–T2.7、T6.1–T6.4 | 第 2–4 周 | 对 30 篇样本完成扫描 → 分类预览 → 软链接应用 → 撤销全链路 |
| **M2 可转换可翻译**(MVP-β) | 格式转换与摘要/全文翻译 | WP3 的 P0、T4.1–T4.8、T6.5、T7.4 | 第 5–7 周 | 5 种格式转换可用;含公式论文翻译后公式 100% 还原 |
| **M3 插件与完善**(v1.0) | 插件宿主 + 大纲插件 + P1 能力 | WP5、各 WP 的 P1 任务、T6.6–T6.7、WP7、WP8 | 第 8–12 周 | 满足 §5 验收标准;PyPI 发布 |
| **M4 生态扩展**(v1.x) | P2 能力 | T1.11、T4.12–T4.13、更多插件 | 视情况 | MCP Sampling/外部 MCP 后端可用 |

## 4.2 关键依赖与关键路径

```
T0.* → T1.1/T1.2 → T1.3 → T1.4 → T1.6 → T1.7
                              ↘ T4.5 → T4.6 → T4.7 → T4.8
T1.1 → T6.3(任务框架) ───────────────→ T4.8、T1.7(扫描异步)
T2.1 → T2.2 → T2.4 → T2.5(需 T6.2) → T2.7
T5.1 → T5.2 → T5.3 → T5.6(需 T2.4)
```

**关键路径**:`解析器 → 占位符保护 → 翻译流水线`(技术风险最高),建议在 M1 期间就用样本并行做 T4.5 的原型验证。

## 4.3 周计划参考(单人)

| 周 | 重点 |
|---|---|
| W1 | WP0;T1.1–T1.2;T6.1 |
| W2 | T1.3–T1.7;T6.4 |
| W3 | T2.1–T2.4;T6.2、T6.3 |
| W4 | T2.5–T2.7;M1 联调与评测(T7.1–T7.3 起步) |
| W5 | T3.1–T3.4 |
| W6 | T3.5;T4.1–T4.4 |
| W7 | T4.5–T4.8;T6.5;M2 验收 |
| W8–9 | WP5(插件宿主、安装器、`outline-survey`) |
| W10 | P1:T1.9–T1.10、T2.8–T2.11、T3.6–T3.8 |
| W11 | P1:T4.9–T4.11、T5.7–T5.9、T6.6–T6.7 |
| W12 | WP7 收尾、WP8 文档与发布 |

---

# 第五部分:测试与验收计划

## 5.1 测试分层

| 层级 | 范围 | 工具 | 说明 |
|---|---|---|---|
| 单元测试 | 解析器、占位符保护、分块、聚类、路径守卫、清单校验 | pytest | 外部 API 全部 mock |
| 集成测试 | 扫描→分类→应用→撤销;转换路由;翻译流水线 | pytest + 临时目录 | 使用 fixtures 样本 |
| 协议测试 | 通过 MCP 协议调用工具,校验入参/出参/错误码 | MCP Inspector / 客户端 SDK | 保证与客户端兼容 |
| 评测 | 元数据准确率、聚类纯度、翻译结构还原率 | 自研脚本 | 指标回归,防止退化 |
| 手工验收 | Claude Desktop 实际对话走查 | — | 按 §5.3 清单 |

## 5.2 测试数据集要求

- 总计约 50 篇,覆盖:单栏/双栏、中英文、扫描件、公式密集、含表格与图、加密/损坏文件各若干
- 至少 3 个明确研究主题 + 若干跨主题论文,用于聚类评测
- 含 5 组重复论文(同一论文不同文件名/版本)
- 样本需为可合法使用的开放获取论文(如 arXiv 论文,注意各论文的许可)

## 5.3 v1.0 验收清单

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| AC-1 | 扫描 | 样本集扫描无崩溃;失败文件均有原因记录;增量扫描有效 |
| AC-2 | 元数据 | 标题准确率 ≥ 85%,摘要提取率 ≥ 80% |
| AC-3 | 分类 | 聚类纯度 ≥ 80%;预览不改动文件;软链接/移动可撤销 |
| AC-4 | 转换 | 支持矩阵内转换全部可执行;原文件哈希不变;缺引擎时提示明确 |
| AC-5 | 翻译 | 含公式样本翻译后公式 100% 还原;失败块可定位;断点续译有效 |
| AC-6 | 翻译后端 | OpenAI 与 Anthropic 后端均可完成摘要与全文翻译 |
| AC-7 | 插件 | 安装 `outline-survey` 并生成大纲;插件异常不影响核心 |
| AC-8 | 安全 | 非白名单路径被拒;移动操作需确认;日志无 API Key 与全文 |
| AC-9 | 兼容 | macOS / Windows / Linux 冒烟通过 |
| AC-10 | 安装 | 新机器按 README 5 分钟内完成配置并成功调用首个工具 |

---

# 第六部分:风险与依赖

## 6.1 风险登记

| ID | 风险 | 概率 | 影响 | 应对措施 | 负责任务 |
|---|---|---|---|---|---|
| R1 | 学术 PDF(双栏/扫描)元数据提取不准 | 高 | 中 | GROBID + 启发式双通道;提供手动修正入口;用评测集持续优化 | T1.4、T1.9、T7.2 |
| R2 | 公式/引用在翻译中被破坏 | 中 | 高 | 占位符保护 + 事后校验 + 失败块重试;M1 期间提前做原型 | T4.5、T4.7 |
| R3 | PDF→DOCX/LaTeX 保真度达不到预期 | 高 | 中 | 明确支持矩阵与「尽力还原」口径;质量报告;可选 marker 增强 | T3.4、T3.6 |
| R4 | 聚类效果在小样本/跨学科场景不佳 | 中 | 中 | 允许指定主题数;支持手动调整;换用学术专用向量模型 | T2.2、T2.8 |
| R5 | 全文翻译成本与耗时失控 | 中 | 中 | 成本预估确认;模型路由;分块并发限制;断点续译 | T4.9、T4.11 |
| R6 | 外部 API 变更或限流 | 中 | 中 | 适配层隔离;重试退避;模型名走配置 | T4.1–T4.3 |
| R7 | MCP Sampling 在多数客户端不可用 | 高 | 低 | 作为 P2 可选后端,默认回退直连 API | T4.12 |
| R8 | 恶意或低质量插件 | 中 | 高 | 权限模型、哈希校验、隔离安装、官方索引审核 | T5.3、T5.4 |
| R9 | 论文内容中的提示注入影响 LLM 行为 | 中 | 中 | 提示词分隔、不可信数据声明、输出校验 | T6.7 |
| R10 | 跨平台路径/依赖差异导致 Windows 问题 | 中 | 中 | CI 三平台矩阵;路径统一用 `pathlib` | T7.6 |
| R11 | 许可证冲突(PyMuPDF 为 AGPL) | 视决策 | 高 | **尽早决策**是否开源;闭源/宽松许可则改用 pypdf+pdfplumber 或商业授权 | 决策项 D1 |
| R12 | 版权合规(翻译/转换他人论文) | 低 | 中 | 文档声明仅限个人学习研究;不提供传播功能 | T8.5 |

## 6.2 待决策项

| 编号 | 问题 | 影响 | 建议截止 |
|---|---|---|---|
| D1 | 项目是否开源、选何种许可证 | 决定能否使用 PyMuPDF,影响 T1.4 | M0 结束前 |
| D2 | 默认分类应用模式(index 还是 symlink) | 影响默认行为与文档 | M1 开始前 |
| D3 | 是否需要与 Zotero 等互通(超出 BibTeX 导出) | 影响 WP2 范围 | M2 开始前 |
| D4 | 向量模型选型(通用 vs 学术专用;中英文混合需求) | 影响聚类效果与安装体积 | T2.1 开始前 |
| D5 | 是否支持多用户/团队部署(HTTP + 鉴权) | 影响架构与安全设计 | M3 前 |
| D6 | 插件是否对第三方开放及审核机制 | 影响 T5.9 与运营投入 | M3 前 |

## 6.3 外部依赖清单

| 依赖 | 类型 | 缺失时的降级策略 |
|---|---|---|
| Pandoc | 本地程序 | 转换功能不可用,`doctor` 提示安装 |
| LaTeX / LibreOffice | 本地程序 | 对应的 PDF 输出不可用,其余格式不受影响 |
| GROBID | 本地服务(Docker) | 降级到 PyMuPDF 启发式解析 |
| Tesseract / OCRmyPDF | 本地程序 | 扫描件标记为「需 OCR」,跳过 |
| OpenAI / Anthropic API | 外部服务 | 翻译不可用;分类命名回退关键词 |
| Crossref / Semantic Scholar / OpenAlex | 外部服务 | 跳过补全,使用解析结果 |

---

# 第七部分:开发规范与协作约定

## 7.1 分支与提交

- 主干 `main` 保持可发布;功能分支命名 `feat/Txx-简述`,修复 `fix/...`
- 提交信息采用 Conventional Commits(`feat:`、`fix:`、`docs:`、`test:`、`refactor:`)
- 每个任务 ID 对应至少一个 PR,PR 描述需关联任务 ID 与验收点

## 7.2 完成定义(Definition of Done)

一个任务视为完成,需同时满足:

1. 功能满足对应 FR 的验收标准
2. 单元测试已覆盖核心逻辑,CI 全绿
3. ruff 与 mypy 无新增告警
4. 涉及用户可见行为的,更新了工具文档或 README
5. 涉及外发内容、文件改动的,通过了安全检查项(路径守卫、确认、日志脱敏)
6. 错误路径有明确的错误码与可读提示

## 7.3 版本策略

- 语义化版本:`0.x` 为 MVP 阶段,`1.0.0` 对应 M3 验收通过
- 插件清单中的 `min_core_version` 与核心版本联动,破坏性变更须提升主版本并在 CHANGELOG 说明

## 7.4 建议的下一步行动

1. 先做决策 D1(开源与否),它决定 PDF 解析库选型
2. 完成 M0:仓库、CI、`ping` 工具,在 Claude Desktop 中真实连通一次
3. 同步构建 T7.1 测试样本集——后续所有评测都依赖它
4. 在 M1 期间并行做 T4.5(占位符保护)的原型验证,尽早暴露最大技术风险
