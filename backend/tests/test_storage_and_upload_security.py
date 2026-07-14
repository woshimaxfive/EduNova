from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document

from backend.app.services.storage import LocalStorageAdapter, S3StorageAdapter
from backend.app.services.upload_security import ClamAvScanner, UploadSecurityError, validate_upload_type


class Body:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self) -> bytes:
        return self.value


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, **kwargs) -> None:
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, **kwargs):
        return {"Body": Body(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    def head_object(self, **kwargs) -> None:
        if (kwargs["Bucket"], kwargs["Key"]) not in self.objects:
            raise KeyError


def test_local_storage_supports_keys_and_legacy_paths(tmp_path: Path) -> None:
    storage = LocalStorageAdapter(tmp_path)
    assert storage.put_bytes("user_1/book.txt", b"book") == "user_1/book.txt"
    assert storage.read_bytes("user_1/book.txt") == b"book"
    assert storage.read_bytes(str(tmp_path / "user_1" / "book.txt")) == b"book"
    with pytest.raises(RuntimeError):
        storage.read_bytes(str(tmp_path.parent / "private.txt"))


def test_s3_compatible_storage_keeps_logical_keys() -> None:
    client = FakeS3()
    storage = S3StorageAdapter(client, "edunova", "materials")
    assert storage.put_bytes("user_1/book.pdf", b"pdf", content_type="application/pdf") == "user_1/book.pdf"
    assert storage.read_bytes("user_1/book.pdf") == b"pdf"
    assert storage.exists("user_1/book.pdf") is True


def test_upload_type_rejects_mime_disguise_and_validates_ooxml() -> None:
    with pytest.raises(UploadSecurityError):
        validate_upload_type("notes.pdf", "application/pdf", b"plain text")

    document = Document()
    document.add_paragraph("无版权测试资料")
    stream = BytesIO()
    document.save(stream)
    assert "wordprocessingml" in validate_upload_type(
        "notes.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        stream.getvalue(),
    )


class FakeClamConnection:
    def __init__(self, result: bytes) -> None:
        self.result = result
        self.sent = bytearray()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def sendall(self, value: bytes) -> None:
        self.sent.extend(value)

    def recv(self, _size: int) -> bytes:
        return self.result


@pytest.mark.parametrize("result", [b"stream: Eicar-Signature FOUND\0", b"stream: scanner error\0"])
def test_clamav_rejects_virus_and_invalid_result(monkeypatch, result: bytes) -> None:
    connection = FakeClamConnection(result)
    monkeypatch.setattr("socket.create_connection", lambda *_args, **_kwargs: connection)
    with pytest.raises(UploadSecurityError):
        ClamAvScanner("clamav", 3310, 1).scan(b"sample")


def test_clamav_accepts_clean_stream(monkeypatch) -> None:
    connection = FakeClamConnection(b"stream: OK\0")
    monkeypatch.setattr("socket.create_connection", lambda *_args, **_kwargs: connection)
    ClamAvScanner("clamav", 3310, 1).scan(b"sample")
    assert connection.sent.startswith(b"zINSTREAM\0")
