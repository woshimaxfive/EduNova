from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryLayer = Literal["episode", "fact"]
MemoryCategory = Literal["goal", "preference", "difficulty", "habit"]


class MemoryItem(BaseModel):
    id: str
    layer: MemoryLayer
    category: str
    content: str
    topic: str
    source: str
    session_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    created_at: datetime
    updated_at: datetime
    revision: int
    indexed: bool = False


class MemoryPage(BaseModel):
    items: list[MemoryItem]
    total: int
    page: int
    page_size: int


class MemoryExport(BaseModel):
    exported_at: datetime
    items: list[MemoryItem]
    raw_chat_history_included: bool = False


class ConfirmedMemoryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=500)
    confirmed: Literal[True]


class MemoryCorrectionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    content: str = Field(min_length=1, max_length=1600)
    revision: int = Field(ge=1)
    confirmed: Literal[True]


class MemoryActionResult(BaseModel):
    affected_count: int
    raw_chat_history_preserved: bool = True
