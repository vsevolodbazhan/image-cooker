# `image-cooker`

Python-based CLI tool that prepares web-optimized images.

## Usage

Point to a source directory or file that contains original JPEG or PNG images; `image-cooker` will process the given images in two stages:

1. Downscale so the longest edge is at most `--max-edge` pixels (2560 by default). Images smaller than the cap are not upscaled.
2. Convert the resulting images to WebP format at the chosen `--quality` (85 by default).

```shell
image-cooker \
  --source <directory-or-file> \
  --target <directory-or-file> \
  [--max-edge 2560] \
  [--quality 85] \
  [--recursive / --no-recursive]
```

When `--source` is a directory, the source tree is mirrored under `--target`, with every output written as `.webp`.

## Install

```shell
uv sync
uv run image-cooker --source <path> --target <path>
```

## Develop

```shell
uv sync
uv run pytest
```
