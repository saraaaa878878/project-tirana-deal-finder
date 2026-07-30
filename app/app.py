"""
app/app.py

Flask web app for TIRANA/41.

Routes:
    /                home page: hero, filters, and a grid of listing cards,
                     each showing a great / good / bad deal badge
    /listing/<id>    details page for a single listing

Everything is read through app/data.py, which loads the cleaned listings and the
trained model once at startup. Run it with:

    python -m app.app
"""

from __future__ import annotations

from uuid import uuid4
import os
import sqlite3
from functools import wraps
import unicodedata

from flask import (
    Flask, render_template, request, abort, jsonify, session,
    redirect, url_for, flash, g,
)
from werkzeug.security import generate_password_hash, check_password_hash

from app import data
from backend import stats, chat
from app.translations import TRANSLATIONS

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me-before-production")
app.config["DATABASE"] = os.path.join(app.instance_path, "tirana_deals.sqlite3")

# In-memory chat history, keyed by conversation id.
# Fine for a teaching demo (single process; resets on restart).
_conversations: dict[str, list] = {}

PAGE_SIZE = 24  # listing cards shown per page


# Property photography is intentionally kept in the presentation layer.  The
# matching uses the listing address so it does not alter the dataset or model.
FIRST_PAGE_IMAGES = {
    0: "images/properties/property-02-kodra-e-diellit.webp",
    1: "images/properties/property-03-donika-kastrioti.webp",
    2: "images/properties/property-01-donald-trump.webp",
    3: "images/properties/property-04-ismail-qemali.webp",
    4: "images/properties/property-06-don-bosko.webp",
    5: "images/properties/property-05-jordan-misja.webp",
    6: "images/properties/property-07-fresk.webp",
    7: "images/properties/property-08-sheshi-wilson.webp",
    # The Materniteti listing was supplied with the same source photo.
    8: "images/properties/property-08-sheshi-wilson.webp",
    9: "images/properties/property-09-gani-domi.webp",
    10: "images/properties/property-10-ish-ekspozita.webp",
    11: "images/properties/property-11-kompleksi-halili.webp",
    12: "images/properties/property-12-kodra-e-priftit.webp",
    13: "images/properties/property-14-vila-l-astir.webp",
    14: "images/properties/property-13-green-city.webp",
    15: "images/properties/property-15-tirane-300k.webp",
    16: "images/properties/property-16-ali-demi.webp",
    17: "images/properties/property-17-rruga-e-kavajes.webp",
    18: "images/properties/property-18-misto-mame.webp",
    19: "images/properties/property-19-ringside-residence.webp",
    20: "images/properties/property-20-foto-janku.webp",
    21: "images/properties/property-21-ibrahim-rugova.webp",
    22: "images/properties/property-22-lion-2.webp",
    23: "images/properties/property-24-kodra-e-priftit.webp",
}

PROPERTY_IMAGES = (
    (("misto mame",), "images/properties/property-18-misto-mame.webp"),
    (("ringside",), "images/properties/property-19-ringside-residence.webp"),
    (("foto janku",), "images/properties/property-20-foto-janku.webp"),
    (("ibrahim rugova",), "images/properties/property-21-ibrahim-rugova.webp"),
    (("lion residence 2", "lion 2"), "images/properties/property-22-lion-2.webp"),
    (("dritan hoxha", "kompleksi aura"), "images/properties/property-23-kompleksi-aura.webp"),
    (("kodra e priftit",), "images/properties/property-12-kodra-e-priftit.webp"),
)


def _normalise_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


import re

_POSTCODE_RE = re.compile(r"\s*\b\d{4}\b\s*")
_SQ_TO_EN = {"Tiranë": "Tirana", "Shqipëri": "Albania", "Kamëz": "Kamza"}
_EN_TO_SQ = {v: k for k, v in _SQ_TO_EN.items()}


def display_address(address, lang="sq"):
    """Return a listing's address cleaned up and localised for the given language."""
    if not address:
        return None
    text = _POSTCODE_RE.sub(" ", str(address)).strip()
    text = re.sub(r"\s*,\s*", ", ", text).strip(", ")
    replacements = _EN_TO_SQ if lang == "sq" else _SQ_TO_EN
    for old, new in replacements.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text or None


def listing_image(listing):
    """Return a local photo for a listing when an address match is available."""
    try:
        first_page_image = FIRST_PAGE_IMAGES.get(int(listing.get("listing_id")))
    except (TypeError, ValueError):
        first_page_image = None
    if first_page_image:
        return url_for("static", filename=first_page_image)
    address = _normalise_text(listing.get("address"))
    for needles, filename in PROPERTY_IMAGES:
        if any(needle in address for needle in needles):
            return url_for("static", filename=filename)
    return None


def deal_score(listing):
    """Turn the existing model gap into a compact 1–99 presentation score."""
    gap = listing.get("gap_pct")
    if gap is None:
        return None
    return max(1, min(99, round(50 + float(gap) * 2)))


def get_db():
    if "db" not in g:
        os.makedirs(app.instance_path, exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        g.db.execute(
            "CREATE TABLE IF NOT EXISTS favourites (user_id INTEGER NOT NULL, listing_id INTEGER NOT NULL, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, listing_id), "
            "FOREIGN KEY(user_id) REFERENCES users(id))"
        )
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def load_user_and_language():
    if request.args.get("lang") in {"sq", "en"}:
        session["lang"] = request.args["lang"]
    g.lang = session.get("lang", "sq")
    g.user = None
    if session.get("user_id"):
        g.user = get_db().execute(
            "SELECT id, name, email FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()


@app.context_processor
def inject_globals():
    lang = getattr(g, "lang", "sq")
    favourite_ids = set()
    if getattr(g, "user", None):
        favourite_ids = {
            row["listing_id"] for row in get_db().execute(
                "SELECT listing_id FROM favourites WHERE user_id=?",
                (g.user["id"],),
            ).fetchall()
        }
    return {
        "t": TRANSLATIONS[lang],
        "lang": lang,
        "current_user": getattr(g, "user", None),
        "favourite_ids": favourite_ids,
        "listing_image": listing_image,
        "deal_score": deal_score,
        "display_address": display_address,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash(TRANSLATIONS[g.lang]["login_to_save"], "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def _to_int(value):
    """Parse a query-string value into an int, or None if blank/invalid."""
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _listing_context():
    # All filters are optional; a blank field means "no filter".
    filters = {
        "min_price": _to_int(request.args.get("min_price")),
        "max_price": _to_int(request.args.get("max_price")),
        "bedrooms": _to_int(request.args.get("bedrooms")),
        "min_sqm": _to_int(request.args.get("min_sqm")),
        "max_sqm": _to_int(request.args.get("max_sqm")),
        "deal_grade": request.args.get("deal_grade") or None,
    }
    page = max(1, _to_int(request.args.get("page")) or 1)

    matches = data.search_listings(**filters)
    total = len(matches)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    page_listings = matches[start:start + PAGE_SIZE]

    return dict(
        listings=page_listings,
        total=total,
        page=page,
        total_pages=total_pages,
        filters=filters,
        bounds=data.get_filter_bounds(),
        stats=data.get_hero_stats(),
    )


@app.route("/")
def home():
    # Show only great deals that have a real property photo on the homepage.
    great_deals = data.search_listings(deal_grade="great")
    featured = [listing for listing in great_deals if listing_image(listing)][:3]

    return render_template(
        "home.html",
        featured=featured,
        stats=data.get_hero_stats(),
    )


@app.route("/listings")
def listings():
    return render_template("index.html", **_listing_context())


@app.route("/analytics")
def analytics():
    return render_template(
        "analytics.html",
        stats=stats.get_market_stats(),
        points=stats.get_map_points(),
    )


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    """Receive a message, run the tool-calling assistant, return its answer."""
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Please type a message."}), 400

    conversation_id = payload.get("conversation_id") or uuid4().hex
    history = _conversations.get(conversation_id)

    try:
        result = chat.ask(message, history=history)
    except Exception as exc:  # keep the widget alive on any backend failure
        app.logger.exception("chat failed")
        return jsonify({
            "conversation_id": conversation_id,
            "answer": "Sorry, I ran into a problem answering that. Please try again.",
            "error": str(exc),
        }), 200

    _conversations[conversation_id] = result["history"]
    return jsonify({
        "conversation_id": conversation_id,
        "answer": result["answer"],
        "tools_used": [t["tool"] for t in result["trace"]],
    })


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = data.get_listing(listing_id)
    if listing is None:
        abort(404)
    is_favourite = False
    if g.user:
        is_favourite = get_db().execute(
            "SELECT 1 FROM favourites WHERE user_id=? AND listing_id=?",
            (g.user["id"], listing_id),
        ).fetchone() is not None
    return render_template("detail.html", listing=listing, is_favourite=is_favourite)


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("favourites"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        error = None
        if not name or not email or not password:
            error = TRANSLATIONS[g.lang]["all_fields_required"]
        elif len(password) < 8:
            error = TRANSLATIONS[g.lang]["password_length"]
        if error is None:
            try:
                db = get_db()
                cursor = db.execute(
                    "INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                    (name, email, generate_password_hash(password)),
                )
                db.commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                session["lang"] = g.lang
                return redirect(url_for("favourites"))
            except sqlite3.IntegrityError:
                error = TRANSLATIONS[g.lang]["email_exists"]
        flash(error, "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("favourites"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["lang"] = g.lang
            return redirect(request.args.get("next") or url_for("favourites"))
        flash(TRANSLATIONS[g.lang]["invalid_login"], "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    lang = g.lang
    session.clear()
    session["lang"] = lang
    return redirect(url_for("home"))


@app.route("/favourites")
@login_required
def favourites():
    ids = [
        row["listing_id"] for row in get_db().execute(
            "SELECT listing_id FROM favourites WHERE user_id=? ORDER BY created_at DESC",
            (g.user["id"],),
        ).fetchall()
    ]
    listings = [data.get_listing(i) for i in ids]
    return render_template("favourites.html", listings=[item for item in listings if item])


@app.route("/api/favourites/<int:listing_id>", methods=["POST"])
@login_required
def toggle_favourite(listing_id):
    if data.get_listing(listing_id) is None:
        abort(404)
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM favourites WHERE user_id=? AND listing_id=?",
        (g.user["id"], listing_id),
    ).fetchone()
    if exists:
        db.execute("DELETE FROM favourites WHERE user_id=? AND listing_id=?", (g.user["id"], listing_id))
        saved = False
    else:
        db.execute("INSERT INTO favourites(user_id,listing_id) VALUES(?,?)", (g.user["id"], listing_id))
        saved = True
    db.commit()
    return jsonify({"saved": saved})


@app.route("/buyer-guide")
def buyer_guide():
    return render_template("buyer_guide.html")


@app.route("/mortgage")
def mortgage():
    return render_template("mortgage.html")


if __name__ == "__main__":
    # debug=True gives auto-reload + helpful error pages during development.
    app.run(debug=True, port=5000)