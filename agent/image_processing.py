"""Bounded image normalization — Tau image_processing.py port, lean-shim.

Lean proofs don't attach images, but the TUI paste/file-drop path can carry
them.  This port keeps Tau's constants and normalizer; when Pillow is not
installed it returns an ``ImageProcessingFailure`` (callers render an omitted
note instead of erroring).
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_SOURCE_IMAGE_BYTES = 50 * 1024 * 1024  # 50 MiB
DEFAULT_MAX_INLINE_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MiB
DEFAULT_MAX_SOURCE_IMAGE_PIXELS = 40_000_000  # 40 MP
DEFAULT_TARGET_LONG_SIDE = 1536

_PNG_KIND = "png"
_JPEG_KIND = "jpeg"
_WEBP_KIND = "webp"

try:
    from PIL import Image as _PILImage

    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PILImage = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False


@dataclass(frozen=True, slots=True)
class ImageProcessingFailure:
    reason: str


@dataclass(frozen=True, slots=True)
class ImageProcessingResult:
    kind: str
    data: bytes
    width: int
    height: int


def detect_image_kind(data: bytes) -> str | None:
    """Classify image bytes by magic header (PNG/JPEG/WebP/BMP)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _PNG_KIND
    if data.startswith(b"\xff\xd8"):
        return _JPEG_KIND
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return _WEBP_KIND
    if data.startswith(b"BM"):
        return "bmp"
    return None


def process_image(data: bytes, *, max_source_bytes: int = DEFAULT_MAX_SOURCE_IMAGE_BYTES) -> ImageProcessingResult | ImageProcessingFailure:
    """Normalize image bytes to a bounded PNG/JPEG/WebP (Tau process_image)."""
    kind = detect_image_kind(data)
    if kind is None:
        return ImageProcessingFailure("unrecognized image format")
    if len(data) > max_source_bytes:
        return ImageProcessingFailure("image exceeds the maximum source size limit")
    if not _PIL_AVAILABLE:
        return ImageProcessingFailure("Pillow not installed")
    try:
        image = _PILImage.open(__import__("io").BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001
        return ImageProcessingFailure(f"failed to decode image: {exc}")
    width, height = image.size
    if width * height > DEFAULT_MAX_SOURCE_IMAGE_PIXELS:
        return ImageProcessingFailure("image exceeds the maximum pixel limit")
    long_side = max(width, height)
    if long_side > DEFAULT_TARGET_LONG_SIDE:
        scale = DEFAULT_TARGET_LONG_SIDE / long_side
        new_width = max(1, round(width * scale))
        new_height = max(1, round(height * scale))
        image = image.resize((new_width, new_height), _PILImage.LANCZOS)
    output = __import__("io").BytesIO()
    if kind == _PNG_KIND:
        image.save(output, format="PNG")
    elif kind == _WEBP_KIND:
        image.save(output, format="WEBP")
    else:
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(output, format="JPEG")
    encoded = output.getvalue()
    if len(encoded) > DEFAULT_MAX_INLINE_IMAGE_BYTES:
        return ImageProcessingFailure("processed image exceeds the inline size limit")
    return ImageProcessingResult(kind=kind, data=encoded, width=width, height=height)