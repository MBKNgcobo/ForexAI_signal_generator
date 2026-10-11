# Contributing to ForexAI

This is a monorepo: `.NET API (ForexAI/) + Python AI service (forexai-ai/) +
React dashboard (forexai-dashboard/)`, wired by `docker-compose.yml`.
The Python service is the most active area — notes below focus there.

## Prerequisites

- Python 3.14, Node 20+, .NET 9 SDK, Docker Desktop + Compose v2.
- No real credentials needed for tests — the Python suite is hermetic.

## Python AI service (`forexai-ai/`)

```powershell
cd forexai-ai
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env   # fill in real values, never commit .env
```

Run / check:

```powershell
uvicorn app.main:app --reload          # service on :8000, /health stays up without keys
python -m pytest -q                    # 382 hermetic tests, no network
python -m pytest -q --cov=app          # with coverage
ruff check app tests                   # lint gate (CI runs this too)
```

Safety rules:

- Never commit `.env`, credentials, API keys, or `data/trade_log.jsonl`.
  Only `.env.example` is tracked.
- MT5 work stays on demo: keep `MT5_DRY_RUN=true` unless you have
  explicitly armed a demo run (`MT5_DRY_RUN=false` + `--live` dual-key).
- `TRADE_LOG_PATH` is redirected to a temp file in tests — do not point it
  at the real `data/trade_log.jsonl` in test code.
- Generated artifacts (`data/**`, `models/*.joblib`, `backups/`,
  `file-structure.txt`, `*.log`, `.coverage`) are git-ignored — do not force-add.

## Full stack

```powershell
copy .env.example .env   # at repo root, fill placeholders
docker compose up -d --build
docker compose config --quiet   # validates interpolation without starting
```

## Commits & PRs

- Conventional commits: `feat(mt5): ...`, `fix(ai): ...`, `docs: ...`, `chore: ...`.
- Keep PRs scoped; include `pytest` + `ruff` output for Python changes.
- Do not push, force-push, rewrite history, or change branch protection —
  maintainer handles remote operations.
