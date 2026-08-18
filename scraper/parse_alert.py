"""
Pulls individual listings out of a WG-Gesucht "Email Alert" message.

IMPORTANT — read this before you rely on the output:
I haven't seen a live copy of WG-Gesucht's current alert-email template, so
this is a best-effort, defensive parser rather than something verified
against the real thing. It's built to degrade safely: anything it can't
confidently parse gets skipped and dumped to scraper/unparsed_emails/ instead
of silently producing wrong data.

After your first real alert email arrives, open one of those dumped files,
compare it to what this parser expects below, and adjust the regexes if
needed. The structure (find links -> take the text around each one -> pull
out price/town) should hold even if the exact wording WG-Gesucht uses shifts.
"""

import os
import re
from dataclasses import dataclass

from . import config

LINK_RE = re.compile(r"https?://(?:www\.)?wg-gesucht\.de/[^\s\"'<>]+\.html")
PRICE_RE = re.compile(r"(\d{2,4}(?:[.,]\d{2})?)\s*€")
# German postal code (5 digits) followed by a town/district name.
PLACE_RE = re.compile(r"\b\d{5}\s+([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-\. ]{1,40})")
# Fallback: "München - Schwabing" / "München Schwabing" style district tags.
DISTRICT_RE = re.compile(r"\b(München|Muenchen)[\s\-]*([A-Za-zÄÖÜäöüß\-]*)")


@dataclass
class ParsedListing:
    url: str
    title: str
    price_eur: float | None
    town: str


def _clean_block(block: str) -> str:
    return "\n".join(line.strip() for line in block.splitlines() if line.strip())


def _guess_title(block_before_link: str) -> str:
    lines = [l.strip() for l in block_before_link.splitlines() if l.strip()]
    # Heuristic: within this listing's block, the title is the last
    # reasonably-long line that isn't itself the price or the
    # postal-code/town line — those two always come AFTER the title in
    # WG-Gesucht's listing summaries, so scanning from the end and skipping
    # them lands on the title even when there's boilerplate earlier in the
    # block (e.g. a greeting before the very first listing in an email).
    candidates = [
        l for l in lines
        if 8 <= len(l) <= 120 and not PRICE_RE.search(l) and not PLACE_RE.search(l)
    ]
    if candidates:
        return candidates[-1]
    return lines[-1] if lines else "(untitled listing)"


def _guess_town(block: str) -> str:
    m = PLACE_RE.search(block)
    if m:
        return m.group(1).strip()
    m = DISTRICT_RE.search(block)
    if m:
        district = m.group(2).strip()
        return f"München {district}".strip() if district else "München"
    return ""


def _guess_price(block: str) -> float | None:
    m = PRICE_RE.search(block)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_alert_email(plain_text: str, subject: str = "") -> list[ParsedListing]:
    if not plain_text:
        return []

    links = list(LINK_RE.finditer(plain_text))
    if not links:
        return []

    listings = []
    seen_urls = set()
    prev_end = 0
    for m in links:
        url = m.group(0).rstrip(".,)")
        # Scope everything to the text strictly between the previous link
        # (or the start of the email) and this one, so blocks never bleed
        # into a neighbouring listing's title/price/town.
        block = _clean_block(plain_text[prev_end:m.start()])
        prev_end = m.end()

        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = _guess_title(block)
        price = _guess_price(block)
        town = _guess_town(block)

        listings.append(ParsedListing(url=url, title=title, price_eur=price, town=town))

    return listings


def dump_unparsed(subject: str, plain_text: str, html: str, reason: str) -> None:
    os.makedirs(config.UNPARSED_DIR, exist_ok=True)
    safe_subject = re.sub(r"[^a-zA-Z0-9]+", "_", subject)[:60] or "email"
    path = os.path.join(config.UNPARSED_DIR, f"{safe_subject}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"REASON: {reason}\nSUBJECT: {subject}\n\n--- PLAIN TEXT ---\n{plain_text}\n\n--- HTML ---\n{html}\n")
