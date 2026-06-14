#!/usr/bin/env bash
# =============================================================================
# Big Sur Camp Watcher — runs camply against both providers and notifies you
# when a site opens.  Reads trip params from search_config.yaml, creds from .env
#
# Usage:
#   ./scan.sh once     # single pass, then exit  (good for cron / GitHub Actions)
#   ./scan.sh watch    # poll both providers every $INTERVAL min until you stop it
#                      # (use this the morning of an 8AM drop)
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")"

MODE="${1:-once}"
INTERVAL="${INTERVAL:-5}"        # minutes between polls in 'watch' mode
CONFIG="search_config.yaml"

# ---- load creds --------------------------------------------------------------
if [[ -f .env ]]; then set -a; source .env; set +a; fi
NOTIFY="${CAMPLY_NOTIFICATIONS:-Silent}"

# ---- activate venv if present ------------------------------------------------
[[ -d .venv ]] && source .venv/bin/activate

# ---- pull trip params + IDs out of the yaml (PyYAML ships with camply) -------
read_yaml() { python3 - "$CONFIG" "$1" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1])) or {}
d = cfg
for k in sys.argv[2].split("."):
    d = d.get(k, {}) if isinstance(d, dict) else {}
print(" ".join(map(str, d)) if isinstance(d, list) else ("" if isinstance(d, dict) else d))
PY
}

START=$(read_yaml start_date)
END=$(read_yaml end_date)
NIGHTS=$(read_yaml nights)
RDG_CAMPS=$(read_yaml recreation_dot_gov.campgrounds)
RC_AREAS=$(read_yaml reserve_california.rec_areas)

# Single, non-blocking pass over one provider (so both providers get a turn).
run() {
  echo ">> $(date '+%F %T')  camply campsites $*"
  camply campsites "$@" \
    --start-date "$START" --end-date "$END" --nights "$NIGHTS" \
    --notifications "$NOTIFY" --notify-first-try \
    || echo "   (no matches / transient error)"
}

one_pass() {
  if [[ -n "${RDG_CAMPS// }" ]]; then
    args=(--provider RecreationDotGov); for id in $RDG_CAMPS; do args+=(--campground "$id"); done
    run "${args[@]}"
  fi
  if [[ -n "${RC_AREAS// }" ]]; then
    args=(--provider ReserveCalifornia); for id in $RC_AREAS; do args+=(--rec-area "$id"); done
    run "${args[@]}"
  fi
}

if [[ "$MODE" == "watch" ]]; then
  echo "Watching both providers every ${INTERVAL} min. Ctrl-C to stop."
  while true; do one_pass; echo "--- sleeping ${INTERVAL}m ---"; sleep "$((INTERVAL*60))"; done
else
  one_pass
fi
