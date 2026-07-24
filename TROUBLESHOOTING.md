# Troubleshooting

Stuck? You're in good company — **everyone** hits these. Find your error below.
Each entry says what you'll see, why it happens, and how to fix it.

**A golden rule first:** when something behaves strangely after you changed a file,
**stop the app and start it again**. In the terminal running the app, press **Ctrl+C**,
then run the start command again. This fixes a surprising number of issues (see
[Flask didn't pick up my changes](#flask-didnt-pick-up-my-changes)).

---

## Contents

- [Setup & terminal](#setup--terminal)
- [Git & GitHub](#git--github)
- [Python & virtual environment](#python--virtual-environment)
- [Running the web app](#running-the-web-app)
- [The AI chat assistant](#the-ai-chat-assistant)

---

## Setup & terminal

### The password isn't showing when I type
Not a bug. When Ubuntu (or `sudo`) asks for a password, **nothing appears** as you type — no
dots, no stars. Just type it and press **Enter**.

### `command not found` after installing something
Two common causes:
- You typed the command in the **wrong window**. Project commands go in the **Ubuntu**
  terminal, not Windows PowerShell.
- The install didn't finish. Re-run the install from Step 3 of [`SETUP.md`](SETUP.md).

### `Permission denied`
If a command needs admin rights, it usually needs `sudo` in front, e.g.
`sudo apt install ...`. Don't put `sudo` in front of Python or Git project commands, though —
those don't need it.

---

## Git & GitHub

### `Could not resolve host: github.com`
Your WSL can't reach the internet — it's a DNS problem, **not** your password or token.
Fix it in this order:

1. Close WSL and restart it. From **Windows PowerShell**:
```powershell
   wsl --shutdown
```
   Then reopen Ubuntu and try again.
2. If that doesn't work, set a DNS server inside **Ubuntu**:
```bash
   echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
```
3. If you're on a **VPN or a work/school network**, disconnect it and try again — those often
   block WSL's network.

### `Authentication failed` when pushing to GitHub
GitHub no longer accepts your account password on the command line. You need a
**Personal Access Token** used in place of the password:
<https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>.

### My push was rejected (`Updates were rejected...`)
The version on GitHub has commits your computer doesn't. Pull them first, then push:
```bash
git pull --rebase origin main
git push origin main
```

### I checked out an old session and my files look different / "detached HEAD"
That's expected — `git checkout session-3` shows the code **as it was** at that session, and
Git warns you're "detached." To get back to the latest version:
```bash
git checkout main
```

---

## Python & virtual environment

### `ModuleNotFoundError: No module named 'pandas'` (or flask, sklearn, etc.)
Almost always: your **virtual environment isn't active**, or the packages aren't installed.
From the project folder:
```bash
source .venv/bin/activate       # you should see (.venv) at the start of the line
pip install -r requirements.txt
```
If `.venv` doesn't exist yet, create it first:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### How do I know if my virtual environment is active?
Your terminal line starts with **`(.venv)`**. If it doesn't, run `source .venv/bin/activate`.
You need to activate it **every time you open a new terminal**.

### `pip: command not found`
Use `pip` **inside** an active virtual environment. If you're setting up and it's still
missing, install it: `sudo apt install -y python3-pip`.

### `externally-managed-environment` error from pip
You're installing **outside** a virtual environment. Activate `.venv` first
(`source .venv/bin/activate`) and install again — packages belong in the venv, not system-wide.

---

## Running the web app

### `python -m app.app` — I get an import error
Run it from the **project root folder** (the one containing the `app/` and `backend/` folders),
with the virtual environment active. Check where you are with `pwd` and move with `cd` if needed.

### The page won't load / "site can't be reached"
- Make sure the app is actually running — the terminal should say
  `Running on http://127.0.0.1:5000`.
- Open exactly **http://localhost:5000** in your browser.
- If the terminal shows an error instead, read the **last few lines** — that's the real cause.

### Flask didn't pick up my changes
On Windows/WSL, the auto-reload sometimes misses file changes (especially files under
`/mnt/c/...`). **Stop and restart** the app: press **Ctrl+C**, then run `python -m app.app`
again. When in doubt, restart — it's the reliable fix.

### `'stats' is undefined` (or a similar template error)
The page expects data the route isn't sending — usually because a file edit didn't save, or
the app is running an **old** version in memory. Save the file, then **restart the app**
(Ctrl+C → rerun).

### The listings show a strange, tiny price (like "€126")
Known data issue: a few listings had the **price-per-m²** entered where the total price should
be. It's on the roadmap to clean up. Not something you broke.

### The deal badges are missing / everything says "no estimate"
The model file is missing. Generate it by running the check that trains and saves the model:
```bash
python tests/smoke_test.py
```
Then restart the app.

---

## The AI chat assistant

### The chat replies "Sorry, I ran into a problem"
Usually the API key. Check that:
- You created a `.env` file (copied from `.env.example`) in the project root.
- It contains `GEMINI_API_KEY=` followed by your real key, with **no spaces or quotes**.
- You **restarted** the app after editing `.env` (it's only read at startup).

Quick test of just the key:
```bash
python -c "from backend import llm; print(llm.generate([llm.user_message('hi')])['text'])"
```
A friendly reply means the key works.

### `ModuleNotFoundError: No module named 'google.genai'`
You may have the **old** package installed, which conflicts with the current one. Fix:
```bash
pip uninstall google-generativeai -y
pip install -U google-genai
```

### `429 RESOURCE_EXHAUSTED`
You've hit the **free-tier rate limit** (too many requests, or the daily cap). Options:
- Wait a minute and try again (the app already retries automatically).
- Make sure you're using **your own** Google account/project — the free quota is shared per
  project, so a shared key runs out fast.

### `503 UNAVAILABLE` / "model is experiencing high demand"
This is **Google's** servers being briefly busy, not your fault. The app automatically waits
and retries, and falls back to a lighter model. If it persists, wait a few minutes.

### `.env` changes seem to have no effect
The `.env` file is read **once, when the app starts**. After editing it, **restart the app**
(Ctrl+C → `python -m app.app`).

---

## Still stuck?

1. Read the **last few lines** of the error in the terminal — the real cause is usually there.
2. Copy the exact error text and search it, or bring it to class.
3. Try the golden rule: **stop the app, restart it** (Ctrl+C → rerun).

You're not expected to memorize any of this — that's what this file is for.