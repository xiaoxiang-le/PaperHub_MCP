from itertools import permutations
from pathlib import Path

import pytest

from paperhub.security.path_guard import file_hash


@pytest.mark.parametrize("source,target", list(permutations(["md", "docx", "tex", "html"], 2)))
def test_real_pandoc_conversion_matrix(library, source, target):
    pytest.importorskip("pypandoc")
    paths = {
        "md": library.guard.roots[0] / "attention.md",
        "docx": library.guard.roots[0] / "protein.docx",
        "tex": library.guard.roots[0] / "graph.tex",
    }
    if source == "html":
        path = library.guard.roots[0] / "paper.html"
        path.write_text(
            "<html><body><h1>Research Paper</h1><p>Methods and results.</p></body></html>",
            encoding="utf-8",
        )
    else:
        path = paths[source]
    before = file_hash(path)
    result = library.converter.convert(str(path), target)
    assert Path(result["path"]).stat().st_size > 0
    assert file_hash(path) == before


@pytest.mark.parametrize("target", ["docx", "tex", "html"])
def test_real_pdf_to_pandoc_chain(library, target):
    pytest.importorskip("pypandoc")
    result = library.converter.convert(str(library.guard.roots[0] / "robot.pdf"), target)
    assert Path(result["path"]).stat().st_size > 0
    assert result["warnings"][0]["type"] == "layout_loss"
