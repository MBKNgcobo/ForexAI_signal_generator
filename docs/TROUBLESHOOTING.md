# ForexAI — Troubleshooting (plain English)

## Quick triage

1. Is Docker Desktop running (whale icon steady)? If not, start it, wait,
   run `start.bat` again.
2. Run `status.bat`. Note which line says `[FAIL]`.
3. Run `logs.bat`. Read the last 20 lines.
4. Match below. Still stuck → `collect-diagnostics.bat`, send the folder.

## The 10 common cases

| # | Symptom | Cause | Fix |
| --- | --- | --- | --- |
| 1 | `Docker is not installed` | No Docker | Install Docker Desktop, reboot, retry |
| 2 | `Docker is installed but not running` | Whale still starting | Wait until steady, retry |
| 3 | `These values in .env are still placeholders` | `.env` unfinished | Notepad opens automatically — fill the 4 values, save, retry |
| 4 | `Port 80/8080 is already in use` | Another app owns it | Set `DASHBOARD_PORT` (e.g. 8080/8090) in `.env`, run `start.bat` |
| 5 | `docker compose up failed` | Bad `.env` value or port clash | Read the error above it; fix `.env`; retry |
| 6 | `Services did not all become healthy` | Slow first build or bad key | `status.bat` shows which; `logs.bat` names it; wait 3 min + retry |
| 7 | Dashboard `[FAIL]`, others `[OK]` | nginx still starting / wrong port | Wait 30 s, check `DASHBOARD_PORT` in `.env` matches the URL |
| 8 | `API ready [FAIL]` | DB or AI unreachable, or keys missing | `logs.bat`: look for `Jwt`, `ConnectionString`, `POSTGRES_PASSWORD` |
| 9 | Login works, analysis fails / 503 | Missing `TWELVE_DATA_API_KEY` / `OPENROUTER_API_KEY` | `AI ready` line + `/ready` names the variable; fix `.env`, `start.bat` |
| 10 | Blank dashboard / `/api` 502 | API still building | Wait, `status.bat` until API `[OK]`, hard-refresh (Ctrl+F5) |

## Useful commands (only if support asks)

```bat
scripts\status-forexai.bat       health + exited containers
scripts\logs-forexai.bat         last 100 lines + saves logs.txt
collect-diagnostics.bat          support bundle (secrets redacted)
docker compose ps                container table
docker compose logs --tail 50    last 50 lines
```

## Data safety reminders

- `stop.bat` / `docker compose down` NEVER delete data.
- `reset.bat` / `docker compose down -v` ALWAYS delete data. The script
  makes you type `RESET` and urges a backup first.
- If Docker Desktop itself was reset / fresh PC: `start.bat` once,
  `stop.bat`, restore newest `backups\*.sql` (see BACKUP_AND_RESTORE.md).
