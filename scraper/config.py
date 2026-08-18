"""
All the knobs you're likely to want to turn live here.
Nothing in this file talks to the network — it's just settings.
Real secrets (passwords, API keys) come from environment variables, never
hardcoded values, so this file is safe to commit to a public repo.
"""

import os

# --- Where you're commuting from --------------------------------------------
ORIGIN_ADDRESS = "Tivolistraße, München, Germany"

# --- Filters -----------------------------------------------------------------
MAX_PRICE_EUR = 700          # strictly lower than this
MAX_TRANSIT_MINUTES = 60     # "almost an hour" — set to 55 for a stricter cut

# A listing is dropped BEFORE geocoding if its town/district text contains any
# of these (case-insensitive substring match) — this is how "nothing inside
# Munich's city limits" gets enforced. WG-Gesucht shows Munich addresses as
# "München" or "München - <Stadtteil>"; surrounding towns show under their own
# name (e.g. "Unterföhring", "Gräfelfing"), so this single match is normally
# enough. Add more strings here if you spot an edge case.
EXCLUDED_TOWN_SUBSTRINGS = ["münchen", "muenchen"]

# --- Email alert inbox (IMAP) ------------------------------------------------
# Point one or more WG-Gesucht "Email Alerts" at a mailbox you control, then
# fill these in as GitHub Actions secrets (see README.md) — never commit real
# values here.
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")
IMAP_FOLDER = os.environ.get("IMAP_FOLDER", "INBOX")

# Only emails whose "From" header contains this are treated as WG-Gesucht
# alerts. Check a real alert email once one arrives and adjust if needed.
SENDER_FILTER = os.environ.get("SENDER_FILTER", "wg-gesucht.de")

# --- Google Distance Matrix (public transit + walking travel time) ---------
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# --- Paths --------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(_ROOT, "data")
LISTINGS_PATH = os.path.join(DATA_DIR, "listings.json")
GEOCODE_CACHE_PATH = os.path.join(_SCRAPER_DIR, "geocode_cache.json")
TRANSIT_CACHE_PATH = os.path.join(_SCRAPER_DIR, "transit_cache.json")
UNPARSED_DIR = os.path.join(_SCRAPER_DIR, "unparsed_emails")
