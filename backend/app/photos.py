"""Checking uploaded photos (outfit and profile pictures)."""

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

# What a photo file starts with, so only real images are accepted.
IMAGE_SIGNATURES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png"}


async def read_photo(photo: UploadFile) -> tuple[bytes, str]:
    """The photo's bytes and type. JPEG or PNG, at most 5 MB."""
    limit = get_settings().max_photo_bytes
    content = await photo.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The photo is too big (max 5 MB).")
    content_type = next(
        (kind for sig, kind in IMAGE_SIGNATURES.items() if content.startswith(sig)), None
    )
    if content_type is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use a JPEG or PNG photo.")
    return content, content_type
