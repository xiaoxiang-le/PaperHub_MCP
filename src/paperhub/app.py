import asyncio
import importlib.metadata
import os
import shutil
from typing import Any

from paperhub.classify.applier import ClassificationApplier
from paperhub.classify.cluster import ClassifyService
from paperhub.classify.embedder import LocalEmbedder
from paperhub.config import Config
from paperhub.convert.service import ConvertService
from paperhub.core.db import Database
from paperhub.core.tasks import TaskContext, TaskService
from paperhub.errors import PaperHubError
from paperhub.library.parsers import ParserRegistry
from paperhub.library.scanner import LibraryService
from paperhub.plugins.host import PluginService
from paperhub.security.confirm import Confirmations
from paperhub.security.path_guard import PathGuard
from paperhub.translate.pipeline import TranslateService


class Application:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.data_dir / "paperhub.sqlite3")
        self.guard = PathGuard(config.library.paths, config.convert.output_dir)
        self.confirmations = Confirmations(self.db, config.security.confirmation_ttl)
        self.parsers = ParserRegistry()
        self.library = LibraryService(self.db, self.guard, self.parsers, config.library.file_types)
        self.tasks = TaskService(self.db)
        self.classifier = ClassifyService(
            self.db, self.library, LocalEmbedder(config.embedding, self.db)
        )
        self.applier = ClassificationApplier(self.classifier, self.guard, self.confirmations)
        self.converter = ConvertService(
            config.convert, self.guard, self.parsers, self.library, self.db
        )
        self.translator = TranslateService(
            config.translate, self.library, self.db, self.guard, self.confirmations, self.tasks
        )
        self.plugins = PluginService(
            self.db,
            self.library,
            self.guard,
            self.confirmations,
            config.data_dir / "plugins",
            config.plugins.timeout,
        )
        self.tasks.runners.update(
            scan=self._scan,
            convert=self.converter.batch,
            convert_single=self._convert_single,
            translate=self.translator.run,
        )

    async def _scan(self, context: TaskContext, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.library.scan, payload["path"], payload["recursive"], payload["file_types"], context
        )

    async def _convert_single(
        self, context: TaskContext, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.converter.convert,
            payload["path"],
            payload["target_format"],
            payload.get("template"),
            payload.get("csl"),
            context,
        )

    def doctor(self) -> dict[str, Any]:
        versions: dict[str, str | None] = {}
        for package in ("mcp", "pypdf", "python-docx", "sentence-transformers"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = None
        engines = {
            name: shutil.which(name)
            for name in ("pandoc", "xelatex", "latexmk", "soffice", "ocrmypdf", "tesseract")
        }
        try:
            engines["pandoc"] = self.converter.engine("pandoc")
        except PaperHubError:
            pass
        return {
            "engines": engines,
            "packages": versions,
            "api_keys": {
                name: bool(os.environ.get(name)) for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
            },
            "library_paths": [
                {"path": str(p), "exists": p.expanduser().is_dir()}
                for p in self.config.library.paths
            ],
            "embedding_engine": self.config.embedding.engine,
            "data_dir": str(self.config.data_dir),
            "output_dir": str(self.guard.output),
        }
