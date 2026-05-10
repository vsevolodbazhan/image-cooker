# image-cooker

> Bake your blog photos. Downscale once, re-encode as WebP, ship to the web.

![CI](https://img.shields.io/github/actions/workflow/status/vsevolodbazhan/image-cooker/ci.yml?branch=main&label=ci)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Built with Typer](https://img.shields.io/badge/CLI-Typer-informational)
![Image library](https://img.shields.io/badge/imaging-Pillow-orange)

`image-cooker` is a small, opinionated Python CLI that takes the giant
JPEG/PNG files your camera produces and turns them into web-optimised
WebP images that don't sink your Lighthouse score.

It does one thing — and it does it well: **shrink, then re-encode.**

---

## Why

Modern cameras output 4000×6000-pixel JPEGs at 5–15 MB each. Browsers
ignore the DPI metadata embedded in those files; the only things that
matter for web performance are the **pixel dimensions** and the **codec
efficiency**. So `image-cooker` only attacks those two levers:

1. **Downscale** so the longest edge is at most 2560 px (configurable).
   Aspect ratio is preserved; smaller images are never upscaled.
2. **Re-encode** as WebP at quality 85 (configurable), with EXIF
   stripped to keep files small and avoid leaking camera metadata.

A real-world photo blog post dropped from **140 MB to 47 MB (-66%)**
with no perceptible quality loss, just by running the defaults.

---

## Features

- **Single binary CLI** powered by [Typer](https://typer.tiangolo.com/) —
  rich `--help`, validated input, sensible exit codes.
- **JPEG and PNG in, WebP out.** Alpha channel preserved automatically
  for transparent PNGs.
- **Mirrors directory trees.** Point it at `~/Pictures/blog/` and get
  back the same structure under your target folder, every file as
  `.webp`.
- **Single-file mode** when you just need to cook one photo.
- **Recursive or shallow.** Toggle with `--recursive / --no-recursive`.
- **Lanczos resampling** for the downscale step — the same algorithm
  professional image tools use.
- **Per-file resilience.** A bad file is logged and skipped; the rest of
  the batch keeps going. The process exits non-zero if anything failed.
- **Parallel by default.** Uses every CPU core to fan out the batch via
  a process pool. Tunable with `--jobs N`, or set to `1` for sequential.
- **Zero hidden state.** No config files, no caches, no surprise
  network calls. What you pass on the command line is what you get.

---

## Quick start

```sh
uv run image-cooker --source ~/Pictures/blog --target ./optimised
```

Output:

```
~/Pictures/blog/IMG_0001.jpg -> ./optimised/IMG_0001.webp  3888x5175 -> 1923x2560  4.2 MB -> 1.4 MB (-66.7%)
~/Pictures/blog/IMG_0002.jpg -> ./optimised/IMG_0002.webp  6000x4000 -> 2560x1707  6.1 MB -> 2.0 MB (-67.2%)
...

42 converted, 0 failed. Total: 140.0 MB -> 47.0 MB (-66.4%)
```

---

## Installation

### From source (current)

```sh
git clone https://github.com/vsevolodbazhan/image-cooker.git
cd image-cooker
uv sync
```

Then run via `uv run image-cooker ...` or activate the venv and use
the `image-cooker` console script directly.

### Requirements

- Python **3.10+**
- [uv](https://docs.astral.sh/uv/) (recommended), or any
  PEP 517–compatible installer (pip, pipx, hatch, …)

---

## Usage

```text
Usage: image-cooker [OPTIONS]

  Prepare web-optimized WebP images from JPEG/PNG sources.
```

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--source PATH` | *(required)* | Source file or directory containing JPEG/PNG images. |
| `--target PATH` | *(required)* | Output file (when source is a file) or directory (when source is a directory). |
| `--max-edge INT` | `2560` | Cap on the longest edge in pixels. Aspect ratio is preserved; smaller images are not upscaled. |
| `--quality INT` | `85` | WebP encoder quality, 1–100. |
| `--recursive / --no-recursive` | `recursive` | Recurse into subdirectories when source is a directory. |
| `--jobs INT`, `-j INT` | host CPU count | Number of worker processes. `1` disables parallelism. |
| `-h`, `--help` | | Show the help message and exit. |

### Examples

**Optimise a whole blog photo folder, recursively:**

```sh
uv run image-cooker --source ~/Pictures/blog --target ~/Sites/cooked
```

**Cook a single hero image with custom settings:**

```sh
uv run image-cooker \
  --source hero.jpg \
  --target hero.webp \
  --max-edge 1920 \
  --quality 88
```

**Build a smaller thumbnail set in a sibling directory:**

```sh
uv run image-cooker \
  --source ~/Pictures/blog \
  --target ./thumbs \
  --max-edge 960 \
  --quality 75
```

**Process only the top level (no recursion):**

```sh
uv run image-cooker --source ./photos --target ./out --no-recursive
```

---

## How it works

The pipeline is deliberately small and easy to reason about:

1. **Discover** — walk `--source` (recursive by default), collect
   `*.jpg`, `*.jpeg`, `*.png` (case-insensitive). Non-image files are
   ignored.
2. **Plan output paths** — mirror the source tree under `--target`,
   replacing each file's extension with `.webp`. In single-file mode,
   `--target` is treated as the output file path.
3. **Resize** — if the longest edge exceeds `--max-edge`, downscale
   with Lanczos resampling and the aspect ratio preserved. Smaller
   images pass through untouched.
4. **Normalise mode** for the WebP encoder:
   - Opaque sources (JPEG, opaque PNG) → `RGB`
   - Transparent sources (RGBA PNG, palette+transparency) → `RGBA`
5. **Encode** with `format="WEBP", quality=<q>, method=6`. EXIF is
   intentionally **not** carried over.
6. **Report** — one line per file plus a final summary.

That's it. There is no caching, no parallelism, no hidden config — the
code is short enough to read in a sitting.

---

## Tuning guide

The defaults (`--max-edge 2560`, `--quality 85`) target high-quality
photo blogs on retina displays. If you want to push further:

- **Smaller files, same look:** drop `--quality` to `82` or `80`. Below
  ~75 you'll start seeing artefacts on smooth gradients (skies, skin).
- **Smaller files for thumbnails or grid layouts:** drop `--max-edge`.
  `1920` is fine for most blogs; `1280` is great for non-retina layouts.
- **No-compromise archive copy:** raise `--quality` to `92` and
  `--max-edge` to `3200`. Files get noticeably bigger but quality is
  effectively transparent.

---

## Development

```sh
git clone https://github.com/vsevolodbazhan/image-cooker.git
cd image-cooker
uv sync
uv run pre-commit install   # one-time: wire up commit + push hooks
uv run pytest
```

Quality gates run automatically:

- **On `git commit`** — `ruff check --fix`, `ruff format`, `pyright`
- **On `git push`** — `pytest`

To run them manually: `uv run pre-commit run --all-files`.

Project layout:

```
image-cooker/
├── pyproject.toml              # PEP 621 + PEP 735 dep groups
├── uv.lock                     # reproducible env
├── src/image_cooker/
│   ├── __init__.py
│   ├── __main__.py             # python -m image_cooker
│   ├── cli.py                  # Typer command, orchestration
│   └── processor.py            # discovery + image transform
└── tests/
    ├── test_cli.py             # CLI integration tests
    └── test_processor.py       # pipeline unit tests
```

The whole project is intentionally tiny — fewer than 250 lines of
Python — and fully covered by `pytest`. Contributions welcome.

---

## License

[MIT](LICENSE)

---

## Acknowledgements

- [Pillow](https://python-pillow.org/) for the imaging primitives
- [Typer](https://typer.tiangolo.com/) for the delightful CLI
- [uv](https://docs.astral.sh/uv/) for fast, reproducible Python envs
