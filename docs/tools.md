# MCP 工具手册

所有工具成功返回 `{"ok": true, "data": ...}`；业务错误返回 `{"ok": false, "error": {"code", "message", "hint", ...}}`。协议层参数类型错误由 MCP SDK 返回。论文元数据和插件内容均应视为不可信数据。

| 工具 | 主要参数 | 返回/行为 |
|---|---|---|
| ping | 无 | 名称与版本 |
| doctor | 无 | 引擎路径、包版本、授权目录、Key 是否配置；不会显示 Key |
| reload_config | 无 | 空闲时重新读取 TOML 和环境变量；更改 data_dir 需重启 |
| scan_library | path, recursive=true, file_types=null | task_id；默认 PDF/DOCX/MD/TEX |
| get_paper_info | paper_id | 元数据、摘要、文件状态 |
| update_paper_metadata | paper_id, fields | 手工修正 title/authors/year/abstract/keywords/doi/language；不改原文件 |
| search_papers | query, topic=null, year_range=null, limit=20, semantic=false | 论文列表；year_range=[起始,结束]，limit≤200 |
| classify_papers | scope=null, num_topics=null | 预览 plan；scope 为论文 ID 数组，null 表示全部可用论文 |
| get_classification | plan_id | 方案及分组 |
| adjust_classification | plan_id, topics | topics=[{name,paper_ids}]；每篇原论文恰好出现一次，支持重命名、合并、拆分、调组 |
| apply_classification | plan_id, mode=index, confirm_token=null | index/symlink/move；move 需用户确认 |
| undo_classification | plan_id | 从日志恢复；遇到冲突停止 |
| find_duplicates | scope=null | 可能重复的论文 ID 对及判断原因 |
| export_bibtex | scope=null, style=bibtex | style=bibtex/csl-json；生成新文件 |
| convert_format | target_format, path 或 paper_id, template=null, csl=null | 异步任务；template/csl 路径需授权，模板为 DOCX |
| batch_convert | target_format, scope=null | 异步任务，逐文件失败隔离 |
| translate_abstract | paper_id, target_lang=zh-CN, backend=openai, glossary={}, confirm_token=null | 外发确认后，一次请求翻译标题和摘要，返回原文和译文 |
| translate_paper | paper_id, target_lang=zh-CN, backend=openai, mode=full, glossary={}, confirm_token=null | mode=full/bilingual；确认后异步处理 |
| load_glossary | path | CSV 格式 source,target，返回可传入 glossary 的字典 |
| get_task_status | task_id | status、progress、result，不返回内部 payload |
| cancel_task | task_id | 协作式取消；外部请求和转换进程会取消/终止 |
| resume_task | task_id | 恢复 failed/cancelled/interrupted 任务；翻译复用成功分块 |
| list_plugins | installed_only=false | 官方本地目录及已安装插件 |
| install_plugin | plugin_name, confirm_token=null, wheel_path=null, manifest=null, sha256=null | 先预览权限，再确认安装；第三方只接受本地 wheel |
| enable_plugin / disable_plugin / uninstall_plugin | plugin_name | 插件生命周期 |
| generate_outline | plugin=outline-survey, scope=null, options={} | 结构化大纲、章节要点、论文 ID 引用建议 |
| edit_outline | outline_id, title, sections | 更新指定大纲；sections 为完整新章节列表，其余章节可原样保留 |
| export_outline | outline_id, target_format=md | Markdown 原生导出；DOCX/TEX 需要 Pandoc |

## 两阶段确认

第一次调用：

```json
{"plan_id":"<plan-id>","mode":"move"}
```

返回 `E_CONFIRM_REQUIRED`，包含 `confirm_token`、`expires_in`、`preview`。客户端必须向用户展示预览并获得同意，再调用：

```json
{"plan_id":"<plan-id>","mode":"move","confirm_token":"<token>"}
```

任何参数或源文件/方案变化都可能使令牌无效。翻译确认包含模型、外部服务地址、文本字符数、估算 tokens 和费用。第三方插件确认包含权限、入口、版本、哈希与信任说明。

## 任务状态

`pending → running → done / failed / cancelled`。进程异常退出后，下次启动把未完成任务标记为 `interrupted`，由 `resume_task` 显式恢复。`progress` 为 0～1；批量任务即使有单文件失败也可以为 `done`，调用者应检查 `result.failed`。翻译有失败分块时任务为 `failed`，报告列出分块索引和错误码，成功分块已持久化。

## 资源与提示模板

- `paperhub://library/index`：授权范围内论文元数据。
- `paperhub://paper/{paper_id}`：指定论文元数据。
- `paperhub://topics/{topic_id}`：已应用主题中的论文。
- `paperhub://plugins/installed`：已安装插件。

提示模板：`organize_my_library(path)`、`write_survey_outline()`、`translate_with_glossary(paper_id,target_lang)`。

