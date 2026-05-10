from __future__ import annotations

from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from image_cooker.cli import app

runner = CliRunner()


def _make_jpeg(path: Path, size: tuple[int, int], colour: tuple[int, int, int]) -> None:
    Image.new("RGB", size, colour).save(path, format="JPEG", quality=95)


def test_cli_parallel_processes_full_batch(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    expected = []
    for i in range(4):
        _make_jpeg(src_dir / f"img{i}.jpg", (1200, 800), (i * 40, 100, 200))
        expected.append(f"img{i}.webp")

    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--source",
            str(src_dir),
            "--target",
            str(out_dir),
            "--jobs",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out_dir.iterdir()) == expected
    for name in expected:
        with Image.open(out_dir / name) as img:
            assert img.format == "WEBP"


def test_cli_jobs_one_uses_sequential_path(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    _make_jpeg(src_dir / "a.jpg", (800, 600), (10, 20, 30))
    _make_jpeg(src_dir / "b.jpg", (800, 600), (40, 50, 60))

    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        ["--source", str(src_dir), "--target", str(out_dir), "--jobs", "1"],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "a.webp").exists()
    assert (out_dir / "b.webp").exists()
