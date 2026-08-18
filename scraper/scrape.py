#!/usr/bin/env python3
"""
Main entry point, run on a schedule by .github/workflows/update.yml.

Pipeline:
  1. Pull unread WG-Gesucht alert emails from the configured mailbox.
  2. Extract candidate listings (id, url, town, price) from each email.
  3. Drop anything inside Munich city limits (we only want the commuter
     belt) and anything already known to be over budget.
  4. Geocode the remaining towns and look up transit time from
     config.ORIGIN_ADDRESS.
  5. Keep listings that are <= config.MAX_TRANSIT_MINUTES away and
     <= config.PRICE_MAX_EUR.
  6. Merge into data/listings.json (dedup by id, drop stale entries).

Exits with status 0 even if the mailbox is empty or a step fails for one
listing — a bad run shouldn't block the next scheduled run. Real errors
are printed to stderr so they show up in the GitHub Actions log.
"""

import datetime
import sys

from . import config
from .location import (
    display_name,
    geocode,
    is_munich_city,
    town_from_slug,
    transit_minutes,
)
from .mailbox import fetch_alert_emails, parse_listings
from .utils import load_json, save_json


def log(*args):
    print(*args, file=sys.stderr)


def main():
    if not config.IMAP_USER or not config.IMAP_PASSWORD:
        log("IMAP_USER / IMAP_PASSWORD not set — nothing to do. "
            "See README.md for setup.")
        return
    if not config.GOOGLE_MAPS_API_KEY:
        log("GOOGLE_MAPS_API_KEY not set — can't compute transit times. "
            "See README.md for setup.")
        return

    geocode_cache = load_json(config.GEOCODE_CACHE_PATH, {})
    transit_cache = load_json(config.TRANSIT_CACHE_PATH, {})
    store = load_json(config.LISTINGS_PATH, {"updated_at": None, "listings": []})
    existing_by_id = {item["id"]: item for item in store["listings"]}

    log("Fetching alert emails...")
    try:
        emails = fetch_alert_emails(
            config.IMAP_HOST, config.IMAP_USER, config.IMAP_PASSWORD, config.IMAP_FOLDER
        )
    except Exception as exc:  # noqa: BLE001 - keep the workflow alive
        log(f"IMAP fetch failed: {exc}")
        emails = []
    log(f"{len(emails)} new alert email(s).")

    candidates = {}
    for html in emails:
        for listing in parse_listings(html):
            candidates[listing["id"]] = listing
    log(f"{len(candidates)} candidate listing(s) found in those emails.")

    kept = 0
    for ad_id, listing in candidates.items():
        town_slug = town_from_slug(listing["slug"])

        if config.EXCLUDE_MUNICH_CITY and is_munich_city(town_slug):
            continue

        price = listing["price_eur"]
        if price is not None and price > config.PRICE_MAX_EUR:
            continue

        coords = geocode(town_slug, geocode_cache)
        if coords is None:
            log(f"Could not geocode '{town_slug}' for ad {ad_id}, skipping.")
            continue

        minutes = transit_minutes(
            config.ORIGIN_ADDRESS, coords["lat"], coords["lng"],
            config.GOOGLE_MAPS_API_KEY, transit_cache,
        )
        if minutes is None:
            log(f"Could not get transit time for '{town_slug}' (ad {ad_id}), skipping.")
            continue
        if minutes > config.MAX_TRANSIT_MINUTES:
            continue

        existing_by_id[ad_id] = {
            "id": ad_id,
            "url": listing["url"],
            "title": listing["title"],
            "town": display_name(town_slug),
            "price_eur": price,
            "transit_minutes": minutes,
            "lat": coords["lat"],
            "lng": coords["lng"],
            "first_seen": existing_by_id.get(ad_id, {}).get(
                "first_seen", datetime.datetime.utcnow().isoformat()
            ),
        }
        kept += 1

    log(f"{kept} listing(s) matched the filters this run.")

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=config.MAX_LISTING_AGE_DAYS)
    fresh = [
        item for item in existing_by_id.values()
        if datetime.datetime.fromisoformat(item["first_seen"]) > cutoff
    ]
    fresh.sort(key=lambda item: item["transit_minutes"])

    store = {
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "origin_address": config.ORIGIN_ADDRESS,
        "price_max_eur": config.PRICE_MAX_EUR,
        "max_transit_minutes": config.MAX_TRANSIT_MINUTES,
        "listings": fresh,
    }

    save_json(config.LISTINGS_PATH, store)
    save_json(config.GEOCODE_CACHE_PATH, geocode_cache)
    save_json(config.TRANSIT_CACHE_PATH, transit_cache)
    log(f"Wrote {len(fresh)} listing(s) to {config.LISTINGS_PATH}.")


if __name__ == "__main__":
    main()
