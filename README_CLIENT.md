# ForexAI — Client README

> If you only read one file, read `START_HERE.txt` next to this one.

## What you received

A complete trading-signal platform that runs on your own PC with Docker:

| Part | What it does | You open |
| --- | --- | --- |
| Dashboard | Charts, signals, history | `http://localhost` (or your `DASHBOARD_PORT`) |
| API | Accounts, signal storage | Runs in the background |
| AI service | Market data + AI analysis | Runs in the background |
| Database | All your data | Runs in the background, backed up via script |

## Start / stop in 30 seconds

```text
start.bat    start (checks Docker, config, health, opens browser)
status.bat   is everything healthy? (want 5x [OK])
stop.bat     stop - data is kept
restart.bat  quick restart (use start.bat after editing .env)
logs.bat     recent logs + saves logs.txt for support
collect-diagnostics.bat   builds a support bundle (no secrets inside)
reset.bat    DELETE everything (backup first, asks for RESET)
```

Docker Desktop must be running before `start.bat` (whale icon steady).

## Configuration (one file: `.env`)

`start.bat` creates `.env` from `.env.example` on first run. You edit 4 values:

| Value | What to put | Where you get it |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | Any long random text you make up | Your head / password manager |
| `JWT_KEY` | A different long random text (min 32 chars) | Your head / password manager |
| `TWELVE_DATA_API_KEY` | Market-data key | https://twelvedata.com free account |
| `OPENROUTER_API_KEY` | AI reasoning key | https://openrouter.ai sign in |

Optional host ports (`DASHBOARD_PORT=80`, `API_PORT=8080`, `AI_PORT=8001`,
`POSTGRES_PORT=5434`): change only if a port is taken. Port 80 needs
Administrator approval on first use; if that bothers you set
`DASHBOARD_PORT=8080` and open `http://localhost:8080`.
Full variable reference: `docs/ENVIRONMENT_VARIABLES.md`.

**Never** send `.env` to anyone and never commit it. It holds passwords/keys.

## Your data

- Lives in the Docker volume `forexai_forexai-postgres-data`. Survives
  `stop.bat`, reboots, updates, even deleting + re-unzipping this folder.
- Only `reset.bat` / `docker compose down -v` deletes it. Never run that
  without a backup.
- Backup: double-click `scripts\backup-forexai.bat` → `backups\*.sql`.
  Copy that file to USB/cloud regularly.
- Restore is a support job (see `docs/BACKUP_AND_RESTORE.md`).

## When something is wrong

1. Run `status.bat` — every `[FAIL]` line tells you which part is down.
2. Run `logs.bat` — the bottom lines usually name the cause in plain words.
3. Check `docs/TROUBLESHOOTING.md` for the 10 common cases.
4. Still stuck: run `collect-diagnostics.bat`, zip the created
   `diagnostics\forexai-*` folder, send it + a screenshot + what you did.

## Never do these

- Never run `docker compose down -v` or a command pasted from a chat.
- Never delete `backups\` or "clean up" this folder.
- Never share `.env`, API keys, or screenshots containing them.
- Never set `DASHBOARD_PORT` to a port another app uses.

More: `docs/USER_GUIDE.md` (using the app),
`docs/INSTALLATION_GUIDE.md` (fresh install),
`docs/TROUBLESHOOTING.md`, `docs/BACKUP_AND_RESTORE.md`, `docs/FAQ.md`.
