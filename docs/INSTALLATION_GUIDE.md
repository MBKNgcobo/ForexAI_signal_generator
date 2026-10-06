# ForexAI — Installation Guide (fresh Windows PC)

Target: Windows 10/11 64-bit, ~8 GB free disk, internet, administrator
rights once (Docker install). 30–45 minutes including the first build.

## Step 1 — Install Docker Desktop

1. Download: https://docs.docker.com/get-docker/
2. Run the installer (accept WSL 2 / Virtual Machine Platform if offered).
3. Reboot if asked. Start Docker Desktop, wait until the whale icon is
   steady (not animating). Keep Docker Desktop running for every step below.

Verify (optional): open PowerShell, run `docker --version` and
`docker compose version`. Both must print a version.

## Step 2 — Unzip ForexAI somewhere permanent

Unzip `ForexAI-v1.0.0-Windows.zip` to e.g. `C:\ForexAI`. Do not run it
from inside the ZIP viewer, Downloads temp, or a USB stick you will
remove — the folder must stay put; Docker volumes keep the data but the
compose file and `.env` live here.

You should see: `start.bat`, `START_HERE.txt`, `docker-compose.yml`,
`.env.example`, `scripts\`, `docs\`.

## Step 3 — First start (creates your config)

1. Double-click **`start.bat`**.
2. First run copies `.env.example` → `.env` and opens Notepad. Fill in:

| Value | What to type |
| --- | --- |
| `POSTGRES_PASSWORD` | Any long random text (letters+numbers, 20+ chars) |
| `JWT_KEY` | A different long random text, min 32 characters |
| `TWELVE_DATA_API_KEY` | From https://twelvedata.com (free account → API key) |
| `OPENROUTER_API_KEY` | From https://openrouter.ai (sign in → API keys) |

3. Save (Ctrl+S), close Notepad, double-click `start.bat` again.
4. The script refuses to continue while placeholders remain — that is
   intentional; a stack that boots without keys can never answer.
5. First build takes 5–15 min (downloads base images, builds 3 images,
   runs DB migrations + seed). Later starts take <1 min.
6. When all 4 services report healthy, the browser opens at
   `http://localhost` (or `http://localhost:YOUR_PORT`).

> Port 80 (default) triggers a Windows admin prompt on first use. If you
> prefer no prompt, set `DASHBOARD_PORT=8080` in `.env` before starting
> and open `http://localhost:8080` instead.

## Step 4 — Create the first login

The dashboard has no public sign-up (by design). Double-click
`scripts\add-user-forexai.bat`, answer email / display name / password
(min 6 chars: upper + lower + number + symbol). Then sign in in the browser.

## Step 5 — Confirm health

Double-click `status.bat`. You want:

```text
[OK] dashboard .../health
[OK] API .../health
[OK] API ready .../health/ready
[OK] AI .../health
[OK] AI ready .../ready
```

`forexai-db-migrate Exited (0)` in the container list is NORMAL (one-shot
migration job). Anything else non-zero is not — see TROUBLESHOOTING.md.

## macOS / Linux

Same folder, terminal instead of double-click:

```bash
cp .env.example .env   # fill in the 4 values
./start.sh              # start
./status.sh             # health
./stop.sh               # stop (data kept)
./logs.sh               # logs
```

Needs Docker Desktop (mac) or Docker Engine + Compose v2 (Linux).
MT5 features are Windows-only; Twelve Data path works everywhere.
