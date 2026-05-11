# Agent Instructions

These instructions apply to the whole repository.

## Engineering Style

- Follow an OOP-first design principle. Prefer cohesive classes with explicit
  responsibilities over loosely grouped procedural helpers.
- Add NumPy-style docstrings to classes and public methods.

## Quality Checks

- Run formatters and linters before finishing changes.
- Use the project tooling from `pyproject.toml`; at minimum run:

```sh
uv run ruff format src tests
uv run ruff check src tests
uv run pyright
uv run pytest
```

## Commits

- Use Conventional Commits for commit messages.
- Examples:
  - `feat: add batch resize settings`
  - `fix: preserve alpha when converting pngs`
  - `refactor: organize image processing around objects`
