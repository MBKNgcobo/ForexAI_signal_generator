# ForexAI — Client Installation Guide (Windows)

> **Just using the app?** You don't need this document — see the
> plain-English [user guide](./user-guide.md).

This guide installs the complete ForexAI platform on one Windows PC. No cloud
accounts are needed beyond two free API keys.

## 1. What you need

| Requirement | Notes |
| --- | --- |
| Windows 10/11, 64-bit | Administrator rights once (to install Docker) |
| Docker Desktop | https://docs.docker.com/desktop/setup/windows/install/ |
| ~8 GB free disk | Docker images + database |
| Internet | Needed for the install, updates and live analysis |
| Twelve Data API key | https://twelvedata.com — free tier is enough (market candles) |
| OpenRouter API key | https://openrouter.ai — free tier is enough (AI reasoning) |

## 2. Install Docker Desktop

1. Download and install from the link above.
2. Start Docker Desktop and wait until its whale icon in the taskbar is steady.
3. If Windows asks to enable WSL 2 / Virtual Machine Platform, accept and
   reboot once.

## 3. Get the ForexAI files

Unzip the delivered package (or `git clone` the repository) into a permanent
folder, for example `C:\ForexAI`. The scripts are in the `scripts\` subfolder
and expect to run from there.

## 4. Configure your keys

Open a terminal in the package folder and run:

```bat
scripts\start-forexai.bat
```

On the first run the script creates a `.env` file from the template and opens
it in Notepad. Fill in at least these four values:

| Value | Where it comes from |
| --- | --- |
| `POSTGRES_PASSWORD` | Make one up — any long random text |
| `JWT_KEY` | Make one up — any long random text, different from the above |
| `TWELVE_DATA_API_KEY` | twelvedata.com → free account → API key |
| `OPENROUTER_API_KEY` | openrouter.ai → sign in → API keys |

Save the file, close Notepad, run the script again. It refuses to continue
while it still sees `replace-me` placeholders — this prevents a stack that
starts but can never answer a request.

## 5. First start

The script now builds four Docker images (first run takes roughly 5–15
minutes) and waits until every service reports **healthy**. It then opens
**http://localhost** in your browser, where you should see the ForexAI
dashboard.

## 6. Create the first account

The dashboard does not include a self-service sign-up screen. The easy way —
double-click **`scripts\add-user-forexai.bat`** and answer the three
questions (email, display name, password); the script handles everything and
reports any problem in plain English.

Alternative — one PowerShell command (change the values first):

```powershell
Invoke-RestMethod -Uri http://localhost:8080/api/Auth/register -Method Post `
  -ContentType 'application/json' `
  -Body '{"email":"owner@example.com","displayName":"Owner","password":"ChangeMe-Str0ng!"}'
```

Then log in at http://localhost with that email and password. Further users
are created the same way.

## 7. Everyday use

| I want to... | Do this |
| --- | --- |
| Start | `scripts\start-forexai.bat` |
| Check everything is healthy | `scripts\status-forexai.bat` |
| Stop (data is kept) | `scripts\stop-forexai.bat` |
| Apply a change to `.env` | edit the file, then run the start script again |
| Back up the database | `scripts\backup-forexai.bat` → file in `backups\` |
| Update to a newer version | `scripts\update-forexai.bat` |
| Collect logs for support | `docker compose logs --tail 100 > logs.txt` |

## 8. Your data

- All data (accounts, signals, history) lives in the Docker volume
  `forexai_forexai-postgres-data`. It survives restarts, updates and even
  deleting + re-unzipping the package folder. The volume is only destroyed by
  `docker compose down -v` — never run that command.
- Backups are plain SQL files in `backups\`. Copy them off this PC regularly.
- To restore a backup: stop the stack (`scripts\stop-forexai.bat`), run

  ```bat
  docker exec -i forexai-postgres psql -U postgres -d forexai < backups\forexai-YYYYMMDD-HHMMSS.sql
  ```

  then start the stack again.
- If Docker Desktop itself is ever reset (fresh PC), start the stack once,
  stop it, and restore your newest backup as above.

## 9. Ports

| Service | Default | Change with |
| --- | --- | --- |
| Dashboard (browser) | http://localhost | `DASHBOARD_PORT` in `.env` |
| .NET API | 127.0.0.1:8080 | `API_PORT` |
| AI service | 127.0.0.1:8001 | `AI_PORT` |
| PostgreSQL | 127.0.0.1:5434 | `POSTGRES_PORT` |

Only the dashboard is reachable from other computers. API, AI service and
database answer on this PC only (loopback, `127.0.0.1`).

## 10. Troubleshooting

| Problem | What to do |
| --- | --- |
| "Docker is installed but not running" | Start Docker Desktop, wait until it has finished, run the script again. |
| "port is already in use" | Another program owns the port: edit `.env`, set `DASHBOARD_PORT` to e.g. 8080, run the start script again. |
| "placeholders" error | The script opens `.env` — fill in the four values from section 4. |
| Build or start fails | Run `docker compose logs --tail 100 > logs.txt` and send us `logs.txt`. |
| Login works but analysis fails | Run `scripts\status-forexai.bat` — the `API ready` line names the missing dependency (usually an API key in `.env`). |
| It worked yesterday, not today | `docker compose ps`: any container not `Up (healthy)`? Send that output plus `logs.txt`. |

## 11. Uninstall

```bat
scripts\stop-forexai.bat
```

If you are sure you will not reinstall, permanently remove everything with:

```bat
docker compose down -v
```

> **Warning:** `down -v` deletes the database volume. Take a backup first
> (section 7) if there is any chance you will want the data later.

Then delete the package folder and uninstall Docker Desktop.