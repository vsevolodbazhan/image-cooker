from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

SUPPORTED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


@dataclass(frozen=True)
class ConversionResult:
    """Result metadata for one completed image conversion.

    Attributes
    ----------
    src
        Source image path.
    dst
        Destination WebP path.
    src_bytes
        Source file size in bytes.
    dst_bytes
        Destination file size in bytes.
    src_size
        Original image dimensions as ``(width, height)``.
    dst_size
        Final image dimensions as ``(width, height)``.
    """

    src: Path
    dst: Path
    src_bytes: int
    dst_bytes: int
    src_size: tuple[int, int]
    dst_size: tuple[int, int]


@dataclass(frozen=True)
class ImageDiscoverer:
    """Find source images supported by the conversion pipeline.

    Attributes
    ----------
    supported_suffixes
        Lowercase filename suffixes accepted as source images.
    """

    supported_suffixes: frozenset[str] = SUPPORTED_SUFFIXES

    def discover(self, source: Path, recursive: bool) -> Iterator[Path]:
        """Yield supported image files from a file or directory.

        Parameters
        ----------
        source
            Source file or directory to inspect.
        recursive
            Whether directory traversal should include nested directories.

        Yields
        ------
        Path
            Supported image paths in sorted traversal order.
        """

        if source.is_file():
            if self.supports(source):
                yield source
            return
        walker = source.rglob("*") if recursive else source.iterdir()
        for path in sorted(walker):
            if path.is_file() and self.supports(path):
                yield path

    def supports(self, path: Path) -> bool:
        """Return whether a path has a supported image suffix.

        Parameters
        ----------
        path
            Path to check.

        Returns
        -------
        bool
            ``True`` when the suffix is supported.
        """

        return path.suffix.lower() in self.supported_suffixes


@dataclass(frozen=True)
class ResizePolicy:
    """Aspect-preserving resize policy based on a maximum edge length.

    Attributes
    ----------
    max_edge
        Maximum allowed width or height in pixels.
    """

    max_edge: int

    def target_size(self, size: tuple[int, int]) -> tuple[int, int] | None:
        """Calculate resized dimensions for an image.

        Parameters
        ----------
        size
            Original dimensions as ``(width, height)``.

        Returns
        -------
        tuple[int, int] | None
            New dimensions, or ``None`` when no resize is needed.
        """

        width, height = size
        longest = max(width, height)
        if longest <= self.max_edge:
            return None
        scale = self.max_edge / longest
        if width >= height:
            return self.max_edge, max(1, round(height * scale))
        return max(1, round(width * scale)), self.max_edge

    def apply(self, image: Image.Image) -> Image.Image:
        """Resize an image when it exceeds ``max_edge``.

        Parameters
        ----------
        image
            Pillow image to resize.

        Returns
        -------
        Image.Image
            Original image when already small enough, otherwise a resized copy.
        """

        resized_dims = self.target_size(image.size)
        if resized_dims is None:
            return image
        return image.resize(resized_dims, Image.Resampling.LANCZOS)


class WebPModeNormalizer:
    """Normalize Pillow image modes before WebP encoding."""

    def normalize(self, image: Image.Image) -> Image.Image:
        """Convert an image to a WebP-compatible RGB or RGBA mode.

        Parameters
        ----------
        image
            Pillow image to normalize.

        Returns
        -------
        Image.Image
            Original image or converted image suitable for WebP output.
        """

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


@dataclass(frozen=True)
class WebPConversionSettings:
    """Settings that control WebP conversion.

    Attributes
    ----------
    max_edge
        Maximum allowed width or height in pixels.
    quality
        WebP encoder quality from 1 to 100.
    """

    max_edge: int
    quality: int

    @property
    def resize_policy(self) -> ResizePolicy:
        """Resize policy derived from the conversion settings.

        Returns
        -------
        ResizePolicy
            Policy using this settings object's ``max_edge``.
        """

        return ResizePolicy(self.max_edge)


@dataclass(frozen=True)
class WebPConverter:
    """Convert source images to resized WebP files.

    Attributes
    ----------
    settings
        Conversion settings for resizing and encoding.
    normalizer
        Mode normalizer used before WebP encoding.
    """

    settings: WebPConversionSettings
    normalizer: WebPModeNormalizer = WebPModeNormalizer()

    def convert(self, src: Path, dst: Path) -> ConversionResult:
        """Convert one source image to WebP.

        Parameters
        ----------
        src
            Source JPEG or PNG path.
        dst
            Destination WebP path.

        Returns
        -------
        ConversionResult
            Metadata describing the completed conversion.
        """

        dst.parent.mkdir(parents=True, exist_ok=True)
        src_bytes = src.stat().st_size
        with Image.open(src) as image:
            image.load()
            original_size = image.size
            image = self.settings.resize_policy.apply(image)
            image = self.normalizer.normalize(image)
            image.save(dst, format="WEBP", quality=self.settings.quality, method=6)
            final_size = image.size
        return ConversionResult(
            src=src,
            dst=dst,
            src_bytes=src_bytes,
            dst_bytes=dst.stat().st_size,
            src_size=original_size,
            dst_size=final_size,
        )


@dataclass(frozen=True)
class DestinationMapper:
    """Map source paths to mirrored WebP destination paths.

    Attributes
    ----------
    source_root
        Root directory paths are made relative to.
    target_root
        Root directory mirrored output paths are placed under.
    """

    source_root: Path
    target_root: Path

    def mirror(self, src: Path) -> Path:
        """Return the mirrored WebP destination for a source path.

        Parameters
        ----------
        src
            Source image path under ``source_root``.

        Returns
        -------
        Path
            Mirrored destination path under ``target_root`` with a ``.webp``
            suffix.
        """

        relative = src.relative_to(self.source_root)
        return (self.target_root / relative).with_suffix(".webp")


def discover(source: Path, recursive: bool) -> Iterator[Path]:
    return ImageDiscoverer().discover(source, recursive)


def compute_resize(size: tuple[int, int], max_edge: int) -> tuple[int, int] | None:
    return ResizePolicy(max_edge).target_size(size)


def _normalize_for_webp(image: Image.Image) -> Image.Image:
    return WebPModeNormalizer().normalize(image)


def convert(
    src: Path,
    dst: Path,
    max_edge: int,
    quality: int,
) -> ConversionResult:
    settings = WebPConversionSettings(max_edge=max_edge, quality=quality)
    return WebPConverter(settings).convert(src, dst)


def mirror_destination(src: Path, source_root: Path, target_root: Path) -> Path:
    return DestinationMapper(source_root, target_root).mirror(src)
