#!/usr/bin/env python3
"""Regenerate sitemap.xml with fresh lastmod dates and video/clip deep links."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

WEBSITE = Path(__file__).resolve().parent
BASE = "https://shaykhabdullahfaisal.com"
TODAY = date.today().isoformat()

STATIC_PAGES = [
    ("/", "weekly", "1.0"),
    ("/audio.html", "weekly", "0.95"),
    ("/videos.html", "weekly", "0.9"),
    ("/clips.html", "weekly", "0.85"),
    ("/pdfs.html", "monthly", "0.8"),
    ("/biography.html", "monthly", "0.75"),
]


def load_ids(js_name: str, const_name: str) -> list[int]:
    text = (WEBSITE / js_name).read_text(encoding="utf-8")
    if f"const {const_name}" not in text:
        raise SystemExit(f"Missing {const_name} in {js_name}")
    ids = [int(m) for m in re.findall(r'"id":\s*(\d+)', text)]
    return sorted(set(ids))


def url_entry(loc: str, changefreq: str, priority: str) -> str:
    return (
        "  <url>\n"
        f"    <loc>{escape(loc)}</loc>\n"
        f"    <lastmod>{TODAY}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>"
    )


def main() -> int:
    video_ids = load_ids("videos-data.js", "VIDEOS")
    clip_ids = load_ids("clips-data.js", "CLIPS")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for path, changefreq, priority in STATIC_PAGES:
        lines.append(url_entry(f"{BASE}{path}", changefreq, priority))

    for vid in video_ids:
        lines.append(url_entry(f"{BASE}/videos.html?video={vid}", "monthly", "0.6"))

    for cid in clip_ids:
        lines.append(url_entry(f"{BASE}/clips.html?clip={cid}", "monthly", "0.55"))

    lines.append("</urlset>")
    lines.append("")

    out = WEBSITE / "sitemap.xml"
    out.write_text("\n".join(lines), encoding="utf-8")
    total = len(STATIC_PAGES) + len(video_ids) + len(clip_ids)
    print(
        f"Wrote {out} ({total} URLs: {len(STATIC_PAGES)} pages, "
        f"{len(video_ids)} videos, {len(clip_ids)} clips)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())