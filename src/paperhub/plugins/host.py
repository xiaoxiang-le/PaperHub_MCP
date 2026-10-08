import configparser
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from paperhub.core.db import Database
from paperhub.errors import PaperHubError, require
from paperhub.library.scanner import LibraryService
from paperhub.plugins.api import Outline, PluginContext
from paperhub.plugins.builtin import BUILTINS, builtin_outline
from paperhub.plugins.manifest import PluginManifest
from paperhub.security.confirm import Confirmations
from paperhub.security.path_guard import PathGuard, file_hash, write_new

# Third-party Python runs in a separate process for timeout/crash isolation. It is
# trusted executable code, NOT an OS sandbox. No API keys are inherited.
WORKER = r"""
import contextlib, importlib.metadata, json, os, sys
from types import SimpleNamespace
request_path, response_path = sys.argv[1:3]
with open(request_path, encoding="utf-8") as stream:
    request = json.load(stream)
try:
    entry = next(e for e in importlib.metadata.entry_points(group="paperhub.outlines")
                 if e.name == request["manifest"]["name"] and e.value == request["manifest"]["entry"])
    with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
        plugin = entry.load()()
        result = plugin.generate(SimpleNamespace(**request["context"]), request["options"])
        if hasattr(result, "model_dump"):
            result = result.model_dump()
    answer = {"ok": True, "outline": result}
except BaseException as exc:
    answer = {"ok": False, "error_type": type(exc).__name__}
with open(response_path, "w", encoding="utf-8") as stream:
    json.dump(answer, stream, ensure_ascii=False)
"""


class PluginService:
    def __init__(
        self,
        db: Database,
        library: LibraryService,
        guard: PathGuard,
        confirmations: Confirmations,
        install_dir: Path,
        timeout: float,
    ):
        self.db, self.library, self.guard, self.confirmations = db, library, guard, confirmations
        self.install_dir, self.timeout = install_dir.resolve(), timeout

    def list_plugins(self, installed_only: bool = False) -> list[dict[str, Any]]:
        installed = {p["name"]: p for p in self.db.list("plugin")}
        if installed_only:
            return list(installed.values())
        return [
            installed.pop(name, {**m.model_dump(), "installed": False, "enabled": False})
            for name, m in BUILTINS.items()
        ] + list(installed.values())

    def install(
        self,
        name: str,
        token: str | None,
        wheel_path: str | None = None,
        manifest_data: dict[str, Any] | None = None,
        sha256: str | None = None,
    ) -> dict[str, Any]:
        require(self.db.get("plugin", name) is None, "E_CONFLICT", "插件已安装，请先卸载旧版本")
        sha256 = sha256.lower() if sha256 else None
        wheel = None
        if wheel_path:
            wheel = self.guard.read(wheel_path)
            require(wheel.is_file() and wheel.suffix == ".whl", "E_ARGUMENT", "需要本地 wheel 文件")
            require(
                sha256 is not None and file_hash(wheel) == sha256.lower(),
                "E_PLUGIN_HASH",
                "插件 SHA256 不匹配",
            )
            try:
                manifest = PluginManifest.model_validate(manifest_data)
                require(manifest.name == name, "E_ARGUMENT", "插件名称不匹配")
                with zipfile.ZipFile(wheel) as archive:
                    meta_names = [
                        f for f in archive.namelist() if f.endswith(".dist-info/METADATA")
                    ]
                    require(len(meta_names) == 1, "E_PLUGIN_MANIFEST", "wheel 元数据无效")
                    pkg = BytesParser().parsebytes(archive.read(meta_names[0]))
                    require(
                        pkg["Version"] == manifest.version,
                        "E_PLUGIN_MANIFEST",
                        "wheel 版本与清单不匹配",
                    )
                    entries = configparser.ConfigParser()
                    entries.read_string(
                        archive.read(meta_names[0].replace("METADATA", "entry_points.txt")).decode()
                    )
                    require(
                        entries.get("paperhub.outlines", name) == manifest.entry,
                        "E_PLUGIN_MANIFEST",
                        "wheel 入口与清单不匹配",
                    )
            except (ValidationError, ValueError, KeyError, configparser.Error, zipfile.BadZipFile):
                raise PaperHubError("E_PLUGIN_MANIFEST", "插件清单或 wheel 无效") from None
        else:
            require(
                name in BUILTINS, "E_NOT_FOUND", "插件不在本地官方目录，第三方需提供 wheel 与清单"
            )
            manifest = BUILTINS[name]
        manifest.compatible()
        if wheel:
            require(
                not (set(manifest.permissions) - {"read_library", "read_topics"}),
                "E_PLUGIN_PERMISSION",
                "当前第三方宿主只支持 read_library/read_topics 权限",
            )
        preview = {
            "manifest": manifest.model_dump(),
            "sha256": sha256,
            "runtime_trust": "第三方 Python 具有当前用户进程权限，独立进程不是安全沙箱"
            if wheel
            else "官方本地模板",
        }
        self.confirmations.verify(
            "install_plugin",
            {"preview": preview, "wheel": str(wheel)},
            token,
            "请确认插件权限 / Confirm plugin permissions",
            **preview,
        )
        python_path = None
        if wheel:
            directory = self.install_dir / f"{name}-{uuid.uuid4().hex[:12]}"
            directory.mkdir(parents=True, exist_ok=False)
            venv.EnvBuilder(with_pip=True).create(directory)
            python_path = directory / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            require(file_hash(wheel) == sha256, "E_PLUGIN_HASH", "确认后插件文件变化")
            with tempfile.TemporaryFile() as quiet:
                try:
                    result = subprocess.run(
                        [
                            str(python_path),
                            "-m",
                            "pip",
                            "install",
                            "--no-index",
                            "--no-deps",
                            "--disable-pip-version-check",
                            str(wheel),
                        ],
                        stdout=quiet,
                        stderr=quiet,
                        timeout=120,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    require(
                        result.returncode == 0,
                        "E_PLUGIN_INSTALL",
                        "wheel 安装失败；依赖须随可信环境预置",
                    )
                except subprocess.TimeoutExpired:
                    raise PaperHubError("E_PLUGIN_INSTALL", "插件安装超时") from None
        installed = {
            **manifest.model_dump(),
            "enabled": True,
            "installed": True,
            "python": str(python_path) if python_path else None,
            "sha256": sha256,
        }
        self.db.put("plugin", name, installed)
        return installed

    def enable(self, name: str, enabled: bool) -> dict[str, Any]:
        plugin = self.db.get("plugin", name)
        require(plugin is not None, "E_NOT_FOUND", "插件未安装")
        assert plugin is not None
        plugin["enabled"] = enabled
        self.db.put("plugin", name, plugin)
        return plugin

    def uninstall(self, name: str) -> dict[str, Any]:
        plugin = self.db.get("plugin", name)
        require(plugin is not None, "E_NOT_FOUND", "插件未安装")
        assert plugin is not None
        if plugin.get("python"):
            directory = Path(plugin["python"]).parent.parent.resolve()
            require(
                directory.is_relative_to(self.install_dir) and directory != self.install_dir,
                "E_PATH_DENIED",
                "插件安装目录无效",
            )
            shutil.rmtree(directory)
        self.db.delete("plugin", name)
        return {"name": name, "uninstalled": True}

    def generate(
        self, name: str, scope: list[str] | None, options: dict[str, Any]
    ) -> dict[str, Any]:
        plugin = self.db.get("plugin", name)
        require(plugin is not None and plugin["enabled"], "E_PLUGIN_DISABLED", "请先安装并启用插件")
        assert plugin is not None
        permissions = set(plugin["permissions"])
        papers = self.library.papers(scope) if "read_library" in permissions else []
        topics = (
            [
                t
                for plan in self.db.list("plan")
                if plan["status"] == "applied"
                for t in plan["topics"]
            ]
            if "read_topics" in permissions
            else []
        )
        context = PluginContext(papers=papers, topics=topics)
        if not plugin.get("python"):
            outline = builtin_outline(name, context, options)
        else:
            require(
                not (permissions & {"call_llm", "network", "write_output"}),
                "E_PLUGIN_PERMISSION",
                "当前第三方适配器只提供 read_library 和 read_topics 上下文",
            )
            with tempfile.TemporaryDirectory(prefix="paperhub-plugin-") as temp:
                request, response = Path(temp) / "request.json", Path(temp) / "response.json"
                request.write_text(
                    json.dumps(
                        {"manifest": plugin, "context": context.model_dump(), "options": options},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                environment = {
                    k: v
                    for k, v in os.environ.items()
                    if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "LANG"}
                }
                with tempfile.TemporaryFile() as quiet:
                    try:
                        subprocess.run(
                            [plugin["python"], "-I", "-c", WORKER, str(request), str(response)],
                            env=environment,
                            stdout=quiet,
                            stderr=quiet,
                            timeout=self.timeout,
                            check=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                        require(
                            response.exists() and response.stat().st_size <= 1024 * 1024,
                            "E_PLUGIN_FAILED",
                            "插件结果缺失或过大",
                        )
                        result = json.loads(response.read_text(encoding="utf-8"))
                        require(
                            result.get("ok") is True,
                            "E_PLUGIN_FAILED",
                            "插件运行失败，核心服务仍可用",
                        )
                        outline = Outline.model_validate(result["outline"])
                    except (subprocess.SubprocessError, ValueError, OSError):
                        raise PaperHubError(
                            "E_PLUGIN_FAILED", "插件异常、超时或输出无效，核心服务仍可用"
                        ) from None
        known = {p["id"] for p in papers}
        require(
            all(set(section.citations) <= known for section in outline.sections),
            "E_PLUGIN_FAILED",
            "插件引用了未授权或不存在的论文",
        )
        item = {"id": str(uuid.uuid4()), "plugin": name, **outline.model_dump()}
        self.db.put("outline", item["id"], item)
        return item

    def edit(self, outline_id: str, title: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
        previous = self.db.get("outline", outline_id)
        require(previous is not None, "E_NOT_FOUND", "大纲不存在")
        assert previous is not None
        outline = Outline.model_validate(
            {"title": title, "sections": sections, "notes": previous["notes"]}
        )
        for section in outline.sections:
            for paper_id in section.citations:
                self.library.get(paper_id)
        item = {**previous, **outline.model_dump()}
        self.db.put("outline", outline_id, item)
        return item

    def export(self, outline_id: str) -> dict[str, Any]:
        outline = self.db.get("outline", outline_id)
        require(outline is not None, "E_NOT_FOUND", "大纲不存在")
        assert outline is not None
        parts = [f"# {outline['title']}", *outline["notes"]]
        for section in outline["sections"]:
            parts += [
                f"## {section['title']}",
                "\n".join("- " + p for p in section["points"]),
                "建议引用: " + ", ".join(section["citations"]),
            ]
        destination = self.guard.output_file(f"outlines/{outline_id}-{uuid.uuid4().hex[:8]}.md")
        write_new(destination, "\n\n".join(parts))
        return {"path": str(destination)}
