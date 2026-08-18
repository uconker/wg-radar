"""
Talks to the inbox that receives WG-Gesucht email alerts.

We never touch wg-gesucht.de directly here — this only reads a mailbox you
already control, via IMAP. That's why this project sidesteps WG-Gesucht's
bot-detection entirely: it's not scraping anything, just reading emails that
WG-Gesucht itself already decided to send you.
"""

import email
import imaplib
from email.header import decode_header
from email.message import Message

from . import config


def _decode(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _extract_bodies(msg: Message) -> tuple[str, str]:
    """Returns (plain_text, html) — either may be empty."""
    plain, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if ctype == "text/plain" and not plain:
                plain = text
            elif ctype == "text/html" and not html:
                html = text
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html = text
            else:
                plain = text
    return plain, html


def fetch_unseen_alerts() -> list[dict]:
    """
    Connects, finds unseen emails from WG-Gesucht, and returns a list of
    dicts: {uid, subject, date, plain, html}. Does NOT mark anything as
    seen — call mark_seen() yourself once you've successfully processed a
    message, so a crash mid-run doesn't lose emails.
    """
    if not config.IMAP_USER or not config.IMAP_PASSWORD:
        raise RuntimeError(
            "IMAP_USER / IMAP_PASSWORD are not set — see README.md for how "
            "to create these as GitHub Actions secrets."
        )

    results = []
    conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    try:
        conn.login(config.IMAP_USER, config.IMAP_PASSWORD)
        conn.select(config.IMAP_FOLDER)

        # FROM search is a substring match in most IMAP servers, incl. Gmail.
        status, data = conn.search(None, f'(UNSEEN FROM "{config.SENDER_FILTER}")')
        if status != "OK":
            return results

        uids = data[0].split()
        for uid in uids:
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            plain, html = _extract_bodies(msg)
            results.append(
                {
                    "uid": uid.decode(),
                    "subject": _decode(msg.get("Subject", "")),
                    "date": msg.get("Date", ""),
                    "plain": plain,
                    "html": html,
                }
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()

    return results


def mark_seen(uid: str) -> None:
    conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    try:
        conn.login(config.IMAP_USER, config.IMAP_PASSWORD)
        conn.select(config.IMAP_FOLDER)
        conn.store(uid.encode(), "+FLAGS", "\\Seen")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()
