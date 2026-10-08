from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.feature_extraction.text import TfidfVectorizer

from paperhub.config import EmbeddingConfig
from paperhub.core.db import Database
from paperhub.errors import PaperHubError
from paperhub.security.confirm import fingerprint


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> NDArray[Any]: ...


class LocalEmbedder:
    """TF-IDF baseline or lazy sentence-transformers loaded strictly from local files."""

    def __init__(self, config: EmbeddingConfig, db: Database):
        self.config, self.db = config, db
        self.model: Any = None

    def encode(self, texts: list[str]) -> NDArray[Any]:
        if self.config.engine == "tfidf":
            # Character ngrams also support Chinese text without a tokenizer download.
            return (
                TfidfVectorizer(
                    analyzer="char", ngram_range=(2, 4), max_features=8000, sublinear_tf=True
                )
                .fit_transform(texts)
                .toarray()
            )
        if self.config.engine != "sentence-transformers" or not self.config.model:
            raise PaperHubError("E_CONFIG", "请配置 embedding.engine 和本地模型路径")
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.config.model, local_files_only=True)
            except (ImportError, OSError):
                raise PaperHubError(
                    "E_EMBEDDING_MISSING",
                    "本地语义模型不可用 / Model missing",
                    "安装 paperhub-mcp[semantic] 并配置本地模型目录",
                ) from None
        vectors = []
        for text in texts:
            key = fingerprint({"model": self.config.model, "text": text})
            cached = self.db.get("embedding", key)
            if not cached:
                vector = self.model.encode([text], normalize_embeddings=True)[0].tolist()
                cached = {"vector": vector}
                self.db.put("embedding", key, cached)
            vectors.append(cached["vector"])
        return np.asarray(vectors)
