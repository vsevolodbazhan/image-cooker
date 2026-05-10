from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from image_cooker.processor import (
    SUPPORTED_SUFFIXES,
    compute_resize,
    convert,
    discover,
    mirror_destination,
)


def _make_jpeg(path: Path, size: tuple[int, int]) -> Path:
    img = Image.new("RGB", size, color=(180, 90, 40))
    img.save(path, format="JPEG", quality=95)
    return path


def _make_png_rgba(path: Path, size: tuple[int, int]) -> Path:
    img = Image.new("RGBA", size, color=(0, 0, 0, 0))
    img.save(path, format="PNG")
    return path


@pytest.mark.parametrize(
    "size, max_edge, expected",
    [
        ((4000, 3000), 1920, (1920, 1440)),
        ((3000, 4000), 1920, (1440, 1920)),
        ((2000, 2000), 1920, (1920, 1920)),
        ((1920, 1080), 1920, None),
        ((800, 600), 1920, None),
        ((1921, 1), 1920, (1920, 1)),
    ],
)
def test_compute_resize(size, max_edge, expected):
    assert compute_resize(size, max_edge) == expected


def test_discover_directory_recursive(tmp_path: Path):
    (tmp_path / "nested").mkdir()
    a = _make_jpeg(tmp_path / "a.jpg", (100, 100))
    b = _make_jpeg(tmp_path / "nested" / "b.JPEG", (100, 100))
    c = _make_png_rgba(tmp_path / "nested" / "c.png", (100, 100))
    (tmp_path / "skip.txt").write_text("nope")
    (tmp_path / "skip.gif").write_bytes(b"\x00")

    found = sorted(discover(tmp_path, recursive=True))
    assert found == sorted([a, b, c])


def test_discover_directory_non_recursive(tmp_path: Path):
    (tmp_path / "nested").mkdir()
    a = _make_jpeg(tmp_path / "a.jpg", (100, 100))
    _make_jpeg(tmp_path / "nested" / "b.jpg", (100, 100))

    found = list(discover(tmp_path, recursive=False))
    assert found == [a]


def test_discover_single_file(tmp_path: Path):
    f = _make_jpeg(tmp_path / "single.jpg", (100, 100))
    assert list(discover(f, recursive=True)) == [f]


def test_discover_single_unsupported_file(tmp_path: Path):
    f = tmp_path / "x.gif"
    f.write_bytes(b"\x00")
    assert list(discover(f, recursive=True)) == []


def test_supported_suffixes_lowercase():
    assert all(s == s.lower() for s in SUPPORTED_SUFFIXES)


def test_convert_resizes_large_jpeg(tmp_path: Path):
    src = _make_jpeg(tmp_path / "big.jpg", (3888, 5175))
    dst = tmp_path / "out.webp"

    result = convert(src, dst, max_edge=1920, quality=80)

    assert dst.exists()
    with Image.open(dst) as out:
        assert out.format == "WEBP"
        assert out.size == (1443, 1920)
    assert result.dst_size == (1443, 1920)
    assert result.src_size == (3888, 5175)
    assert result.dst_bytes < result.src_bytes


def test_convert_does_not_upscale(tmp_path: Path):
    src = _make_jpeg(tmp_path / "small.jpg", (800, 600))
    dst = tmp_path / "out.webp"

    result = convert(src, dst, max_edge=1920, quality=80)

    with Image.open(dst) as out:
        assert out.size == (800, 600)
    assert result.dst_size == (800, 600)


def test_convert_preserves_alpha(tmp_path: Path):
    src = _make_png_rgba(tmp_path / "alpha.png", (2400, 1200))
    dst = tmp_path / "out.webp"

    convert(src, dst, max_edge=1200, quality=80)

    with Image.open(dst) as out:
        assert out.mode in ("RGBA",)
        assert out.size == (1200, 600)


def test_convert_creates_parent_dir(tmp_path: Path):
    src = _make_jpeg(tmp_path / "a.jpg", (100, 100))
    dst = tmp_path / "deeply" / "nested" / "out.webp"

    convert(src, dst, max_edge=1920, quality=80)

    assert dst.exists()


def test_mirror_destination(tmp_path: Path):
    source_root = tmp_path / "src"
    target_root = tmp_path / "out"
    src = source_root / "sub" / "photo.JPG"

    dst = mirror_destination(src, source_root, target_root)

    assert dst == target_root / "sub" / "photo.webp"
