# ForexAI — FAQ

**Do I need to know Python / Docker / programming?**
No. Install Docker Desktop, double-click `start.bat`, open the address
it shows. That is the whole job.

**What does it cost?**
The software + Docker + database are free. You only pay for the two API
keys you bring (both have free tiers sufficient to start):
Twelve Data (market candles) and OpenRouter (AI reasoning).

**Where is the app?**
`http://localhost` by default (or `http://localhost:YOUR_PORT` if you
changed `DASHBOARD_PORT`). Only that page is reachable from other
computers; API/AI/database answer on this PC only.

**Where is my data?**
In the Docker volume `forexai_forexai-postgres-data`. It survives
restarts, updates, reboots, even deleting this folder. Only `reset.bat`
deletes it.

**How do I add users?**
Double-click `scripts\add-user-forexai.bat`, answer 3 questions. There is
no public sign-up page by design.

**Does it trade automatically?**
No. It produces BUY/SELL/NO_TRADE signals with entry/SL/TP + reasoning.
A human decides. Nothing here is financial advice.

**Why NO_TRADE?**
That means "no good setup right now" — a real answer, not an error.
Waiting is often the safest choice.

**Why does analysis sometimes say "busy / wait"?**
The free market-data plan (8 req/min) is temporarily used up. Wait a
minute, retry. Normal on busy days.

**Can I use it on two computers?**
One install = one database. For a second PC, repeat the install there
(data starts empty; copy a backup across if you want history).

**Can I use MetaTrader 5?**
MT5 order execution is Windows-local and optional (Twelve Data path is
the default). See the AI service env reference + `DEPLOYMENT.md`.

**How do I update?**
Unpack the new ZIP over this folder (keep your `.env`), then
`start.bat`. Or `scripts\update-forexai.bat` for a git checkout.
Data is preserved; backup first anyway.

**How do I uninstall?**
`stop.bat`. If you will never reinstall AND have a backup:
`reset.bat` (or `docker compose down -v`), delete the folder, uninstall
Docker Desktop.

**Is my `.env` safe to email?**
Never. It holds passwords + API keys. Support only ever needs the
`collect-diagnostics.bat` bundle, which redacts all values.
