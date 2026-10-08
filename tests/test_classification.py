from pathlib import Path

import pytest
from conftest import confirmation

from paperhub.errors import PaperHubError


def test_preview_adjust_index_and_undo(library):
    app = library
    before = sorted(p.name for p in app.guard.roots[0].iterdir())
    plan = app.classifier.classify(None, 2)
    assert plan["status"] == "draft" and len(plan["topics"]) == 2
    assert before == sorted(p.name for p in app.guard.roots[0].iterdir())
    assert not app.guard.output.exists()
    topics = [{"name": "Merged topic", "paper_ids": list(plan["snapshots"])}]
    edited = app.classifier.adjust(plan["id"], topics)
    assert edited["topics"][0]["name"] == "Merged topic"
    applied = app.applier.apply(plan["id"], "index", None)
    assert len(app.library.papers(topic=applied["topics"][0]["id"])) == 4
    assert app.applier.undo(plan["id"])["status"] == "reverted"
    assert not app.guard.output.exists()


def test_move_confirmation_undo_preserves_hashes(library):
    app = library
    plan = app.classifier.classify(None, 1)
    token = confirmation(lambda: app.applier.apply(plan["id"], "move", None))
    assert all(Path(s["path"]).exists() for s in plan["snapshots"].values())
    app.applier.apply(plan["id"], "move", token)
    assert all(not Path(s["path"]).exists() for s in plan["snapshots"].values())
    assert len(app.library.papers()) == 4
    app.applier.undo(plan["id"])
    assert all(Path(s["path"]).exists() for s in plan["snapshots"].values())
    assert {p["id"]: p["file_hash"] for p in app.library.papers()} == {
        paper_id: snap["hash"] for paper_id, snap in plan["snapshots"].items()
    }


def test_move_conflict_does_not_overwrite(library):
    app = library
    plan = app.classifier.classify(None, 1)
    token = confirmation(lambda: app.applier.apply(plan["id"], "move", None))
    app.applier.apply(plan["id"], "move", token)
    first = list(plan["snapshots"].values())[-1]
    source = Path(first["path"])
    source.write_text("new user content", encoding="utf-8")
    with pytest.raises(PaperHubError) as error:
        app.applier.undo(plan["id"])
    assert error.value.code == "E_CONFLICT"
    assert source.read_text() == "new user content"


def test_symlink_apply_and_undo(library):
    app = library
    probe = app.guard.roots[0] / "probe.link"
    try:
        probe.symlink_to(app.guard.roots[0] / "attention.md")
        probe.unlink()
    except OSError:
        pytest.skip("Windows requires developer mode or symlink privileges")
    plan = app.classifier.classify(None, 1)
    app.applier.apply(plan["id"], "symlink", None)
    links = list(app.guard.output.rglob("*.md"))
    assert links and all(p.is_symlink() for p in links)
    app.applier.undo(plan["id"])
    assert not any(p.is_file() for p in app.guard.output.rglob("*"))
    assert len(app.library.papers()) == 4


def test_changed_source_blocks_apply(library):
    plan = library.classifier.classify(None, 1)
    path = Path(next(iter(plan["snapshots"].values()))["path"])
    path.write_bytes(b"changed")
    with pytest.raises(PaperHubError) as error:
        library.applier.apply(plan["id"], "index", None)
    assert error.value.code == "E_SOURCE_CHANGED"


def test_invalid_grouping_and_topic_count(library):
    with pytest.raises(PaperHubError):
        library.classifier.classify(None, 5)
    plan = library.classifier.classify(None, 1)
    paper_id = next(iter(plan["snapshots"]))
    with pytest.raises(PaperHubError):
        library.classifier.adjust(plan["id"], [{"name": "bad", "paper_ids": [paper_id, paper_id]}])


def test_auto_clusters_and_hybrid_search(library):
    plan = library.classifier.classify(None, None)
    assert sum(len(t["paper_ids"]) for t in plan["topics"]) == 4
    results = library.classifier.hybrid_search("transformer attention", None, None, 3)
    assert "Transformer" in results[0]["title"]
    assert results[0]["embedding_engine"] == "tfidf"
