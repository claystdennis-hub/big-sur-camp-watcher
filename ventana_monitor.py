#!/usr/bin/env python3
"""
Ventana Campground (Hyatt property SJCAC) availability monitor.

Ventana isn't on Recreation.gov or ReserveCalifornia, so camply can't see it —
it's sold through Hyatt. This script drives a headless browser to the Hyatt
booking page for the dates you want, expands the full site list, and pushes a
Pushover alert if your target sites (49 / 50) are bookable.

VERIFIED against the live page (2026 dates):
  * Booking URL:  https://www.hyatt.com/shop/rooms/sjcac?checkinDate=YYYY-MM-DD&checkoutDate=YYYY-MM-DD&rooms=1&adults=2
  * Site labels:  "Campsite 49", "Campsite 50" (single digits are zero-padded,
                  e.g. "Campsite 02"; hike-in sites read "Hike-in Campsite 01").
  * The page lists ONLY bookable sites, 8 at a time behind a "SHOW MORE" button,
    so we must expand the list before scanning.
  * Sold-out / unavailable dates redirect to a /search/ page with a
    "not available during those dates" banner.

Setup:
  pip install playwright requests python-dotenv
  playwright install chromium
Run:
  python ventana_monitor.py once     # single pass
  python ventana_monitor.py watch    # loop every INTERVAL_MIN minutes
"""

import os
import re
import sys
import json
import time
import datetime as dt
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
PROPERTY = "sjcac"                      # Hyatt property code for Ventana Campground
TARGET_SITES = ["49", "50"]            # sites you want; alert fires if any are bookable
ALERT_ON_ANY_SITE = False              # True = also alert when ANY site is open
ADULTS = 2
INTERVAL_MIN = int(os.getenv("VENTANA_INTERVAL_MIN", "20"))
STATE_FILE = Path(__file__).with_name(".ventana_state.json")  # dedupe repeat alerts

# Date ranges to check, each (checkin, checkout) as YYYY-MM-DD.
# Built from Clay's OPEN Fri/Sat weekends (calendar conflicts excluded).
# Summer/early-fall use Fri->Mon (3 nights) because Ventana enforces a 3-night
# minimum in peak season; October uses Fri->Sun (2 nights, off-season).
DATE_RANGES = [
    ("2026-06-19", "2026-06-22"),      # Fri -> Mon
    ("2026-06-26", "2026-06-29"),
    ("2026-07-17", "2026-07-20"),
    ("2026-08-07", "2026-08-10"),
    ("2026-08-28", "2026-08-31"),
    ("2026-09-04", "2026-09-07"),      # Labor Day wknd (you have golf Mon 9/7 — trim if needed)
    ("2026-09-11", "2026-09-14"),
    ("2026-09-18", "2026-09-21"),
    ("2026-09-25", "2026-09-28"),      # your tentative Big Sur weekend — site 49 was OPEN on last check
    ("2026-10-16", "2026-10-18"),      # Fri -> Sun (off-season, 2 nights)
    ("2026-10-23", "2026-10-25"),
    ("2026-10-30", "2026-11-01"),
]

BOOKING_URL = (
    "https://www.hyatt.com/shop/rooms/{prop}"
    "?checkinDate={cin}&checkoutDate={cout}&rooms=1&adults={adults}"
)

# Matches "Campsite 49", "Campsite 049", "Hike-in Campsite 49" (zero-pad tolerant).
def site_pattern(n):
    return re.compile(r"(?:Hike-?in\s+)?Campsite\s*0*" + re.escape(str(int(n))) + r"\b",
                      re.IGNORECASE)

UNAVAILABLE_MARKERS = ["not available during those dates", "no rooms available",
                       "sold out", "no availability"]


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


def fetch_listing(checkin, checkout):
    """Render the booking page, expand all sites, return (final_url, body_text)."""
    url = BOOKING_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"),
            viewport={"width": 1280, "height": 1800},
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3500)

        # If Hyatt bounced us to the search page, the dates are unavailable.
        if "/search/" not in page.url:
            # Expand the full site list: click "SHOW MORE" until it's gone.
            for _ in range(20):
                try:
                    btn = page.get_by_text("SHOW MORE", exact=False)
                    if btn.count() == 0 or not btn.first.is_visible():
                        break
                    btn.first.click()
                    page.wait_for_timeout(1200)
                except Exception:
                    break

        final_url, text = page.url, page.inner_text("body")
        browser.close()
        return final_url, text


def find_open_sites(text):
    return [n for n in TARGET_SITES if site_pattern(n).search(text)]


def check_range(checkin, checkout, state):
    print(f">> {dt.datetime.now():%F %T}  Ventana {checkin} -> {checkout}")
    try:
        final_url, text = fetch_listing(checkin, checkout)
    except Exception as e:
        print(f"   error loading page: {e}")
        return

    unavailable = ("/search/" in final_url) or any(m in text.lower() for m in UNAVAILABLE_MARKERS)
    open_sites = find_open_sites(text)
    key = f"{checkin}:{checkout}"
    already = set(state.get(key, []))

    if open_sites:
        new = [s for s in open_sites if s not in already]
        if new:
            sites = ", ".join(open_sites)
            book_url = BOOKING_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
            notify(f"\U0001f3d5 Ventana site {sites} OPEN",
                   f"Site {sites} bookable {checkin} -> {checkout}. Grab it on Hyatt.",
                   url=book_url)
            state[key] = sorted(already | set(open_sites))
            save_state(state)
        else:
            print(f"   still open ({open_sites}) — already alerted")
    else:
        print("   targets not available" + (" (dates sold out)" if unavailable else ""))
        if key in state:                     # reset so a reopen re-alerts
            state.pop(key); save_state(state)


def run_once():
    state = load_state()
    for cin, cout in DATE_RANGES:
        check_range(cin, cout, state)


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
