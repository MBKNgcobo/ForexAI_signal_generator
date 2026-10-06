# ForexAI — User Guide (Plain English)

This guide is for people who **use** ForexAI and people who **look after it**.
You do not need any technical knowledge for anything in this document.

**Which part is for me?**

| I want to... | Read |
| --- | --- |
| Get trading signals and manage them | **Part 1 — Using ForexAI** |
| Start/stop the app, make backups, add people | **Part 2 — Looking after ForexAI** |
| Install ForexAI on a fresh computer | [Installation guide](./client-installation.md) |
| Technical detail (ports, environment, code) | [Project README](../README.md) |

---

## Part 1 — Using ForexAI

### 1. Signing in

1. Open your browser and go to **http://localhost** (or the web address your
   installer gave you).
2. You will see **"Sign in to ForexAI"**.
3. Type the **email** and **password** your installer or office owner gave you
   and press **Sign in**.

> There is no "create account" box on the sign-in page on purpose — accounts
> are created by the person looking after the app (see Part 2, section 5).
> If you don't have a login yet, ask them for one.

### 2. Your screen at a glance

After signing in you will see:

- **Left sidebar**
  - **Dashboard** — where you get new signals (this is your everyday screen).
  - **Signal History** — every signal the app has produced, with its outcome.
  - A green dot with **"AI services online"** — when the dot is green the
    system is working. (If it ever looks wrong, see section 7.)
- **Top bar** — the page title and a **"Live system"** indicator.

### 3. Getting a signal (step by step)

1. On the **Dashboard**, find **"Configure analysis"**.
2. Choose your **currency pair** (for example EURUSD), your **timeframe**
   (for example 1 Hour) and how much recent data to use.
3. Press **Run AI analysis**. The button turns into **Analysing...**.
4. Wait — this takes up to about a minute. The app is reading live market
   data, checking the world economy and running its statistical model.
5. When it finishes, the panels below fill in with the result (section 4).

> **If it says the service is busy or to wait:** the free market-data plan
> gets used up temporarily. Wait a minute and press **Run AI analysis** again.

### 4. Understanding your result

Four groups of information appear below the chart:

| Panel | What it means in plain English |
| --- | --- |
| **Market chart** | The recent price movement of the pair you chose. |
| **Agent analysis** | Three independent opinions: **technical** (recent price patterns), **fundamental** (world economic data and events), **quant** (a statistical model trained on historical data). They do not have to agree — disagreement is shown on purpose. |
| **Risk profile** | How risky the trade would be: where the **stop loss** (the price at which you should get out if you are wrong) and **take profit** (the price at which you should take your gains) are placed, and whether the risk vs. reward is good enough. |
| **Final decision** | The bottom line: **BUY**, **SELL** or **NO_TRADE**, with a **Model confidence** percentage, entry price, stop loss, take profit and a written explanation. |

Three things worth remembering:

- **NO_TRADE means "this is not a good setup right now"** — it is a real
  answer, not an error. Often the safest choice is to wait.
- **Confidence is a suggestion, not a promise.** Even a high-confidence
  signal can lose. Nothing here is financial advice.
- **The app never trades for you.** It produces signals; a human decides.

### 5. Human review — accepting or rejecting a signal

Below the decision you will see **"Human Review"** with the signal's details
(ID, direction, confidence, status, entry, stop loss, take profit and the
reasoning).

- Press **Accept** if you agree with the signal — it is marked as accepted
  and kept for your records.
- Press **Reject** if you don't — it is marked as rejected.
- Your decision, your name and the time are written into the signal's
  **audit trail**, so there is always a record of who decided what.

Once reviewed, a signal cannot be changed — review it when you are sure.

### 6. Signal History

Click **Signal History** in the left sidebar:

- Use the **status filter** to show only **Under Review**, **Accepted** or
  **Rejected** signals.
- Click a signal to open it: you get the full detail, the **Reasoning**
  (why the AI suggested it) and the **Audit Trail** (who did what, when).
- Use the paging buttons at the bottom to move through older signals.

### 7. When something doesn't look right

| What you see | What it means | What to do |
| --- | --- | --- |
| "Unable to log in" | Wrong email or password. | Check for typos; ask the owner to confirm the account exists (Part 2 §5). |
| "service busy" / "rate limit" / please wait | The free market-data plan is temporarily used up. | Wait a minute, press **Run AI analysis** again. |
| "couldn't connect" / page won't load at all | The app is probably stopped. | Tell the person looking after it (Part 2). |
| The green dot is missing or red | A service in the background is not healthy. | Tell the person looking after it; they can run the status check (Part 2 §1). |
| An error box you don't recognize | — | Take a screenshot (see Part 2 §6) and send it for support. |

---

*Part 2 continues below — for the person looking after the machine.*

---

## Part 2 — Looking after ForexAI

Everything here is done by **double-clicking files** in the `scripts`
folder (inside the ForexAI folder). No typing of commands.

### 1. The three buttons you will use most

| To do this | Double-click | What happens |
| --- | --- | --- |
| Start the app | `scripts\start-forexai.bat` | Checks everything, starts the app, waits until all parts are healthy, then opens the browser for you. First run after a change can take a few minutes. |
| Check it is healthy | `scripts\status-forexai.bat` | Shows a status table and a list of **[OK]** lines. Five `[OK]` lines = everything works. |
| Stop the app | `scripts\stop-forexai.bat` | Turns everything off. **Your data is kept.** |

Notes:

- **Docker Desktop must be running first** (look for the whale icon in the
  system tray). The start script tells you if it isn't.
- In the status list, `forexai-db-migrate ... Exited (0)` is **normal** — it
  is the one-time database updater. It is only a problem if it says
  something other than `(0)`.
- Restarting the computer? Wait for Docker Desktop to finish starting, then
  run the start script.

### 2. Backups

1. Double-click `scripts\backup-forexai.bat`.
2. A file like `backups\forexai-20261005-174140.sql` appears — that is a
   complete copy of your data (accounts, signals, history).
3. Copy that file somewhere safe (USB drive, cloud folder) now and then.

Keep several backups. Restoring a backup is a job for your installer — do
not try it yourself.

### 3. Changing a setting (for example an expired API key)

1. Find the file named `.env` in the ForexAI folder
   (if you don't see it: in File Explorer, turn on "View → Hidden items").
2. Right-click it → **Open with** → **Notepad**.
3. Change only the value you were told to change, save (Ctrl+S) and close.
4. Double-click `scripts\start-forexai.bat` again so the change takes effect.

Never send this file to anyone — it contains your passwords and keys.

### 4. Adding or replacing people's logins

Double-click `scripts\add-user-forexai.bat` and answer the three questions:

1. Email address (their sign-in), 2. display name, 3. password (twice).

The script tells you if the app isn't running, if the password is too weak
(at least 6 characters with an uppercase letter, a lowercase letter, a
number and a symbol) or if the email already exists. Tell the person their
email and password over a safe channel (in person or a password manager —
never by open email).

### 5. When you need help — what to send

Send all five of these things; it saves a lot of back-and-forth:

1. **A screenshot of the problem** — press **Windows + Shift + S**, drag
   over the message, then paste (Ctrl+V) into your email or chat.
2. **A screenshot of the status window** — run `scripts\status-forexai.bat`
   and capture the whole window the same way.
3. **What you were trying to do** when it happened.
4. **Approximately when** it started.
5. **Anything you changed** recently (a setting, a new account, a restart).

### 6. Please never do these

- ❌ **Never** run `docker compose down -v` or any command someone sends you
  in a chat — deleting the wrong thing can erase your data permanently.
- ❌ **Never** delete the `backups` folder or the contents of the ForexAI
  folder "to clean up".
- ❌ **Never** share your `.env` file, API keys, or a screenshot containing
  them.
- ❌ **Never** ignore a problem for weeks — small issues are easy to fix,
  big ones are not.

---

### Good to know (both parts)

- ForexAI gives **decision support, not financial advice**. You decide.
- The market-data plan is free-tier, so on busy days the app may ask you to
  wait — this is normal and the app tells you clearly when it happens.
- Your data lives in Docker and survives restarts, updates and even moving
  the ForexAI folder. It is only lost if the backup advice above was
  ignored.

*Related docs: [Installation guide](./client-installation.md) ·
[Project README](../README.md)*