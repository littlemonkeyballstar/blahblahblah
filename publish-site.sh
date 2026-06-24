#!/usr/bin/env bash
# Regenerate catalogs and list every file that must be uploaded together.
set -euo pipefail
cd "$(dirname "$0")"

AUDIO_SRC="$(python3 - <<'PY'
from pathlib import Path
root = Path(__file__).resolve().parent.parent / "www" / "SheikhFaisalAudioLectures"
print(root)
PY
)"

echo "Regenerating media/search catalog..."
python3 generate-media-catalog.py

if [[ -d "$AUDIO_SRC" ]]; then
  echo "Regenerating audio catalog from $AUDIO_SRC ..."
  python3 generate-catalog.py
else
  echo ""
  echo "Skipping audio catalog regen — source not found:"
  echo "  $AUDIO_SRC"
  echo "Run generate-catalog.py manually on a machine with the MP3 library."
fi

echo ""
echo "Deploy checklist — upload ALL of these together (partial uploads break search/play):"
echo ""

STATIC_FILES=(
  index.html
  audio.html
  videos.html
  clips.html
  pdfs.html
  biography.html
  404.html
  site.js
  site.css
  chrome.css
  catalog-version.js
  lectures-meta.js
  lectures-home.js
  lectures-data.js
  home-previews-pool.js
  search-index.js
  videos-data.js
  clips-data.js
  pdfs-data.js
  data/search-audio.json
  sitemap.xml
  robots.txt
)

for file in "${STATIC_FILES[@]}"; do
  if [[ -f "$file" ]]; then
    printf '%s\n' "$file"
  else
    printf '%s  # missing — skip or regenerate\n' "$file" >&2
  fi
done

while IFS= read -r -d '' chunk; do
  printf '%s\n' "${chunk#./}"
done < <(find data/lectures -maxdepth 1 -name '*.js' -print0 2>/dev/null | sort -z)

for thumb_dir in thumb/videos thumb/clips; do
  if [[ -d "$thumb_dir" ]]; then
    echo ""
    echo "New ${thumb_dir} assets (upload when you add lectures):"
    if git rev-parse --is-inside-work-tree &>/dev/null; then
      git status --porcelain "$thumb_dir/" 2>/dev/null | sed 's/^.. //' | grep -E '\.(jpg|jpeg|png|webp)$' || true
    fi
  fi
done
echo "(If none listed above, still upload any new thumb/videos or thumb/clips JPGs.)"

echo ""
echo "Generator scripts (not uploaded): generate-catalog.py, generate-media-catalog.py"