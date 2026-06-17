#!/usr/bin/env python3
"""
Ventana Campground (Hyatt property SJCAC) availability monitor.

Hyatt guards its booking API with Kasada anti-bot protection, which blocks
headless browsers AND cold script requests (403). The method that gets through
(confirmed working): launch a REAL, visible browser, let the booking page run
Kasada's JS and make its own availability call, and intercept that response.
We then check the JSON for site 50 (the trigger) and 49 (bonus), alert via
Pushover, and write dashboard.html.

To avoid hijacking your screen, the browser window is launched OFF-SCREEN. It
only runs ~1-2 min, twice a day (8am/6pm via launchd).

Setup:  pip install playwright requests python-dotenv && playwright install chromium
Run:    python ventana_monitor.py once     # single pass (what the schedule uses)
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
from playwright.sync_api import sync_playwright

load_dotenv()

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
PROPERTY = "sjcac"
MUST_HAVE = "50"                       # site 50 — alerts fire on this
PAIR_SITE = "49"                       # bonus: if open the SAME weekend, book both
ADULTS = 2
INTERVAL_MIN = int(os.getenv("VENTANA_INTERVAL_MIN", "60"))
STATE_FILE = Path(__file__).with_name(".ventana_state.json")
DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")

# Kasada blocks headless — the window MUST be visible. We shove it off-screen so
# it doesn't steal focus. If your Mac clamps the position and it still shows,
# delete the --window-position arg.
LAUNCH_ARGS = ["--window-position=-3000,-3000", "--window-size=1200,850"]
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Your open Fri/Sat weekends. Summer = 3 nights (Ventana's summer minimum), Oct = 2.
DATE_RANGES = [
    ("2026-06-19", "2026-06-22"),
    ("2026-06-26", "2026-06-29"),
    ("2026-07-17", "2026-07-20"),
    ("2026-08-07", "2026-08-10"),
    ("2026-08-28", "2026-08-31"),
    ("2026-09-04", "2026-09-07"),      # Labor Day wknd (golf Mon 9/7 — trim if needed)
    ("2026-09-11", "2026-09-14"),
    ("2026-09-18", "2026-09-21"),
    ("2026-09-25", "2026-09-28"),
    ("2026-10-16", "2026-10-18"),      # off-season, 2 nights
    ("2026-10-23", "2026-10-25"),
    ("2026-10-30", "2026-11-01"),
]

SHOP_URL = ("https://www.hyatt.com/shop/rooms/{prop}"
            "?checkinDate={cin}&checkoutDate={cout}&rooms=1&adults={adults}")


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


def evaluate(rooms, checkin, checkout, state):
    """rooms = roomRates dict, or None if the page never returned data."""
    book_url = SHOP_URL.format(prop=PROPERTY, cin=checkin, cout=checkout, adults=ADULTS)
    key = f"{checkin}:{checkout}"

    if rooms is None:                       # interception got nothing (block/timeout)
        print("   no data (page didn't return availability)")
        return {"checkin": checkin, "checkout": checkout, "status": "no data",
                "open": [], "url": book_url, "total": 0}

    has50 = f"CS{int(MUST_HAVE):02d}" in rooms
    has49 = f"CS{int(PAIR_SITE):02d}" in rooms
    print(f"   sites_available={len(rooms)} site_50={has50} site_49={has49}")

    if has50:
        level = "both" if has49 else "50"
        if state.get(key) != level:
            if has49:
                notify("\U0001f3d5\U0001f389 Ventana 49 + 50 BOTH open",
                       f"Jackpot: 49 AND 50 bookable {checkin} -> {checkout}. Book both.",
                       url=book_url)
            else:
                notify("\U0001f3d5 Ventana site 50 OPEN",
                       f"Site 50 bookable {checkin} -> {checkout} (49 not open). Grab it.",
                       url=book_url)
            state[key] = level
            save_state(state)
        else:
            print(f"   50 still open ({level}) — already alerted")
        status = "OPEN: 49 + 50" if has49 else "OPEN: 50"
        open_sites = ["49", "50"] if has49 else ["50"]
    else:
        if key in state:
            state.pop(key); save_state(state)
        status = "sold out" if not rooms else "no 50"
        open_sites = []

    return {"checkin": checkin, "checkout": checkout, "status": status,
            "open": open_sites, "url": book_url, "total": len(rooms)}


def run_once():
    state = load_state()
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=LAUNCH_ARGS)
        ctx = browser.new_context(viewport={"width": 1200, "height": 850}, user_agent=UA)
        page = ctx.new_page()

        captured = {"data": None}
        def on_response(resp):
            try:
                if f"roomrates/{PROPERTY}" in resp.url and resp.status == 200:
                    captured["data"] = resp.json()
            except Exception:
                pass
        page.on("response", on_response)

        for cin, cout in DATE_RANGES:
            print(f">> {dt.datetime.now():%F %T}  Ventana {cin} -> {cout}")
            captured["data"] = None
            url = SHOP_URL.format(prop=PROPERTY, cin=cin, cout=cout, adults=ADULTS)
            try:
                page.goto(url, wait_until="load", timeout=45000)
                page.wait_for_timeout(4500)        # let the page fire its availability call
            except Exception as e:
                print(f"   load failed: {e}")
                results.append(evaluate(None, cin, cout, state))
                continue
            data = captured["data"]
            rooms = (data or {}).get("roomRates", {}) if data is not None else None
            results.append(evaluate(rooms, cin, cout, state))

        browser.close()
    write_dashboard(results)


# ----------------------------------------------------------------------------
def write_dashboard(results):
    now = dt.datetime.now().strftime("%a %b %-d, %Y %-I:%M %p")
    rows = ""
    any_open = False
    for r in sorted(results, key=lambda x: x["checkin"]):
        if r["status"].startswith("OPEN"):
            any_open = True
            cell = (f'<a href="{html.escape(r["url"])}" '
                    f'style="color:#1a7f37;font-weight:700">{html.escape(r["status"])} &rarr; book</a>')
        else:
            color = ("#8c5800" if r["status"] == "sold out"
                     else "#cf222e" if r["status"] in ("error", "no data") else "#57606a")
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
<p style="color:#57606a;margin-top:0">Site 50 (49 = bonus) &middot; last checked {now}</p>
<p style="font-size:18px;font-weight:600">{banner}</p>
<table style="width:100%;border-collapse:collapse;font-size:15px">
<thead><tr style="border-bottom:2px solid #d0d7de;text-align:left">
<th style="padding:8px 0">Weekend</th><th style="padding:8px 0;text-align:right">Status</th></tr></thead>
<tbody>{rows}</tbody></table>
<p style="color:#8c959f;font-size:12px;margin-top:24px">
Auto-generated by ventana_monitor.py (8am / 6pm). Pushover alerts you the moment site 50 opens.</p>
</body></html>"""
    DASHBOARD_FILE.write_text(doc)
    print(f"   dashboard -> {DASHBOARD_FILE}")


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
