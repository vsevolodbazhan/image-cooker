from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from image_cooker.processor import (
    ConversionResult,
    DestinationMapper,
    ImageDiscoverer,
    WebPConversionSettings,
    WebPConverter,
    convert,
)

DEFAULT_JOBS = os.cpu_count() or 1

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@dataclass(frozen=True)
class ConversionJob:
    """Planned source-to-destination conversion.

    Attributes
    ----------
    src
        Source image path.
    dst
        Destination WebP path.
    """

    src: Path
    dst: Path


@dataclass(frozen=True)
class ConversionFailure:
    """Failure raised while converting one source image.

    Attributes
    ----------
    src
        Source image path that failed.
    error
        Exception raised by the conversion attempt.
    """

    src: Path
    error: Exception


@dataclass(frozen=True)
class BatchOutcome:
    """Aggregated results for a conversion batch.

    Attributes
    ----------
    results
        Successful conversion results.
    failures
        Conversion failures.
    """

    results: list[ConversionResult]
    failures: list[ConversionFailure]


class ResultFormatter:
    """Format conversion results, failures, and totals for CLI output."""

    def format_result(self, result: ConversionResult) -> str:
        """Format one successful conversion result.

        Parameters
        ----------
        result
            Conversion result to format.

        Returns
        -------
        str
            Human-readable result line.
        """

        src_w, src_h = result.src_size
        dst_w, dst_h = result.dst_size
        delta_pct = self._delta_pct(result.src_bytes, result.dst_bytes)
        return (
            f"{result.src} -> {result.dst}  "
            f"{src_w}x{src_h} -> {dst_w}x{dst_h}  "
            f"{self.format_kb(result.src_bytes)} -> {self.format_kb(result.dst_bytes)} "
            f"({delta_pct:+.1f}%)"
        )

    def format_totals(self, results: list[ConversionResult], failure_count: int) -> str:
        """Format aggregate conversion totals.

        Parameters
        ----------
        results
            Successful conversion results.
        failure_count
            Number of failed conversions.

        Returns
        -------
        str
            Human-readable summary line.
        """

        total_src = sum(r.src_bytes for r in results)
        total_dst = sum(r.dst_bytes for r in results)
        delta_pct = self._delta_pct(total_src, total_dst)
        return (
            f"\n{len(results)} converted, {failure_count} failed. "
            f"Total: {self.format_kb(total_src)} -> {self.format_kb(total_dst)} "
            f"({delta_pct:+.1f}%)"
        )

    def format_failure(self, failure: ConversionFailure) -> str:
        """Format one conversion failure.

        Parameters
        ----------
        failure
            Conversion failure to format.

        Returns
        -------
        str
            Human-readable failure line.
        """

        return f"FAIL {failure.src}: {failure.error}"

    def format_kb(self, num_bytes: int) -> str:
        """Format bytes as kibibytes for CLI output.

        Parameters
        ----------
        num_bytes
            Byte count to format.

        Returns
        -------
        str
            Formatted kibibyte value.
        """

        return f"{num_bytes / 1024:,.1f} KB"

    def _delta_pct(self, before: int, after: int) -> float:
        return (after - before) / before * 100 if before else 0.0


class ConsoleReporter:
    """Write formatted conversion progress to the Typer console."""

    def __init__(self, formatter: ResultFormatter | None = None) -> None:
        """Create a console reporter.

        Parameters
        ----------
        formatter
            Formatter used to render output lines.
        """

        self.formatter = formatter or ResultFormatter()

    def result(self, result: ConversionResult) -> None:
        """Print one successful conversion result.

        Parameters
        ----------
        result
            Conversion result to print.
        """

        typer.echo(self.formatter.format_result(result))

    def failure(self, failure: ConversionFailure) -> None:
        """Print one conversion failure to stderr.

        Parameters
        ----------
        failure
            Conversion failure to print.
        """

        typer.echo(self.formatter.format_failure(failure), err=True)

    def totals(self, outcome: BatchOutcome) -> None:
        """Print aggregate conversion totals.

        Parameters
        ----------
        outcome
            Batch outcome to summarize.
        """

        typer.echo(self.formatter.format_totals(outcome.results, len(outcome.failures)))


class ConversionPlanner:
    """Plan conversion jobs from CLI source and target paths."""

    def __init__(self, discoverer: ImageDiscoverer | None = None) -> None:
        """Create a conversion planner.

        Parameters
        ----------
        discoverer
            Discoverer used to find supported images in directories.
        """

        self.discoverer = discoverer or ImageDiscoverer()

    def plan(self, source: Path, target: Path, recursive: bool) -> list[ConversionJob]:
        """Build conversion jobs for a file or directory source.

        Parameters
        ----------
        source
            Source file or directory.
        target
            Destination file path or output directory.
        recursive
            Whether directory discovery should include nested directories.

        Returns
        -------
        list[ConversionJob]
            Planned source-to-destination conversions.
        """

        if source.is_file():
            return [ConversionJob(source, self.single_file_target(source, target))]

        mapper = DestinationMapper(source, target)
        return [
            ConversionJob(path, mapper.mirror(path))
            for path in self.discoverer.discover(source, recursive)
        ]

    def single_file_target(self, source: Path, target: Path) -> Path:
        """Resolve the output path for single-file conversion.

        Parameters
        ----------
        source
            Source image path.
        target
            Destination file path or existing output directory.

        Returns
        -------
        Path
            Destination WebP path.
        """

        if target.exists() and target.is_dir():
            return (target / source.name).with_suffix(".webp")
        return target.with_suffix(".webp")


class BatchRunner:
    """Execute conversion jobs sequentially or in a process pool."""

    def __init__(self, reporter: ConsoleReporter | None = None) -> None:
        """Create a batch runner.

        Parameters
        ----------
        reporter
            Reporter used for progress and failure output.
        """

        self.reporter = reporter or ConsoleReporter()

    def run(
        self,
        jobs: list[ConversionJob],
        settings: WebPConversionSettings,
        worker_count: int,
    ) -> BatchOutcome:
        """Run a batch of conversion jobs.

        Parameters
        ----------
        jobs
            Conversion jobs to execute.
        settings
            Conversion settings applied to each job.
        worker_count
            Number of worker processes to use. A value of 1 runs sequentially.

        Returns
        -------
        BatchOutcome
            Successful results and failures.
        """

        if worker_count <= 1 or len(jobs) <= 1:
            return self._run_sequential(jobs, settings)
        return self._run_parallel(jobs, settings, worker_count)

    def _run_sequential(
        self, jobs: list[ConversionJob], settings: WebPConversionSettings
    ) -> BatchOutcome:
        results: list[ConversionResult] = []
        failures: list[ConversionFailure] = []
        converter = WebPConverter(settings)
        for job in jobs:
            try:
                result = converter.convert(job.src, job.dst)
            except Exception as exc:  # noqa: BLE001
                failure = ConversionFailure(job.src, exc)
                self.reporter.failure(failure)
                failures.append(failure)
                continue
            self.reporter.result(result)
            results.append(result)
        return BatchOutcome(results, failures)

    def _run_parallel(
        self,
        jobs: list[ConversionJob],
        settings: WebPConversionSettings,
        worker_count: int,
    ) -> BatchOutcome:
        results: list[ConversionResult] = []
        failures: list[ConversionFailure] = []
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            future_to_src = {
                pool.submit(convert, job.src, job.dst, settings.max_edge, settings.quality): job.src
                for job in jobs
            }
            for future in as_completed(future_to_src):
                src = future_to_src[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    failure = ConversionFailure(src, exc)
                    self.reporter.failure(failure)
                    failures.append(failure)
                    continue
                self.reporter.result(result)
                results.append(result)
        return BatchOutcome(results, failures)


def _resolve_single_file_target(source: Path, target: Path) -> Path:
    return ConversionPlanner().single_file_target(source, target)


@app.command(help="Prepare web-optimized WebP images from JPEG/PNG sources.")
def main(
    source: Annotated[
        Path,
        typer.Option(
            "--source",
            exists=True,
            help="Source file or directory containing JPEG/PNG images.",
        ),
    ],
    target: Annotated[
        Path,
        typer.Option(
            "--target",
            help="Output file (when source is a file) or directory (when source is a directory).",
        ),
    ],
    max_edge: Annotated[
        int,
        typer.Option(
            "--max-edge",
            min=1,
            help=(
                "Cap on the longest edge in pixels. Aspect ratio is preserved; "
                "smaller images are not upscaled."
            ),
        ),
    ] = 2560,
    quality: Annotated[
        int,
        typer.Option(
            "--quality",
            min=1,
            max=100,
            help="WebP encoder quality (1-100).",
        ),
    ] = 85,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive/--no-recursive",
            help="Recurse into subdirectories when source is a directory.",
        ),
    ] = True,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            "-j",
            min=1,
            help=(
                "Number of worker processes. 1 disables parallelism. "
                "Defaults to the host CPU count."
            ),
        ),
    ] = DEFAULT_JOBS,
) -> None:
    source = source.resolve()
    target = target.resolve() if target.is_absolute() else Path.cwd() / target
    settings = WebPConversionSettings(max_edge=max_edge, quality=quality)
    planner = ConversionPlanner()
    reporter = ConsoleReporter()

    planned_jobs = planner.plan(source, target, recursive)
    if not planned_jobs:
        typer.echo("No JPEG/PNG images found.", err=True)
        raise typer.Exit(0)

    outcome = BatchRunner(reporter).run(planned_jobs, settings, jobs)
    reporter.totals(outcome)
    if outcome.failures:
        raise typer.Exit(1)


def _run(
    pairs: list[tuple[Path, Path]], max_edge: int, quality: int, jobs: int
) -> tuple[list[ConversionResult], list[tuple[Path, Exception]]]:
    planned_jobs = [ConversionJob(src, dst) for src, dst in pairs]
    settings = WebPConversionSettings(max_edge=max_edge, quality=quality)
    outcome = BatchRunner().run(planned_jobs, settings, jobs)
    return _legacy_outcome(outcome)


def _run_sequential(
    pairs: list[tuple[Path, Path]], max_edge: int, quality: int
) -> tuple[list[ConversionResult], list[tuple[Path, Exception]]]:
    planned_jobs = [ConversionJob(src, dst) for src, dst in pairs]
    settings = WebPConversionSettings(max_edge=max_edge, quality=quality)
    return _legacy_outcome(BatchRunner()._run_sequential(planned_jobs, settings))


def _run_parallel(
    pairs: list[tuple[Path, Path]], max_edge: int, quality: int, jobs: int
) -> tuple[list[ConversionResult], list[tuple[Path, Exception]]]:
    planned_jobs = [ConversionJob(src, dst) for src, dst in pairs]
    settings = WebPConversionSettings(max_edge=max_edge, quality=quality)
    return _legacy_outcome(BatchRunner()._run_parallel(planned_jobs, settings, jobs))


def _print_totals(results: list[ConversionResult], failures: list[tuple[Path, Exception]]) -> None:
    outcome = BatchOutcome(
        results,
        [ConversionFailure(src, error) for src, error in failures],
    )
    ConsoleReporter().totals(outcome)


def _format_kb(num_bytes: int) -> str:
    return ResultFormatter().format_kb(num_bytes)


def _format_result(result: ConversionResult) -> str:
    return ResultFormatter().format_result(result)


def _legacy_outcome(
    outcome: BatchOutcome,
) -> tuple[list[ConversionResult], list[tuple[Path, Exception]]]:
    return outcome.results, [(failure.src, failure.error) for failure in outcome.failures]
