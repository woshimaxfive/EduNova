from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from backend.app.services import material_parsers


@pytest.fixture
def docling_modules(monkeypatch):
    """Exercise backend selection without loading the optional AI models."""
    default_backend = type("DefaultBackend", (), {})
    pdfium_backend = type("PdfiumBackend", (), {})

    class PdfFormatOption:
        def __init__(self, *, pipeline_options):
            self.pipeline_options = pipeline_options
            self.backend = default_backend

    definitions = {
        "docling.datamodel.base_models": {
            "InputFormat": SimpleNamespace(PDF="pdf", DOCX="docx", PPTX="pptx"),
        },
        "docling.datamodel.pipeline_options": {"PdfPipelineOptions": SimpleNamespace},
        "docling.document_converter": {
            "DocumentConverter": SimpleNamespace,
            "PdfFormatOption": PdfFormatOption,
        },
        "docling.backend.pypdfium2_backend": {"PyPdfiumDocumentBackend": pdfium_backend},
        "docling_parse": {"__file__": "C:/EduNova/docling_parse/__init__.py"},
    }
    for name, attributes in definitions.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    return default_backend, pdfium_backend


@pytest.mark.parametrize(
    ("platform", "package_file", "use_pdfium"),
    [
        ("win32", "C:/EduNova/docling_parse/__init__.py", False),
        ("win32", "C:/Users/同学/EduNova/docling_parse/__init__.py", True),
        ("win32", "C:/Users/élève/EduNova/docling_parse/__init__.py", True),
        ("linux", "/home/同学/docling_parse/__init__.py", False),
    ],
)
def test_backend_selection_preserves_pipeline_contract(
    monkeypatch, docling_modules, platform, package_file, use_pdfium
):
    default_backend, pdfium_backend = docling_modules
    monkeypatch.setattr(material_parsers, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(sys.modules["docling_parse"], "__file__", package_file)
    extractor = material_parsers.DoclingDocumentExtractor(artifacts_path=Path("models/docling"))

    converter = extractor._build_converter(275, do_table_structure=False)

    option = converter.format_options["pdf"]
    assert option.backend is (pdfium_backend if use_pdfium else default_backend)
    assert converter.allowed_formats == ["pdf", "docx", "pptx"]
    assert vars(option.pipeline_options) == {
        "artifacts_path": Path("models/docling"),
        "document_timeout": 275,
        "do_ocr": False,
        "do_table_structure": False,
        "enable_remote_services": False,
        "allow_external_plugins": False,
    }


def test_missing_pdfium_dependency_is_not_silently_ignored(monkeypatch, docling_modules):
    monkeypatch.setattr(material_parsers, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(sys.modules["docling_parse"], "__file__", "C:/同学/docling_parse/__init__.py")
    monkeypatch.setitem(sys.modules, "docling.backend.pypdfium2_backend", None)
    extractor = material_parsers.DoclingDocumentExtractor(artifacts_path="models/docling")

    with pytest.raises(ImportError):
        extractor._build_converter(120)
