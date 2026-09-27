from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
import sys
from typing import Any, Protocol
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


class DocumentParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    page_number: int | None
    kind: str = "paragraph"
    heading_level: int | None = None


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    blocks: list[ParsedBlock] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[ParsedPage]
    blocks: list[ParsedBlock]
    parser: str
    source_page_count: int | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text.strip()).strip()


class DocumentStructureExtractor(Protocol):
    def parse_document(self, extension: str, content: bytes) -> ParsedDocument: ...


class DocumentParser:
    """Legacy extractor retained as an explicit rollback path."""

    parser_version = "ingestion-v1"
    office_text_namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }

    def extract_text(self, extension: str, content: bytes) -> str:
        return self.parse_document(extension, content).text

    def parse_document(self, extension: str, content: bytes) -> ParsedDocument:
        if extension in {".txt", ".md", ".markdown"}:
            return self._extract_text_document(extension, content)
        if extension == ".pdf":
            return self._extract_pdf_document(content)
        if extension == ".docx":
            return self._extract_docx_document(content)
        if extension == ".pptx":
            return self._extract_pptx_document(content)
        raise DocumentParseError("unsupported parser")

    def _extract_text_document(self, extension: str, content: bytes) -> ParsedDocument:
        text = content.decode("utf-8", errors="replace").replace("\r\n", "\n")
        blocks: list[ParsedBlock] = []
        if extension in {".md", ".markdown"}:
            paragraph_lines: list[str] = []

            def flush_paragraph() -> None:
                cleaned = self._clean_block_text("\n".join(paragraph_lines))
                paragraph_lines.clear()
                if cleaned:
                    blocks.append(ParsedBlock(cleaned, 1))

            for line in text.splitlines():
                heading = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
                if heading:
                    flush_paragraph()
                    blocks.append(ParsedBlock(heading.group(2).strip(), 1, "heading", len(heading.group(1))))
                elif line.strip():
                    paragraph_lines.append(line)
                else:
                    flush_paragraph()
            flush_paragraph()
        else:
            for paragraph in re.split(r"\n\s*\n", text):
                cleaned = self._clean_block_text(paragraph)
                if cleaned:
                    blocks.append(ParsedBlock(cleaned, 1))
        if not blocks:
            raise DocumentParseError("text has no extractable content")
        page = ParsedPage(1, "\n\n".join(block.text for block in blocks), blocks)
        return ParsedDocument([page], blocks, f"text:{self.parser_version}")

    def _extract_pdf_document(self, content: bytes) -> ParsedDocument:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            pages: list[ParsedPage] = []
            all_blocks: list[ParsedBlock] = []
            for index, page in enumerate(reader.pages, start=1):
                raw = (page.extract_text() or "").replace("\r\n", "\n")
                blocks = [
                    ParsedBlock(cleaned, index)
                    for part in re.split(r"\n\s*\n|(?<=。)\s*\n", raw)
                    if (cleaned := self._clean_block_text(part))
                ]
                if not blocks and (cleaned_page := self._clean_block_text(raw)):
                    blocks = [ParsedBlock(cleaned_page, index)]
                pages.append(ParsedPage(index, "\n\n".join(block.text for block in blocks), blocks))
                all_blocks.extend(blocks)
        except Exception as exc:
            fallback_text = self._extract_pdf_text_stream(content)
            if fallback_text:
                block = ParsedBlock(fallback_text, 1)
                return ParsedDocument([ParsedPage(1, fallback_text, [block])], [block], f"pdf-fallback:{self.parser_version}")
            raise DocumentParseError("pdf parse failed") from exc
        if not any(page.text.strip() for page in pages):
            raise DocumentParseError("pdf has no extractable text")
        return ParsedDocument(pages, all_blocks, f"pypdf:{self.parser_version}")

    def _extract_docx_document(self, content: bytes) -> ParsedDocument:
        try:
            with ZipFile(BytesIO(content)) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
        except (BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise DocumentParseError("docx parse failed") from exc
        blocks: list[ParsedBlock] = []
        for paragraph in root.findall(".//w:p", self.office_text_namespaces):
            text = self._clean_block_text("".join(node.text or "" for node in paragraph.findall(".//w:t", self.office_text_namespaces)))
            if not text:
                continue
            style_node = paragraph.find("./w:pPr/w:pStyle", self.office_text_namespaces)
            style = style_node.get(f"{{{self.office_text_namespaces['w']}}}val", "") if style_node is not None else ""
            match = re.search(r"(?:heading|标题)\s*([1-6])", style, re.IGNORECASE)
            level = int(match.group(1)) if match else None
            blocks.append(ParsedBlock(text, None, "heading" if level else "paragraph", level))
        if not blocks:
            raise DocumentParseError("docx parse failed")
        return ParsedDocument([], blocks, f"docx-xml:{self.parser_version}")

    def _extract_pptx_document(self, content: bytes) -> ParsedDocument:
        try:
            with ZipFile(BytesIO(content)) as archive:
                slide_names = sorted(
                    (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                    key=lambda name: int(re.search(r"(\d+)", name.rsplit("/", 1)[-1]).group(1)),
                )
                if not slide_names:
                    raise DocumentParseError("pptx has no slides")
                pages: list[ParsedPage] = []
                blocks: list[ParsedBlock] = []
                for page_number, name in enumerate(slide_names, start=1):
                    root = ElementTree.fromstring(archive.read(name))
                    texts = [self._clean_block_text(node.text or "") for node in root.findall(".//a:t", self.office_text_namespaces)]
                    texts = [text for text in texts if text]
                    slide_blocks = [
                        ParsedBlock(text, page_number, "heading" if index == 0 else "paragraph", 1 if index == 0 else None)
                        for index, text in enumerate(texts)
                    ]
                    pages.append(ParsedPage(page_number, "\n\n".join(texts), slide_blocks))
                    blocks.extend(slide_blocks)
        except (BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise DocumentParseError("pptx parse failed") from exc
        if not blocks:
            raise DocumentParseError("pptx parse failed")
        return ParsedDocument(pages, blocks, f"pptx-xml:{self.parser_version}")

    @classmethod
    def _extract_pdf_text_stream(cls, content: bytes) -> str:
        decoded = content.decode("latin-1", errors="ignore")
        matches = re.findall(r"\(([^()\r\n]{3,})\)\s*Tj", decoded)
        return cls._clean_block_text(" ".join(match.replace(r"\(", "(").replace(r"\)", ")") for match in matches))

    @staticmethod
    def _clean_block_text(value: str) -> str:
        lines = [re.sub(r"[\t  ]+", " ", line).strip() for line in value.replace("\r", "\n").splitlines()]
        return "\n".join(line for line in lines if line).strip()


class DoclingDocumentExtractor:
    """Adapt Docling output to EduNova's stable, page-aware document contract."""

    supported_extensions = {".pdf", ".docx", ".pptx"}
    large_pdf_threshold_bytes = 10 * 1024 * 1024
    large_pdf_seconds_per_mib = 25.0

    def __init__(
        self,
        *,
        artifacts_path: str | Path,
        timeout_seconds: float = 120.0,
        max_timeout_seconds: float | None = None,
        converter: Any | None = None,
    ) -> None:
        self.artifacts_path = Path(artifacts_path)
        self.timeout_seconds = timeout_seconds
        self.max_timeout_seconds = max(timeout_seconds, max_timeout_seconds or timeout_seconds)
        self._converter = converter

    def parse_document(self, extension: str, content: bytes) -> ParsedDocument:
        if extension not in self.supported_extensions:
            raise DocumentParseError("unsupported docling parser")
        if not content:
            raise DocumentParseError("document is empty")
        if extension == ".pdf" and self._converter is None and not self.artifacts_path.is_dir():
            raise DocumentParseError("docling model artifacts are unavailable")
        source_page_count = self._pdf_page_count(content) if extension == ".pdf" else None
        try:
            is_large_textbook = (
                extension == ".pdf"
                and len(content) > self.large_pdf_threshold_bytes
                and bool(source_page_count and source_page_count >= 200)
            )
            converter = self._converter or self._build_converter(
                self.effective_timeout_seconds(extension, content),
                do_table_structure=not is_large_textbook,
            )
            result = converter.convert(self._document_stream(extension, content), raises_on_error=True)
            status = getattr(getattr(result, "status", None), "value", getattr(result, "status", None))
            if status not in {None, "success"}:
                raise DocumentParseError("docling conversion did not complete")
            document = result.document
            parsed = self._adapt_document(document, source_page_count=source_page_count)
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError("docling parse failed") from exc
        if not parsed.blocks:
            raise DocumentParseError("docling returned no extractable content")
        return parsed

    def effective_timeout_seconds(self, extension: str, content: bytes) -> float:
        if extension != ".pdf" or len(content) <= self.large_pdf_threshold_bytes:
            return self.timeout_seconds
        size_mib = len(content) / (1024 * 1024)
        return min(self.max_timeout_seconds, max(self.timeout_seconds, size_mib * self.large_pdf_seconds_per_mib))

    def _build_converter(self, timeout_seconds: float, *, do_table_structure: bool = True) -> Any:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise DocumentParseError("docling is not installed in this worker") from exc

        pdf_options = PdfPipelineOptions(
            artifacts_path=self.artifacts_path,
            document_timeout=timeout_seconds,
            do_ocr=False,
            do_table_structure=do_table_structure,
            enable_remote_services=False,
            allow_external_plugins=False,
        )
        pdf_format = PdfFormatOption(pipeline_options=pdf_options)
        if sys.platform == "win32":
            import docling_parse

            # docling-parse opens bundled font resources using narrow C++ paths.
            # Use Docling's installed PDFium backend for non-ASCII package paths;
            # keep the same layout/table pipeline and page-aware output contract.
            package_path = docling_parse.__file__
            if package_path and not str(Path(package_path).parent).isascii():
                from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

                pdf_format.backend = PyPdfiumDocumentBackend
        return DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX],
            format_options={InputFormat.PDF: pdf_format},
        )

    @staticmethod
    def _document_stream(extension: str, content: bytes) -> Any:
        try:
            from docling.datamodel.base_models import DocumentStream
        except ImportError as exc:
            raise DocumentParseError("docling is not installed in this worker") from exc
        return DocumentStream(name=f"material{extension}", stream=BytesIO(content))

    @classmethod
    def _adapt_document(cls, document: Any, *, source_page_count: int | None = None) -> ParsedDocument:
        blocks: list[ParsedBlock] = []
        page_blocks: dict[int, list[ParsedBlock]] = {}
        for item, _level in document.iterate_items():
            text = cls._item_text(item, document)
            if not text:
                continue
            label = str(getattr(item, "label", "")).lower()
            item_level = getattr(item, "level", None)
            is_heading = "title" in label or "section_header" in label
            heading_level = int(item_level) if is_heading and isinstance(item_level, int) and 1 <= item_level <= 6 else (1 if is_heading else None)
            page_number = cls._page_number(item)
            block = ParsedBlock(
                text=text,
                page_number=page_number,
                kind="heading" if is_heading else ("table" if "table" in label else "paragraph"),
                heading_level=heading_level,
            )
            blocks.append(block)
            if page_number is not None:
                page_blocks.setdefault(page_number, []).append(block)

        pages = [
            ParsedPage(number, "\n\n".join(block.text for block in items), items)
            for number, items in sorted(page_blocks.items())
        ]
        try:
            from importlib.metadata import version

            docling_version = version("docling-slim")
        except (ImportError, ModuleNotFoundError):
            docling_version = "unknown"
        return ParsedDocument(
            pages=pages,
            blocks=blocks,
            parser=f"docling:{docling_version}",
            source_page_count=source_page_count,
        )

    @staticmethod
    def _pdf_page_count(content: bytes) -> int:
        try:
            from pypdf import PdfReader

            return len(PdfReader(BytesIO(content)).pages)
        except Exception as exc:
            raise DocumentParseError("pdf page count unavailable") from exc

    @classmethod
    def _item_text(cls, item: Any, document: Any) -> str:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            return DocumentParser._clean_block_text(text)
        export = getattr(item, "export_to_markdown", None)
        if callable(export):
            try:
                value = export(document)
            except TypeError:
                value = export()
            if isinstance(value, str):
                value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
                return DocumentParser._clean_block_text(value)
        return ""

    @staticmethod
    def _page_number(item: Any) -> int | None:
        provenance = getattr(item, "prov", None) or []
        for entry in provenance:
            value = getattr(entry, "page_no", None)
            if isinstance(value, int):
                return max(1, value)
        return None


class RoutingDocumentStructureExtractor:
    """Route plain text to the stable parser and rich documents to the selected backend."""

    def __init__(self, rich_document_extractor: DocumentStructureExtractor) -> None:
        self.rich_document_extractor = rich_document_extractor
        self.plain_text_extractor = DocumentParser()

    def parse_document(self, extension: str, content: bytes) -> ParsedDocument:
        if extension in {".txt", ".md", ".markdown"}:
            return self.plain_text_extractor.parse_document(extension, content)
        return self.rich_document_extractor.parse_document(extension, content)


def create_document_structure_extractor(
    *,
    parser_name: str,
    artifacts_path: str | Path,
    timeout_seconds: float,
    max_timeout_seconds: float | None = None,
) -> DocumentStructureExtractor:
    if parser_name == "legacy":
        return DocumentParser()
    if parser_name == "docling":
        return RoutingDocumentStructureExtractor(
            DoclingDocumentExtractor(
                artifacts_path=artifacts_path,
                timeout_seconds=timeout_seconds,
                max_timeout_seconds=max_timeout_seconds,
            )
        )
    raise ValueError(f"unsupported document parser: {parser_name}")
