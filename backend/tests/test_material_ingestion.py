from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from backend.app.agents.material_ingestion import MaterialIngestionError, MaterialIngestionGraphRunner
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.core.config import Settings
from backend.app.models import Material, MaterialChunk, User
from backend.app.services.material_parsers import ParsedBlock, ParsedDocument, ParsedPage


@dataclass
class FakeSession:
    added: list[object] = field(default_factory=list)
    commit_count: int = 0

    def execute(self, _statement):
        return None

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def commit(self) -> None:
        self.commit_count += 1


def make_user() -> User:
    return User(id=1, account="reader", hashed_password="x", display_name="学生", role="student", starter_mode="blank")


def make_material(filename: str, storage_path: str) -> Material:
    return Material(
        id=11,
        user_id=1,
        filename=filename,
        storage_path=storage_path,
        content_type="text/markdown",
        parse_status="pending",
        ingestion_status="pending",
        outline_json={},
        quality_json={},
        metadata_json={},
    )


def recorder(logs: list[object]) -> AgentTraceRecorder:
    return AgentTraceRecorder(repository_add_log=lambda log: logs.append(log))


def test_material_ingestion_graph_preserves_sections_and_requires_confirmation(tmp_path: Path) -> None:
    storage = tmp_path / "materials"
    source = storage / "user_1" / "notes.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "# 第一章 线性表\n" + "顺序表支持按下标访问，插入时需要移动元素。" * 40
        + "\n## 链表\n" + "链表通过指针连接结点，插入和删除不需要整体移动。" * 40
        + "\n# 第二章 栈与队列\n" + "栈遵循后进先出，队列遵循先进先出。" * 40,
        encoding="utf-8",
    )
    material = make_material("notes.md", "user_1/notes.md")
    session = FakeSession()
    logs: list[object] = []

    result = MaterialIngestionGraphRunner(
        session,  # type: ignore[arg-type]
        settings=Settings(_env_file=None, material_storage_dir=str(storage)),
        trace_recorder=recorder(logs),
    ).run(user=make_user(), material=material, trace_id="trace-ingestion")

    chunks = [item for item in session.added if isinstance(item, MaterialChunk)]
    assert result["ingestion_status"] == "awaiting_confirmation"
    assert material.parse_status == "completed"
    assert material.ingestion_status == "awaiting_confirmation"
    assert material.outline_json["confirmed"] is False
    assert material.quality_json["passed"] is True
    assert all(0 < len(chunk.content) <= 1200 for chunk in chunks)
    assert all(chunk.section_path_json for chunk in chunks)
    assert all(chunk.page_number == 1 for chunk in chunks)
    assert len({tuple(chunk.section_path_json) for chunk in chunks}) >= 3
    assert [log.agent_name for log in logs] == [
        "validate",
        "extract_pages",
        "normalize_layout",
        "detect_outline",
        "model_refine",
        "chunk",
        "quality_gate",
        "persist",
    ]


class LowQualityParser:
    def parse_document(self, _extension: str, _content: bytes) -> ParsedDocument:
        pages = [ParsedPage(page_number=index, text="") for index in range(1, 31)]
        blocks = [ParsedBlock(text="只有一段正文", page_number=1, kind="paragraph")]
        return ParsedDocument(pages=pages, blocks=blocks, parser="test-low-quality")


def test_material_ingestion_quality_failure_exposes_safe_diagnostics(tmp_path: Path) -> None:
    storage = tmp_path / "materials"
    source = storage / "user_1" / "bad.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not-empty")
    runner = MaterialIngestionGraphRunner(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None, material_storage_dir=str(storage)),
        parser=LowQualityParser(),  # type: ignore[arg-type]
        trace_recorder=recorder([]),
    )

    with pytest.raises(MaterialIngestionError) as captured:
        runner.run(user=make_user(), material=make_material("bad.pdf", "user_1/bad.pdf"), trace_id="trace-bad")

    assert captured.value.quality["passed"] is False
    assert captured.value.quality["readable_page_ratio"] < 0.70
    assert "low_readable_page_ratio" in captured.value.quality["risk_flags"]
    assert "missing_meaningful_outline" in captured.value.quality["risk_flags"]


def test_outline_detection_rejects_body_references_and_repairs_safe_ocr_typos() -> None:
    runner = MaterialIngestionGraphRunner.__new__(MaterialIngestionGraphRunner)

    assert runner._heading_level("8.3.2 快速排序") == 3
    assert runner._heading_level("8.15 (f)和图 8.15 (g) 所示。至此排序完毕。") is None
    assert runner._heading_level("3.2 和 3.3 都属于这种情况。") is None
    assert runner._section_chapter_number("0.08, 0.14, 0.23") == "0"
    assert runner._normalize_heading("8.2.1 直接插人排序") == "8.2.1 直接插入排序"
    assert runner._normalize_heading("1.4.3 算法的时问复杂度") == "1.4.3 算法的时间复杂度"
