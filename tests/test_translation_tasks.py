import asyncio
from pathlib import Path

import pytest
from conftest import MockBackend, confirmation, wait_task

from paperhub.app import Application
from paperhub.core.models import TranslateRequest
from paperhub.errors import PaperHubError
from paperhub.translate.protector import PLACEHOLDER, Protector
from paperhub.translate.segmenter import segment


@pytest.mark.parametrize(
    "text",
    [
        "Math $E=mc^2$ then $$a+b=c$$ and [1, 2].",
        r"Equations \(x+y\) and \[z=1\] and \cite{smith2024}.",
        "```python\nprint('$not math$')\n``` and `code`.",
        r"\begin{align}a&=b\\c&=d\end{align} Figure 1 Table 3.",
        "![caption](image.png) [reference](https://example.com) [@smith2024]",
    ],
)
def test_structure_roundtrip_and_mismatch(text):
    protector = Protector(text)
    assert protector.restore(protector.text) == text
    assert protector.values
    first = next(iter(protector.values))
    with pytest.raises(PaperHubError):
        protector.restore(protector.text.replace(first, ""))
    with pytest.raises(PaperHubError):
        protector.restore(protector.text + first)


def test_segment_exact_join_and_placeholder_boundaries():
    source = ("Paragraph one $x^2$.\n\n" + "long " * 90 + "\n\n") * 8
    protector = Protector(source)
    chunks = segment(protector.text, 500)
    assert "".join(chunks) == protector.text
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert sum(len(PLACEHOLDER.findall(c)) for c in chunks) == len(protector.values)
    assert all("{{PH_" not in PLACEHOLDER.sub("", c) for c in chunks)


async def test_translation_requires_consent_and_preserves_source(library):
    app = library
    backend = MockBackend()
    app.translator.register(backend)
    paper = next(p for p in app.library.papers() if p["file_type"] == "md")
    token = confirmation(
        lambda: app.translator.start(paper["id"], "zh-CN", "mock", "full", {}, None)
    )
    assert backend.calls == []
    submitted = app.translator.start(paper["id"], "zh-CN", "mock", "full", {}, token)
    state = await wait_task(app, submitted["task_id"])
    assert state["status"] == "done"
    output = Path(state["result"]["path"]).read_text(encoding="utf-8")
    original = app.library.get(paper["id"], True)["text"]
    assert output == original
    assert "$E=mc^2$" in output and "[1, 2]" in output


async def test_failed_translation_resumes_only_failed_chunks(app):
    path = app.guard.roots[0] / "long.md"
    path.write_text(
        "# Long Paper\n\n" + ("good text. " * 60) + "\n\nBADBLOCK\n\n" + ("more good text. " * 60),
        encoding="utf-8",
    )
    app.library.scan(str(app.guard.roots[0]), True, None)
    paper = app.library.papers()[0]
    backend = MockBackend()
    backend.fail_on = "BADBLOCK"
    app.translator.register(backend)
    token = confirmation(lambda: app.translator.start(paper["id"], "zh", "mock", "full", {}, None))
    task_id = app.translator.start(paper["id"], "zh", "mock", "full", {}, token)["task_id"]
    result = await wait_task(app, task_id)
    assert result["status"] == "failed"
    assert result["result"]["error"]["failed_chunks"]
    original_calls = len(backend.calls)
    backend.fail_on = None
    app.tasks.resume(task_id)
    result = await wait_task(app, task_id)
    assert result["status"] == "done"
    assert len(backend.calls) == original_calls + 1
    assert Path(result["result"]["path"]).read_text(encoding="utf-8") == path.read_text(
        encoding="utf-8"
    )


async def test_placeholder_corruption_is_reported(library):
    app = library
    backend = MockBackend()
    backend.corrupt = True
    app.translator.register(backend)
    paper = next(p for p in app.library.papers() if p["file_type"] == "md")
    token = confirmation(lambda: app.translator.start(paper["id"], "zh", "mock", "full", {}, None))
    task_id = app.translator.start(paper["id"], "zh", "mock", "full", {}, token)["task_id"]
    state = await wait_task(app, task_id)
    assert state["status"] == "failed"
    assert state["result"]["error"]["failed_chunks"][0]["code"] == "E_PLACEHOLDER_MISMATCH"


async def test_abstract_and_bilingual_output(library):
    app = library
    backend = MockBackend()
    app.translator.register(backend)
    paper = next(p for p in app.library.papers() if p["file_type"] == "md")
    with pytest.raises(PaperHubError) as error:
        await app.translator.abstract(paper["id"], "zh", "mock", {}, None)
    translated = await app.translator.abstract(
        paper["id"], "zh", "mock", {}, error.value.details["confirm_token"]
    )
    assert translated["translation"] == translated["source"]
    assert len(backend.calls) == 1
    token = confirmation(
        lambda: app.translator.start(paper["id"], "zh", "mock", "bilingual", {}, None)
    )
    task_id = app.translator.start(paper["id"], "zh", "mock", "bilingual", {}, token)["task_id"]
    state = await wait_task(app, task_id)
    output = Path(state["result"]["path"]).read_text(encoding="utf-8")
    assert "Original / 原文" in output and "Translation / 译文" in output


async def test_cancel_translation_promptly_and_resume(library):
    app = library
    backend = MockBackend()
    backend.delay = 5
    app.translator.register(backend)
    paper = app.library.papers()[0]
    token = confirmation(lambda: app.translator.start(paper["id"], "zh", "mock", "full", {}, None))
    task_id = app.translator.start(paper["id"], "zh", "mock", "full", {}, token)["task_id"]
    await asyncio.sleep(0.02)
    app.tasks.cancel(task_id)
    state = await wait_task(app, task_id)
    assert state["status"] == "cancelled"
    backend.delay = 0
    app.tasks.resume(task_id)
    assert (await wait_task(app, task_id))["status"] == "done"


async def test_restart_marks_interrupted_task_and_restores_runners(app):
    app.db.put(
        "task",
        "interrupted-test",
        {
            "id": "interrupted-test",
            "type": "scan",
            "status": "running",
            "cancel_requested": False,
            "payload": {"path": str(app.guard.roots[0]), "recursive": True, "file_types": None},
        },
    )
    restarted = Application(app.config)
    assert restarted.tasks.status("interrupted-test")["status"] == "interrupted"
    restarted.tasks.resume("interrupted-test")
    assert (await wait_task(restarted, "interrupted-test"))["status"] == "done"


async def test_backend_errors_do_not_leak_credentials(app, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = app.translator.backends["openai"]
    with pytest.raises(PaperHubError) as error:
        await backend.translate(TranslateRequest(text="confidential text", target_lang="zh"))
    assert error.value.code == "E_BACKEND_AUTH"
    assert "confidential text" not in str(error.value.as_dict())
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    with pytest.raises(PaperHubError) as error:
        await backend.translate(TranslateRequest(text="confidential text", target_lang="zh"))
    assert error.value.code == "E_CONFIG"
    assert "secret-test-key" not in str(error.value.as_dict())
