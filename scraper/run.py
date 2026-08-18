"""
Entry point. Run as: python -m scraper.run

Pipeline:
  1. Pull unseen WG-Gesucht alert emails from the inbox (mailbox.py)
  2. Parse each one into individual listings (parse_alert.py)
  3. Drop anything inside Munich city limits, or already known
  4. Geocode the town, look up transit time from Tivolistraße (location.py)
  5. Keep it if price < MAX_PRICE_EUR and transit <= MAX_TRANSIT_MINUTES
  6. Merge into data/listings.json, mark the source email as read
"""

import json
import os
import sys
from datetime import datetime, timezone

from . import config, location, mailbox, parse_alert


def load_listings() -> dict:
    if os.path.exists(config.LISTINGS_PATH):
        with open(config.LISTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": None, "listings": []}


def save_listings(data: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.LISTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_in_munich(town: str) -> bool:
    town_lower = town.lower()
    return any(s in town_lower for s in config.EXCLUDED_TOWN_SUBSTRINGS)


def main() -> None:
    store = load_listings()
    known_urls = {item["url"] for item in store["listings"]}

    try:
        alerts = mailbox.fetch_unseen_alerts()
    except RuntimeError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(alerts)} unseen alert email(s).")

    new_count = 0
    for alert in alerts:
        parsed = parse_alert.parse_alert_email(alert["plain"], alert["subject"])

        if not parsed:
            parse_alert.dump_unparsed(
                alert["subject"], alert["plain"], alert["html"],
                reason="no wg-gesucht.de links found in plain text",
            )
            mailbox.mark_seen(alert["uid"])
            continue

        any_unresolved = False
        for item in parsed:
            if item.url in known_urls:
                continue

            if not item.town:
                parse_alert.dump_unparsed(
                    alert["subject"], alert["plain"], alert["html"],
                    reason=f"could not extract a town for {item.url}",
                )
                any_unresolved = True
                continue

            if is_in_munich(item.town):
                known_urls.add(item.url)  # remember it so we don't re-check every run
                continue

            if item.price_eur is not None and item.price_eur >= config.MAX_PRICE_EUR:
                known_urls.add(item.url)
                continue

            coords = location.geocode_town(item.town)
            if coords is None:
                parse_alert.dump_unparsed(
                    alert["subject"], alert["plain"], alert["html"],
                    reason=f"geocoding failed for town '{item.town}' ({item.url})",
                )
                any_unresolved = True
                continue

            minutes = location.transit_minutes_from_origin(item.town, *coords)
            known_urls.add(item.url)

            if minutes is None or minutes > config.MAX_TRANSIT_MINUTES:
                continue

            store["listings"].append(
                {
                    "url": item.url,
                    "title": item.title,
                    "price_eur": item.price_eur,
                    "town": item.town,
                    "transit_minutes": minutes,
                    "added_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            new_count += 1

        # Only mark the email read once every listing in it either matched
        # or was safely classified — an unresolved one means "try again
        # next run", in case it was a transient geocoding hiccup.
        if not any_unresolved:
            mailbox.mark_seen(alert["uid"])

    store["listings"].sort(key=lambda x: x["transit_minutes"])
    store["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_listings(store)

    print(f"Added {new_count} new listing(s). Total: {len(store['listings'])}.")


if __name__ == "__main__":
    main()
