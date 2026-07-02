# FastAPI Project Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the `jarvis-be` FastAPI backend as a bare, working skeleton: uv-managed dependencies, a `create_app()` app factory with CORS, a `/health` endpoint, config loading via pydantic-settings, and dev tooling (ruff, mypy, pytest, pre-commit).

**Architecture:** A single `app/` package with an app-factory pattern (`create_app()` in `app/main.py`) rather than a module-level `app` instance, so it's directly testable via FastAPI's `TestClient`. Config lives in one `Settings` class (`app/config.py`) backed by `pydantic-settings`, reading from `.env`. Routers live under `app/api/`, one file per resource — currently just `health.py`.

**Tech Stack:** Python 3.12, `uv` (dependency/venv management — not pip), FastAPI, uvicorn, pydantic-settings, ruff, mypy, pytest, pre-commit.

## Global Constraints

- Use `uv` for all dependency installation — never `pip install` directly.
- Python version pinned to 3.12 (`.python-version`).
- No business/domain logic in this plan — bare skeleton only (per spec's "Out of scope").
- Repo root is `jarvis-be/` (already `git init`'d as its own repo, per approved design spec at `docs/superpowers/specs/2026-07-01-fastapi-setup-design.md`).
- `app/` uses the app-factory pattern (`create_app()`), not a module-level `app`.
- CORS defaults must allow `http://localhost:3000` (jarvis-fe dev server).

---

### Task 1: Bootstrap the uv project

**Files:**
- Create: `jarvis-be/.gitignore`
- Create: `jarvis-be/.python-version`
- Create: `jarvis-be/pyproject.toml`

**Interfaces:**
- Produces: a `uv`-managed project at repo root with `fastapi`, `uvicorn[standard]`, `pydantic-settings` as runtime deps, and `ruff`, `mypy`, `pytest`, `httpx`, `pre-commit` as dev deps. Later tasks run `uv run <tool>` against this environment.

- [ ] **Step 1: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
```

- [ ] **Step 2: Create `.python-version`**

```
3.12
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "jarvis-be"
version = "0.1.0"
description = "Jarvis backend API"
requires-python = ">=3.12"
dependencies = []

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 4: Add runtime dependencies**

Run: `uv add fastapi "uvicorn[standard]" pydantic-settings`
Expected: command succeeds, `uv.lock` is created/updated, `pyproject.toml`'s `dependencies` list is populated, `.venv/` is created.

- [ ] **Step 5: Add dev dependencies**

Run: `uv add --dev ruff mypy pytest httpx pre-commit`
Expected: command succeeds, `pyproject.toml` gains a `[dependency-groups]` (or equivalent) `dev` entry listing all five packages, `uv.lock` updates.

- [ ] **Step 6: Verify the environment**

Run: `uv run python -c "import fastapi, uvicorn, pydantic_settings; print('ok')"`
Expected output: `ok`

- [ ] **Step 7: Commit**

```bash
git add .gitignore .python-version pyproject.toml uv.lock
git commit -m "chore: bootstrap uv project with fastapi deps"
```

---

### Task 2: Config module

**Files:**
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing from earlier tasks beyond the uv environment from Task 1.
- Produces: `app.config.Settings` — a `pydantic_settings.BaseSettings` subclass with fields `app_env: str` (default `"local"`) and `cors_origins: list[str]` (default `["http://localhost:3000"]`); and `app.config.settings`, a module-level `Settings()` instance. Task 3's `create_app()` imports `settings` from here.

- [ ] **Step 1: Create empty package files**

Create `app/__init__.py` (empty file) and `tests/__init__.py` (empty file).

- [ ] **Step 2: Write the failing test**

Create `tests/test_config.py`:

```python
from app.config import Settings


def test_settings_defaults():
    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.cors_origins == ["http://localhost:3000"]


def test_settings_reads_app_env_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (collection error) — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 4: Write `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add pydantic-settings config module"
```

---

### Task 3: App factory + health endpoint

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/health.py`
- Create: `app/main.py`
- Create: `tests/test_health.py`

**Interfaces:**
- Consumes: `app.config.settings` (from Task 2) — specifically `settings.cors_origins`.
- Produces: `app.main.create_app() -> FastAPI`, the app factory later used to run the server (`uvicorn app.main:create_app --factory`).

- [ ] **Step 1: Create `app/api/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test**

Create `tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_health.py -v`
Expected: FAIL (collection error) — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Write `app/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Write `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Jarvis API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)

    return app
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_health.py -v`
Expected: 1 passed

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -v`
Expected: 3 passed (2 from `test_config.py`, 1 from `test_health.py`)

- [ ] **Step 8: Commit**

```bash
git add app/api/__init__.py app/api/health.py app/main.py tests/test_health.py
git commit -m "feat: add app factory with CORS and /health endpoint"
```

---

### Task 4: Dev tooling (ruff, mypy, pre-commit)

**Files:**
- Modify: `pyproject.toml`
- Create: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: the `app/` and `tests/` source created in Tasks 1–3 (used as the lint/type-check target).
- Produces: nothing consumed by later tasks — this task's deliverable is the tooling itself passing cleanly.

- [ ] **Step 1: Add ruff and mypy config to `pyproject.toml`**

Append to the existing `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 2: Run ruff and fix any findings**

Run: `uv run ruff check .`
Expected: `All checks passed!` (if not, run `uv run ruff check --fix .` and re-run; fix anything ruff can't auto-fix)

Run: `uv run ruff format --check .`
Expected: no files need reformatting (if it lists files, run `uv run ruff format .`)

- [ ] **Step 3: Run mypy and fix any findings**

Run: `uv run mypy app`
Expected: `Success: no issues found in N source files`

If mypy reports missing type stubs for a third-party package, add an override block to `pyproject.toml` for that specific module (e.g. `[[tool.mypy.overrides]]` / `module = "<pkg>.*"` / `ignore_missing_imports = true`) rather than disabling strict mode globally.

- [ ] **Step 4: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: uv run mypy app
        language: system
        pass_filenames: false
        types: [python]
```

- [ ] **Step 5: Install the git hook and run it against all files**

Run: `uv run pre-commit install`
Expected: `pre-commit installed at .git/hooks/pre-commit`

Run: `uv run pre-commit run --all-files`
Expected: all three hooks show `Passed`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml
git commit -m "chore: add ruff, mypy, and pre-commit tooling"
```

---

### Task 5: Env example + README + manual smoke test

**Files:**
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: `app.main.create_app` (Task 3) for the manual smoke test.
- Produces: nothing consumed by other tasks — this is the final, user-facing task.

- [ ] **Step 1: Create `.env.example`**

```
APP_ENV=local
CORS_ORIGINS=["http://localhost:3000"]
```

- [ ] **Step 2: Create `README.md`**

```markdown
# jarvis-be

Python/FastAPI backend for Jarvis.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

\`\`\`bash
uv sync
cp .env.example .env
\`\`\`

## Run

\`\`\`bash
uv run uvicorn app.main:create_app --factory --reload
\`\`\`

Server runs at http://localhost:8000. Health check: http://localhost:8000/health

## Test

\`\`\`bash
uv run pytest
\`\`\`

## Lint & type-check

\`\`\`bash
uv run ruff check .
uv run ruff format .
uv run mypy app
\`\`\`
```

- [ ] **Step 3: Manual smoke test — start the server**

Run in background: `uv run uvicorn app.main:create_app --factory --reload &`
Wait for log line: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 4: Manual smoke test — hit the health endpoint**

Run: `curl -s http://127.0.0.1:8000/health`
Expected output: `{"status":"ok"}`

- [ ] **Step 5: Stop the server**

Run: `kill %1` (or find and kill the uvicorn process started in Step 3)

- [ ] **Step 6: Commit**

```bash
git add .env.example README.md
git commit -m "docs: add README and .env.example"
```

---

## Final Verification

- [ ] `uv run pytest -v` — all tests pass
- [ ] `uv run ruff check .` — clean
- [ ] `uv run mypy app` — clean
- [ ] `uv run pre-commit run --all-files` — all hooks pass
- [ ] Manual smoke test (Task 5, Steps 3–5) succeeds
