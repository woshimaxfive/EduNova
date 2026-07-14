from __future__ import annotations

from io import BytesIO
import socket
import struct
from typing import Protocol
from zipfile import BadZipFile, ZipFile

import puremagic

from backend.app.core.config import Settings


class UploadSecurityError(ValueError):
    pass


class MalwareScanner(Protocol):
    def scan(self, content: bytes) -> None: ...


class DisabledMalwareScanner:
    def scan(self, content: bytes) -> None:
        del content


class ClamAvScanner:
    def __init__(self, host: str, port: int, timeout_seconds: float) -> None:
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    def scan(self, content: bytes) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as connection:
                connection.sendall(b"zINSTREAM\0")
                for offset in range(0, len(content), 64 * 1024):
                    chunk = content[offset : offset + 64 * 1024]
                    connection.sendall(struct.pack("!I", len(chunk)) + chunk)
                connection.sendall(struct.pack("!I", 0))
                result = connection.recv(4096).decode("utf-8", errors="replace")
        except (OSError, TimeoutError) as exc:
            raise UploadSecurityError("文件安全扫描服务不可用，已拒绝上传。") from exc
        if " FOUND" in result:
            raise UploadSecurityError("文件未通过安全扫描，已拒绝上传。")
        if " OK" not in result:
            raise UploadSecurityError("文件安全扫描结果无效，已拒绝上传。")


def build_malware_scanner(settings: Settings) -> MalwareScanner:
    if not settings.clamav_enabled:
        return DisabledMalwareScanner()
    return ClamAvScanner(settings.clamav_host, settings.clamav_port, settings.clamav_timeout_seconds)


def validate_upload_type(filename: str, declared_mime: str, content: bytes) -> str:
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    declared = (declared_mime or "application/octet-stream").split(";", 1)[0].strip().lower()
    if extension in {".txt", ".md", ".markdown"}:
        if b"\x00" in content[:8192]:
            raise UploadSecurityError("文件内容与文本扩展名不匹配。")
        try:
            content[:8192].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadSecurityError("文本资料必须使用 UTF-8 编码。") from exc
        detected = "text/plain"
    else:
        try:
            detected = str(puremagic.from_string(content, mime=True))
        except puremagic.PureError as exc:
            raise UploadSecurityError("无法确认上传文件的真实类型。") from exc

    if extension in {".docx", ".pptx"}:
        expected_folder = "word/" if extension == ".docx" else "ppt/"
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
        except BadZipFile as exc:
            raise UploadSecurityError("Office 文件容器无效。") from exc
        if not any(name.startswith(expected_folder) for name in names):
            raise UploadSecurityError("Office 文件内容与扩展名不匹配。")
        detected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if extension == ".docx" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    expected = {
        ".pdf": {"application/pdf"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".webp": {"image/webp"},
        ".doc": {"application/x-ole-storage", "application/msword"},
        ".ppt": {"application/x-ole-storage", "application/vnd.ms-powerpoint"},
    }
    if extension in expected and detected not in expected[extension]:
        raise UploadSecurityError("文件内容与扩展名不匹配。")
    declared_expected = {
        ".pdf": {"application/pdf"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".webp": {"image/webp"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        ".txt": {"text/plain"},
        ".md": {"text/plain", "text/markdown"},
        ".markdown": {"text/plain", "text/markdown"},
    }
    if declared not in {"", "application/octet-stream"} and extension in declared_expected and declared not in declared_expected[extension]:
        raise UploadSecurityError("声明的 MIME 类型与文件扩展名不匹配。")
    return detected
