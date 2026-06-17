#!/usr/bin/env python3
"""Generate videos-data.js and clips-data.js from Internet Archive + local thumbs."""
import json
import re
import shutil
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
VIDEO_SRC = WEBSITE.parent / "www" / "Sheikh Faisal Video Lectures"
VIDEO_THUMB_OUT = WEBSITE / "thumb" / "videos"
VIDEOS_ARCHIVE = "https://archive.org/metadata/FaisalVideos"
CLIPS_ARCHIVE = "https://archive.org/metadata/the-creed-of-the-shia"
BLOCKED = {"__ia_thumb.jpg", "__ia_thumb.png"}

# Lectures to hide from the public video library
EXCLUDED_VIDEOS = {
    "02.Sheikh Abdullah Faisal - Unity The Way Forward.mp4",
    "03.Sheikh Abdullah Faisal - Them versus Us.mp4",
    "04.Sheikh Abdullah Faisal - The Muslim Home.mp4",
    "05.Sheikh Abdullah Faisal - The Jinn.mp4",
    "06.Sheikh Abdullah Faisal - The Devil's Deception of The Shia.mp4",
    "07.Sheikh Abdullah Faisal - The Devil's Deception of The Saudi Salafis.mp4",
    "08.Sheikh Abdullah Faisal - The Devil's Deception of The Qadiani.mp4",
    "09.Sheikh Abdullah Faisal - The Devil's Deception of The Murji.mp4",
    "10.Sheikh Abdullah Faisal - Tawba.mp4",
    "11.Sheikh Abdullah Faisal - Signs Before The Day of Judgement.mp4",
    "12.Sheikh Abdullah Faisal - Natural Instincts.mp4",
    "13.Sheikh Abdullah Faisal - Muslim Character.mp4",
    "14.Sheikh Abdullah Faisal - Love and Hate for Allah's Sake.mp4",
    "15.Sheikh Abdullah Faisal - Ideological Warfare.mp4",
    "16.Sheikh Abdullah Faisal - Human Rights.mp4",
    "17.Sheikh Abdullah Faisal - Democracy   The Greatest Shirk.mp4",
    "18.Sheikh Abdullah Faisal - Cancers in the Body of The Ummah.mp4",
    "19.Sheikh Abdullah Faisal   Al Isra Wal Mira'aj.mp4",
}


def norm(text: str) -> str:
    """Normalize title/filename for matching (safe for titles like '02.Christianity…')."""
    text = text.lower().strip()
    text = re.sub(r"\.(mp4|m4v|webm|jpg|jpeg|png|webp)$", "", text, flags=re.I)
    text = re.sub(r"\s*\(\d+\)$", "", text)
    text = re.sub(r"\s*_thumb$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) > 8 and len(b) > 8 and (a in b or b in a):
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def fetch_metadata(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def build_thumb_index() -> dict[str, str]:
    """Index all images in thumb/videos/ and source thumb/ folder."""
    index: dict[str, str] = {}
    VIDEO_THUMB_OUT.mkdir(parents=True, exist_ok=True)

    folders = [VIDEO_THUMB_OUT]
    src_thumb = VIDEO_SRC / "thumb"
    if src_thumb.is_dir():
        folders.append(src_thumb)

    for folder in folders:
        for src in folder.iterdir():
            if src.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            if src.name in BLOCKED:
                continue
            if folder == src_thumb:
                dest = VIDEO_THUMB_OUT / src.name
                if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                    shutil.copy2(src, dest)
            rel = f"thumb/videos/{src.name}"
            for key in (norm(src.stem), norm(src.name)):
                if key:
                    index.setdefault(key, rel)
    return index


def find_thumb(filename: str, local_index: dict[str, str], archive_map: dict[str, str]) -> str | None:
    key = norm(filename)
    if key in local_index:
        return local_index[key]

    best_rel = None
    best_score = 0.0
    for k, rel in local_index.items():
        score = similarity(key, k)
        if score > best_score and score >= 0.92:
            best_score = score
            best_rel = rel
    if best_rel:
        return best_rel

    if key in archive_map:
        return archive_map[key]
    for k, rel in archive_map.items():
        if similarity(key, k) >= 0.92:
            return rel
    return None


def build_videos():
    meta = fetch_metadata(VIDEOS_ARCHIVE)
    local_index = build_thumb_index()

    archive_thumb_map: dict[str, str] = {}
    for item in meta.get("files", []):
        name = item.get("name", "")
        if "FaisalVideos.thumbs/" in name and name.endswith(".jpg") and "_000001." in name:
            base = name.split("/")[-1]
            stem = re.sub(r"_000001\.jpg$", "", base)
            archive_thumb_map[norm(stem)] = f"https://archive.org/download/FaisalVideos/{name}"

    all_mp4 = [
        f["name"] for f in meta.get("files", [])
        if f.get("name", "").endswith(".mp4") and not f["name"].startswith("FaisalVideos.thumbs")
    ]
    chosen = []
    seen = set()
    for name in sorted(all_mp4):
        if name in EXCLUDED_VIDEOS:
            continue
        plain = name.replace(".ia.mp4", ".mp4")
        if name.endswith(".ia.mp4") and plain in all_mp4:
            continue
        dedupe_key = plain.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        chosen.append(name)

    videos = []
    for name in chosen:
        videos.append({
            "id": len(videos),
            "title": Path(name).stem,
            "file": name,
            "archive": name,
            "thumb": find_thumb(name, local_index, archive_thumb_map),
            "stream": "https://archive.org/download/FaisalVideos/" + urllib.parse.quote(name),
        })

    return videos


def build_clips():
    meta = fetch_metadata(CLIPS_ARCHIVE)

    archive_thumb_map: dict[str, str] = {}
    for item in meta.get("files", []):
        name = item.get("name", "")
        if "the-creed-of-the-shia.thumbs/" in name and name.endswith(".jpg") and "_000001." in name:
            base = name.split("/")[-1]
            stem = re.sub(r"_000001\.jpg$", "", base)
            archive_thumb_map[norm(stem)] = f"https://archive.org/download/the-creed-of-the-shia/{name}"

    all_mp4 = [f["name"] for f in meta.get("files", []) if f.get("name", "").endswith(".mp4")]
    chosen = []
    seen = set()

    for name in sorted(all_mp4):
        plain = name.replace(".ia.mp4", ".mp4")
        dedupe_key = plain.lower()
        if name.endswith(".ia.mp4") and plain in all_mp4:
            continue
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        chosen.append(name)

    clips = []
    for name in chosen:
        stem = Path(name).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        thumb = find_thumb(stem + ".mp4", {}, archive_thumb_map)
        if not thumb:
            thumb = find_thumb(name, {}, archive_thumb_map)

        clips.append({
            "id": len(clips),
            "title": stem,
            "file": name,
            "archive": name,
            "thumb": thumb,
            "stream": "https://archive.org/download/the-creed-of-the-shia/" + urllib.parse.quote(name),
        })

    return clips


def write_js(filename: str, const_name: str, base_const: str, base_url: str, items: list):
    path = WEBSITE / filename
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-media-catalog.py to refresh */\n")
        handle.write(f'const {base_const} = "{base_url}";\n\n')
        handle.write(f"const {const_name} = ")
        json.dump(items, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")
    print(f"Wrote {path} ({len(items)} items)")


def main():
    videos = build_videos()
    clips = build_clips()
    write_js("videos-data.js", "VIDEOS", "VIDEOS_ARCHIVE_BASE", "https://archive.org/download/FaisalVideos/", videos)
    write_js("clips-data.js", "CLIPS", "CLIPS_ARCHIVE_BASE", "https://archive.org/download/the-creed-of-the-shia/", clips)

    v_thumbs = sum(1 for v in videos if v.get("thumb"))
    c_thumbs = sum(1 for c in clips if c.get("thumb"))
    print(f"Videos: {len(videos)} ({v_thumbs} with thumbnails)")
    print(f"Clips: {len(clips)} ({c_thumbs} with thumbnails)")


if __name__ == "__main__":
    main()