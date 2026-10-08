import os
import tomllib
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from paperhub.errors import PaperHubError


class LibraryConfig(BaseModel):
    paths: list[Path] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=lambda: ["pdf", "docx", "md", "tex"])
    default_apply_mode: Literal["index", "symlink", "move"] = "index"


class EmbeddingConfig(BaseModel):
    engine: Literal["tfidf", "sentence-transformers"] = "tfidf"
    model: str = ""


class ConvertConfig(BaseModel):
    output_dir: Path = Path.home() / ".paperhub" / "output"
    timeout: float = Field(default=120, gt=0, le=600)
    pandoc_path: str = "auto"
    routes: dict[str, list[str]] = Field(default_factory=dict)


class BackendConfig(BaseModel):
    model: str = ""
    base_url: str | None = None
    input_per_million: float | None = Field(default=None, ge=0)
    output_per_million: float | None = Field(default=None, ge=0)

    @field_validator("base_url")
    @classmethod
    def safe_endpoint(cls, value: str | None) -> str | None:
        if value:
            endpoint = urlsplit(value)
            if (
                endpoint.scheme not in ("http", "https")
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError("Provider URL must not contain credentials, query or fragments")
            if endpoint.scheme == "http" and endpoint.hostname not in (
                "localhost",
                "127.0.0.1",
                "::1",
            ):
                raise ValueError("Remote provider URLs require HTTPS")
        return value


class TranslateConfig(BaseModel):
    default_backend: str = "openai"
    default_target_lang: str = "zh-CN"
    concurrency: int = Field(default=3, ge=1, le=10)
    max_retries: int = Field(default=2, ge=0, le=5)
    chunk_chars: int = Field(default=6000, ge=500, le=16000)
    timeout: float = Field(default=60, gt=0, le=300)
    backends: dict[str, BackendConfig] = Field(
        default_factory=lambda: {"openai": BackendConfig(), "anthropic": BackendConfig()}
    )


class SecurityConfig(BaseModel):
    allow_network_metadata: bool = False
    confirmation_ttl: int = Field(default=300, ge=30, le=3600)


class PluginConfig(BaseModel):
    timeout: float = Field(default=30, gt=0, le=300)


class Config(BaseModel):
    data_dir: Path = Path.home() / ".paperhub"
    library: LibraryConfig = Field(default_factory=LibraryConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    convert: ConvertConfig = Field(default_factory=ConvertConfig)
    translate: TranslateConfig = Field(default_factory=TranslateConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)

    @field_validator("data_dir")
    @classmethod
    def absolute_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()


def load_config(path: Path | None = None) -> Config:
    config_path = path or Path(os.environ.get("PAPERHUB_CONFIG", "~/.paperhub/config.toml"))
    config_path = config_path.expanduser().resolve()
    data: dict[str, Any] = {}
    try:
        if config_path.exists():
            with config_path.open("rb") as stream:
                data = tomllib.load(stream)
        if os.environ.get("PAPERHUB_LIBRARY_PATHS"):
            data.setdefault("library", {})["paths"] = os.environ["PAPERHUB_LIBRARY_PATHS"].split(
                os.pathsep
            )
        if os.environ.get("PAPERHUB_DATA_DIR"):
            data["data_dir"] = os.environ["PAPERHUB_DATA_DIR"]
        if os.environ.get("PAPERHUB_OUTPUT_DIR"):
            data.setdefault("convert", {})["output_dir"] = os.environ["PAPERHUB_OUTPUT_DIR"]
        for name in ("openai", "anthropic"):
            if model := os.environ.get(f"PAPERHUB_{name.upper()}_MODEL"):
                data.setdefault("translate", {}).setdefault("backends", {}).setdefault(name, {})[
                    "model"
                ] = model
        return Config.model_validate(data)
    except (OSError, ValueError) as exc:
        raise PaperHubError(
            "E_CONFIG",
            "配置文件无效 / Invalid configuration",
            f"检查 TOML 语法、字段类型和路径 ({type(exc).__name__})",
        ) from None
