#!/usr/bin/env bash
# Installs the 8am/6pm launchd job for the Ventana monitor. Run once from the
# project folder: bash setup_launchd.sh
set -e
PLIST="com.bigsur.ventana.plist"
DEST="$HOME/Library/LaunchAgents/$PLIST"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST" "$DEST"

# Reload if already present
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"

echo "Loaded $PLIST — runs daily at 8:00 AM and 6:00 PM."
echo "It writes dashboard.html and ventana.log in this folder, and Pushover-alerts you on a hit."
echo "Run it right now to test:  ./.venv/bin/python ventana_monitor.py once && open dashboard.html"
