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

Unit tests cover deterministic behavior such as workflow validation, stream
events, and HTTP serialization. Provider integration tests should be kept
separate because they require API credentials and make nondeterministic network
calls. Once representative workflow prompts and scoring criteria exist, add
LangSmith evaluations to measure semantic workflow quality and compare prompt
or model changes over time.

## Lint & type-check

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
```
