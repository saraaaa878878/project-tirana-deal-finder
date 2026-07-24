# Tirana Deal Finder

An AI-powered web app that estimates a fair price for apartments in Tirana, then flags the
**great / good / market-price** deals — with a browsable listings site, a market dashboard
with a price map, and a chat assistant you can talk to in plain language.

This is the reference build for a 3-week (plus a Week 0 warm-up) summer school on
**building software with AI**. The goal isn't to memorize syntax — it's to design, build,
and debug a real product using an AI coding assistant.

![Hero Image](https://i.imgur.com/GP33gzs.jpeg)

---

## What it does

- **Prices every listing** with a machine-learning model trained on ~4,500 real Tirana listings.
- **Grades each one** great / good / market by comparing the predicted price to the asking price.
- **Lets you browse & filter** listings, with a deal badge on every card.
- **Shows the market** on an analytics page: charts + a color-coded map of every listing.
- **Answers questions** through a chat assistant that calls the app's own functions
  (e.g. "best deals under €150k", "price a 90m² 2-bed with an elevator").

---

## Tech stack

- **Data & ML:** Python, pandas, scikit-learn, joblib
- **Web:** Flask, Jinja, Bootstrap
- **Visualization:** Chart.js, Leaflet (+ markercluster)
- **AI layer:** Google Gemini via the `google-genai` SDK (tool-calling)
- **Tooling:** Git/GitHub, VS Code + WSL

---

## New to the terminal, Git, or VS Code?

If you're not comfortable with WSL, the terminal, Git, or virtual environments yet,
**start with [`SETUP.md`](SETUP.md)** — the Week 0 guide that walks through installing
everything from scratch. Come back here once your environment is ready.

---

## Quick start

Run these from a terminal (WSL / Ubuntu) with Python 3.10+ installed.

```bash
# 1. Get the code
git clone https://github.com/evisp/tirana-deal-finder.git
cd tirana-deal-finder

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the dependencies
pip install -r requirements.txt

# 4. Add your API key (for the chat assistant)
cp .env.example .env
#   then open .env and paste your free Gemini key into GEMINI_API_KEY=
#   (get one at https://aistudio.google.com  ->  "Get API key")

# 5. Clean the data and train the model (creates the files the app needs)
python tests/smoke_test.py

# 6. Start the web app
python -m app.app
```

Then open **http://localhost:5000** in your browser.

> The listings site and analytics page work without an API key. The **chat assistant**
> needs a Gemini key in `.env`. Free-tier quota is per Google Cloud **project**, not per key —
> so each student should use their own Google account/project.

---

## Running each part

| I want to… | Command |
|---|---|
| Clean the raw data | `python -m backend.preprocessing` |
| Train + save the model and run all checks | `python tests/smoke_test.py` |
| Run the web app (site + analytics + chat) | `python -m app.app` |
| Talk to the assistant in the terminal | `python -m backend.chat "best deals under 150000?"` |
| Chat interactively in the terminal | `python -m backend.chat` |
| Check the AI layer (no API calls used) | `python tests/smoke_test_ai.py` |
| Open the teaching notebooks | `jupyter notebook` then open `notebooks/` |

---

## How the course is structured

The build is split into six sessions, each saved as a **git tag** so you can jump to the
exact state of the code at any point.

| Tag | Session | What's built |
|---|---|---|
| `session-1` | Data → Clean dataset + EDA | `backend/preprocessing.py`, cleaning notebook |
| `session-2` | Model + deal scorer | `backend/model.py`, modeling notebook, `model.joblib` |
| `session-3` | Home page + deal badges | Flask app, listing cards, detail page |
| `session-4` | Analytics + price map | `backend/stats.py`, charts, Leaflet map |
| `session-5` | Functions → AI tools | `backend/tools.py`, `llm.py`, `chat.py` |
| `session-6` | Chat assistant in the app | `/chat` route, chat widget |

To view the code as it was at a given session:

```bash
git checkout session-3     # look at the Session 3 state
git checkout main          # return to the latest version
```

> **Read docs from `main`, run code from tags.** The README and other docs live on `main`
> and are always current; the tags are frozen snapshots of the code for each session.

---

## Following the sessions

We build this project across six sessions. Each session is saved as a **tag** —
a frozen snapshot of the code at that point. Checking them out in order lets you
**watch the project grow**: `session-1` is just data cleaning; by `session-4` there's
a full web app with a map.

Each week, start fresh from that week's session. The ritual is always the same
**three steps**:

```bash
# 1. Switch to this week's session
git checkout session-1      # then session-2, session-3, ... in the following weeks

# 2. Rebuild the data + model (they aren't stored in git — you generate them)
python tests/smoke_test.py

# 3. Run whatever that session built
python -m app.app           # (Sessions 3+; earlier sessions run their own scripts)
```

That's it: **checkout → smoke test → run.**

### A few things that are normal (not errors!)

- **"You are in 'detached HEAD' state"** — Git always says this when you check out a tag.
  It just means you're viewing a snapshot. You can safely ignore it.
- **Files appear and disappear between sessions** — that's the point. Earlier sessions
  simply have fewer files, because less had been built yet.
- **Your tweaks from last week are gone after switching** — expected. Each week we start
  clean from the new session. Homework is for practice; you don't need to keep it.

### Don't forget the smoke test

The trained model and cleaned data are **not** stored in git — you regenerate them with
`python tests/smoke_test.py`. If you skip this after a checkout, the site will run but every
listing will say **"no estimate"** (because there's no model yet). Just run the smoke test
and restart.

### What runs at each session

- **`session-1`** — data cleaning. Run: `python -m backend.preprocessing`
- **`session-2`** — the model. Run: `python tests/smoke_test.py` (trains + checks)
- **`session-3` onward** — the web app. Run: `python -m app.app`, then open
  <http://localhost:5000>

---

## Project structure

```
tirana-deal-finder/
├── data/                     # raw dataset (+ generated clean dataset)
├── models/                   # trained model (generated; not in git)
├── notebooks/                # teaching notebooks (cleaning, modeling)
├── backend/                  # logic — reused by the app AND the AI tools
│   ├── preprocessing.py      #   the data-cleaning pipeline
│   ├── model.py              #   train / predict / score_deal
│   ├── stats.py              #   market statistics
│   ├── tools.py              #   the six functions exposed to the AI
│   ├── llm.py                #   Gemini wrapper (retry + fallback)
│   └── chat.py               #   the tool-calling loop
├── app/                      # the web layer (Flask)
│   ├── app.py                #   routes
│   ├── data.py               #   loads listings + model, adds deal grades
│   ├── templates/            #   pages (home, detail, analytics)
│   └── static/               #   css + js (charts, map, chat)
├── tests/                    # smoke tests
├── requirements.txt
├── .env.example              # copy to .env and add your key
└── README.md
```

---

## Troubleshooting

Hitting an error? Common issues (WSL networking, the Gemini SDK, `.env` not loading,
rate limits) are collected in **[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)**.

---

## Known issues / roadmap

- Some listings have an implausibly low price (a few hundred euros) because the price-per-m²
  was entered as the total price. These are being cleaned up in a follow-up pass.
- The model reaches R² ≈ 0.5 — good enough for a clear demo; accuracy improvements are a
  natural next step (more features, location signal).

---

## A note on the data

Prices shown are **model estimates for a teaching project**, not real valuations or advice.
The dataset is a snapshot of public Tirana listings used purely for education.