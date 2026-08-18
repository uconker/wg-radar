# Zimmer-Radar

Shows WG-Gesucht rooms that are:
- outside Munich's city limits,
- within ~1 hour of Tivolistraße by public transit + walking,
- under 700€.

It works by reading **your own WG-Gesucht email alerts**, not by scraping
wg-gesucht.de. That's a deliberate choice: WG-Gesucht currently serves an
automated "please confirm you're human" challenge to non-browser requests,
and this project doesn't try to defeat that. Email alerts are a feature
WG-Gesucht already offers for exactly this purpose, so this just automates
reading an inbox you control.

## How it works

```
WG-Gesucht email alert → your inbox (IMAP) → GitHub Action every few hours
  → parses each alert → drops anything inside Munich → geocodes the town
  → checks transit time to Tivolistraße (Google Maps) → keeps matches
  → commits data/listings.json → GitHub Pages shows it
```

## One-time setup

### 1. Create an inbox for the alerts

Easiest: a fresh, free Gmail account used for nothing else.

1. In that account, go to **Google Account → Security → 2-Step Verification**
   and turn it on (required for app passwords).
2. Then **Security → App passwords**, create one for "Mail", and save the
   16-character password somewhere safe — you'll need it below.

### 2. Point WG-Gesucht at that inbox

1. Sign into your normal WG-Gesucht account and go to **My WG-Gesucht →
   Filters and Email Alerts**.
2. Create a search: city **München**, the widest radius your account offers
   (this is what covers the surrounding towns — Dachau, Fürstenfeldbruck,
   Freising, Erding, Ebersberg, Starnberg, etc. — in one go), max rent
   **700€**, and set the alert email address to the inbox from step 1.
3. If your account doesn't offer a radius option, create one alert per
   surrounding town you care about instead — they can all point at the same
   inbox, the script doesn't care how many alerts feed it.
4. Save. Do **not** turn on email alerts for Munich-only searches — you don't
   need them, since the script drops anything inside Munich anyway.

### 3. Get a Google Maps API key

1. In the [Google Cloud Console](https://console.cloud.google.com/), create
   a project, enable the **Distance Matrix API**, and create an API key
   under **APIs & Services → Credentials**.
2. You'll need billing enabled on the project, but the free monthly credit
   comfortably covers this — each *new* town is looked up once and cached
   forever after (see `scraper/transit_cache.json`), so volume stays low.
3. Restrict the key to the Distance Matrix API only, to be safe.

### 4. Add GitHub repository secrets

In your repo, go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `IMAP_USER` | the Gmail address from step 1 |
| `IMAP_PASSWORD` | the 16-character app password from step 1 |
| `GOOGLE_MAPS_API_KEY` | the key from step 3 |

(`IMAP_HOST`, `IMAP_FOLDER`, `SENDER_FILTER` all have sensible defaults in
`scraper/config.py` — only add them as secrets if you need to override one.)

### 5. Enable GitHub Pages

**Settings → Pages → Source: Deploy from a branch → `main` / `/ (root)`.**
Your site will be live at `https://<username>.github.io/<repo-name>/`.

### 6. Turn on the schedule

The workflow in `.github/workflows/update.yml` already runs every 4 hours.
Push this repo to GitHub and it starts automatically — or trigger it once by
hand from the **Actions** tab (**Update listings → Run workflow**) so you
don't have to wait for the first scheduled run.

## Tuning it

Everything adjustable lives in `scraper/config.py`:

- `MAX_PRICE_EUR`, `MAX_TRANSIT_MINUTES` — the two filters.
- `EXCLUDED_TOWN_SUBSTRINGS` — how "inside Munich" is detected.
- Cron schedule — edit the `cron:` line in `.github/workflows/update.yml`
  ([crontab.guru](https://crontab.guru) helps).

## The one fragile part

`scraper/parse_alert.py` extracts title/price/town from the *text* of an
alert email using pattern matching, because I haven't seen a live copy of
WG-Gesucht's current email template to build against. It's written to fail
safely — anything it can't confidently parse gets skipped and dumped into
`scraper/unparsed_emails/` instead of producing wrong data.

After your first real alert arrives and a run has happened, check that
folder (only exists locally when you run the script yourself — it's
git-ignored). If real listings are ending up there instead of on the site,
open one, compare it to the regexes in `parse_alert.py`, and adjust — the
comments in that file point at exactly what each pattern is looking for.

## Legal note

This automates your own inbox, not WG-Gesucht's servers, which is a
meaningfully different (and much safer) thing to do than scraping. Even so,
this is for personal use finding a room — it's not a redistribution product,
and it's worth a skim of WG-Gesucht's terms if you're unsure.
