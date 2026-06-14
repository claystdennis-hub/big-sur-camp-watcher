#!/usr/bin/env python3
"""
Ventana Campground (Hyatt property SJCAC) availability monitor.

Ventana isn't on Recreation.gov or ReserveCalifornia, so camply can't see it —
it's sold through Hyatt. This script drives a headless browser to the Hyatt
booking page for the dates you want, expands the full site list, pushes a
Pushover alert if your target sites (49 / 50) are bookable, and writes a local
dashboard.html you can double-click to see the latest status.

IMPORTANT: run this from a residential connection (your Mac). Hyatt serves an
empty page to datacenter IPs (e.g. GitHub Actions), so cloud runs don't work.

Setup:
  pip install -r requirements.txt
  playwright install chromium
Run:
  python ventana_monitor.py once     # single pass (what the 8am/6pm job uses)
  python ventana_monitor.py watch    # loop every INTERVAL_MIN minutes
"""

import os
import re
import sys
import json
import time
import html
import datetime as dt
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
PROPERTY = "sjcac"                     # Hyatt property code for Ventana Campground
TARGET_SITES = ["49", "50"]            # sites you want; alert fires if any are bookable
ALERT_ON_ANY_SITE = False              # True = also alert when ANY site is open
ADULTS = 2
INTERVAL_MIN = int(os.getenv("VENTANA_INTERVAL_MIN", "20"))
STATE_FILE = Path(__file__).with_name(".ventana_state.json")     # dedupe repeat alerts
DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")      # glance-able status page

# Date ranges to check, each (checkin, checkout) as YYYY-MM-DD.
# Built from Clay's OPEN Fri/Sat weekends (calendar conflicts excluded).
# Summer/early-fall use Fri->Mon (3 nights) for Ventana's 3-night summer minimum;
# October uses Fri->Sun (2 nights, off-season).
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

BOOKING_URL = (
    "https://www.hyatt.com/shop/rooms/{prop}"
    "?checkinDate={cin}&checkoutDate={cout}&rooms=1&adults={adults}"
)


def site_pattern(n):
    """Matches 'Campsite 49', 'Campsite 049', 'Hike-in Campsite 49' (zero-pad tolerant)."""
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


def make_browser(p):
    """Launch a VISIBLE browser using real Chrome if available. Hyatt serves a
    blank page to headless Chromium, so headed + the system Chrome channel is
    what actually renders the site list."""
    args = ["--disable-blink-features=AutomationControlled"]
    try:
        return p.chromium.launch(headless=False, channel="chrome", args=args)
    except Exception:
        # Fall back to Playwright's bundled Chromium (still headed).
        return p.chromium.launch(headless=False, args=args)


def fetch_listing(ctx, checkin, checkout):
    """Render the booking page in the given context; expand all sites; return
    (final_url, body_text)."""
    url = BOOKING_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3500)

        # Dismiss the cookie/consent banner first — otherwise it intercepts the
        # "SHOW MORE" click and we only ever see the first 8 sites (so 49/50,
        # which load in a later batch, are never found).
        for sel in ("#onetrust-reject-all-handler", "#onetrust-accept-btn-handler",
                    "button:has-text('Reject')", "button:has-text('Accept')"):
            try:
                b = page.locator(sel).first
                if b.is_visible(timeout=1000):
                    b.click(timeout=2000)
                    page.wait_for_timeout(800)
                    break
            except Exception:
                pass

        # If Hyatt bounced us to the search page, the dates are unavailable.
        if "/search/" not in page.url:
            # Expand the full site list: click "SHOW MORE" until it's gone.
            for _ in range(30):
                try:
                    btn = page.get_by_role("button", name="SHOW MORE")
                    if btn.count() == 0:
                        btn = page.get_by_text("SHOW MORE", exact=False)
                    if btn.count() == 0 or not btn.first.is_visible():
                        break
                    btn.first.scroll_into_view_if_needed(timeout=3000)
                    btn.first.click(timeout=3000)
                    page.wait_for_timeout(1500)
                except Exception:
                    break

        return page.url, page.inner_text("body")
    finally:
        page.close()


def find_open_sites(text):
    return [n for n in TARGET_SITES if site_pattern(n).search(text)]


def check_range(ctx, checkin, checkout, state):
    """Check one date range; alert if needed; return a dashboard result dict."""
    print(f">> {dt.datetime.now():%F %T}  Ventana {checkin} -> {checkout}")
    book_url = BOOKING_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
    try:
        final_url, text = fetch_listing(ctx, checkin, checkout)
    except Exception as e:
        print(f"   error loading page: {e}")
        return {"checkin": checkin, "checkout": checkout, "status": "error",
                "open": [], "url": book_url}

    unavailable = ("/search/" in final_url) or any(m in text.lower() for m in UNAVAILABLE_MARKERS)
    open_sites = find_open_sites(text)
    campsite_tokens = len(re.findall(r"Campsite", text))
    print(f"   [debug] campsite_tokens={campsite_tokens} "
          f"search_redirect={'/search/' in final_url} body_len={len(text)}")
    key = f"{checkin}:{checkout}"
    already = set(state.get(key, []))

    if open_sites:
        new = [s for s in open_sites if s not in already]
        if new:
            sites = ", ".join(open_sites)
            notify(f"\U0001f3d5 Ventana site {sites} OPEN",
                   f"Site {sites} bookable {checkin} -> {checkout}. Grab it on Hyatt.",
                   url=book_url)
            state[key] = sorted(already | set(open_sites))
            save_state(state)
        else:
            print(f"   still open ({open_sites}) — already alerted")
        status = "OPEN"
    else:
        if key in state:                     # reset so a reopen re-alerts
            state.pop(key); save_state(state)
        if unavailable:
            status = "sold out"
        elif campsite_tokens == 0:
            status = "no data"               # page didn't render (block / network)
        else:
            status = "no 49/50"              # sites exist for these dates, just not yours
        print(f"   {status}")

    return {"checkin": checkin, "checkout": checkout, "status": status,
            "open": open_sites, "url": book_url}


# ----------------------------------------------------------------------------
def write_dashboard(results):
    """Write a self-contained dashboard.html summarizing the latest run."""
    now = dt.datetime.now().strftime("%a %b %-d, %Y %-I:%M %p")
    colors = {"OPEN": "#1a7f37", "no 49/50": "#57606a", "sold out": "#8c5800",
              "no data": "#cf222e", "error": "#cf222e"}
    rows = ""
    any_open = False
    for r in sorted(results, key=lambda x: x["checkin"]):
        c = colors.get(r["status"], "#57606a")
        label = r["status"]
        if r["status"] == "OPEN":
            any_open = True
            label = "OPEN: " + ", ".join(r["open"])
            cell = f'<a href="{html.escape(r["url"])}" style="color:#1a7f37;font-weight:700">{label} &rarr; book</a>'
        else:
            cell = f'<span style="color:{c}">{html.escape(label)}</span>'
        rows += (f'<tr><td>{r["checkin"]} &rarr; {r["checkout"]}</td>'
                 f'<td style="text-align:right">{cell}</td></tr>')

    banner = ("\U0001f3d5 A target site is OPEN — check the green row below."
              if any_open else "No target sites (49/50) open right now.")
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
Auto-generated by ventana_monitor.py. Refresh this page after the next run (8am / 6pm).
You also get a Pushover alert the moment a site opens.</p>
</body></html>"""
    DASHBOARD_FILE.write_text(doc)
    print(f"   dashboard -> {DASHBOARD_FILE}")


def run_once():
    state = load_state()
    results = []
    with sync_playwright() as p:
        browser = make_browser(p)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"),
            viewport={"width": 1280, "height": 1800},
        )
        try:
            for c, o in DATE_RANGES:
                results.append(check_range(ctx, c, o, state))
        finally:
            browser.close()
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
