"""
Turns a town/district name into a travel time from ORIGIN_ADDRESS.

Two network calls, both cached to disk (keyed by the town string) so a
listing's town only ever gets geocoded and routed once, no matter how many
times it reappears across future runs:

  1. Nominatim (OpenStreetMap) — free geocoding, no API key, rate-limited to
     one request/second per their usage policy (see caller for the sleep).
  2. Google Distance Matrix, mode=transit — needs GOOGLE_MAPS_API_KEY. This
     is the only paid-capable API call in the whole project; the free
     monthly credit on a Google Cloud account covers this kind of volume
     comfortably for personal use, but keep an eye on billing.
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

from . import config

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# Nominatim's usage policy requires a descriptive User-Agent identifying the
# app — not a browser UA. Replace the email if you want abuse reports to
# reach you instead of nobody.
NOMINATIM_HEADERS = {"User-Agent": "wg-radar/1.0 (personal, non-commercial use)"}


def _load_cache(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(path: str, cache: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def geocode_town(town: str) -> tuple[float, float] | None:
    cache = _load_cache(config.GEOCODE_CACHE_PATH)
    if town in cache:
        return tuple(cache[town]) if cache[town] else None

    query = f"{town}, Bayern, Germany"
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers=NOMINATIM_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    time.sleep(1)  # be polite: Nominatim allows max 1 request/second

    coords = None
    if results:
        coords = (float(results[0]["lat"]), float(results[0]["lon"]))

    cache[town] = list(coords) if coords else None
    _save_cache(config.GEOCODE_CACHE_PATH, cache)
    return coords


def _next_weekday_9am() -> int:
    """Unix timestamp for the next upcoming Monday 9:00 — a stable, typical
    commute-time reference so transit durations aren't computed against e.g.
    a Sunday night with reduced service."""
    now = datetime.now()
    days_ahead = (7 - now.weekday()) % 7  # 0=Monday
    days_ahead = days_ahead or 7
    target = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
    return int(target.timestamp())


def transit_minutes_from_origin(town: str, lat: float, lon: float) -> int | None:
    if not config.GOOGLE_MAPS_API_KEY:
        raise RuntimeError(
            "GOOGLE_MAPS_API_KEY is not set — see README.md for how to "
            "create one and add it as a GitHub Actions secret."
        )

    cache = _load_cache(config.TRANSIT_CACHE_PATH)
    if town in cache:
        return cache[town]

    resp = requests.get(
        DISTANCE_MATRIX_URL,
        params={
            "origins": config.ORIGIN_ADDRESS,
            "destinations": f"{lat},{lon}",
            "mode": "transit",
            "departure_time": _next_weekday_9am(),
            "key": config.GOOGLE_MAPS_API_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    minutes = None
    try:
        element = data["rows"][0]["elements"][0]
        if element["status"] == "OK":
            minutes = round(element["duration"]["value"] / 60)
    except (KeyError, IndexError):
        pass

    cache[town] = minutes
    _save_cache(config.TRANSIT_CACHE_PATH, cache)
    return minutes
