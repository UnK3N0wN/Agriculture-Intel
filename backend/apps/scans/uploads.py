import hashlib
import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import APIException

MIN_SIDE = 64  # pixels


class UploadRejected(APIException):
    status_code = 400
    default_detail = "This image can't be used."
    default_code = "invalid_image"

    def __init__(self, detail=None, code=None, status_code=None):
        super().__init__(detail=detail, code=code)
        if status_code is not None:
            self.status_code = status_code


@dataclass(frozen=True)
class SanitizedImage:
    data: bytes
    mime: str
    sha256: str
    width: int
    height: int


def detect_format(head):
    """Identify the image type from its first bytes ("magic bytes"), ignoring name and Content-Type."""
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    return None


def _too_large():
    limit_mb = settings.UPLOAD_MAX_BYTES / (1024 * 1024)
    return UploadRejected(
        f"This file is too large. The maximum size is {limit_mb:.0f} MB.",
        code="file_too_large",
        status_code=413,
    )


def _unsupported():
    return UploadRejected(
        "Unsupported file type. Please upload a JPEG, PNG or WebP photo.",
        code="unsupported_type",
    )


def _flatten_to_rgb(img):
    """Return a brand-new RGB image with no metadata attached."""
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if has_alpha:
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    rgb = img.convert("RGB")
    fresh = Image.new("RGB", rgb.size)
    fresh.paste(rgb)
    return fresh


def sanitize_image(upload):
    max_bytes = settings.UPLOAD_MAX_BYTES

    size = getattr(upload, "size", None)
    if size and size > max_bytes:
        raise _too_large()
    data = upload.read(max_bytes + 1)  # never read more than the limit
    if len(data) > max_bytes:
        raise _too_large()

    detected = detect_format(data[:16])
    if detected is None:
        raise _unsupported()

    try:
        with Image.open(io.BytesIO(data), formats=[detected]) as img:
            if img.format != detected:
                raise _unsupported()

            width, height = img.size  # header only, nothing decoded yet
            if width * height > settings.UPLOAD_MAX_PIXELS:
                raise UploadRejected(
                    "This image has too many pixels. Please upload a smaller photo.",
                    code="image_dimensions_too_large",
                )
            if min(width, height) < MIN_SIDE:
                raise UploadRejected(
                    f"This image is too small. Both sides must be at least {MIN_SIDE} pixels.",
                    code="image_too_small",
                )

            img.load()  # full decode: catches truncated or corrupt files
            oriented = ImageOps.exif_transpose(img)  # apply phone rotation BEFORE stripping EXIF
            clean = _flatten_to_rgb(oriented)
    except UploadRejected:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        raise UploadRejected(
            "We couldn't read this image. It may be damaged. Please try another photo.",
            code="unreadable_image",
        )

    max_side = settings.UPLOAD_MAX_SIDE
    clean.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    clean.save(out, format="JPEG", quality=88, optimize=True)  # no exif= and no icc_profile= passed
    result = out.getvalue()
    return SanitizedImage(
        data=result,
        mime="image/jpeg",
        sha256=hashlib.sha256(result).hexdigest(),
        width=clean.width,
        height=clean.height,
    )


def _safe_join(root, relative):
    root_resolved = Path(root).resolve()
    target = (root_resolved / relative).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError("Path escapes the private media folder.")
    return target


def store_image(user_id, sanitized):
    """Save to the private folder under a random name. Returns the RELATIVE path."""
    relative = Path("scans") / str(user_id) / f"{uuid.uuid4().hex}.jpg"
    target = _safe_join(settings.PRIVATE_MEDIA_ROOT, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as fh:  # "x" = fail if the file already exists
        fh.write(sanitized.data)
    try:
        os.chmod(target, 0o640)
    except OSError:
        pass  # Windows ignores Unix permissions
    return relative.as_posix()


def read_stored_image(relative_path):
    return _safe_join(settings.PRIVATE_MEDIA_ROOT, relative_path).read_bytes()


def delete_stored_image(relative_path):
    try:
        _safe_join(settings.PRIVATE_MEDIA_ROOT, relative_path).unlink(missing_ok=True)
    except (ValueError, OSError):
        pass