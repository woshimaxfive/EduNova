from io import BytesIO

import pytest
from reportlab.pdfgen.canvas import Canvas

from backend.app.services.material_parsers import DocumentParseError, DocumentParser, DoclingDocumentExtractor


def test_pdf_parser_preserves_compressed_text_and_page_provenance() -> None:
    stream = BytesIO()
    canvas = Canvas(stream, pageCompression=1)
    texts = ["Chapter 1: stacks use last-in first-out.", "Chapter 2: queues use first-in first-out."]
    for text in texts:
        canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    content = stream.getvalue()

    document = DocumentParser().parse_document(".pdf", content)

    assert document.parser.startswith("pypdf:")  # A fallback must not hide a broken dependency.
    assert DoclingDocumentExtractor._pdf_page_count(content) == 2
    assert [page.page_number for page in document.pages] == [1, 2]
    for index, text in enumerate(texts, start=1):
        page = document.pages[index - 1]
        assert text in page.text
        assert page.blocks
        assert all(block.page_number == index for block in page.blocks)
    assert all(text in document.text for text in texts)


def test_invalid_pdf_is_rejected_by_parser_and_page_preflight() -> None:
    content = b"not a PDF document"

    with pytest.raises(DocumentParseError, match="pdf parse failed"):
        DocumentParser().parse_document(".pdf", content)
    with pytest.raises(DocumentParseError, match="pdf page count unavailable"):
        DoclingDocumentExtractor._pdf_page_count(content)
