from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from backend.app.core.config import Settings


class StorageError(RuntimeError):
    pass


class StorageAdapter(Protocol):
    def put_bytes(self, key: str, content: bytes, *, content_type: str | None = None) -> str: ...
    def read_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def promote(self, source_key: str, destination_key: str) -> str: ...
    def local_path(self, key: str) -> Path | None: ...


class LocalStorageAdapter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def put_bytes(self, key: str, content: bytes, *, content_type: str | None = None) -> str:
        del content_type
        normalized = self._logical_key(key)
        target = self._resolve(normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return normalized

    def read_bytes(self, key: str) -> bytes:
        return self._resolve_compatible(key).read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._resolve_compatible(key).is_file()
        except StorageError:
            return False

    def local_path(self, key: str) -> Path | None:
        return self._resolve_compatible(key)

    def delete(self, key: str) -> None:
        path = self._resolve_compatible(key)
        if path.is_file():
            path.unlink()

    def promote(self, source_key: str, destination_key: str) -> str:
        source = self._resolve_compatible(source_key)
        destination_key = self._logical_key(destination_key)
        destination = self._resolve(destination_key)
        if not source.is_file():
            raise StorageError("临时对象不存在，无法提升为正式对象。")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        return destination_key

    def _resolve_compatible(self, key: str) -> Path:
        candidate = Path(key)
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if not resolved.is_relative_to(self.root):
                raise StorageError("旧文件路径不在允许的存储根目录内。")
            return resolved
        return self._resolve(self._logical_key(key))

    def _resolve(self, key: str) -> Path:
        resolved = (self.root / Path(key)).resolve()
        if not resolved.is_relative_to(self.root):
            raise StorageError("对象键越过存储根目录。")
        return resolved

    @staticmethod
    def _logical_key(key: str) -> str:
        path = PurePosixPath(str(key).replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise StorageError("对象键无效。")
        return path.as_posix()


class S3StorageAdapter:
    def __init__(self, client: Any, bucket: str, prefix: str = "") -> None:
        if not bucket:
            raise StorageError("S3 bucket 未配置。")
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def put_bytes(self, key: str, content: bytes, *, content_type: str | None = None) -> str:
        logical = LocalStorageAdapter._logical_key(key)
        kwargs = {"Bucket": self.bucket, "Key": self._object_key(logical), "Body": content}
        if content_type:
            kwargs["ContentType"] = content_type
        self.client.put_object(**kwargs)
        return logical

    def read_bytes(self, key: str) -> bytes:
        logical = LocalStorageAdapter._logical_key(key)
        response = self.client.get_object(Bucket=self.bucket, Key=self._object_key(logical))
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._object_key(LocalStorageAdapter._logical_key(key)))
            return True
        except Exception:
            return False

    def local_path(self, key: str) -> Path | None:
        del key
        return None

    def delete(self, key: str) -> None:
        logical = LocalStorageAdapter._logical_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=self._object_key(logical))

    def promote(self, source_key: str, destination_key: str) -> str:
        source = LocalStorageAdapter._logical_key(source_key)
        destination = LocalStorageAdapter._logical_key(destination_key)
        self.client.copy_object(
            Bucket=self.bucket,
            Key=self._object_key(destination),
            CopySource={"Bucket": self.bucket, "Key": self._object_key(source)},
        )
        self.client.delete_object(Bucket=self.bucket, Key=self._object_key(source))
        return destination

    def _object_key(self, logical: str) -> str:
        return f"{self.prefix}/{logical}" if self.prefix else logical


def build_storage(settings: Settings, *, kind: str) -> StorageAdapter:
    roots = {
        "materials": settings.material_storage_dir,
        "chat-attachments": settings.chat_attachment_storage_dir,
        "exports": settings.export_dir,
    }
    root = roots.get(kind, settings.export_dir)
    if settings.storage_backend == "local":
        return LocalStorageAdapter(root)
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
    )
    return S3StorageAdapter(client, settings.s3_bucket, prefix=kind)


def promote_storage_object(storage: StorageAdapter, source_key: str, destination_key: str, *, content_type: str | None = None) -> str:
    """Promote an object, retaining compatibility with narrow in-memory test adapters.

    Production adapters implement server-side/local promotion. The fallback is
    deliberately copy-then-delete so it never loses the only temporary copy.
    """
    promote = getattr(storage, "promote", None)
    if callable(promote):
        return str(promote(source_key, destination_key))
    content = storage.read_bytes(source_key)
    stored = storage.put_bytes(destination_key, content, content_type=content_type)
    storage.delete(source_key)
    return stored
