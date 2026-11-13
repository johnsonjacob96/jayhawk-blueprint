#!/bin/bash
set -euo pipefail
export PATH="$HOME/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
# Use the committed root export, including the latest generated data snapshot.
node --check app.js
python3 rebuild/stage_site.py
wrangler pages deploy _site --project-name jayhawk-blueprint --branch main
