from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.errors import make_trace_id
from backend.app.core.config import Settings
from backend.app.models import ChatMessageAttachment, ChatSession, Material, User
from backend.app.services.storage import StorageAdapter, StorageError, build_storage, promote_storage_object
from backend.app.services.upload_security import (
    MalwareScanner,
    UploadSecurityError,
    build_malware_scanner,
    validate_upload_type,
)


MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_EDGE = 4096
MAX_IMAGE_PIXELS = 16_000_000
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg"}


class TutorAttachmentError(ValueError):
    pass


class TutorAttachmentNotFoundError(LookupError):
    pass


class TutorAttachmentService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        *,
        storage: StorageAdapter | None = None,
        scanner: MalwareScanner | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.material_storage = storage or build_storage(settings, kind="materials")
        self.legacy_storage = storage or build_storage(settings, kind="chat-attachments")
        self.storage = self.material_storage
        self.scanner = scanner or build_malware_scanner(settings)

    def upload(
        self,
        *,
        user: User,
        session_id: int,
        filename: str,
        declared_mime: str,
        content: bytes,
    ) -> ChatMessageAttachment:
        session = self._session(user.id, session_id)
        del session
        clean_name = Path(filename or "image.png").name[:255]
        extension = Path(clean_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise TutorAttachmentError("图片提问仅支持 PNG、JPG 和 JPEG。")
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise TutorAttachmentError("单张图片不能超过 4 MiB。")
        try:
            detected = validate_upload_type(clean_name, declared_mime, content)
            self.scanner.scan(content)
        except UploadSecurityError as exc:
            raise TutorAttachmentError(str(exc)) from exc
        if detected not in ALLOWED_MIME_TYPES:
            raise TutorAttachmentError("无法确认图片的真实类型。")
        normalized, mime_type, width, height = self._normalize_image(content, detected)
        digest = sha256(normalized).hexdigest()
        suffix = ".png" if mime_type == "image/png" else ".jpg"
        key = f"user_{user.id}/{uuid4().hex}{suffix}"
        temporary_key = f"tmp/materials/{uuid4().hex}-{Path(key).name}"
        try:
            self.material_storage.put_bytes(temporary_key, normalized, content_type=mime_type)
            stored_key = key
        except StorageError as exc:
            raise TutorAttachmentError("图片保存失败，请稍后重试。") from exc
        trace_id = make_trace_id()
        material = Material(
            user_id=user.id,
            filename=clean_name,
            content_type=mime_type,
            storage_path=stored_key,
            parse_status="uploaded",
            agent_trace_id=trace_id,
            extracted_text=None,
            metadata_json={
                "size_bytes": len(normalized),
                "size_label": self._format_size(len(normalized)),
                "extension": suffix.lstrip(".").upper(),
                "detail": "已入库，可用于图片提问",
                "agent_trace_id": trace_id,
                "storage_state": "pending_promotion",
                "temporary_storage_key": temporary_key,
                "width": width,
                "height": height,
            },
            ingestion_status="stored",
            outline_version=0,
            outline_json={},
            quality_json={},
        )
        try:
            self.db.add(material)
            self.db.flush()
            attachment = ChatMessageAttachment(
                user_id=user.id,
                session_id=session_id,
                message_id=None,
                material_id=material.id,
                storage_key=None,
                original_filename=clean_name,
                mime_type=mime_type,
                size_bytes=len(normalized),
                width=width,
                height=height,
                sha256=digest,
                status="pending",
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
            self.db.add(attachment)
            self.db.commit()
            self.db.refresh(attachment)
        except Exception:
            self.db.rollback()
            self.material_storage.delete(temporary_key)
            raise
        try:
            promote_storage_object(self.material_storage, temporary_key, stored_key, content_type=mime_type)
            material.metadata_json = {
                **(material.metadata_json or {}),
                "storage_state": "ready",
                "temporary_storage_key": None,
            }
            self.db.add(material)
            self.db.commit()
        except Exception:
            # 保留已提交的 material 及临时键，后续巡检可重试 promote。
            self.db.rollback()
        return attachment

    def attach_material(self, *, user: User, session_id: int, material_id: int) -> ChatMessageAttachment:
        self._session(user.id, session_id)
        material = self.db.scalar(
            select(Material).where(Material.id == material_id, Material.user_id == user.id)
        )
        if material is None or material.content_type not in ALLOWED_MIME_TYPES:
            raise TutorAttachmentNotFoundError("图片资料不存在、格式不支持或无权访问。")
        existing = self.db.scalar(
            select(ChatMessageAttachment).where(
                ChatMessageAttachment.user_id == user.id,
                ChatMessageAttachment.session_id == session_id,
                ChatMessageAttachment.material_id == material.id,
                ChatMessageAttachment.message_id.is_(None),
                ChatMessageAttachment.status == "pending",
            )
        )
        if existing is not None:
            return existing
        try:
            content = self.material_storage.read_bytes(material.storage_path)
            normalized, mime_type, width, height = self._normalize_image(content, material.content_type)
        except (StorageError, OSError) as exc:
            raise TutorAttachmentNotFoundError("图片资料文件不存在。") from exc
        attachment = ChatMessageAttachment(
            user_id=user.id,
            session_id=session_id,
            message_id=None,
            material_id=material.id,
            storage_key=None,
            original_filename=material.filename,
            mime_type=mime_type,
            size_bytes=len(normalized),
            width=width,
            height=height,
            sha256=sha256(normalized).hexdigest(),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def get(self, *, user: User, attachment_id: int) -> ChatMessageAttachment:
        attachment = self.db.scalar(
            select(ChatMessageAttachment).where(
                ChatMessageAttachment.id == attachment_id,
                ChatMessageAttachment.user_id == user.id,
            )
        )
        if attachment is None or attachment.status == "deleted":
            raise TutorAttachmentNotFoundError("图片不存在或已删除。")
        return attachment

    def read(self, *, user: User, attachment_id: int) -> tuple[ChatMessageAttachment, bytes]:
        attachment = self.get(user=user, attachment_id=attachment_id)
        if attachment.material_id is not None:
            material = self.db.scalar(
                select(Material).where(Material.id == attachment.material_id, Material.user_id == user.id)
            )
            if material is None:
                raise TutorAttachmentNotFoundError("图片资料不存在或已删除。")
            try:
                content = self.material_storage.read_bytes(material.storage_path)
                normalized, _, _, _ = self._normalize_image(content, material.content_type)
                return attachment, normalized
            except (StorageError, OSError) as exc:
                raise TutorAttachmentNotFoundError("图片资料文件不存在。") from exc
        if not attachment.storage_key:
            raise TutorAttachmentNotFoundError("图片不存在或已删除。")
        try:
            return attachment, self.legacy_storage.read_bytes(attachment.storage_key)
        except (StorageError, OSError) as exc:
            raise TutorAttachmentNotFoundError("图片文件不存在。") from exc

    def delete(self, *, user: User, attachment_id: int) -> ChatMessageAttachment:
        attachment = self.get(user=user, attachment_id=attachment_id)
        if attachment.material_id is None and attachment.storage_key:
            try:
                self.legacy_storage.delete(attachment.storage_key)
            except (StorageError, OSError):
                pass
        attachment.storage_key = None
        attachment.status = "deleted"
        attachment.expires_at = None
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def cleanup_expired_pending(self, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        attachments = list(
            self.db.scalars(
                select(ChatMessageAttachment)
                .where(
                    ChatMessageAttachment.status == "pending",
                    ChatMessageAttachment.expires_at < now,
                )
                .limit(limit)
            )
        )
        for attachment in attachments:
            if attachment.material_id is None and attachment.storage_key:
                try:
                    self.legacy_storage.delete(attachment.storage_key)
                except (StorageError, OSError):
                    pass
            self.db.delete(attachment)
        if attachments:
            self.db.commit()
        return len(attachments)

    def _session(self, user_id: int, session_id: int) -> ChatSession:
        session = self.db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
                ChatSession.archived_from_home.is_(False),
            )
        )
        if session is None:
            raise TutorAttachmentNotFoundError("会话不存在或无权访问。")
        return session

    @staticmethod
    def _format_size(size: int) -> str:
        if size >= 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        if size >= 1024:
            return f"{(size + 1023) // 1024} KB"
        return f"{size} B"

    @staticmethod
    def _normalize_image(content: bytes, detected_mime: str) -> tuple[bytes, str, int, int]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as probe:
                    if getattr(probe, "is_animated", False):
                        raise TutorAttachmentError("暂不支持动画图片。")
                    probe.verify()
                with Image.open(BytesIO(content)) as source:
                    width, height = source.size
                    if (
                        width <= 0
                        or height <= 0
                        or max(width, height) > MAX_IMAGE_EDGE
                        or width * height > MAX_IMAGE_PIXELS
                    ):
                        raise TutorAttachmentError("图片尺寸过大，最长边不能超过4096像素。")
                    image = ImageOps.exif_transpose(source)
                    width, height = image.size
                    output = BytesIO()
                    if detected_mime == "image/jpeg":
                        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
                        mime_type = "image/jpeg"
                    else:
                        if image.mode not in {"RGB", "RGBA"}:
                            image = image.convert("RGBA")
                        image.save(output, format="PNG", optimize=True)
                        mime_type = "image/png"
                    return output.getvalue(), mime_type, width, height
        except TutorAttachmentError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError) as exc:
            raise TutorAttachmentError("图片已损坏或尺寸不安全。") from exc
