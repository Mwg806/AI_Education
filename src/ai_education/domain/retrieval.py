"""Unified retrieval contracts shared by all education knowledge sources."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ai_education.domain.protocols import StrictModel


class RetrievalQuery(StrictModel):
    query: str = Field(min_length=1, max_length=4_000)
    agent_role: str = Field(min_length=1, max_length=64)
    subject: str | None = Field(default=None, max_length=64)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict)
    allow_answer_content: bool = False


class SourceCitation(StrictModel):
    source_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=500)
    source_type: str = Field(min_length=1, max_length=64)
    authority_level: Literal["A", "B", "C", "unknown"] = "unknown"
    content_version: str = Field(default="unknown", max_length=96)
    license_status: Literal["owned", "licensed", "public", "unknown"] = "unknown"
    page: int | None = Field(default=None, ge=1)
    public_reference: str | None = Field(default=None, max_length=1_000)


class RetrievalResult(StrictModel):
    result_id: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=20_000)
    score: float = Field(ge=0, le=1)
    citation: SourceCitation
    metadata: dict[str, Any] = Field(default_factory=dict)
    contains_restricted_answer: bool = False


class RetrievalResponse(StrictModel):
    query: RetrievalQuery
    results: list[RetrievalResult] = Field(default_factory=list)
    retrieval_mode: str = Field(default="deterministic", max_length=64)
    index_version: str = Field(default="unknown", max_length=96)
    failure_reason: str | None = Field(default=None, max_length=1_000)
