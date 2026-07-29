# TIRANA/41 — UI & feature handoff

This version changes only the Flask web layer inside `app/`. The ML model,
preprocessing pipeline, datasets, notebooks and AI tools are intentionally
unchanged.

## New user-facing features

- Separate visual homepage and direct `/listings` results page
- Complete Albanian/English language switch stored in the user session
- Responsive editorial “TIRANA/41” design system
- Register, log in and log out with hashed passwords
- Per-user saved properties backed by local SQLite
- Interactive mortgage calculator
- Albania property-purchase document guide
- Property photography for the first 24 listing cards
- Empty-filter state with a one-click reset
- Three interactive map modes: Midnight, Paper and Deal Heat
- Listing comparison tray for up to three properties
- Property Passport detail layout with price signal and Deal Score
- Existing ML deal badges, analytics, map and chat kept in place

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tests/smoke_test.py
python -m app.app
```

Open `http://localhost:5000`.

For a shared or production environment, set a strong `SECRET_KEY` environment
variable. The SQLite file is created automatically in `instance/`.
