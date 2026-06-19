#!/usr/bin/env python3
"""Build compact home-previews-pool.js from catalog files."""
import json
import re
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent


def extract_array(name: str, text: str) -> list:
    match = re.search(rf"const {name} = (\[.*?\]);", text, re.S)
    return json.loads(match.group(1))


def compact_audio_from_search(entries: list[dict]) -> list[dict]:
    pool = []
    for item in entries:
        entry = {
            "id": item["id"],
            "title": item["title"],
            "categoryLabel": item.get("sub", ""),
        }
        if item.get("thumb"):
            entry["thumb"] = item["thumb"]
        pool.append(entry)
    return pool


def main() -> None:
    clips = extract_array("CLIPS", (WEBSITE / "clips-data.js").read_text(encoding="utf-8"))
    videos = extract_array("VIDEOS", (WEBSITE / "videos-data.js").read_text(encoding="utf-8"))
    audio_path = WEBSITE / "data" / "search-audio.json"
    audio_entries = json.loads(audio_path.read_text(encoding="utf-8")) if audio_path.is_file() else []

    lines = ["/* Auto-generated — run build-home-previews-pool.py to refresh */"]
    lines.append(
        "const HOME_CLIPS_POOL = "
        + json.dumps(
            [{"id": item["id"], "title": item["title"], "thumb": item.get("thumb")} for item in clips],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + ";"
    )
    lines.append(
        "const HOME_VIDEOS_POOL = "
        + json.dumps(
            [{"id": item["id"], "title": item["title"], "thumb": item.get("thumb")} for item in videos],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + ";"
    )
    lines.append(
        "const HOME_AUDIO_POOL = "
        + json.dumps(compact_audio_from_search(audio_entries), ensure_ascii=False, separators=(",", ":"))
        + ";"
    )

    out = WEBSITE / "home-previews-pool.js"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()