from __future__ import annotations

from pydantic import BaseModel


class MaterialUploadResult(BaseModel):
    id: str
    material_id: int
    course_id: int | None
    filename: str
    title: str
    type: str
    detail: str
    modified: str
    size: str
    parse_status: str


class MaterialListItem(BaseModel):
    id: str
    title: str
    type: str
    detail: str
    modified: str
    size: str
    category: str
    extension: str
    parse_status: str
    course_ids: list[str]


class MaterialDetail(MaterialListItem):
    filename: str
    content_type: str
    extracted_text_preview: str | None


class MaterialProgress(BaseModel):
    status: str
    progress_percent: int
    message: str


class AttachCourseMaterialsRequest(BaseModel):
    material_ids: list[int]


class AttachCourseMaterialsResult(BaseModel):
    course_id: str
    material_ids: list[str]
    attached_count: int
