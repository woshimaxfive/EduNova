from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import re
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

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text.strip()).strip()


class DocumentParser:
    """Extract ordered, page-aware blocks without inventing document structure."""

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
