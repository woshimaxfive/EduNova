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

from backend.app.core.config import Settings
from backend.app.models import ChatMessageAttachment, ChatSession, User
from backend.app.services.storage import StorageAdapter, StorageError, build_storage
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
        self.storage = storage or build_storage(settings, kind="chat-attachments")
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
        key = f"users/{user.id}/sessions/{session_id}/{uuid4().hex}{suffix}"
        try:
            stored_key = self.storage.put_bytes(key, normalized, content_type=mime_type)
        except StorageError as exc:
            raise TutorAttachmentError("图片保存失败，请稍后重试。") from exc
        attachment = ChatMessageAttachment(
            user_id=user.id,
            session_id=session_id,
            message_id=None,
            storage_key=stored_key,
            original_filename=clean_name,
            mime_type=mime_type,
            size_bytes=len(normalized),
            width=width,
            height=height,
            sha256=digest,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        try:
            self.db.add(attachment)
            self.db.commit()
            self.db.refresh(attachment)
        except Exception:
            self.db.rollback()
            self.storage.delete(stored_key)
            raise
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
        if not attachment.storage_key:
            raise TutorAttachmentNotFoundError("图片不存在或已删除。")
        try:
            return attachment, self.storage.read_bytes(attachment.storage_key)
        except (StorageError, OSError) as exc:
            raise TutorAttachmentNotFoundError("图片文件不存在。") from exc

    def delete(self, *, user: User, attachment_id: int) -> ChatMessageAttachment:
        attachment = self.get(user=user, attachment_id=attachment_id)
        if attachment.storage_key:
            try:
                self.storage.delete(attachment.storage_key)
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
            if attachment.storage_key:
                try:
                    self.storage.delete(attachment.storage_key)
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
