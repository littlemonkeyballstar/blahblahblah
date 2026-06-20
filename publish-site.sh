#!/usr/bin/env bash
# Regenerate catalogs and list every file that must be uploaded together.
set -euo pipefail
cd "$(dirname "$0")"

echo "Regenerating audio catalog..."
python3 generate-catalog.py
echo "Regenerating media/search catalog..."
python3 generate-media-catalog.py

echo ""
echo "Upload ALL of these files in one deploy (partial uploads break the site):"
printf '%s\n' \
  index.html \
  audio.html \
  site.js \
  site.css \
  lectures-home.js \
  lectures-meta.js \
  lectures-data.js \
  home-previews-pool.js \
  search-index.js \
  data/search-audio.json \
  data/lectures/*.js