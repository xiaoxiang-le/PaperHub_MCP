import csv
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import confirmation

from paperhub.config import BackendConfig
from paperhub.core.models import TranslateRequest
from paperhub.errors import PaperHubError
from paperhub.security.path_guard import file_hash
from paperhub.translate.backends import APIBackend
from paperhub.translate.pipeline import parse_glossary


class AsyncClient:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=self)
        self.messages = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


async def test_openai_and_anthropic_adapters_mocked(app, monkeypatch):
    import anthropic
    import openai

    class OpenAIClient(AsyncClient):
        async def create(self, **kwargs):
            assert "untrusted_document_data" in kwargs["messages"][1]["content"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop", message=SimpleNamespace(content="中文译文")
                    )
                ],
                usage=None,
            )

    class AnthropicClient(AsyncClient):
        async def create(self, **kwargs):
            assert "untrusted_document_data" in kwargs["messages"][0]["content"]
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="中文译文")],
                usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 20}),
            )

    monkeypatch.setattr(openai, "AsyncOpenAI", OpenAIClient)
    monkeypatch.setattr(anthropic, "AsyncAnthropic", AnthropicClient)
    for name in ("openai", "anthropic"):
        monkeypatch.setenv(f"{name.upper()}_API_KEY", "secret-test-key")
        backend = APIBackend(
            name,
            BackendConfig(model="test", input_per_million=1, output_per_million=2),
            app.config.translate,
        )
        response = await backend.translate(
            TranslateRequest(text="untrusted instructions", target_lang="zh")
        )
        assert response.text == "中文译文"
        assert backend.estimate_cost(1000).estimated_usd is not None


async def test_provider_error_is_redacted(app, monkeypatch):
    import openai

    class FailedClient(AsyncClient):
        async def create(self, **kwargs):
            exception = RuntimeError("secret-test-key private-fulltext")
            exception.status_code = 429
            raise exception

    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    monkeypatch.setattr(openai, "AsyncOpenAI", FailedClient)
    backend = APIBackend("openai", BackendConfig(model="test"), app.config.translate)
    with pytest.raises(PaperHubError) as error:
        await backend.translate(TranslateRequest(text="private-fulltext", target_lang="zh"))
    assert error.value.code == "E_BACKEND_RATE"
    assert "secret-test-key" not in str(error.value.as_dict())
    assert "private-fulltext" not in str(error.value.as_dict())


def test_glossary_csv():
    assert parse_glossary("source,target\nattention,注意力\n") == {"attention": "注意力"}
    with pytest.raises(PaperHubError):
        parse_glossary("wrong,columns\nx,y")


def tiny_wheel(path: Path) -> Path:
    wheel = path / "tiny_plugin-0.1.0-py3-none-any.whl"
    module = """
import os, time
class Plugin:
    def generate(self, ctx, options):
        assert not os.environ.get("OPENAI_API_KEY")
        if options.get("crash"):
            raise RuntimeError("private plugin failure")
        if options.get("hang"):
            time.sleep(10)
        return {"title":"Third party outline", "sections":[{"title":"Evidence", "points":[],
            "citations":[p["id"] for p in ctx.papers]}], "notes":[]}
"""
    files = {
        "tiny_plugin.py": module,
        "tiny_plugin-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\nName: tiny-plugin\nVersion: 0.1.0\n",
        "tiny_plugin-0.1.0.dist-info/WHEEL": "Wheel-Version: 1.0\nGenerator: paperhub-tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "tiny_plugin-0.1.0.dist-info/entry_points.txt": "[paperhub.outlines]\ntiny-plugin = tiny_plugin:Plugin\n",
    }
    record = io.StringIO()
    writer = csv.writer(record)
    for file in files:
        writer.writerow([file, "", ""])
    writer.writerow(["tiny_plugin-0.1.0.dist-info/RECORD", "", ""])
    files["tiny_plugin-0.1.0.dist-info/RECORD"] = record.getvalue()
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return wheel


def test_real_isolated_wheel_install_crash_and_timeout(library, monkeypatch):
    app = library
    wheel = tiny_wheel(app.guard.roots[0])
    manifest = {
        "name": "tiny-plugin",
        "version": "0.1.0",
        "entry": "tiny_plugin:Plugin",
        "permissions": ["read_library"],
        "min_core_version": "0.1.0",
    }
    sha = file_hash(wheel)
    token = confirmation(
        lambda: app.plugins.install("tiny-plugin", None, str(wheel), manifest, sha)
    )
    app.plugins.install("tiny-plugin", token, str(wheel), manifest, sha)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    result = app.plugins.generate("tiny-plugin", None, {})
    assert len(result["sections"][0]["citations"]) == 4
    with pytest.raises(PaperHubError) as error:
        app.plugins.generate("tiny-plugin", None, {"crash": True})
    assert error.value.code == "E_PLUGIN_FAILED"
    app.plugins.timeout = 0.2
    with pytest.raises(PaperHubError):
        app.plugins.generate("tiny-plugin", None, {"hang": True})
    assert app.library.papers() and app.doctor()
    app.plugins.uninstall("tiny-plugin")
    assert app.plugins.list_plugins(True) == []
