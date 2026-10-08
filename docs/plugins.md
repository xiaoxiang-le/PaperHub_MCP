# 插件开发

官方本地插件 `outline-survey`、`outline-empirical`、`outline-thesis`、`outline-from-draft` 均需通过安装确认后启用。它们生成结构模板及建议引用，不推断实验结果。

第三方插件采用 Python wheel + `paperhub.outlines` entry point。仓库提供可独立打包的 [示例](../plugins/outline-example/pyproject.toml)。插件 `generate(ctx, options)` 接收具有 `papers`、`topics` 字段的上下文；返回 JSON 可序列化字典：

```json
{
  "title":"My outline",
  "sections":[{"title":"Related Work","points":["Compare methods"],"citations":["<paper-id>"]}],
  "notes":[]
}
```

引用必须来自传入的论文 ID。缺少 `read_library` / `read_topics` 权限时对应数组为空。当前只支持这两种宿主能力。生成结果通过 Pydantic 校验，异常、超时、非法输出不影响核心服务。

清单示例：

```json
{
  "name":"outline-example",
  "version":"0.1.0",
  "type":"outline",
  "entry":"outline_example:ExamplePlugin",
  "permissions":["read_library","read_topics"],
  "min_core_version":"0.1.0",
  "description":"A local outline plugin"
}
```

打包、安装流程：

```powershell
python -m build plugins/outline-example
Get-FileHash plugins/outline-example/dist/*.whl -Algorithm SHA256
```

将 wheel 放入授权目录，调用 `install_plugin(plugin_name="outline-example", wheel_path="...", manifest={...}, sha256="...")`；用户确认后再提供返回的 `confirm_token`。宿主通过 venv + `pip --no-index --no-deps` 安装，只接受与清单一致的入口和版本。目前不自动从网络安装依赖；示例插件只依赖 Python 标准库。

SHA256 由可信分发渠道提供，不应把来自同一不可信来源的哈希当成真实性证明。独立进程用于错误与超时隔离，不能阻止恶意插件访问用户文件系统，详见 [安全说明](security.md)。

