import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from paperhub.core.db import Database
from paperhub.core.models import ParsedDocument
from paperhub.core.tasks import TaskContext
from paperhub.errors import PaperHubError, require
from paperhub.library.parsers import ParserRegistry
from paperhub.security.path_guard import PathGuard, file_hash


class LibraryService:
    def __init__(
        self, db: Database, guard: PathGuard, parsers: ParserRegistry, file_types: list[str]
    ):
        self.db, self.guard, self.parsers, self.file_types = db, guard, parsers, file_types

    def get(self, paper_id: str, include_text: bool = False) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM paper WHERE id=?", (paper_id,)).fetchone()
        if not row:
            raise PaperHubError("E_NOT_FOUND", "论文不存在 / Paper not found")
        # Revalidate even cached data after paths are removed from configuration.
        self.guard.read(row["file_path"])
        result = dict(row)
        doc = json.loads(result.pop("document"))
        if not include_text:
            doc.pop("text", None)
        result.update(doc)
        result["content_trust"] = "untrusted_document_data"
        return result

    def update_metadata(self, paper_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        paper = self.get(paper_id, include_text=True)
        allowed = {"title", "authors", "year", "abstract", "keywords", "doi", "language"}
        require(bool(fields) and set(fields) <= allowed, "E_ARGUMENT", "仅允许修改论文元数据字段")
        try:
            document = ParsedDocument.model_validate({**paper, **fields, "meta_source": "manual"})
        except ValueError:
            raise PaperHubError("E_ARGUMENT", "元数据字段类型无效 / Invalid metadata") from None
        require(bool(document.title.strip()), "E_ARGUMENT", "论文标题不能为空")
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE paper SET title=?,abstract=?,document=?,updated_at=? WHERE id=?",
                (
                    document.title,
                    document.abstract,
                    document.model_dump_json(),
                    time.time(),
                    paper_id,
                ),
            )
            conn.execute("DELETE FROM paper_fts WHERE paper_id=?", (paper_id,))
            conn.execute(
                "INSERT INTO paper_fts VALUES(?,?,?,?)",
                (paper_id, document.title, document.abstract, " ".join(document.keywords)),
            )
        return self.get(paper_id)

    def papers(
        self, scope: list[str] | None = None, topic: str | None = None
    ) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            ids = [
                row[0] for row in conn.execute("SELECT id FROM paper WHERE status='ok' ORDER BY id")
            ]
        if topic:
            topics = [
                t
                for plan in self.db.list("plan")
                if plan["status"] == "applied"
                for t in plan["topics"]
                if t["id"] == topic
            ]
            require(bool(topics), "E_NOT_FOUND", "主题不存在 / Topic not found")
            ids = [i for i in ids if i in topics[0]["paper_ids"]]
        if scope is not None:
            ids = [i for i in ids if i in scope]
            missing = set(scope) - set(ids)
            require(
                not missing,
                "E_NOT_FOUND",
                "选定论文不可用 / Selected papers unavailable",
                paper_ids=sorted(missing),
            )
        result = []
        for paper_id in ids:
            try:
                result.append(self.get(paper_id))
            except PaperHubError as exc:
                if exc.code != "E_PATH_DENIED":
                    raise
        return result

    def scan(
        self,
        path: str,
        recursive: bool,
        file_types: list[str] | None,
        context: TaskContext | None = None,
    ) -> dict[str, Any]:
        root = self.guard.read(path)
        require(root.is_dir(), "E_NOT_FOUND", "扫描目录不存在 / Directory not found")
        extensions = set(file_types if file_types is not None else self.file_types)
        require(extensions <= self.parsers.parsers.keys(), "E_FORMAT_UNSUPPORTED", "扫描格式不支持")
        report: dict[str, Any] = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "missing": 0,
            "failed": [],
            "denied": [],
        }
        candidates = root.rglob("*") if recursive else root.iterdir()
        files = []
        for item in candidates:
            if context:
                context.check()
            if item.suffix.lower().lstrip(".") not in extensions:
                continue
            if item.is_dir():
                continue
            try:
                resolved = self.guard.read(item)
                # Exclude managed outputs, including when output_dir lies inside the library.
                if resolved.is_relative_to(self.guard.output):
                    continue
                if resolved.is_file() and resolved not in files:
                    files.append(resolved)
            except PaperHubError:
                report["denied"].append(str(item))
        seen = set()
        for index, item in enumerate(files):
            stat: os.stat_result | None
            if context:
                context.check()
            seen.add(str(item))
            with self.db.connect() as conn:
                old = conn.execute("SELECT * FROM paper WHERE file_path=?", (str(item),)).fetchone()
            try:
                stat = item.stat()
                digest = file_hash(item)
                if old and old["file_hash"] == digest and old["status"] == "ok":
                    report["skipped"] += 1
                    if context:
                        context.progress(index + 1, len(files))
                    continue
                parsed = self.parsers.parse(item)
                require(file_hash(item) == digest, "E_SOURCE_CHANGED", "解析期间源文件发生变化")
                status, reason, doc = "ok", None, parsed.model_dump()
            except (OSError, PaperHubError) as exc:
                status = "failed"
                reason = exc.message if isinstance(exc, PaperHubError) else type(exc).__name__
                doc = {"title": item.stem, "text": "", "abstract": ""}
                stat = item.stat() if item.exists() else None
                digest = ""
                report["failed"].append({"path": str(item), "reason": reason})
            now, paper_id = time.time(), old["id"] if old else str(uuid.uuid4())
            with self.db.connect() as conn:
                conn.execute(
                    """INSERT INTO paper VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(file_path) DO UPDATE SET file_hash=excluded.file_hash,
                    file_mtime=excluded.file_mtime,file_size=excluded.file_size,
                    status=excluded.status,fail_reason=excluded.fail_reason,title=excluded.title,
                    abstract=excluded.abstract,document=excluded.document,updated_at=excluded.updated_at""",
                    (
                        paper_id,
                        str(item),
                        digest,
                        item.suffix.lstrip("."),
                        stat.st_mtime_ns if stat else 0,
                        stat.st_size if stat else 0,
                        status,
                        reason,
                        doc["title"],
                        doc["abstract"],
                        json.dumps(doc, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                conn.execute("DELETE FROM paper_fts WHERE paper_id=?", (paper_id,))
                if status == "ok":
                    conn.execute(
                        "INSERT INTO paper_fts VALUES(?,?,?,?)",
                        (
                            paper_id,
                            doc["title"],
                            doc["abstract"],
                            " ".join(doc.get("keywords", [])),
                        ),
                    )
                    report["updated" if old else "added"] += 1
                conn.execute("DELETE FROM object WHERE kind='embedding' AND id=?", (paper_id,))
            if context:
                context.progress(index + 1, len(files))
        with self.db.connect() as conn:
            for row in conn.execute("SELECT id,file_path,file_type,status FROM paper").fetchall():
                indexed_path = Path(row["file_path"])
                in_scope = (
                    indexed_path.is_relative_to(root) if recursive else indexed_path.parent == root
                )
                if (
                    in_scope
                    and row["file_type"] in extensions
                    and row["file_path"] not in seen
                    and not indexed_path.exists()
                    and row["status"] != "missing"
                ):
                    conn.execute(
                        "UPDATE paper SET status='missing',updated_at=? WHERE id=?",
                        (time.time(), row["id"]),
                    )
                    conn.execute("DELETE FROM paper_fts WHERE paper_id=?", (row["id"],))
                    report["missing"] += 1
        return report

    def search(
        self,
        query: str,
        topic: str | None = None,
        year_range: list[int] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        require(1 <= limit <= 200, "E_ARGUMENT", "limit 必须在 1 到 200 之间")
        require(year_range is None or len(year_range) == 2, "E_ARGUMENT", "year_range 需要两个年份")
        papers = self.papers(topic=topic)
        if year_range:
            papers = [
                p for p in papers if p.get("year") and year_range[0] <= p["year"] <= year_range[1]
            ]
        if not query.strip():
            return papers[:limit]
        # Quote each token: a user's query must never become executable FTS syntax.
        expression = " OR ".join('"' + token.replace('"', '""') + '"' for token in query.split())
        with self.db.connect() as conn:
            scores = {
                r["paper_id"]: -r["score"]
                for r in conn.execute(
                    "SELECT paper_id,bm25(paper_fts) AS score FROM paper_fts WHERE paper_fts MATCH ?",
                    (expression,),
                )
            }
        for paper in papers:
            haystack = (
                paper["title"] + " " + paper["abstract"] + " " + " ".join(paper.get("keywords", []))
            ).casefold()
            paper["score"] = scores.get(paper["id"], 0) + sum(
                token.casefold() in haystack for token in query.split()
            )
        return sorted([p for p in papers if p["score"] > 0], key=lambda p: -p["score"])[:limit]
