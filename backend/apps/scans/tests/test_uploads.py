import io
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.scans.uploads import (
    UploadRejected,
    read_stored_image,
    sanitize_image,
    store_image,
)


def upload(data, name="photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


def test_exif_metadata_is_stripped(make_image):
    original = make_image("JPEG", exif=True)
    assert len(Image.open(io.BytesIO(original)).getexif()) > 0  # sanity: input HAS metadata

    result = sanitize_image(upload(original))
    out = Image.open(io.BytesIO(result.data))
    assert out.format == "JPEG"
    assert len(out.getexif()) == 0
    assert result.mime == "image/jpeg"


def test_file_type_comes_from_bytes_not_from_name_or_content_type(make_image):
    png_bytes = make_image("PNG")
    result = sanitize_image(upload(png_bytes, name="leaf.jpg", content_type="image/jpeg"))
    assert Image.open(io.BytesIO(result.data)).format == "JPEG"


def test_accepts_webp(make_image):
    result = sanitize_image(upload(make_image("WEBP"), "leaf.webp", "image/webp"))
    assert result.width == 300 and result.height == 200


def test_png_with_transparency_becomes_rgb_jpeg(make_image):
    result = sanitize_image(upload(make_image("PNG", mode="RGBA"), "leaf.png", "image/png"))
    out = Image.open(io.BytesIO(result.data))
    assert out.format == "JPEG"
    assert out.mode == "RGB"


def test_rejects_fake_image(make_image):
    fake = upload(b"MZ this is definitely not an image " * 10, "evil.jpg", "image/jpeg")
    with pytest.raises(UploadRejected) as exc:
        sanitize_image(fake)
    assert exc.value.get_codes() == "unsupported_type"


def test_rejects_truncated_image(make_image):
    data = make_image("JPEG")
    with pytest.raises(UploadRejected) as exc:
        sanitize_image(upload(data[: len(data) // 2]))
    assert exc.value.get_codes() == "unreadable_image"


def test_rejects_file_over_byte_limit(make_image, settings):
    settings.UPLOAD_MAX_BYTES = 200
    with pytest.raises(UploadRejected) as exc:
        sanitize_image(upload(make_image("JPEG", size=(400, 400))))
    assert exc.value.status_code == 413
    assert exc.value.get_codes() == "file_too_large"


def test_rejects_too_many_pixels(make_image, settings):
    settings.UPLOAD_MAX_PIXELS = 10_000
    with pytest.raises(UploadRejected) as exc:
        sanitize_image(upload(make_image("JPEG", size=(200, 200))))
    assert exc.value.get_codes() == "image_dimensions_too_large"


def test_rejects_tiny_image(make_image):
    with pytest.raises(UploadRejected) as exc:
        sanitize_image(upload(make_image("JPEG", size=(30, 30))))
    assert exc.value.get_codes() == "image_too_small"


def test_large_images_are_shrunk(make_image, settings):
    settings.UPLOAD_MAX_SIDE = 1600
    result = sanitize_image(upload(make_image("JPEG", size=(3200, 1800))))
    assert (result.width, result.height) == (1600, 900)


def test_store_image_uses_random_names_inside_private_root(make_image, settings):
    sanitized = sanitize_image(upload(make_image("JPEG")))
    first = store_image(7, sanitized)
    second = store_image(7, sanitized)

    assert first != second
    for rel in (first, second):
        assert rel.startswith("scans/7/") and rel.endswith(".jpg")
        assert (Path(settings.PRIVATE_MEDIA_ROOT) / rel).is_file()
    assert read_stored_image(first) == sanitized.data


@pytest.mark.parametrize("bad_path", ["../../etc/passwd", "/etc/passwd", "scans/../../secret.txt"])
def test_read_stored_image_blocks_path_traversal(bad_path):
    with pytest.raises(ValueError):
        read_stored_image(bad_path)