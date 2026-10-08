import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from paperhub.config import BackendConfig
from paperhub.server import create_server


def test_metadata_correction_updates_fts_and_persists(library):
    app = library
    paper = app.library.papers()[0]
    updated = app.library.update_metadata(
        paper["id"], {"title": "Corrected Metadata Title", "year": 2026}
    )
    assert updated["meta_source"] == "manual"
    assert app.library.search("Corrected Metadata")[0]["id"] == paper["id"]
    app.library.scan(str(app.guard.roots[0]), True, None)
    assert app.library.get(paper["id"])["title"] == "Corrected Metadata Title"


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example/v1",
        "https://user:secret@example.org/v1",
        "https://example.org/v1?api_key=secret",
    ],
)
def test_provider_url_rejects_cleartext_and_credentials(url):
    with pytest.raises(ValidationError):
        BackendConfig(base_url=url)


def test_semantic_model_loading_is_offline_and_vectors_cached(library, monkeypatch):
    calls = []

    class OfflineModel:
        def __init__(self, model, **options):
            assert options["local_files_only"] is True
            calls.append(("loaded", model))

        def encode(self, texts, **options):
            calls.append(("encoded", texts))
            return np.asarray([[1.0, 0.5, 0.25] for text in texts])

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=OfflineModel)
    )
    embedder = library.classifier.embedder
    embedder.config.engine = "sentence-transformers"
    embedder.config.model = "local-model-test"
    first = embedder.encode(["paper one", "paper two"])
    second = embedder.encode(["paper one", "paper two"])
    assert np.allclose(first, second)
    assert len(calls) == 3


async def test_config_reload(app, tmp_path):
    config = tmp_path / "config.toml"

    def path(p):
        return json.dumps(str(p).replace("\\", "/"))

    config.write_text(
        f"data_dir = {path(app.config.data_dir)}\n"
        f"[library]\npaths = [{path(app.guard.roots[0])}]\n"
        f"[convert]\noutput_dir = {path(app.guard.output)}\n"
        '[translate]\ndefault_backend = "anthropic"\ndefault_target_lang = "en"\n',
        encoding="utf-8",
    )
    server = create_server(app, config)
    result = await server.call_tool("reload_config", {})
    assert result[1]["ok"] is True
    assert result[1]["data"]["reloaded"] is True
