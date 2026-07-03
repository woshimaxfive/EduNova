from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RagSearchRequest(BaseModel):
    course_id: int
    query: str
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("检索问题不能为空。")
        return cleaned


class RagSearchResultItem(BaseModel):
    chunk_id: int
    course_id: int
    material_id: int
    knowledge_point_id: int | None
    content: str
    source_title: str
    page_number: int | None
    section_title: str | None
    score: float


class RagSearchResponse(BaseModel):
    course_id: int
    query: str
    top_k: int
    results: list[RagSearchResultItem]
