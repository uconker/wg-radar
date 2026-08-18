"""Small stateless helpers used by scrape.py."""

import json
import os
import re
import unicodedata


def normalize_slug(text: str) -> str:
    """Lowercase, expand German umlauts, collapse to hyphen-separated ascii.

    "Schwabing-West" -> "schwabing-west"
    "Schwanthalerhöhe" -> "schwanthalerhoehe"
    """
    text = text.strip().lower()
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_weekday_9am_epoch(reference=None):
    """Epoch seconds for the next upcoming Monday 09:00 local time.

    Used as a stable reference departure time for transit queries, so
    commute estimates reflect a normal weekday morning rather than
    whatever moment the workflow happens to run.
    """
    import datetime

    now = reference or datetime.datetime.now()
    days_ahead = (7 - now.weekday()) % 7  # 0 = Monday
    if days_ahead == 0:
        days_ahead = 7
    target_date = now.date() + datetime.timedelta(days=days_ahead)
    target = datetime.datetime.combine(target_date, datetime.time(9, 0))
    return int(target.timestamp())
