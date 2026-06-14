# Big Sur Camp Watcher

Monitors the campgrounds that actually exist in Big Sur — across the two
booking systems that run them — and pushes an alert to your phone the moment a
site opens, with a link to the booking page. You finish a 15-second checkout.

It's a thin, sane wrapper around [`camply`](https://github.com/juftin/camply),
the mature open-source campsite scanner, pre-configured for Big Sur and wired
for free always-on hosting.

## Why it works this way (read this first)

There are two completely different "availability" events, and only one is
winnable by software:

1. **The 6-months-out drop.** New inventory appears at a fixed time
   (ReserveCalifornia: 8:00:00 AM PT). Coastal sites sell out in *seconds*. No
   alert tool wins this — you have to be logged in and clicking at 8:00:00.
   For this, run `./scan.sh watch` that morning so you see inventory the instant
   it's live, and have the booking page already open.
2. **Cancellations.** People cancel constantly, freeing single nights at random.
   *This* is the sweet spot for monitoring — a 24/7 poller catches openings you'd
   never see manually. This is what the GitHub Actions setup below is for.

**On auto-booking:** you asked for it as a fast-follow, and that's the right call
to defer. Note that *no* tool on the market — free or paid (Campnab included) —
auto-books, because Recreation.gov and ReserveCalifornia both use CAPTCHAs,
bot-detection, and ToS that prohibit automated checkout. A bot fighting CAPTCHA
is also *slower* than you tapping confirm on a pre-loaded page. Phase 2 plan and
honest risks are at the bottom.

## What's in here

```
big-sur-camp-watcher/
├── README.md              # this file
├── search_config.yaml     # EDIT: your dates, nights, which campgrounds
├── .env.example           # copy to .env, add notification creds
├── scan.sh                # run it: ./scan.sh once  |  ./scan.sh watch
├── campgrounds.md          # IDs + booking deep links for every Big Sur site
└── .github/workflows/scan.yml   # free 24/7 hosting via GitHub Actions cron
```

## Setup (about 15 minutes)

**1. Install camply** (needs Python 3.9+):

```bash
cd big-sur-camp-watcher
python3 -m venv .venv && source .venv/bin/activate
pip install camply
chmod +x scan.sh
```

**2. Set up notifications.** Copy `.env.example` to `.env` and fill in one
channel. Pushover ($5 one-time, instant phone push) is the best experience;
Telegram is free; email works everywhere. See `.env.example` for the exact keys.

**3. Set your trip** in `search_config.yaml` — start/end dates, nights, and which
campgrounds. Kirk Creek, Plaskett Creek, and Pfeiffer Big Sur are pre-filled.
To add Andrew Molera or Limekiln, grab their IDs with the discovery commands in
`campgrounds.md`.

**4. Test it:**

```bash
./scan.sh once
```

You'll see it query both providers. If a matching site is open, you get a
notification immediately.

## Running it 24/7 (recommended hosting)

**Use GitHub Actions cron — free, always-on, nothing to maintain.** You don't
need a server or to leave your Mac on. Why this over a VPS or your laptop: a $5
VPS works but is a box to patch and pay for; your laptop only polls while it's
awake and online. GitHub runs the job on a schedule in their cloud for free.

1. Push this folder to a **private** GitHub repo.
2. Repo → **Settings → Secrets and variables → Actions** → add
   `PUSHOVER_PUSH_TOKEN` and `PUSHOVER_PUSH_USER` (or your channel's keys).
3. The workflow in `.github/workflows/scan.yml` then runs every ~15 min
   automatically. Trigger a manual test run from the **Actions** tab.

Caveat: GitHub's scheduled runs are best-effort and can lag a few minutes under
load — fine for cancellation-sniping, not for the 8AM drop. For the drop, run
`./scan.sh watch` locally that morning (polls every 5 min, or set
`INTERVAL=1 ./scan.sh watch` to hammer it).

## Ventana monitor (Hyatt — separate from camply)

Ventana Campground (sites 49/50) is sold through Hyatt, not the government
systems, so camply can't watch it. `ventana_monitor.py` handles it with a
headless browser. The Hyatt booking URL and site labels were verified against the
live page, so it's ready to run.

```bash
pip install -r requirements.txt
playwright install chromium
python ventana_monitor.py once     # single pass
python ventana_monitor.py watch    # loop every 20 min (VENTANA_INTERVAL_MIN to change)
```

Set your target weekends in the `DATE_RANGES` list at the top of the script
(remember Ventana's 3-night summer minimum). It alerts via the same Pushover keys
in `.env` and dedupes so you're not re-pinged for the same opening.

To run it 24/7 on GitHub Actions, add a job that does `pip install -r
requirements.txt && playwright install --with-deps chromium` then
`python ventana_monitor.py once` on a cron — same pattern as `scan.yml`.

## Note on auto-booking
We deliberately stopped at alerts (you wanted final say, and the booking +
cancellation fees made speculative holds not worth it). If you ever want a
Playwright booker that completes checkout on an alert, it can be added on top of
this — but the alert-with-tap-through flow wins most grabs without that fragility.
