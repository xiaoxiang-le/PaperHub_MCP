from typing import Any

from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    text: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    doi: str = ""
    language: str = ""
    meta_source: str = "parsed"


class TranslateRequest(BaseModel):
    text: str
    target_lang: str
    glossary: dict[str, str] = Field(default_factory=dict)


class TranslateResponse(BaseModel):
    text: str
    usage: dict[str, Any] = Field(default_factory=dict)


class CostEstimate(BaseModel):
    input_tokens: int
    estimated_output_tokens: int
    estimated_usd: tuple[float, float] | None = None
