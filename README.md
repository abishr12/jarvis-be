# jarvis-be

Python/FastAPI backend for Jarvis.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

## Run

```bash
uv run uvicorn app.main:create_app --factory --reload
```

Server runs at http://localhost:8000. Health check: http://localhost:8000/health

## Test

```bash
uv run pytest
```

## Lint & type-check

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
```
