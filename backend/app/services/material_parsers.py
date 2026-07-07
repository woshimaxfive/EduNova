from __future__ import annotations

import re
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


class DocumentParseError(RuntimeError):
    pass


class DocumentParser:
    office_text_namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }

    def extract_text(self, extension: str, content: bytes) -> str:
        if extension in {".txt", ".md", ".markdown"}:
            return content.decode("utf-8", errors="replace")
        if extension == ".pdf":
            return self._extract_pdf(content)
        if extension == ".docx":
            return self._extract_docx(content)
        if extension == ".pptx":
            return self._extract_pptx(content)
        raise DocumentParseError("unsupported parser")

    def _extract_pdf(self, content: bytes) -> str:
        text_parts: list[str] = []
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)
        except Exception as exc:
            fallback_text = self._extract_pdf_text_stream(content)
            if fallback_text:
                return fallback_text
            raise DocumentParseError("pdf parse failed") from exc

        text = self._clean_text("\n\n".join(text_parts))
        if text:
            return text
        fallback_text = self._extract_pdf_text_stream(content)
        if fallback_text:
            return fallback_text
        raise DocumentParseError("pdf has no extractable text")

    def _extract_docx(self, content: bytes) -> str:
        try:
            with ZipFile(BytesIO(content)) as archive:
                xml_content = archive.read("word/document.xml")
        except (BadZipFile, KeyError) as exc:
            raise DocumentParseError("docx parse failed") from exc
        return self._extract_xml_text(xml_content, ".//w:t", "docx parse failed")

    def _extract_pptx(self, content: bytes) -> str:
        try:
            with ZipFile(BytesIO(content)) as archive:
                slide_names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
                if not slide_names:
                    raise DocumentParseError("pptx has no slides")
                slide_texts = [
                    self._extract_xml_text(archive.read(name), ".//a:t", "pptx parse failed")
                    for name in slide_names
                ]
        except BadZipFile as exc:
            raise DocumentParseError("pptx parse failed") from exc
        return self._clean_text("\n\n".join(part for part in slide_texts if part))

    def _extract_xml_text(self, xml_content: bytes, path: str, error_message: str) -> str:
        try:
            root = ElementTree.fromstring(xml_content)
        except ElementTree.ParseError as exc:
            raise DocumentParseError(error_message) from exc
        texts = [node.text or "" for node in root.findall(path, self.office_text_namespaces)]
        text = self._clean_text(" ".join(texts))
        if not text:
            raise DocumentParseError(error_message)
        return text

    @classmethod
    def _extract_pdf_text_stream(cls, content: bytes) -> str:
        decoded = content.decode("latin-1", errors="ignore")
        matches = re.findall(r"\(([^()\r\n]{3,})\)\s*Tj", decoded)
        return cls._clean_text(" ".join(match.replace(r"\(", "(").replace(r"\)", ")") for match in matches))

    @staticmethod
    def _clean_text(value: str) -> str:
        return "\n".join(" ".join(line.split()) for line in value.replace("\r\n", "\n").splitlines() if line.strip()).strip()
