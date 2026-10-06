# ForexAI — Backup & Restore

## What is backed up

Everything in PostgreSQL: accounts, signals, history, RAG evidence.
Code, `.env`, and Docker images are NOT in the backup (keep the ZIP +
a copy of `.env` in your password manager separately).

Data lives in the Docker volume `forexai_forexai-postgres-data`. It
survives `stop.bat`, reboots, updates, and re-unzipping this folder.
Only `reset.bat` / `docker compose down -v` destroys it.

## Backup (30 seconds)

Double-click `scripts\backup-forexai.bat`. A file appears:

```text
backups\forexai-YYYYMMDD-HHMMSS.sql
```

Copy it to USB / cloud regularly. Keep several generations; name includes
date+time so they sort themselves.

How often: daily if you trade daily, weekly minimum, always before
`reset.bat`, updates, or moving PCs.

## Restore (support job — read fully first)

1. `stop.bat` (stack must be stopped).
2. Start once so the volume exists, then stop again:

```bat
docker compose up -d postgres
docker compose stop postgres
```

   (Fresh-PC case: run `start.bat` once, then `stop.bat`.)
3. Restore the newest backup (adjust the filename):

```bat
docker exec -i forexai-postgres psql -U postgres -d forexai < backups\forexai-YYYYMMDD-HHMMSS.sql
```

4. `start.bat`, `status.bat` (want 5x `[OK]`), sign in and spot-check
   Signal History.

> The `psql` user/database default to `postgres`/`forexai`. If you changed
> `POSTGRES_USER`/`POSTGRES_DB` in `.env`, substitute your values.

## Moving to a new PC

1. Install Docker Desktop on the new PC.
2. Copy this whole folder (or fresh ZIP + your `.env` + newest backup).
3. `start.bat` once, `stop.bat`, restore as above, `start.bat`.
