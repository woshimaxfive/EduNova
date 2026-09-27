from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from backend.app.agents.material_ingestion import MaterialIngestionError, MaterialIngestionGraphRunner
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.core.config import Settings
from backend.app.models import Material, MaterialChunk, User
from backend.app.services.material_parsers import DocumentParseError, DoclingDocumentExtractor
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
    from backend.app.services.ai_capabilities import AI_CAPABILITIES
    assert AI_CAPABILITIES["material_ingestion"].validate_output(result, None) == result
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
    assert runner._heading_level("图中各部件的功能如下：") is None
    assert runner._heading_level("1. 上机前的准备") is None
    assert runner._heading_level("1.2。3 计算机的工作步骤") == 3
    assert runner._heading_level("2.3 什么是摩尔定律？") is None
    assert runner._heading_level("3.7 GB") is None
    assert runner._heading_level("16.67 MHz") is None
    assert runner._heading_level("63.7 （估计）") is None
    assert runner._heading_level("0.1 0 0 1") is None
    assert runner._heading_level("4.17 写出 1100、1101 对应的汉明码。") is None
    assert runner._heading_level("6.20 用原码和补码计算 x·y。") is None
    assert runner._heading_level("10.3 列出了对应 10 条机器指令的微指令码点。") is None


class DoclingNoisyHeadingParser:
    def parse_document(self, _extension: str, _content: bytes) -> ParsedDocument:
        blocks = [
            ParsedBlock("1.1 计算机系统简介", 1, "heading", 1),
            ParsedBlock("计算机系统由硬件和软件共同组成。" * 30, 1),
            ParsedBlock("图中各部件的功能如下：", 2, "heading", 1),
            ParsedBlock("控制器协调各部件完成取指和执行。" * 30, 2),
            ParsedBlock("1.2。3 计算机的工作步骤", 2, "heading", 1),
            ParsedBlock("程序和数据先装入主存储器。" * 30, 2),
            ParsedBlock("2.1 总线概述", 3, "heading", 1),
            ParsedBlock("总线连接计算机的主要功能部件。" * 30, 3),
        ]
        pages = [
            ParsedPage(index, "\n".join(block.text for block in blocks if block.page_number == index))
            for index in range(1, 4)
        ]
        return ParsedDocument(pages, blocks, "docling:test", source_page_count=3)


def test_docling_outline_uses_numbered_semantics_instead_of_every_visual_header(tmp_path: Path) -> None:
    storage = tmp_path / "materials"
    source = storage / "user_1" / "textbook.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"programmatic-docling-outline-stand-in")
    material = make_material("textbook.pdf", "user_1/textbook.pdf")
    runner = MaterialIngestionGraphRunner(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None, material_storage_dir=str(storage)),
        parser=DoclingNoisyHeadingParser(),  # type: ignore[arg-type]
        trace_recorder=recorder([]),
    )

    runner.run(user=make_user(), material=material, trace_id="trace-docling-outline")

    titles = [item["title"] for item in material.outline_json["sections"] if item["included"]]
    assert titles == ["第1章", "1.1 计算机系统简介", "1.2.3 计算机的工作步骤", "第2章", "2.1 总线概述"]
    assert "图中各部件的功能如下：" not in titles
    assert material.quality_json["empty_section_ratio"] == 0.0


class DoclingWordHeadingParser:
    def parse_document(self, _extension: str, _content: bytes) -> ParsedDocument:
        return ParsedDocument([], [
            ParsedBlock("栈与队列", None, "heading", 1),
            ParsedBlock("栈的抽象与后进先出", None, "heading", 2),
            ParsedBlock("栈仅允许在栈顶插入与删除，后入栈的元素先出栈。", None),
            ParsedBlock("队列的先进先出", None, "heading", 2),
            ParsedBlock("队列从队尾插入，从队头删除，先进入的元素先离开。", None),
        ], "docling:test")


def test_docling_docx_preserves_explicit_unnumbered_headings(tmp_path: Path) -> None:
    storage = tmp_path / "materials"
    source = storage / "user_1" / "notes.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"docling-word-structural-headings-fixture")
    material = make_material("notes.docx", "user_1/notes.docx")
    session = FakeSession()
    runner = MaterialIngestionGraphRunner(
        session,  # type: ignore[arg-type]
        settings=Settings(_env_file=None, material_storage_dir=str(storage)),
        parser=DoclingWordHeadingParser(),  # type: ignore[arg-type]
        trace_recorder=recorder([]),
    )

    runner.run(user=make_user(), material=material, trace_id="trace-docling-word")

    sections = material.outline_json["sections"]
    assert [section["title"] for section in sections if section["included"]] == [
        "栈与队列", "栈的抽象与后进先出", "队列的先进先出",
    ]
    assert sections[1]["path"] == ["栈与队列", "栈的抽象与后进先出"]
    chunks = [item for item in session.added if isinstance(item, MaterialChunk)]
    assert len(chunks) == 2
    assert all(section["chunk_indexes"] for section in sections[1:])
    assert material.quality_json["passed"] is True
    assert material.ingestion_status == "awaiting_confirmation"
    assert material.outline_json["confirmed"] is False


class DoclingTocParser:
    def parse_document(self, _extension: str, _content: bytes) -> ParsedDocument:
        blocks: list[ParsedBlock] = []
        for page in range(1, 13):
            blocks.append(ParsedBlock(f"第 {page} 页正文说明" * 20, page))
        blocks.extend([
            ParsedBlock("第9章 控制单元的功能", 4, "heading", 1),
            ParsedBlock("目录", 5, "heading", 1),
            ParsedBlock("第10章 控制单元的设计", 6, "heading", 1),
            ParsedBlock("1.1 计算机系统简介", 10, "heading", 1),
            ParsedBlock("计算机系统由硬件和软件共同组成。" * 30, 10),
        ])
        pages = [
            ParsedPage(index, "\n".join(block.text for block in blocks if block.page_number == index))
            for index in range(1, 13)
        ]
        return ParsedDocument(pages, blocks, "docling:test", source_page_count=12)


def test_docling_toc_window_does_not_create_fake_chapters(tmp_path: Path) -> None:
    storage = tmp_path / "materials"
    source = storage / "user_1" / "toc.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"programmatic-toc-stand-in")
    material = make_material("toc.pdf", "user_1/toc.pdf")
    runner = MaterialIngestionGraphRunner(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None, material_storage_dir=str(storage)),
        parser=DoclingTocParser(),  # type: ignore[arg-type]
        trace_recorder=recorder([]),
    )

    runner.run(user=make_user(), material=material, trace_id="trace-docling-toc")

    titles = [item["title"] for item in material.outline_json["sections"] if item["included"]]
    assert titles == ["第1章", "1.1 计算机系统简介"]


class FakeProvenance:
    page_no = 2


class FakeDoclingItem:
    def __init__(self, text: str, label: str, level: int | None = None, *, with_page: bool = True) -> None:
        self.text = text
        self.label = label
        self.level = level
        self.prov = [FakeProvenance()] if with_page else []


class FakeDoclingDocument:
    def iterate_items(self):
        yield FakeDoclingItem("第二章 树", "section_header", 2), 1
        yield FakeDoclingItem("二叉树每个结点最多有两个孩子。", "text"), 2


class FakeDoclingResult:
    document = FakeDoclingDocument()


class FakeDoclingConverter:
    def convert(self, _source, *, raises_on_error: bool):
        assert raises_on_error is True
        return FakeDoclingResult()


def test_docling_adapter_preserves_heading_and_page_contract() -> None:
    extractor = DoclingDocumentExtractor(
        artifacts_path="unused-in-injected-test",
        converter=FakeDoclingConverter(),
    )
    extractor._document_stream = lambda _extension, _content: object()  # type: ignore[method-assign]
    extractor._pdf_page_count = lambda _content: 2  # type: ignore[method-assign]

    result = extractor.parse_document(".pdf", b"fixture")

    assert result.blocks[0] == ParsedBlock("第二章 树", 2, "heading", 2)
    assert result.blocks[1].page_number == 2
    assert result.pages[0].page_number == 2
    assert "二叉树" in result.pages[0].text
    assert result.parser.startswith("docling:")
    assert result.source_page_count == 2


def test_docling_adapter_removes_internal_picture_placeholders() -> None:
    class PictureItem:
        text = None

        @staticmethod
        def export_to_markdown(_document) -> str:
            return "<!-- Image not available. -->\n图 1.1 计算机组成结构"

    assert DoclingDocumentExtractor._item_text(PictureItem(), object()) == "图 1.1 计算机组成结构"


def test_docling_large_pdf_timeout_is_size_aware_and_capped() -> None:
    extractor = DoclingDocumentExtractor(
        artifacts_path="unused",
        timeout_seconds=120,
        max_timeout_seconds=840,
        converter=FakeDoclingConverter(),
    )

    assert extractor.effective_timeout_seconds(".pdf", b"x" * (9 * 1024 * 1024)) == 120
    assert extractor.effective_timeout_seconds(".pdf", b"x" * (24 * 1024 * 1024)) == 600
    assert extractor.effective_timeout_seconds(".pdf", b"x" * (40 * 1024 * 1024)) == 840
    assert extractor.effective_timeout_seconds(".docx", b"x" * (24 * 1024 * 1024)) == 120


def test_docling_large_textbook_disables_expensive_table_structure(tmp_path: Path) -> None:
    extractor = DoclingDocumentExtractor(
        artifacts_path=tmp_path,
        timeout_seconds=120,
        max_timeout_seconds=840,
    )
    captured: dict[str, object] = {}

    def build_converter(timeout_seconds: float, *, do_table_structure: bool = True):
        captured["timeout_seconds"] = timeout_seconds
        captured["do_table_structure"] = do_table_structure
        return FakeDoclingConverter()

    extractor._build_converter = build_converter  # type: ignore[method-assign]
    extractor._document_stream = lambda _extension, _content: object()  # type: ignore[method-assign]
    extractor._pdf_page_count = lambda _content: 437  # type: ignore[method-assign]

    extractor.parse_document(".pdf", b"x" * (11 * 1024 * 1024))

    assert captured == {"timeout_seconds": 275.0, "do_table_structure": False}


class PartialDoclingResult:
    document = FakeDoclingDocument()
    status = "partial_success"


class PartialDoclingConverter:
    def convert(self, _source, *, raises_on_error: bool):
        assert raises_on_error is True
        return PartialDoclingResult()


def test_docling_partial_result_is_rejected_instead_of_persisted() -> None:
    extractor = DoclingDocumentExtractor(
        artifacts_path="unused",
        converter=PartialDoclingConverter(),
    )
    extractor._document_stream = lambda _extension, _content: object()  # type: ignore[method-assign]
    extractor._pdf_page_count = lambda _content: 437  # type: ignore[method-assign]

    with pytest.raises(DocumentParseError, match="did not complete"):
        extractor.parse_document(".pdf", b"fixture")


class TruncatedLargePdfParser:
    def parse_document(self, _extension: str, _content: bytes) -> ParsedDocument:
        pages = [ParsedPage(page_number=index, text="有效正文" * 20) for index in range(1, 6)]
        blocks = [ParsedBlock(text="有效正文" * 100, page_number=1, kind="paragraph")]
        return ParsedDocument(
            pages=pages,
            blocks=blocks,
            parser="test-truncated",
            source_page_count=437,
        )


def test_quality_gate_uses_source_page_count_to_reject_truncated_large_pdf(tmp_path: Path) -> None:
    storage = tmp_path / "materials"
    source = storage / "user_1" / "large.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"programmatic-large-pdf-stand-in")
    runner = MaterialIngestionGraphRunner(
        FakeSession(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None, material_storage_dir=str(storage)),
        parser=TruncatedLargePdfParser(),  # type: ignore[arg-type]
        trace_recorder=recorder([]),
    )

    with pytest.raises(MaterialIngestionError) as captured:
        runner.run(user=make_user(), material=make_material("large.pdf", "user_1/large.pdf"), trace_id="trace-large")

    assert captured.value.quality["page_count"] == 437
    assert captured.value.quality["readable_page_count"] == 5
    assert "low_readable_page_ratio" in captured.value.quality["risk_flags"]


def test_material_semantic_classification_requires_review_when_confidence_is_low() -> None:
    runner = MaterialIngestionGraphRunner.__new__(MaterialIngestionGraphRunner)

    classified = runner._classification({
        "material_type": "textbook",
        "chapter_role": "core_chapter",
        "knowledge_domain": "数据结构",
        "concept_groups": ["树与森林"],
        "difficulty": "intermediate",
        "confidence": 0.62,
        "needs_review": False,
    })
    invalid = runner._classification({"material_type": "textbook"})

    assert classified["material_type"] == "textbook"
    assert classified["needs_review"] is True
    assert invalid["material_type"] == "unclassified"
    assert invalid["needs_review"] is True
