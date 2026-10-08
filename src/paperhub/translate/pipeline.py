import asyncio
import hashlib
import time
import uuid
from typing import Any

from paperhub.config import TranslateConfig
from paperhub.core.db import Database
from paperhub.core.models import TranslateRequest
from paperhub.core.tasks import TaskContext, TaskService
from paperhub.errors import PaperHubError, require
from paperhub.library.scanner import LibraryService
from paperhub.security.confirm import Confirmations
from paperhub.security.path_guard import PathGuard, file_hash, write_new
from paperhub.translate.backends import APIBackend
from paperhub.translate.base import TranslateBackend
from paperhub.translate.protector import Protector
from paperhub.translate.segmenter import segment


class TranslateService:
    def __init__(
        self,
        config: TranslateConfig,
        library: LibraryService,
        db: Database,
        guard: PathGuard,
        confirmations: Confirmations,
        tasks: TaskService,
    ):
        self.config, self.library, self.db = config, library, db
        self.guard, self.confirmations, self.tasks = guard, confirmations, tasks
        self.backends: dict[str, TranslateBackend] = {
            name: APIBackend(name, settings, config) for name, settings in config.backends.items()
        }

    def register(self, backend: TranslateBackend) -> None:
        self.backends[backend.name] = backend

    def _prepare(
        self, paper_id: str, backend: str, target_lang: str, mode: str, glossary: dict[str, str]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        require(
            backend in self.backends, "E_BACKEND_UNKNOWN", "未注册翻译后端 / Backend not registered"
        )
        require(mode in ("full", "bilingual", "abstract"), "E_ARGUMENT", "翻译模式无效")
        paper = self.library.get(paper_id, include_text=True)
        source = self.guard.read(paper["file_path"])
        require(paper["status"] == "ok" and source.is_file(), "E_NOT_FOUND", "论文不可用")
        require(
            file_hash(source) == paper["file_hash"], "E_SOURCE_CHANGED", "论文已修改，请先重新扫描"
        )
        text = paper["title"] + "\n\n" + paper["abstract"] if mode == "abstract" else paper["text"]
        require(bool(text.strip()), "E_PARSE_FAILED", "论文没有可翻译文本")
        settings = self.config.backends.get(backend)
        payload = {
            "paper_id": paper_id,
            "backend": backend,
            "target_lang": target_lang,
            "mode": mode,
            "glossary": glossary,
            "source_hash": paper["file_hash"],
            "model": settings.model if settings else backend,
            "endpoint": settings.base_url if settings else None,
            "chunk_chars": self.config.chunk_chars,
            "prices": settings.model_dump() if settings else {},
        }
        # Conservative character estimate covers Chinese tokens and prompt overhead.
        tokens = len(text) + 200 * max(1, len(text) // self.config.chunk_chars)
        estimate = self.backends[backend].estimate_cost(tokens).model_dump()
        preview = {
            "external_service": backend,
            "endpoint": payload["endpoint"],
            "model": payload["model"],
            "paper_id": paper_id,
            "characters": len(text),
            "estimate": estimate,
            "mode": mode,
            "notice": "论文内容将发送至所选外部服务；费用为配置单价估算，重试可能增加费用",
        }
        paper["translation_source"] = text
        return paper, {"payload": payload, "preview": preview}

    def start(
        self,
        paper_id: str,
        target_lang: str,
        backend: str,
        mode: str,
        glossary: dict[str, str],
        token: str | None,
    ) -> dict[str, Any]:
        paper, prepared = self._prepare(paper_id, backend, target_lang, mode, glossary)
        self.confirmations.verify(
            "translate",
            prepared["payload"],
            token,
            "内容将发送至外部翻译服务，请确认 / Confirm external transmission",
            **prepared["preview"],
        )
        protector = Protector(paper["translation_source"])
        state_id = str(uuid.uuid4())
        state = {
            **prepared["payload"],
            "source_path": paper["file_path"],
            "source_text": paper["translation_source"],
            "protected": protector.text,
            "values": protector.values,
            "chunks": segment(protector.text, self.config.chunk_chars),
        }
        self.db.put("translation", state_id, state)
        self.db.put(
            "consent",
            state_id,
            {
                "backend": backend,
                "model": prepared["payload"]["model"],
                "confirmed_at": time.time(),
            },
        )
        return self.tasks.submit("translate", {"state_id": state_id})

    async def abstract(
        self,
        paper_id: str,
        target_lang: str,
        backend: str,
        glossary: dict[str, str],
        token: str | None,
    ) -> dict[str, Any]:
        paper, prepared = self._prepare(paper_id, backend, target_lang, "abstract", glossary)
        self.confirmations.verify(
            "translate_abstract",
            prepared["payload"],
            token,
            "摘要将发送至外部服务，请确认 / Confirm external transmission",
            **prepared["preview"],
        )
        protector = Protector(paper["translation_source"])
        translated = await self._translate(protector.text, backend, target_lang, glossary, None)
        self.db.put("consent", str(uuid.uuid4()), {"backend": backend, "confirmed_at": time.time()})
        return {
            "source": paper["translation_source"],
            "translation": protector.restore(translated),
            "target_lang": target_lang,
            "backend": backend,
            "content_trust": "untrusted_document_data",
        }

    async def _translate(
        self,
        text: str,
        backend: str,
        target_lang: str,
        glossary: dict[str, str],
        context: TaskContext | None,
    ) -> str:
        last: PaperHubError | None = None
        for attempt in range(self.config.max_retries + 1):
            if context:
                context.check()
            request = asyncio.create_task(
                self.backends[backend].translate(
                    TranslateRequest(text=text, target_lang=target_lang, glossary=glossary)
                )
            )
            started = time.monotonic()
            try:
                while not request.done():
                    await asyncio.wait({request}, timeout=0.2)
                    if context:
                        context.check()
                    require(
                        time.monotonic() - started <= self.config.timeout,
                        "E_BACKEND_TIMEOUT",
                        "翻译请求超时 / Translation timed out",
                    )
                result = await request
                require(bool(result.text.strip()), "E_BACKEND_EMPTY", "后端返回空译文")
                Protector.validate(text, result.text)
                return result.text
            except PaperHubError as exc:
                if exc.code in ("E_TASK_CANCELLED", "E_BACKEND_AUTH", "E_CONFIG"):
                    raise
                last = exc
            except Exception:
                last = PaperHubError("E_BACKEND_FAILED", "后端调用失败 / Backend failed")
            finally:
                if not request.done():
                    request.cancel()
                await asyncio.gather(request, return_exceptions=True)
            if attempt < self.config.max_retries:
                # Poll cancellation throughout backoff rather than blocking the entire delay.
                for _ in range(5 * 2**attempt):
                    await asyncio.sleep(0.2)
                    if context:
                        context.check()
        assert last is not None
        raise last

    async def run(self, context: TaskContext, payload: dict[str, Any]) -> dict[str, Any]:
        state = self.db.get("translation", payload["state_id"])
        require(state is not None, "E_NOT_FOUND", "翻译断点不存在")
        assert state is not None
        path = self.guard.read(state["source_path"])
        require(file_hash(path) == state["source_hash"], "E_SOURCE_CHANGED", "源论文变化，无法续译")
        backend = state["backend"]
        require(backend in self.backends, "E_BACKEND_UNKNOWN", "后端未注册")
        settings = self.config.backends.get(backend)
        require(
            settings is None
            or (settings.model == state["model"] and settings.base_url == state["endpoint"]),
            "E_CONFIG_CHANGED",
            "模型或服务地址变化，需要重新确认并创建翻译任务",
        )
        chunks = state["chunks"]
        translated: list[str | None] = [None] * len(chunks)
        failures: list[dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.config.concurrency)
        completed = 0

        async def translate_one(index: int, source: str) -> None:
            nonlocal completed
            async with semaphore:
                context.check()
                digest = hashlib.sha256(source.encode()).hexdigest()
                with self.db.connect() as conn:
                    row = conn.execute(
                        "SELECT * FROM translate_chunk WHERE task_id=? AND idx=?",
                        (context.id, index),
                    ).fetchone()
                if row and row["source_hash"] == digest:
                    translated[index] = row["target_text"]
                else:
                    try:
                        output = await self._translate(
                            source, backend, state["target_lang"], state["glossary"], context
                        )
                        with self.db.connect() as conn:
                            conn.execute(
                                "INSERT OR REPLACE INTO translate_chunk VALUES(?,?,?,?)",
                                (context.id, index, digest, output),
                            )
                        translated[index] = output
                    except PaperHubError as exc:
                        if exc.code == "E_TASK_CANCELLED":
                            raise
                        failures.append({"chunk": index, "code": exc.code, "message": exc.message})
                completed += 1
                context.progress(completed, len(chunks))

        workers = [asyncio.create_task(translate_one(i, text)) for i, text in enumerate(chunks)]
        try:
            await asyncio.gather(*workers)
        finally:
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        require(
            not failures,
            "E_TRANSLATE_FAILED",
            "部分分块翻译失败，可使用 resume_task 续译",
            failed_chunks=failures,
        )
        require(file_hash(path) == state["source_hash"], "E_SOURCE_CHANGED", "翻译期间源论文变化")
        protector = Protector("")
        protector.text, protector.values = state["protected"], state["values"]
        protected_result = "".join(t or "" for t in translated)
        final = protector.restore(protected_result)
        if state["mode"] == "bilingual":
            # Exact chunk pairing is retained; no post-translation paragraph guessing.
            pairs = []
            for source, target in zip(chunks, translated, strict=True):
                for token, original in state["values"].items():
                    source = source.replace(token, original)
                    target = (target or "").replace(token, original)
                pairs.append(
                    f"### Original / 原文\n\n{source}\n\n### Translation / 译文\n\n{target}"
                )
            final = "\n\n---\n\n".join(pairs)
        glossary_warnings = [
            term
            for term, target in state["glossary"].items()
            if term in state["source_text"] and target not in final
        ]
        destination = self.guard.output_file(f"translations/{context.id}-{uuid.uuid4().hex[:8]}.md")
        context.check()
        write_new(destination, final)
        return {
            "path": str(destination),
            "chunks": len(chunks),
            "failed_chunks": [],
            "glossary_warnings": glossary_warnings,
            "backend": backend,
        }


def parse_glossary(content: str) -> dict[str, str]:
    """CSV has source,target columns; JSON dictionaries are accepted by MCP directly."""
    import csv
    import io

    reader = csv.DictReader(io.StringIO(content))
    require(
        reader.fieldnames is not None and {"source", "target"} <= set(reader.fieldnames),
        "E_ARGUMENT",
        "术语 CSV 必须包含 source,target 列",
    )
    glossary: dict[str, str] = {}
    for row in reader:
        source, target = row.get("source"), row.get("target")
        require(bool(source) and bool(target), "E_ARGUMENT", "术语表不允许缺少词条或译文")
        assert source is not None and target is not None
        require(
            source not in glossary or glossary[source] == target,
            "E_ARGUMENT",
            "相同术语存在不同译文",
        )
        glossary[source] = target
    return glossary
