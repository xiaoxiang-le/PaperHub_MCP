import asyncio
import json
import os
import sys

from conftest import wait_task
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from paperhub.server import create_server


def unwrap(result):
    if isinstance(result, dict):
        return result
    if isinstance(result, tuple):
        return result[1]
    return json.loads(result[0].text)


async def test_tools_resources_prompts_and_structured_errors(library):
    server = create_server(library)
    tools = {tool.name for tool in await server.list_tools()}
    assert {
        "scan_library",
        "classify_papers",
        "translate_paper",
        "install_plugin",
        "doctor",
    } <= tools
    assert unwrap(await server.call_tool("ping", {}))["ok"]
    denied = unwrap(await server.call_tool("scan_library", {"path": "C:/outside/papers"}))
    assert denied["error"]["code"] == "E_PATH_DENIED"
    search = unwrap(await server.call_tool("search_papers", {"query": "attention"}))
    assert search["data"][0]["title"] == "Efficient Transformer Attention"
    resource = list(await server.read_resource("paperhub://library/index"))
    assert len(json.loads(resource[0].content)["data"]) == 4
    prompts = await server.list_prompts()
    assert len(prompts) == 3
    result = unwrap(await server.call_tool("doctor", {}))
    assert result["ok"] and "api_keys" in result["data"]
    scan = unwrap(await server.call_tool("scan_library", {"path": str(library.guard.roots[0])}))
    assert (await wait_task(library, scan["data"]["task_id"]))["status"] == "done"


async def test_stdio_protocol_end_to_end(app):
    environment = {
        **os.environ,
        "PAPERHUB_LIBRARY_PATHS": str(app.guard.roots[0]),
        "PAPERHUB_DATA_DIR": str(app.config.data_dir),
        "PAPERHUB_OUTPUT_DIR": str(app.guard.output),
    }
    (app.guard.roots[0] / "protocol.md").write_text(
        "# Protocol Paper\nAbstract\nMCP testing", encoding="utf-8"
    )
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "paperhub.server"], env=environment
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        ping = await session.call_tool("ping", {})
        assert not ping.isError and ping.structuredContent["data"]["version"] == "0.1.0"
        scanned = await session.call_tool("scan_library", {"path": str(app.guard.roots[0])})
        task_id = scanned.structuredContent["data"]["task_id"]
        for _ in range(100):
            state = await session.call_tool("get_task_status", {"task_id": task_id})
            if state.structuredContent["data"]["status"] == "done":
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError("scan did not finish")
        papers = await session.call_tool("search_papers", {"query": "Protocol"})
        assert papers.structuredContent["data"][0]["title"] == "Protocol Paper"
        resource = await session.read_resource("paperhub://library/index")
        assert "Protocol Paper" in resource.contents[0].text
