from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from image_cooker.cli import app

runner = CliRunner()
ASSETS_DIR = Path(__file__).parent / "assets"


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


def test_cli_processes_asset_images_and_cleans_output(tmp_path: Path):
    source_images = sorted(ASSETS_DIR.glob("*.jpg"))
    source_snapshot = sorted(path.name for path in ASSETS_DIR.iterdir())
    out_dir = tmp_path / "cooked"

    assert source_images

    try:
        result = runner.invoke(
            app,
            [
                "--source",
                str(ASSETS_DIR),
                "--target",
                str(out_dir),
                "--max-edge",
                "640",
                "--quality",
                "75",
                "--jobs",
                "1",
            ],
        )

        assert result.exit_code == 0, result.output
        outputs = sorted(out_dir.glob("*.webp"))
        assert [path.stem for path in outputs] == [path.stem for path in source_images]

        for output in outputs:
            with Image.open(output) as image:
                assert image.format == "WEBP"
                assert max(image.size) <= 640
    finally:
        if out_dir.exists():
            shutil.rmtree(out_dir)

    assert not out_dir.exists()
    assert sorted(path.name for path in ASSETS_DIR.iterdir()) == source_snapshot
