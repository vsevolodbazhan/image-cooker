from __future__ import annotations

import sys
from pathlib import Path

import click

from image_cooker.processor import (
    ConversionResult,
    convert,
    discover,
    mirror_destination,
)


def _format_kb(num_bytes: int) -> str:
    return f"{num_bytes / 1024:,.1f} KB"


def _format_result(result: ConversionResult) -> str:
    src_w, src_h = result.src_size
    dst_w, dst_h = result.dst_size
    delta_pct = (
        (result.dst_bytes - result.src_bytes) / result.src_bytes * 100
        if result.src_bytes
        else 0.0
    )
    return (
        f"{result.src} -> {result.dst}  "
        f"{src_w}x{src_h} -> {dst_w}x{dst_h}  "
        f"{_format_kb(result.src_bytes)} -> {_format_kb(result.dst_bytes)} "
        f"({delta_pct:+.1f}%)"
    )


def _resolve_single_file_target(source: Path, target: Path) -> Path:
    if target.exists() and target.is_dir():
        return (target / source.name).with_suffix(".webp")
    return target.with_suffix(".webp")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--source",
    "source",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Source file or directory containing JPEG/PNG images.",
)
@click.option(
    "--target",
    "target",
    required=True,
    type=click.Path(path_type=Path),
    help="Output file (when source is a file) or directory (when source is a directory).",
)
@click.option(
    "--max-edge",
    "max_edge",
    type=click.IntRange(min=1),
    default=1920,
    show_default=True,
    help="Cap on the longest edge in pixels. Aspect ratio is preserved; smaller images are not upscaled.",
)
@click.option(
    "--quality",
    "quality",
    type=click.IntRange(min=1, max=100),
    default=80,
    show_default=True,
    help="WebP encoder quality (1-100).",
)
@click.option(
    "--recursive/--no-recursive",
    default=True,
    show_default=True,
    help="Recurse into subdirectories when source is a directory.",
)
def main(
    source: Path,
    target: Path,
    max_edge: int,
    quality: int,
    recursive: bool,
) -> None:
    """Prepare web-optimized WebP images from JPEG/PNG sources."""
    source = source.resolve()
    target = target.resolve() if target.is_absolute() else Path.cwd() / target

    if source.is_file():
        dst = _resolve_single_file_target(source, target)
        results, failures = _run([(source, dst)], max_edge, quality)
    else:
        pairs = [
            (path, mirror_destination(path, source, target))
            for path in discover(source, recursive)
        ]
        if not pairs:
            click.echo("No JPEG/PNG images found.", err=True)
            sys.exit(0)
        results, failures = _run(pairs, max_edge, quality)

    _print_totals(results, failures)
    if failures:
        sys.exit(1)


def _run(
    pairs: list[tuple[Path, Path]], max_edge: int, quality: int
) -> tuple[list[ConversionResult], list[tuple[Path, Exception]]]:
    results: list[ConversionResult] = []
    failures: list[tuple[Path, Exception]] = []
    for src, dst in pairs:
        try:
            result = convert(src, dst, max_edge, quality)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"FAIL {src}: {exc}", err=True)
            failures.append((src, exc))
            continue
        click.echo(_format_result(result))
        results.append(result)
    return results, failures


def _print_totals(
    results: list[ConversionResult], failures: list[tuple[Path, Exception]]
) -> None:
    total_src = sum(r.src_bytes for r in results)
    total_dst = sum(r.dst_bytes for r in results)
    delta_pct = (
        (total_dst - total_src) / total_src * 100 if total_src else 0.0
    )
    click.echo(
        f"\n{len(results)} converted, {len(failures)} failed. "
        f"Total: {_format_kb(total_src)} -> {_format_kb(total_dst)} "
        f"({delta_pct:+.1f}%)"
    )


if __name__ == "__main__":
    main()
