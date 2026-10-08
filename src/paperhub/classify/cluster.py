import threading
import time
import uuid
from typing import Any

import numpy as np
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from paperhub.classify.embedder import LocalEmbedder
from paperhub.core.db import Database
from paperhub.errors import require
from paperhub.library.scanner import LibraryService


class ClassifyService:
    def __init__(self, db: Database, library: LibraryService, embedder: LocalEmbedder):
        self.db, self.library, self.embedder = db, library, embedder
        self.lock = threading.RLock()

    def get(self, plan_id: str) -> dict[str, Any]:
        plan = self.db.get("plan", plan_id)
        require(plan is not None, "E_NOT_FOUND", "分类方案不存在 / Plan not found")
        assert plan is not None
        return plan

    def classify(self, scope: list[str] | None, num_topics: int | None) -> dict[str, Any]:
        papers = self.library.papers(scope)
        require(bool(papers), "E_NOT_FOUND", "论文库为空 / No papers")
        if num_topics is not None:
            require(
                1 <= num_topics <= len(papers), "E_ARGUMENT", "主题数超出范围 / Invalid topic count"
            )
        texts = [p["title"] + " " + (p["abstract"] or p["title"]) for p in papers]
        vectors = self.embedder.encode(texts)
        if num_topics is not None:
            labels = KMeans(n_clusters=num_topics, random_state=42, n_init=10).fit_predict(vectors)
        elif len(papers) < 4:
            labels = np.zeros(len(papers), dtype=int)
        else:
            labels = HDBSCAN(
                min_cluster_size=max(2, min(5, len(papers) // 4)),
                min_samples=1,
                metric="euclidean",
                copy=True,
            ).fit_predict(vectors)
        try:
            keyword_model = TfidfVectorizer(
                token_pattern=r"(?u)\b\w{2,}\b", max_features=5000, stop_words="english"
            )
            keywords_matrix = keyword_model.fit_transform(texts).toarray()
            vocabulary = keyword_model.get_feature_names_out()
        except ValueError:
            keywords_matrix, vocabulary = np.zeros((len(papers), 1)), np.array(["文献"])
        topics = []
        for label in sorted(set(labels)):
            indices = np.where(labels == label)[0]
            weights = keywords_matrix[indices].mean(axis=0)
            keywords = [str(vocabulary[i]) for i in np.argsort(-weights)[:5] if weights[i] > 0]
            center = vectors[indices].mean(axis=0, keepdims=True)
            representative = int(indices[np.argmax(cosine_similarity(vectors[indices], center))])
            topics.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "未分类" if label == -1 else " / ".join(keywords[:3]) or "文献主题",
                    "keywords": keywords,
                    "paper_ids": [papers[int(i)]["id"] for i in indices],
                    "representative_paper": papers[representative]["id"],
                }
            )
        plan: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "status": "draft",
            "created_at": time.time(),
            "topics": topics,
            "embedding_engine": self.embedder.config.engine,
            "snapshots": {
                p["id"]: {"path": p["file_path"], "hash": p["file_hash"]} for p in papers
            },
        }
        self.db.put("plan", plan["id"], plan)
        return plan

    def adjust(self, plan_id: str, topics: list[dict[str, Any]]) -> dict[str, Any]:
        """Replace draft groups: supports rename, merge, split and reassignment atomically."""
        with self.lock:
            plan = self.get(plan_id)
            require(plan["status"] == "draft", "E_PLAN_STATE", "仅能调整预览状态的方案")
            expected = set(plan["snapshots"])
            seen: list[str] = []
            normalized = []
            for topic in topics:
                require(
                    isinstance(topic.get("name"), str) and bool(topic["name"].strip()),
                    "E_ARGUMENT",
                    "主题必须有名称",
                )
                require(
                    isinstance(topic.get("paper_ids"), list) and bool(topic["paper_ids"]),
                    "E_ARGUMENT",
                    "主题必须包含论文",
                )
                seen.extend(topic["paper_ids"])
                normalized.append(
                    {
                        "id": str(uuid.uuid4()),
                        "name": topic["name"][:200],
                        "paper_ids": topic["paper_ids"],
                        "keywords": [],
                        "representative_paper": topic["paper_ids"][0],
                    }
                )
            require(
                set(seen) == expected and len(seen) == len(expected),
                "E_ARGUMENT",
                "方案必须包含每篇原论文恰好一次 / Each paper must occur once",
            )
            plan["topics"] = normalized
            self.db.put("plan", plan_id, plan)
            return plan

    def hybrid_search(
        self, query: str, topic: str | None, year_range: list[int] | None, limit: int
    ) -> list[dict[str, Any]]:
        require(bool(query.strip()), "E_ARGUMENT", "语义检索需要非空 query")
        require(1 <= limit <= 200, "E_ARGUMENT", "limit 必须在 1 到 200 之间")
        require(year_range is None or len(year_range) == 2, "E_ARGUMENT", "year_range 需要两个年份")
        papers = self.library.papers(topic=topic)
        if year_range:
            papers = [
                p for p in papers if p.get("year") and year_range[0] <= p["year"] <= year_range[1]
            ]
        if not papers:
            return []
        vectors = self.embedder.encode([query] + [p["title"] + " " + p["abstract"] for p in papers])
        similarities = cosine_similarity(vectors[:1], vectors[1:])[0]
        lexical_ids = {p["id"] for p in self.library.search(query, topic, year_range, 200)}
        for paper, similarity in zip(papers, similarities, strict=True):
            paper["score"] = 0.75 * float(similarity) + 0.25 * (paper["id"] in lexical_ids)
            paper["embedding_engine"] = self.embedder.config.engine
        return sorted(papers, key=lambda p: -p["score"])[:limit]
