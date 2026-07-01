#!/usr/bin/env python3
"""
Extract clip thumbnail frames with ffmpeg for the published clips library.

Prefers exact filename matches; never uses fuzzy matching (wrong thumbs).
Falls back to the Internet Archive stream URL when no exact local .mp4 exists.

Output: Website/thumb/clips/{archive-stem}.jpg

    python3 extract-clip-thumbs.py
    python3 extract-clip-thumbs.py --force
    python3 extract-clip-thumbs.py --force --source archive
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
THUMB_OUT = WEBSITE / "thumb" / "clips"
CLIPS_ARCHIVE = "https://archive.org/metadata/the-creed-of-the-shia"
CLIPS_STREAM_BASE = "https://archive.org/download/the-creed-of-the-shia/"
VF = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black"

DEFAULT_CLIPS_SRCS = [
    Path("/media/sawako/BIgP/Shaykh Faisal cllips⁄shorts"),
    WEBSITE.parent / "www" / "Shaykh Faisal cllips⁄shorts",
    WEBSITE.parent / "www" / "Shaykh Faisal clips",
]


def resolve_clips_src() -> Path | None:
    env = os.environ.get("FAISAL_CLIPS_SRC", "").strip()
    if env:
        path = Path(env)
        return path if path.is_dir() else None
    for candidate in DEFAULT_CLIPS_SRCS:
        if candidate.is_dir():
            return candidate
    return None


def norm_key(name: str) -> str:
    text = name.lower().strip()
    text = re.sub(r"\.(mp4|m4v|webm|ia|jpg|jpeg|png|webp)$", "", text, flags=re.I)
    text = re.sub(r"\s*\(\d+\)$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def probe_duration(source: str) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", source,
            ],
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        return float(out.decode().strip())
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return None


def seek_time(source: str) -> str:
    duration = probe_duration(source)
    if not duration or duration <= 20:
        return "00:00:03"
    seconds = min(30.0, max(2.0, duration * 0.12))
    return f"00:00:{int(seconds):02d}"


def extract_frame(source: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", seek_time(source), "-i", source,
        "-vframes", "1", "-q:v", "2", "-vf", VF,
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=180)
        return dest.exists() and dest.stat().st_size > 500
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def fetch_metadata() -> dict:
    req = urllib.request.Request(CLIPS_ARCHIVE, headers={"User-Agent": "shaykhabdullahfaisal-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _load_catalog_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_media_catalog", WEBSITE / "generate-media-catalog.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def published_archive_names(meta: dict) -> list[str]:
    """Same dedupe / exclude rules as generate-media-catalog.build_clips."""
    mod = _load_catalog_module()
    EXCLUDED_CLIP_NORMS = mod.EXCLUDED_CLIP_NORMS
    norm = mod.norm

    all_mp4 = [f["name"] for f in meta.get("files", []) if f.get("name", "").endswith(".mp4")]
    chosen: list[str] = []
    seen: set[str] = set()
    for name in sorted(all_mp4):
        plain = name.replace(".ia.mp4", ".mp4")
        dedupe_key = plain.lower()
        if name.endswith(".ia.mp4") and plain in all_mp4:
            continue
        if dedupe_key in seen:
            continue
        stem = Path(name).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        if norm(stem) in EXCLUDED_CLIP_NORMS:
            continue
        seen.add(dedupe_key)
        chosen.append(name)
    return chosen


def load_catalog_files() -> list[str]:
    text = (WEBSITE / "clips-data.js").read_text(encoding="utf-8")
    return re.findall(r'"file":\s*"([^"]+\.mp4)"', text)


def build_local_index(clips_src: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for mp4 in clips_src.iterdir():
        if mp4.suffix.lower() != ".mp4":
            continue
        index[norm_key(mp4.stem)] = mp4
    return index


def find_local_exact(archive_name: str, local_index: dict[str, Path]) -> Path | None:
    stem = Path(archive_name).stem
    if stem.endswith(".ia"):
        stem = stem[:-3]
    return local_index.get(norm_key(stem))


def stream_url(archive_name: str) -> str:
    return CLIPS_STREAM_BASE + urllib.parse.quote(archive_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract local thumbnails for clip library")
    parser.add_argument("--force", action="store_true", help="Re-extract even when output JPG already exists")
    parser.add_argument(
        "--source",
        choices=("auto", "local", "archive"),
        default="auto",
        help="auto = exact local file else archive stream; archive = always stream",
    )
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Only process files listed in clips-data.js (published clips)",
    )
    args = parser.parse_args()

    if not has_ffmpeg():
        print("ffmpeg is required for clip thumbnails")
        return 1

    THUMB_OUT.mkdir(parents=True, exist_ok=True)
    clips_src = resolve_clips_src()
    local_index = build_local_index(clips_src) if clips_src else {}

    if args.catalog:
        archive_names = load_catalog_files()
        print(f"Published clips from catalog: {len(archive_names)}")
    else:
        meta = fetch_metadata()
        archive_names = published_archive_names(meta)
        print(f"Published clips from archive rules: {len(archive_names)}")

    if clips_src:
        print(f"Local clips folder: {clips_src} ({len(local_index)} files)")
    else:
        print("No local clips folder — using archive streams only")

    extracted = skipped = failed = 0
    for archive_name in archive_names:
        stem = Path(archive_name).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        dest = THUMB_OUT / f"{stem}.jpg"

        if dest.exists() and dest.stat().st_size > 500 and not args.force:
            skipped += 1
            continue

        source: str | None = None
        if args.source == "archive":
            source = stream_url(archive_name)
        elif args.source == "local":
            local_mp4 = find_local_exact(archive_name, local_index) if local_index else None
            source = str(local_mp4) if local_mp4 else None
        else:
            local_mp4 = find_local_exact(archive_name, local_index) if local_index else None
            source = str(local_mp4) if local_mp4 else stream_url(archive_name)

        if not source:
            failed += 1
            print(f"  No source: {archive_name}")
            continue

        if extract_frame(source, dest):
            extracted += 1
            label = "local" if source.startswith("/") or Path(source).exists() else "archive"
            print(f"  OK ({label}): {archive_name}")
        else:
            failed += 1
            print(f"  FAIL: {archive_name}")

    print(
        f"Done — extracted {extracted}, skipped {skipped}, failed {failed}"
    )
    print(f"Thumbnails in {THUMB_OUT}: {len(list(THUMB_OUT.glob('*.jpg')))}")
    print("Run: python3 generate-media-catalog.py")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())