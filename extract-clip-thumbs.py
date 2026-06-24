#!/usr/bin/env python3
"""
Extract clip thumbnail frames with ffmpeg from local short .mp4 files.

Matches Internet Archive the-creed-of-the-shia filenames to local clips.

Output: Website/thumb/clips/{archive-stem}.jpg

    FAISAL_CLIPS_SRC="/path/to/clips" python3 extract-clip-thumbs.py
    python3 extract-clip-thumbs.py --force
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
THUMB_OUT = WEBSITE / "thumb" / "clips"
CLIPS_ARCHIVE = "https://archive.org/metadata/the-creed-of-the-shia"
VF = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black"

DEFAULT_CLIPS_SRCS = [
    Path("/media/sawako/BIgP/Shaykh Faisal cllips⁄shorts"),
    WEBSITE.parent / "www" / "Shaykh Faisal clips",
]


def resolve_clips_src() -> Path:
    env = os.environ.get("FAISAL_CLIPS_SRC", "").strip()
    if env:
        return Path(env)
    for candidate in DEFAULT_CLIPS_SRCS:
        if candidate.is_dir():
            return candidate
    return DEFAULT_CLIPS_SRCS[0]


def norm_key(name: str) -> str:
    text = name.lower().strip()
    text = re.sub(r"\.(mp4|m4v|webm|ia|jpg|jpeg|png|webp)$", "", text, flags=re.I)
    text = re.sub(r"\s*\(\d+\)$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) > 8 and len(b) > 8 and (a in b or b in a):
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def video_duration(mp4: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(mp4),
            ],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return float(out.decode().strip())
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return None


def seek_time(mp4: Path) -> str:
    duration = video_duration(mp4)
    if not duration or duration <= 20:
        return "00:00:03"
    seconds = min(30.0, max(2.0, duration * 0.12))
    whole = int(seconds)
    return f"00:00:{whole:02d}"


def extract_frame(mp4: Path, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", seek_time(mp4), "-i", str(mp4),
        "-vframes", "1", "-q:v", "2", "-vf", VF,
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        return dest.exists() and dest.stat().st_size > 500
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def fetch_archive_mp4s() -> list[str]:
    req = urllib.request.Request(CLIPS_ARCHIVE, headers={"User-Agent": "shaykhabdullahfaisal-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return sorted(f["name"] for f in data.get("files", []) if f.get("name", "").lower().endswith(".mp4"))


def build_local_index(clips_src: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for mp4 in clips_src.iterdir():
        if mp4.suffix.lower() != ".mp4":
            continue
        index[norm_key(mp4.stem)] = mp4
    return index


def find_local_mp4(archive_name: str, local_index: dict[str, Path]) -> Path | None:
    stem = Path(archive_name).stem
    if stem.endswith(".ia"):
        stem = stem[:-3]
    key = norm_key(stem)
    if key in local_index:
        return local_index[key]
    best_path = None
    best_score = 0.0
    for local_key, path in local_index.items():
        score = similarity(key, local_key)
        if score > best_score and score >= 0.90:
            best_score = score
            best_path = path
    return best_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract local thumbnails for clip library")
    parser.add_argument("--force", action="store_true", help="Re-extract even when output JPG already exists")
    args = parser.parse_args()

    clips_src = resolve_clips_src()
    if not clips_src.is_dir():
        print(f"Clips folder not found: {clips_src}")
        return 1

    THUMB_OUT.mkdir(parents=True, exist_ok=True)
    use_ffmpeg = has_ffmpeg()
    if not use_ffmpeg:
        print("ffmpeg is required for clip thumbnails")
        return 1

    local_index = build_local_index(clips_src)
    archive_names = fetch_archive_mp4s()
    extracted = skipped = missing_local = failed = 0

    print(f"Source: {clips_src}")
    print(f"Local clip files: {len(local_index)}")
    print(f"Archive catalog: {len(archive_names)} clips")

    for archive_name in archive_names:
        stem = Path(archive_name).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        dest = THUMB_OUT / f"{stem}.jpg"

        if dest.exists() and dest.stat().st_size > 500 and not args.force:
            skipped += 1
            continue

        mp4 = find_local_mp4(archive_name, local_index)
        if not mp4:
            missing_local += 1
            continue

        if extract_frame(mp4, dest):
            extracted += 1
        else:
            failed += 1
            print(f"  Extract failed: {archive_name} ({mp4.name})")

    print(
        f"Done — extracted {extracted}, skipped {skipped}, "
        f"no local file {missing_local}, failed {failed}"
    )
    print(f"Thumbnails in {THUMB_OUT}: {len(list(THUMB_OUT.glob('*.jpg')))}")
    print("Run: python3 generate-media-catalog.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())