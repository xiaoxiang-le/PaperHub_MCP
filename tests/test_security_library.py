import json
import logging
import os
import time

import pytest
from pypdf import PdfWriter

from paperhub.config import load_config
from paperhub.errors import PaperHubError
from paperhub.library.dedupe import find_duplicates
from paperhub.library.export import export_references
from paperhub.logging import SafeJSONFormatter
from paperhub.security.path_guard import write_new


def test_scan_formats_incremental_missing_and_corrupt(library):
    app = library
    papers = app.library.papers()
    assert {p["file_type"] for p in papers} == {"pdf", "docx", "md", "tex"}
    attention = next(p for p in papers if p["file_type"] == "md")
    assert attention["title"] == "Efficient Transformer Attention"
    assert attention["authors"] == ["Ada", "Bob"]
    assert attention["doi"] == "10.1234/attention"
    assert "Fast attention" in attention["abstract"]
    assert "text" not in attention
    report = app.library.scan(str(app.guard.roots[0]), True, None)
    assert report["skipped"] == 4
    root = app.guard.roots[0]
    (root / "attention.md").write_text(
        "# Changed Title\nAbstract\nChanged abstract", encoding="utf-8"
    )
    (root / "graph.tex").unlink()
    (root / "bad.pdf").write_bytes(b"not a pdf")
    report = app.library.scan(str(root), True, None)
    assert report["updated"] == 1 and report["missing"] == 1 and len(report["failed"]) == 1
    assert len(app.library.papers()) == 3
    assert app.library.get(attention["id"])["title"] == "Changed Title"


def test_search_filters_duplicates_and_exports(library):
    app = library
    result = app.library.search("attention", year_range=[2024, 2024])
    assert len(result) == 1
    assert app.library.search("attention", year_range=[2020, 2023]) == []
    assert app.library.search('" NEVERTOKEN*') == []
    root = app.guard.roots[0]
    (root / "duplicate.md").write_bytes((root / "attention.md").read_bytes())
    app.library.scan(str(root), True, None)
    duplicates = find_duplicates(app.library.papers())
    assert any("sha256" in pair["reasons"] for pair in duplicates)
    assert "@article{" in export_references(result, "bibtex")
    assert json.loads(export_references(result, "csl-json"))[0]["issued"]["date-parts"] == [[2024]]


def test_path_guard_traversal_and_outputs(app, tmp_path):
    with pytest.raises(PaperHubError, match="路径"):
        app.guard.read(tmp_path / "secret.txt")
    with pytest.raises(PaperHubError):
        app.guard.write(app.guard.output / ".." / "escape.txt")
    path = app.guard.output_file("safe.txt")
    write_new(path, "hello")
    with pytest.raises(PaperHubError) as error:
        write_new(path, "overwrite")
    assert error.value.code == "E_CONFLICT"
    assert path.read_text() == "hello"


def test_symlink_escape(app, tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("secret")
    link = app.guard.roots[0] / "link.md"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(PaperHubError):
        app.guard.read(link)
    report = app.library.scan(str(app.guard.roots[0]), True, None)
    assert len(report["denied"]) == 1


def test_confirmation_bound_single_use_and_expiry(app):
    from conftest import confirmation

    token = confirmation(lambda: app.confirmations.verify("x", {"a": 1}, None, "preview"))
    with pytest.raises(PaperHubError):
        app.confirmations.verify("x", {"a": 2}, token, "preview")
    app.confirmations.verify("x", {"a": 1}, token, "preview")
    with pytest.raises(PaperHubError):
        app.confirmations.verify("x", {"a": 1}, token, "preview")
    token = confirmation(lambda: app.confirmations.verify("x", {}, None, "preview"))
    with app.db.connect() as conn:
        conn.execute("UPDATE confirmation SET expires=?", (time.time() - 1,))
    with pytest.raises(PaperHubError):
        app.confirmations.verify("x", {}, token, "preview")


def test_empty_pdf_and_encrypted_pdf(app):
    root = app.guard.roots[0]
    for name, encrypted in (("blank.pdf", False), ("encrypted.pdf", True)):
        writer = PdfWriter()
        writer.add_blank_page(100, 100)
        if encrypted:
            writer.encrypt("secret")
        with (root / name).open("wb") as stream:
            writer.write(stream)
    report = app.library.scan(str(root), True, None)
    assert len(report["failed"]) == 2
    assert any("OCR" in error["reason"] for error in report["failed"])


def test_nonrecursive_scan_does_not_mark_nested_missing(app):
    nested = app.guard.roots[0] / "nested"
    nested.mkdir()
    file = nested / "paper.md"
    file.write_text("# Nested paper")
    app.library.scan(str(app.guard.roots[0]), True, None)
    file.unlink()
    assert app.library.scan(str(app.guard.roots[0]), False, None)["missing"] == 0
    assert app.library.scan(str(nested), True, None)["missing"] == 1


def test_config_overrides_and_invalid(app, tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text('[library]\npaths = ["~/Papers"]\n', encoding="utf-8")
    monkeypatch.setenv("PAPERHUB_LIBRARY_PATHS", os.pathsep.join(map(str, app.guard.roots)))
    monkeypatch.setenv("PAPERHUB_DATA_DIR", str(tmp_path / "db"))
    monkeypatch.setenv("PAPERHUB_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("PAPERHUB_OPENAI_MODEL", "test-model")
    config = load_config(path)
    assert config.library.paths == app.guard.roots
    assert config.translate.backends["openai"].model == "test-model"
    path.write_text("broken = [")
    with pytest.raises(PaperHubError) as error:
        load_config(path)
    assert error.value.code == "E_CONFIG"


def test_no_secrets_in_logs(app):
    record = logging.LogRecord(
        "paperhub", logging.ERROR, "", 0, "secret-key and document body", (), None
    )
    assert "secret-key" not in SafeJSONFormatter().format(record)
    assert "document body" not in SafeJSONFormatter().format(record)
    assert not app.doctor()["api_keys"]["OPENAI_API_KEY"]


def test_cached_paper_denied_when_authorization_removed(library):
    paper = library.library.papers()[0]
    library.guard.roots = []
    assert library.library.papers() == []
    with pytest.raises(PaperHubError):
        library.library.get(paper["id"])
