from typing import Any, Protocol

from pydantic import BaseModel, Field


class PluginContext(BaseModel):
    papers: list[dict[str, Any]] = Field(default_factory=list)
    topics: list[dict[str, Any]] = Field(default_factory=list)


class OutlineSection(BaseModel):
    title: str
    points: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    title: str
    sections: list[OutlineSection]
    notes: list[str] = Field(default_factory=list)


class OutlinePlugin(Protocol):
    def generate(self, ctx: PluginContext, options: dict[str, Any]) -> Outline: ...
