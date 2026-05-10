from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

SUPPORTED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


@dataclass(frozen=True)
class ConversionResult:
    src: Path
    dst: Path
    src_bytes: int
    dst_bytes: int
    src_size: tuple[int, int]
    dst_size: tuple[int, int]


def discover(source: Path, recursive: bool) -> Iterator[Path]:
    if source.is_file():
        if source.suffix.lower() in SUPPORTED_SUFFIXES:
            yield source
        return
    walker = source.rglob("*") if recursive else source.iterdir()
    for path in sorted(walker):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def compute_resize(size: tuple[int, int], max_edge: int) -> tuple[int, int] | None:
    width, height = size
    longest = max(width, height)
    if longest <= max_edge:
        return None
    scale = max_edge / longest
    if width >= height:
        return max_edge, max(1, round(height * scale))
    return max(1, round(width * scale)), max_edge


def _normalize_for_webp(image: Image.Image) -> Image.Image:
    if image.mode in ("RGB", "RGBA"):
        return image
    if image.mode == "P":
        target = "RGBA" if "transparency" in image.info else "RGB"
        return image.convert(target)
    if image.mode == "LA":
        return image.convert("RGBA")
    if image.mode in ("L", "1", "I", "F", "CMYK", "YCbCr"):
        return image.convert("RGB")
    return image.convert("RGBA")


def convert(
    src: Path,
    dst: Path,
    max_edge: int,
    quality: int,
) -> ConversionResult:
    dst.parent.mkdir(parents=True, exist_ok=True)
    src_bytes = src.stat().st_size
    with Image.open(src) as image:
        image.load()
        original_size = image.size
        resized_dims = compute_resize(original_size, max_edge)
        if resized_dims is not None:
            image = image.resize(resized_dims, Image.Resampling.LANCZOS)
        image = _normalize_for_webp(image)
        image.save(dst, format="WEBP", quality=quality, method=6)
        final_size = image.size
    return ConversionResult(
        src=src,
        dst=dst,
        src_bytes=src_bytes,
        dst_bytes=dst.stat().st_size,
        src_size=original_size,
        dst_size=final_size,
    )


def mirror_destination(src: Path, source_root: Path, target_root: Path) -> Path:
    relative = src.relative_to(source_root)
    return (target_root / relative).with_suffix(".webp")
