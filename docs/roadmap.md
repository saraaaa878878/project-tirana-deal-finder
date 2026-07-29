# Tirana Deal Finder — Development Roadmap

A property "deal finder" for the Tirana housing market. One coherent build, carried
end-to-end across 3 weeks. Each week consumes the previous week's output.

**Stack (locked):** Flask + Jinja + Bootstrap · pandas + scikit-learn · joblib ·
Chart.js (analytics) · Leaflet + markercluster (map) · LLM tool-calling.

**Hero feature:** the deal classifier — predicted price vs. listed price → great / good / bad.

**Geographic axis:** zone / neighborhood (derived from address or lat/lng), NOT city —
the dataset is 100% Tirana.

**How to use this file:** work top to bottom. Each milestone has a goal, the files we
touch, what's scaffolded vs. left for students, the AI prompts to use, and a "Done when"
checklist. Check boxes as we go.

---

## PHASE 1 — Data → Model  (Week 1)

Goal: turn 4,505 messy listings into a clean dataset and a trained price model with a
deal classifier saved to disk.

### Milestone 1.1 — Clean Dataset + EDA  (Session 1)
**Goal:** raw JSON → trustworthy, documented dataframe + first charts.

- Files: `backend/preprocessing.py`, `notebooks/01_cleaning_eda.ipynb`,
  output `data/listings_clean.parquet`
- Scaffold (instructor): load + save harness, profiling cells, function stubs.
- Students complete: apply the 7-step pipeline from the preprocessing doc; decide and
  justify null/sentinel/outlier handling; produce the first EDA charts (these become
  the analytics page in Phase 2).
- AI prompts:
  - "Write `clean_listings(df)` implementing these 7 steps from this preprocessing doc."
  - "The composition fields use -1 — handle it per the doc and log how many rows changed."
  - "Plot the price distribution and median price by zone."
- **Done when:**
  - [ ] `listing_id` created from row index
  - [ ] negatives handled per doc; counts logged
  - [ ] nulls handled by type (drop / median / false / "unknown")
  - [ ] fields renamed to API names
  - [ ] two views produced: display (all clean) + ML (outliers removed)
  - [ ] `listings_clean.parquet` saved; 3+ EDA charts rendered
- **Student win:** "I turned raw messy JSON into a clean dataset I understand."

### Milestone 1.2 — Model + Deal Scorer  (Session 2)
**Goal:** train a price regressor, evaluate it, and build the hero deal classifier.

- Files: `notebooks/02_modeling.ipynb`, `backend/model.py`, output `models/model.joblib`
- Scaffold (instructor): train/eval/persist loop, `score_deal()` threshold stub.
- Students complete: choose features (incl. price-per-sqm, zone), iterate models,
  read MAE/RMSE/R², set the great/good/bad cutoffs.
- AI prompts:
  - "Suggest features from these columns for predicting price."
  - "My R² is low — what should I try?" (log target, more features, drop noisy cols)
  - "Write `score_deal(predicted, listed)` returning great/good/bad from a % gap."
- **Done when:**
  - [ ] model trained on the ML dataset; MAE/RMSE/R² reported
  - [ ] `model.joblib` saved; reload + predict on one row verified
  - [ ] `predict_price(listing)` and `score_deal(...)` callable from `backend/model.py`
  - [ ] same preprocessing used in training as will be used at predict time
- **Student win:** "I trained a model and a deal classifier, saved to disk."
- ⚠️ Reality check: single-city apartments → expect R² ~0.5–0.7, not 0.9. Frame it.

---

## PHASE 2 — Product  (Week 2)

Goal: a two-page Flask web app — an intelligent home page and an analytics page with a
color-coded price map — powered by the Phase 1 model.

### Milestone 2.1 — Intelligent Home Page  (Session 3)
**Goal:** card-based listing site with search/filters and live deal badges.

- Files: `app/app.py`, `app/templates/{base,index,detail}.html`,
  `app/static/css/style.css`
- Scaffold (instructor): Flask routes, `base.html`, data-loading layer, and a
  black-box `predict_price()` helper so badges work without ML detours.
- Students complete: the Bootstrap card partial, filter logic (price / bedrooms /
  sqm / zone), the details page, and rendering great/good/bad badges.
- AI prompts:
  - "Generate a Bootstrap card for this listing dict."
  - "Add a price-range and zone filter to this Flask route."
  - "Render a colored badge from a great/good/bad score."
- **Done when:**
  - [ ] home page lists cards from `listings_clean.parquet`
  - [ ] search + filters work (price, bedrooms, sqm, zone)
  - [ ] details page by `listing_id`
  - [ ] every card shows predicted price + deal badge
- **Student win:** "I built a property site that already shows AI deal badges."

### Milestone 2.2 — Analytics Page + Price Cluster Map  (Session 4)
**Goal:** second page with market charts and a color-coded geolocation map.

- Files: `app/templates/analytics.html`, `app/static/js/{charts.js,map.js}`,
  `backend/stats.py`
- Scaffold (instructor): `/analytics` route, empty chart/map containers, and a
  `get_market_stats()` helper stub (the SAME function Phase 3 exposes as a tool).
- Students complete: wire pandas groupby summaries into Chart.js; build the Leaflet
  markercluster map with markers colored by price band (green→amber→red by quartile).
- AI prompts:
  - "Turn this pandas groupby into Chart.js-ready JSON."
  - "Build a Leaflet markercluster map; color markers by price quartile."
  - "Add a price histogram and a sqm-vs-price scatter colored by deal grade."
- **Done when:**
  - [ ] `/analytics` renders 3+ charts (distribution, by-zone, scatter)
  - [ ] `get_market_stats(zone)` returns summary data used by the page
  - [ ] map shows all listings, clustered, color-coded by price
- **Student win:** "I built a market dashboard and a price map of Tirana."

---

## PHASE 3 — AI Layer → Demo  (Week 3)

Goal: a natural-language assistant that answers by calling the app's own functions as
tools, integrated into the app, ready for Demo Day.

### Milestone 3.1 — Functions → LLM Tools  (Session 5)
**Goal:** expose the app's real functions as callable tools (tool-calling, not RAG).

- Files: `backend/tools.py`, `backend/chat.py`
- Scaffold (instructor): tool-schema format + dispatch loop.
- Students complete: write `search_properties(zone, max_price, bedrooms)`,
  `score_deal(property_id)`, `get_market_stats(zone)` (reusing Phase 2 code) and their
  JSON schemas; test the LLM picks the right function + args in isolation.
- AI prompts:
  - "Write the tool/function schema for this Python function."
  - "The model called search with bad args — improve the tool description."
  - "Write a dispatch loop that runs the chosen tool and returns the result."
- **Done when:**
  - [ ] 3 tools callable as plain functions, reusing Phase 2 logic
  - [ ] JSON schemas written for each
  - [ ] LLM reliably selects function + args on test questions
- **Student win:** "I exposed my own functions as tools an LLM can call."

### Milestone 3.2 — Chat Integration + Demo Day  (Session 6)
**Goal:** ship the assistant in the app; rehearse the demo.

- Files: `app/static/js/chat.js`, `/chat` route in `app/app.py`, `README.md`
- Scaffold (instructor): chat route + frontend chat box.
- Students complete: connect the box to the Phase 3 dispatcher; handle errors and
  empty results; polish both pages; script and rehearse the demo.
- AI prompts:
  - "Build a chat box that posts to /chat and shows replies."
  - "Format this tool result into a friendly natural-language answer."
  - "Handle the case where a tool returns no listings."
- **Done when:**
  - [ ] full loop works: question → tool call → real backend → phrased answer
  - [ ] chat embedded and usable in the running app
  - [ ] README written; demo rehearsed end-to-end
- **Student win:** "I built an AI that answers questions by running my own functions."

---

## Dependency spine (don't break this)

```
raw JSON
  → preprocessing.py        (1.1)
  → listings_clean.parquet  (1.1)
  → model.joblib            (1.2)
  → home page + badges      (2.1)  uses parquet + model
  → analytics + map         (2.2)  uses parquet + stats.py
  → tools                   (3.1)  reuse model.py / stats.py / query logic
  → chat assistant          (3.2)  uses tools
```