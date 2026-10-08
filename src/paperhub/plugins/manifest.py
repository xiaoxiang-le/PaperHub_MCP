import re

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator

from paperhub import __version__
from paperhub.errors import PaperHubError

PERMISSIONS = {"read_library", "read_topics", "write_output", "call_llm", "network"}


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    type: str = "outline"
    entry: str
    permissions: list[str] = Field(default_factory=list)
    min_core_version: str = "0.1.0"
    description: str = ""

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value):
            raise ValueError("Invalid plugin name")
        return value

    @field_validator("entry")
    @classmethod
    def entry_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", value):
            raise ValueError("Invalid entry point")
        return value

    @field_validator("version", "min_core_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        Version(value)
        return value

    @field_validator("permissions")
    @classmethod
    def known_permissions(cls, value: list[str]) -> list[str]:
        if set(value) - PERMISSIONS:
            raise ValueError("Unknown permissions")
        return value

    def compatible(self) -> None:
        try:
            if Version(self.min_core_version) > Version(__version__) or self.type != "outline":
                raise PaperHubError("E_PLUGIN_INCOMPATIBLE", "插件与当前核心版本不兼容")
        except InvalidVersion:
            raise PaperHubError("E_PLUGIN_INCOMPATIBLE", "插件版本无效") from None
