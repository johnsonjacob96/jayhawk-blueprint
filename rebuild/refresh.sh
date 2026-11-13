#!/bin/bash
set -euo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
# Do not mix an unattended refresh with an in-progress model or UI edit.
git diff --quiet
git diff --cached --quiet
LOCK_DIR="$REPO_DIR/rebuild/data/refresh.lock"
mkdir -p "$REPO_DIR/rebuild/data"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo 'Another refresh owns the lock; exiting.'
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT
git pull --ff-only origin main
SNAPSHOT_DATE="$(/usr/bin/python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo("America/Chicago")).date().isoformat())')"
/usr/bin/python3 rebuild/build.py --season 2027 --as-of "$SNAPSHOT_DATE" --refresh
# Supplemental private corpus: one Kansas game-log request/day. A failure here
# is logged explicitly and does not block independently sourced Torvik grades.
if ! /usr/bin/python3 rebuild/fetch_cbbd.py --season 2027 --team Kansas; then
  printf 'WARNING: CBBD research corpus refresh failed; public grades use Torvik only.\n' >&2
fi
node --check rebuild/web/app.js
/usr/bin/python3 rebuild/publish.py
git add index.html styles.css app.js data.js assets rebuild/history
if ! git diff --cached --quiet; then
  git commit -m "Refresh Kansas player snapshot $SNAPSHOT_DATE"
  git push origin main
fi
bash rebuild/deploy_cloudflare.sh
printf 'Refresh complete: %s\n' "$SNAPSHOT_DATE"
