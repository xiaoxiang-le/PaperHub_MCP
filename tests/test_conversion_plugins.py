import sys
from pathlib import Path

import pytest
from conftest import confirmation, wait_task

from paperhub.convert.service import run_engine
from paperhub.errors import PaperHubError
from paperhub.plugins.manifest import PluginManifest
from paperhub.security.path_guard import file_hash


def test_pdf_to_md_and_missing_engine(library, monkeypatch):
    app = library
    pdf = app.guard.roots[0] / "robot.pdf"
    before = file_hash(pdf)
    result = app.converter.convert(str(pdf), "md")
    assert "Robot Motion" in Path(result["path"]).read_text()
    assert file_hash(pdf) == before
    assert result["warnings"][0]["type"] == "layout_loss"
    monkeypatch.setattr("paperhub.convert.service.shutil.which", lambda _: None)
    monkeypatch.setitem(sys.modules, "pypandoc", None)
    with pytest.raises(PaperHubError) as error:
        app.converter.convert(str(app.guard.roots[0] / "attention.md"), "docx")
    assert error.value.code == "E_CONVERTER_MISSING"


def test_conversion_plugin_and_collision(library):
    class Adapter:
        def can_convert(self, source, target):
            return source == "md" and target == "html"

        def convert(self, source, destination, options):
            destination.write_text("<h1>Converted</h1>")

    library.converter.register(Adapter())
    result = library.converter.convert(
        str(library.guard.roots[0] / "attention.md"), "html", output_name="same.html"
    )
    assert Path(result["path"]).read_text() == "<h1>Converted</h1>"
    with pytest.raises(PaperHubError) as error:
        library.converter.convert(
            str(library.guard.roots[0] / "attention.md"), "html", output_name="same.html"
        )
    assert error.value.code == "E_CONFLICT"


async def test_batch_conversion_failure_isolation_and_checkpoint(library, monkeypatch):
    monkeypatch.setattr("paperhub.convert.service.shutil.which", lambda _: None)
    monkeypatch.setitem(sys.modules, "pypandoc", None)
    ids = [p["id"] for p in library.library.papers()]
    task_id = library.tasks.submit("convert", {"paper_ids": ids, "target_format": "md"})["task_id"]
    state = await wait_task(library, task_id)
    assert state["status"] == "done"
    assert len(state["result"]["results"]) == 1 and len(state["result"]["failed"]) == 3


def test_engine_timeout_and_nonzero_exit():
    with pytest.raises(PaperHubError) as error:
        run_engine([sys.executable, "-c", "import time; time.sleep(10)"], 0.2)
    assert error.value.code == "E_CONVERT_TIMEOUT"
    with pytest.raises(PaperHubError) as error:
        run_engine([sys.executable, "-c", "raise SystemExit(2)"], 2)
    assert error.value.code == "E_CONVERT_FAILED"


@pytest.mark.parametrize(
    "name", ["outline-survey", "outline-empirical", "outline-thesis", "outline-from-draft"]
)
def test_builtin_plugin_lifecycle_export_and_edit(library, name):
    app = library
    token = confirmation(lambda: app.plugins.install(name, None))
    assert app.plugins.list_plugins(True) == []
    app.plugins.install(name, token)
    outline = app.plugins.generate(name, None, {"title": "Test Outline"})
    assert outline["title"] == "Test Outline"
    assert len(outline["sections"]) >= 3
    known = {p["id"] for p in app.library.papers()}
    assert all(set(section["citations"]) <= known for section in outline["sections"])
    output = app.plugins.export(outline["id"])
    assert "Test Outline" in Path(output["path"]).read_text(encoding="utf-8")
    changed = app.plugins.edit(outline["id"], "Changed", outline["sections"])
    assert changed["title"] == "Changed"
    app.plugins.enable(name, False)
    with pytest.raises(PaperHubError):
        app.plugins.generate(name, None, {})
    app.plugins.enable(name, True)
    app.plugins.uninstall(name)
    assert not app.plugins.list_plugins(True)


def test_manifest_and_incompatible_version():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PluginManifest(name="../escape", version="0.1.0", entry="test:Plugin")
    with pytest.raises(ValidationError):
        PluginManifest(name="valid", version="0.1.0", entry="test:Plugin", permissions=["root"])
    manifest = PluginManifest(
        name="valid", version="0.1.0", entry="test:Plugin", min_core_version="99.0.0"
    )
    with pytest.raises(PaperHubError):
        manifest.compatible()


def test_plugin_hash_rejected_before_install(library):
    wheel = library.guard.roots[0] / "bad.whl"
    wheel.write_bytes(b"invalid wheel")
    with pytest.raises(PaperHubError) as error:
        library.plugins.install("third-party", None, str(wheel), {}, "0" * 64)
    assert error.value.code == "E_PLUGIN_HASH"
