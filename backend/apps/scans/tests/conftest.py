import io

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def private_media(settings, tmp_path):
    """Every scans test stores files in a throwaway folder."""
    settings.PRIVATE_MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def make_image():
    def _make(fmt="JPEG", size=(300, 200), mode="RGB", exif=False):
        color = (30, 160, 60) if mode == "RGB" else (30, 160, 60, 128)
        img = Image.new(mode, size, color)
        buf = io.BytesIO()
        kwargs = {}
        if exif:
            tags = Image.Exif()
            tags[0x010F] = "TestCameraMaker"
            tags[0x0131] = "TestSoftware"
            tags[0x010E] = "private description"
            kwargs["exif"] = tags
        img.save(buf, fmt, **kwargs)
        return buf.getvalue()

    return _make