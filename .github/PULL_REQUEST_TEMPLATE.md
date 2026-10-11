# Pull request

## What changed

- ...

## Verification

- [ ] `python -m pytest -q` (forexai-ai) — paste result
- [ ] `ruff check app tests` — paste result
- [ ] `git diff --check` clean
- [ ] No secrets committed (`.env`, keys, tokens)

## Safety

- [ ] MT5 changes tested dry-run first (`MT5_DRY_RUN=true`)
- [ ] No generated artifacts force-added (`data/`, `*.joblib`, `*.log`)
