# Run the Ventana monitor on your Mac (8am + 6pm daily)

Ventana must run from your home network (Hyatt blocks datacenter IPs). This sets
it up once; after that it runs itself twice a day, updates `dashboard.html`, and
Pushover-alerts you when site 49/50 opens.

## One-time setup

Open **Terminal** (Cmd-Space, type "Terminal", Enter) and paste this block, then Enter:

```bash
cd ~ && git clone https://github.com/claystdennis-hub/big-sur-camp-watcher.git 2>/dev/null; cd ~/big-sur-camp-watcher && git pull && \
python3 -m venv .venv && \
./.venv/bin/pip install -r requirements.txt && \
./.venv/bin/python -m playwright install chromium
```

(If macOS prompts to install the Xcode command line tools / git, accept it, then
re-run the block.)

Next, add your Pushover keys:

```bash
cp .env.example .env && open -e .env
```

In the TextEdit window that opens, set these two lines and save:

```
PUSHOVER_PUSH_TOKEN=<your Pushover API token>
PUSHOVER_PUSH_USER=<your Pushover user key>
```

Then test it and install the schedule:

```bash
./.venv/bin/python ventana_monitor.py once && open dashboard.html && bash setup_launchd.sh
```

`dashboard.html` opens showing each weekend's status. After that it's hands-off.

## Day to day
- **Dashboard:** double-click `~/big-sur-camp-watcher/dashboard.html` anytime (it
  shows the last 8am/6pm result).
- **Run it manually:** `cd ~/big-sur-camp-watcher && ./.venv/bin/python ventana_monitor.py once`
- **Alerts:** Pushover pings your phone the moment 49/50 opens (history in the app).
- **Logs:** `ventana.log` in the folder.

## Change the times
Edit `com.bigsur.ventana.plist` (the two Hour values), then `bash setup_launchd.sh` again.

## Turn it off
`launchctl unload ~/Library/LaunchAgents/com.bigsur.ventana.plist`
