# FastAPI Project Setup — Design

Date: 2026-07-01

## Purpose

Scaffold `jarvis-be`, the Python/FastAPI backend for Jarvis, as its own git
repository under the `Jarvis` umbrella folder (sibling to `jarvis-fe`). This
is a bare skeleton: project structure, dependency management, config
loading, a health-check endpoint, and dev tooling. No business/agent logic
yet — that will be specced separately once this foundation exists.

## Repo

`jarvis-be` becomes its own git repository (already initialized), matching
`jarvis-fe`'s setup as an independent repo under the `Jarvis` umbrella
folder.

## Project structure

```
jarvis-be/
├── .git/
├── .gitignore
├── .env.example
├── .python-version            # pins 3.12
├── .pre-commit-config.yaml
├── pyproject.toml             # uv-managed deps, ruff/mypy/pytest config
├── uv.lock
├── README.md
└── app/
    ├── __init__.py
    ├── main.py                # FastAPI app factory + entrypoint
    ├── config.py               # pydantic-settings Settings class
    └── api/
        ├── __init__.py
        └── health.py           # GET /health router
└── tests/
    ├── __init__.py
    └── test_health.py
```

No `services/`, `models/`, or `agents/` directories yet — those get
scaffolded when their first real feature is specced, to avoid empty
speculative structure.

## Dependency management

- `uv` manages the project and virtual environment (not pip).
- Python pinned to 3.12 via `.python-version`.
- Runtime deps: `fastapi`, `uvicorn[standard]`, `pydantic-settings`.
- Dev deps: `ruff`, `pytest`, `mypy`, `pre-commit`.
- All deps locked via `uv.lock`, committed to the repo.

## App & config

- `app/main.py` exposes `create_app() -> FastAPI`, an app factory that
  configures middleware (CORS) and mounts routers. Using a factory (rather
  than a module-level `app`) keeps the app testable and avoids import-time
  side effects.
- `app/config.py` defines `Settings(BaseSettings)` (from
  `pydantic-settings`), loaded from a `.env` file. Fields:
  - `app_env: str` — e.g. `local`, `production` (default `local`)
  - `cors_origins: list[str]` — default `["http://localhost:3000"]`
- `.env.example` is committed with placeholder/default values (no secrets).
  `.env` itself is gitignored.

## CORS

`create_app()` wires `CORSMiddleware` using `settings.cors_origins`, so the
`jarvis-fe` Next.js dev server (`http://localhost:3000`) can call this API
out of the box during local development.

## Health endpoint

`GET /health` (in `app/api/health.py`) returns `{"status": "ok"}`. Used to
verify the server runs, and as the smoke-test target for
`tests/test_health.py` via FastAPI's `TestClient`.

## Dev tooling

- **ruff**: lint + format (replaces black/isort/flake8), configured in
  `pyproject.toml`.
- **mypy**: static type checking, configured in `pyproject.toml`. Since the
  project leans on pydantic typing throughout, mypy is enabled from the
  start rather than added later.
- **pytest**: test runner, run via `uv run pytest`.
- **pre-commit**: `.pre-commit-config.yaml` runs ruff (lint + format) and
  mypy on commit.

## Running it

Local dev: `uv run uvicorn app.main:create_app --factory --reload`.
Documented in the README.

## Out of scope (future specs)

- Business/domain logic (agents, users, deployments).
- Database/ORM setup.
- Auth.
- Docker/deployment configuration.
- Makefile/justfile convenience scripts (can be added later if desired).
