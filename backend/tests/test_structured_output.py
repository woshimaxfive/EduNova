from pydantic import BaseModel

from backend.app.services.structured_output import parse_json_object


class ExamplePayload(BaseModel):
    title: str
    count: int


def test_structured_output_accepts_strict_json_and_fences() -> None:
    assert parse_json_object('{"title":"图","count":2}', ExamplePayload) == {"title": "图", "count": 2}
    assert parse_json_object('```json\n{"title":"图","count":2}\n```', ExamplePayload) == {"title": "图", "count": 2}


def test_structured_output_repairs_once_and_still_validates_schema() -> None:
    assert parse_json_object('说明：{"title":"图","count":2,}', ExamplePayload) == {"title": "图", "count": 2}
    assert parse_json_object('{"title":"图"}', ExamplePayload) is None
