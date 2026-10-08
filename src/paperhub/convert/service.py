import asyncio
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

from paperhub.config import ConvertConfig
from paperhub.core.db import Database
from paperhub.core.tasks import TaskContext
from paperhub.errors import PaperHubError, require
from paperhub.library.parsers import ParserRegistry
from paperhub.library.scanner import LibraryService
from paperhub.security.path_guard import PathGuard, file_hash, write_new

FORMATS = {"md": "markdown", "docx": "docx", "tex": "latex", "html": "html", "pdf": "pdf"}


class Converter(Protocol):
    def can_convert(self, src_fmt: str, dst_fmt: str) -> bool: ...
    def convert(self, src: Path, dst: Path, options: dict[str, Any]) -> None: ...


def run_engine(command: list[str], timeout: float, context: TaskContext | None = None) -> None:
    """No shell; stdout/stderr captured to disk to keep MCP stdio clean and bounded."""
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            command,
            stdout=output,
            stderr=output,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        start = time.monotonic()
        try:
            while process.poll() is None:
                if context:
                    context.check()
                require(time.monotonic() - start < timeout, "E_CONVERT_TIMEOUT", "转换引擎超时")
                time.sleep(0.1)
            require(
                process.returncode == 0,
                "E_CONVERT_FAILED",
                "转换引擎失败 / Conversion failed",
                engine=Path(command[0]).name,
                exit_code=process.returncode,
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


class ConvertService:
    def __init__(
        self,
        config: ConvertConfig,
        guard: PathGuard,
        parsers: ParserRegistry,
        library: LibraryService,
        db: Database,
    ):
        self.config, self.guard, self.parsers, self.library, self.db = (
            config,
            guard,
            parsers,
            library,
            db,
        )
        self.adapters: list[Converter] = []

    def register(self, converter: Converter) -> None:
        self.adapters.insert(0, converter)

    def engine(self, name: str) -> str:
        configured = self.config.pandoc_path if name == "pandoc" else "auto"
        found = shutil.which(name if configured == "auto" else configured)
        if not found and name == "pandoc" and configured == "auto":
            try:
                import pypandoc

                found = pypandoc.get_pandoc_path()
            except (ImportError, OSError):
                pass
        if not found:
            raise PaperHubError(
                "E_CONVERTER_MISSING",
                f"未检测到 {name} / Engine missing",
                f"请安装 {name} 并将其加入 PATH，然后运行 doctor",
            )
        return found

    def convert(
        self,
        path: str,
        target_format: str,
        template: str | None = None,
        csl: str | None = None,
        context: TaskContext | None = None,
        output_name: str | None = None,
    ) -> dict[str, Any]:
        src = self.guard.read(path)
        require(src.is_file(), "E_NOT_FOUND", "源文件不存在 / Source not found")
        target = target_format.lower().lstrip(".")
        source = src.suffix.lower().lstrip(".")
        require(
            source in FORMATS and target in FORMATS and source != target,
            "E_FORMAT_UNSUPPORTED",
            "转换格式或路线不支持 / Unsupported conversion",
        )
        template_path = self.guard.read(template) if template else None
        csl_path = self.guard.read(csl) if csl else None
        if template_path:
            require(
                template_path.is_file() and template_path.suffix == ".docx" and target == "docx",
                "E_ARGUMENT",
                "template 必须为 DOCX 参考模板",
            )
        if csl_path:
            require(csl_path.is_file() and csl_path.suffix == ".csl", "E_ARGUMENT", "CSL 文件无效")
        digest = file_hash(src)
        dst = self.guard.output_file(
            output_name or f"converted/{src.stem}-{uuid.uuid4().hex[:12]}.{target}"
        )
        warnings = []
        if context:
            context.check()
        with tempfile.TemporaryDirectory(prefix="paperhub-convert-") as temporary:
            scratch = Path(temporary)
            actual_src, actual_source = src, source
            produced = scratch / f"result.{target}"
            route = self.config.routes.get(f"{source}->{target}")
            if route is not None:
                expected = (
                    ["pdf_extract"]
                    if source == "pdf" and target == "md"
                    else (
                        ["pdf_extract", "pandoc"]
                        if source == "pdf"
                        else ["libreoffice"]
                        if source == "docx" and target == "pdf"
                        else ["pandoc"]
                    )
                )
                require(
                    route == expected,
                    "E_CONFIG",
                    "该格式对不支持指定的引擎链",
                    supported_route=expected,
                )
            custom = next((c for c in self.adapters if c.can_convert(source, target)), None)
            if custom:
                custom.convert(src, produced, {"template": template, "csl": csl})
            else:
                if source == "pdf":
                    text = self.parsers.parse(src).text
                    actual_src = scratch / "extracted.md"
                    actual_src.write_text(text, encoding="utf-8")
                    actual_source = "md"
                    warnings.append(
                        {
                            "type": "layout_loss",
                            "location": "document",
                            "message": "PDF 文本抽取不会保留原排版、图片或公式结构",
                        }
                    )
                    if target == "md":
                        produced.write_text(text, encoding="utf-8")
                if not produced.exists():
                    if target == "pdf" and source == "docx":
                        run_engine(
                            [
                                self.engine("soffice"),
                                f"-env:UserInstallation={(scratch / 'profile').as_uri()}",
                                "--headless",
                                "--convert-to",
                                "pdf",
                                "--outdir",
                                str(scratch),
                                str(src),
                            ],
                            self.config.timeout,
                            context,
                        )
                        original_output = scratch / f"{src.stem}.pdf"
                        require(
                            original_output.exists(), "E_CONVERT_FAILED", "LibreOffice 未生成 PDF"
                        )
                        original_output.rename(produced)
                    elif target == "pdf" and source == "tex":
                        self.engine("xelatex")
                        # Unrestricted TeX execution is deliberately avoided: Pandoc parses the
                        # input, then creates a fresh TeX document without raw input commands.
                        run_engine(
                            [
                                self.engine("pandoc"),
                                "--sandbox",
                                "-f",
                                "latex-raw_tex",
                                str(src),
                                "-o",
                                str(produced),
                                "--pdf-engine=xelatex",
                                "--pdf-engine-opt=-no-shell-escape",
                            ],
                            self.config.timeout,
                            context,
                        )
                    else:
                        command = [
                            self.engine("pandoc"),
                            "--sandbox",
                            "-f",
                            FORMATS[actual_source]
                            + (
                                "-raw_tex"
                                if target == "pdf" and actual_source in ("md", "tex")
                                else ""
                            ),
                            str(actual_src),
                            "-o",
                            str(produced),
                            "--standalone",
                        ]
                        if target != "pdf":
                            command += ["-t", FORMATS[target]]
                        else:
                            self.engine("xelatex")
                            command += ["--pdf-engine=xelatex", "--pdf-engine-opt=-no-shell-escape"]
                        if template_path:
                            command += ["--reference-doc", str(template_path)]
                        if csl_path:
                            command += ["--citeproc", "--csl", str(csl_path)]
                        run_engine(command, self.config.timeout, context)
            require(
                produced.is_file(), "E_CONVERT_FAILED", "转换引擎未生成结果 / No output produced"
            )
            require(file_hash(src) == digest, "E_SOURCE_CHANGED", "转换期间源文件发生变化")
            if context:
                context.check()
            self.guard.write(dst)
            write_new(dst, produced.read_bytes())
        warnings.append(
            {
                "type": "review_required",
                "location": "document",
                "message": "请核查公式、图片、表格和引用；转换不保证排版一致",
            }
        )
        return {
            "path": str(dst),
            "source_hash": digest,
            "output_hash": file_hash(dst),
            "warnings": warnings,
        }

    async def batch(self, context: TaskContext, payload: dict[str, Any]) -> dict[str, Any]:
        results, failed = [], []
        for index, paper_id in enumerate(payload["paper_ids"]):
            context.check()
            key = f"{context.id}:{paper_id}"
            cached = self.db.get("convert_checkpoint", key)
            if cached and Path(cached["path"]).exists():
                require(
                    file_hash(Path(cached["path"])) == cached["output_hash"],
                    "E_CONFLICT",
                    "已完成的转换结果被修改",
                )
                results.append(cached)
            else:
                try:
                    paper = self.library.get(paper_id)
                    result = await asyncio.to_thread(
                        self.convert,
                        paper["file_path"],
                        payload["target_format"],
                        context=context,
                        output_name=f"converted/{context.id}/{paper_id}.{payload['target_format']}",
                    )
                    self.db.put("convert_checkpoint", key, result)
                    results.append(result)
                except PaperHubError as exc:
                    if exc.code == "E_TASK_CANCELLED":
                        raise
                    failed.append({"paper_id": paper_id, **exc.as_dict()})
            context.progress(index + 1, len(payload["paper_ids"]))
        return {"results": results, "failed": failed}
