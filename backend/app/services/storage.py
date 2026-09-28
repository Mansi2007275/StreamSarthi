"""Photo handling: validate -> re-encode (strips EXIF, neutralises weird files) -> private bucket."""

import io
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_SIDE = 1280
Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard


def process_image(raw: bytes, content_type: str | None, max_mb: int) -> bytes:
    """Return a clean JPEG (max 1280px, no EXIF). Raises AppError on bad input."""
    if content_type not in ALLOWED_MIME:
        raise AppError(415, "UNSUPPORTED_MEDIA", "Only JPG, PNG or WEBP photos are allowed")
    if len(raw) > max_mb * 1024 * 1024:
        raise AppError(413, "FILE_TOO_LARGE", f"Photo must be under {max_mb} MB")
    if not raw:
        raise AppError(422, "EMPTY_FILE", "Photo is empty")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise AppError(422, "INVALID_IMAGE", "File is not a valid image") from e

    img = ImageOps.exif_transpose(img)  # respect phone rotation before we drop EXIF
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)  # no exif= -> metadata stripped
    return out.getvalue()


def photo_path(user_id: str, observation_id: str, indicator_id: str) -> str:
    return f"{user_id}/{observation_id}/{indicator_id}.jpg"


class StorageProtocol(Protocol):
    def upload(self, path: str, data: bytes) -> None: ...
    def signed_url(self, path: str) -> str | None: ...


class SupabaseStorage:
    def __init__(self, client, bucket: str, expiry: int):
        self.bucket = client.storage.from_(bucket)
        self.expiry = expiry

    def upload(self, path: str, data: bytes) -> None:
        self.bucket.upload(path, data, {"content-type": "image/jpeg", "upsert": "true"})

    def signed_url(self, path: str) -> str | None:
        try:
            res = self.bucket.create_signed_url(path, self.expiry)
        except Exception:
            return None
        if isinstance(res, dict):
            return res.get("signedURL") or res.get("signedUrl")
        return getattr(res, "signed_url", None)


def get_storage() -> StorageProtocol:
    from app.services.db import get_supabase

    s = get_settings()
    return SupabaseStorage(get_supabase(), s.storage_bucket, s.signed_url_expiry_seconds)
