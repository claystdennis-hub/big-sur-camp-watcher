#!/usr/bin/env python3
"""
Ventana Campground (Hyatt property SJCAC) availability monitor.

Ventana isn't on Recreation.gov or ReserveCalifornia, so camply can't see it.
This hits Hyatt's room-rates JSON API directly (no browser) and pushes a Pushover
alert when your target sites (49 / 50) are bookable. It also writes dashboard.html.

How it works: Hyatt's booking page calls
  /en-US/shop/service/rooms/roomrates/<prop>?...&checkinDate=...&checkoutDate=...
which returns {"roomRates": {"CS49": {...}, "CS50": {...}, ...}} listing ONLY the
sites available for those dates. Site N appears as key "CS<NN>" (zero-padded).
A plain GET with a browser-like User-Agent is enough — fast, quiet, reliable.

Setup:  pip install requests python-dotenv
Run:    python ventana_monitor.py once     # single pass (the 8am/6pm job uses this)
        python ventana_monitor.py watch     # loop every INTERVAL_MIN minutes
"""

import os
import sys
import json
import time
import html
import datetime as dt
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
PROPERTY = "sjcac"                     # Hyatt property code for Ventana Campground
MUST_HAVE = "50"                       # the site you actually need — alerts fire on this
PAIR_SITE = "49"                       # bonus: if open the SAME weekend, book both (room/privacy)
ADULTS = 2
INTERVAL_MIN = int(os.getenv("VENTANA_INTERVAL_MIN", "60"))
STATE_FILE = Path(__file__).with_name(".ventana_state.json")
DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")

# Your OPEN Fri/Sat weekends (calendar conflicts excluded). Summer/early-fall use
# Fri->Mon (3 nights) for Ventana's 3-night summer minimum; October Fri->Sun.
DATE_RANGES = [
    ("2026-06-19", "2026-06-22"),
    ("2026-06-26", "2026-06-29"),
    ("2026-07-17", "2026-07-20"),
    ("2026-08-07", "2026-08-10"),
    ("2026-08-28", "2026-08-31"),
    ("2026-09-04", "2026-09-07"),      # Labor Day wknd (golf Mon 9/7 — trim if needed)
    ("2026-09-11", "2026-09-14"),
    ("2026-09-18", "2026-09-21"),
    ("2026-09-25", "2026-09-28"),      # your tentative Big Sur weekend
    ("2026-10-16", "2026-10-18"),      # Fri -> Sun (off-season, 2 nights)
    ("2026-10-23", "2026-10-25"),
    ("2026-10-30", "2026-11-01"),
]

API_URL = ("https://www.hyatt.com/en-US/shop/service/rooms/roomrates/{prop}"
           "?spiritCode={prop}&rooms=1&adults={adults}"
           "&checkinDate={cin}&checkoutDate={cout}&kids=0&suiteUpgrade=true")
BOOKING_URL = ("https://www.hyatt.com/shop/rooms/{prop}"
               "?checkinDate={cin}&checkoutDate={cout}&rooms=1&adults={adults}")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ----------------------------------------------------------------------------
def notify(title, message, url=None):
    token, user = os.getenv("PUSHOVER_PUSH_TOKEN"), os.getenv("PUSHOVER_PUSH_USER")
    if not (token and user):
        print(f"!! Pushover creds missing — would have sent: {title}: {message} {url or ''}")
        return
    payload = {"token": token, "user": user, "title": title,
               "message": message, "priority": 1}
    if url:
        payload["url"], payload["url_title"] = url, "Open booking page"
    r = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=15)
    print(f"   pushover -> {r.status_code}")


def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


def fetch_rooms(checkin, checkout):
    """Return Hyatt's roomRates dict for these dates (keys like 'CS49'). Empty
    dict means sold out / nothing available; None means the request failed."""
    url = API_URL.format(prop=PROPERTY, adults=ADULTS, cin=checkin, cout=checkout)
    referer = BOOKING_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
    r = requests.get(url, headers={**HEADERS, "Referer": referer}, timeout=30)
    r.raise_for_status()
    return (r.json() or {}).get("roomRates", {}) or {}


def site_open(rooms, n):
    return f"CS{int(n):02d}" in rooms


def check_range(checkin, checkout, state):
    print(f">> {dt.datetime.now():%F %T}  Ventana {checkin} -> {checkout}")
    book_url = BOOKING_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
    try:
        rooms = fetch_rooms(checkin, checkout)
    except Exception as e:
        print(f"   request failed: {e}")
        return {"checkin": checkin, "checkout": checkout, "status": "error",
                "open": [], "url": book_url}

    has_must = site_open(rooms, MUST_HAVE)      # 50 — the trigger
    has_pair = site_open(rooms, PAIR_SITE)      # 49 — bonus
    print(f"   [debug] sites_available={len(rooms)} site_50={has_must} site_49={has_pair}")
    key = f"{checkin}:{checkout}"
    # Alert only on the must-have (50). Track whether we've alerted, and whether
    # the alert was the "both" jackpot, so a later 49-opening upgrades the alert.
    prev = state.get(key, "")

    if has_must:
        level = "both" if has_pair else "50"
        if prev != level:                       # new, or upgraded to the jackpot
            if has_pair:
                notify("\U0001f3d5\U0001f389 Ventana 49 + 50 BOTH open",
                       f"Jackpot: sites 49 AND 50 bookable {checkin} -> {checkout}. "
                       f"Book both for the extra room.", url=book_url)
            else:
                notify("\U0001f3d5 Ventana site 50 OPEN",
                       f"Site 50 bookable {checkin} -> {checkout}. Grab it on Hyatt "
                       f"(49 not open this weekend).", url=book_url)
            state[key] = level
            save_state(state)
        else:
            print(f"   50 still open ({level}) — already alerted")
        status = "OPEN: 49 + 50" if has_pair else "OPEN: 50"
        open_sites = (["49", "50"] if has_pair else ["50"])
    else:
        if key in state:
            state.pop(key); save_state(state)
        status = "sold out" if not rooms else "no 50"
        open_sites = []
        note = " (49 open, but no 50)" if has_pair else f" ({len(rooms)} other sites)"
        print(f"   {status}{note}")

    return {"checkin": checkin, "checkout": checkout, "status": status,
            "open": open_sites, "url": book_url, "total": len(rooms)}


# ----------------------------------------------------------------------------
def write_dashboard(results):
    now = dt.datetime.now().strftime("%a %b %-d, %Y %-I:%M %p")
    rows = ""
    any_open = False
    for r in sorted(results, key=lambda x: x["checkin"]):
        if r["status"].startswith("OPEN"):       # 50 is bookable
            any_open = True
            cell = (f'<a href="{html.escape(r["url"])}" '
                    f'style="color:#1a7f37;font-weight:700">{html.escape(r["status"])} &rarr; book</a>')
        else:
            color = ("#8c5800" if r["status"] == "sold out"
                     else "#cf222e" if r["status"] == "error" else "#57606a")
            extra = f' ({r.get("total", 0)} other sites)' if r["status"] == "no 50" else ""
            cell = f'<span style="color:{color}">{html.escape(r["status"] + extra)}</span>'
        rows += (f'<tr><td>{r["checkin"]} &rarr; {r["checkout"]}</td>'
                 f'<td style="text-align:right">{cell}</td></tr>')

    banner = ("\U0001f3d5 Site 50 is OPEN — see the green row below."
              if any_open else "Site 50 not open on any weekend right now.")
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ventana Camp Watcher</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:620px;
margin:40px auto;padding:0 16px;color:#1f2328">
<h1 style="margin-bottom:4px">Ventana Camp Watcher</h1>
<p style="color:#57606a;margin-top:0">Sites 49 &amp; 50 &middot; last checked {now}</p>
<p style="font-size:18px;font-weight:600">{banner}</p>
<table style="width:100%;border-collapse:collapse;font-size:15px">
<thead><tr style="border-bottom:2px solid #d0d7de;text-align:left">
<th style="padding:8px 0">Weekend</th><th style="padding:8px 0;text-align:right">Status</th></tr></thead>
<tbody>{rows}</tbody></table>
<p style="color:#8c959f;font-size:12px;margin-top:24px">
Auto-generated by ventana_monitor.py (8am / 6pm). You also get a Pushover alert the
moment a site opens.</p>
</body></html>"""
    DASHBOARD_FILE.write_text(doc)
    print(f"   dashboard -> {DASHBOARD_FILE}")


def run_once():
    state = load_state()
    results = [check_range(c, o, state) for c, o in DATE_RANGES]
    write_dashboard(results)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    if mode == "watch":
        print(f"Watching Ventana every {INTERVAL_MIN} min. Ctrl-C to stop.")
        while True:
            run_once()
            print(f"--- sleeping {INTERVAL_MIN}m ---")
            time.sleep(INTERVAL_MIN * 60)
    else:
        run_once()


if __name__ == "__main__":
    main()
