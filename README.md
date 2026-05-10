# `image-cooker`

Python-based CLI tool that prepares web-optimized images.

## Usage

Point to a source directory or file that contains original JPEG or PNG images; `image-cooker` will process the given images in two stages:

1. Downscale so the longest edge is at most `--max-edge` pixels (1920 by default). Images smaller than the cap are not upscaled.
2. Convert the resulting images to WebP format at the chosen `--quality`.

```shell
image-cooker \
  --source <directory-or-file> \
  --target <directory-or-file> \
  [--max-edge 1920] \
  [--quality 80] \
  [--recursive / --no-recursive]
```

When `--source` is a directory, the source tree is mirrored under `--target`, with every output written as `.webp`.

## Install

```shell
pip install -e .
```

## Develop

```shell
pip install -e '.[dev]'
pytest
```
