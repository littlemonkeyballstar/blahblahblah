#!/usr/bin/env python3
"""
Extract video thumbnail frames with ffmpeg for lectures missing a thumb image.

Sources (in order):
  1. Existing JPG in Sheikh Faisal Video Lectures/thumb/
  2. ffmpeg frame grab at 45s into the local .mp4

Output: Website/thumb/videos/{video-title}.jpg

Requires: ffmpeg

    python3 extract-video-thumbs.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
VIDEO_SRC = WEBSITE.parent / "www" / "Sheikh Faisal Video Lectures"
THUMB_OUT = WEBSITE / "thumb" / "videos"
SRC_THUMB = VIDEO_SRC / "thumb"
BLOCKED = {"__ia_thumb.jpg", "__ia_thumb.png"}


def norm_key(name: str) -> str:
    text = name.lower().strip()
    text = re.sub(r"\.(mp4|m4v|webm|jpg|jpeg|png|webp)$", "", text, flags=re.I)
    text = re.sub(r"\s*\(\d+\)$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def extract_frame(mp4: Path, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "45", "-i", str(mp4),
        "-vframes", "1", "-q:v", "3",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        return dest.exists() and dest.stat().st_size > 500
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def main():
    if not VIDEO_SRC.is_dir():
        print(f"Video folder not found: {VIDEO_SRC}")
        sys.exit(1)

    THUMB_OUT.mkdir(parents=True, exist_ok=True)
    use_ffmpeg = has_ffmpeg()
    if not use_ffmpeg:
        print("Warning: ffmpeg not found — will only copy existing thumb/ images")

    copied = extracted = skipped = 0
    index: dict[str, Path] = {}

    # Index source thumb folder by normalized key
    src_by_key: dict[str, Path] = {}
    if SRC_THUMB.is_dir():
        for img in SRC_THUMB.iterdir():
            if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            if img.name in BLOCKED:
                continue
            src_by_key[norm_key(img.stem)] = img

    mp4_files = sorted(VIDEO_SRC.glob("*.mp4"))
    print(f"Processing {len(mp4_files)} local video files…")

    for mp4 in mp4_files:
        key = norm_key(mp4.stem)
        dest = THUMB_OUT / f"{mp4.stem}.jpg"

        if dest.exists() and dest.stat().st_size > 500:
            skipped += 1
            index[key] = dest
            continue

        if key in src_by_key:
            shutil.copy2(src_by_key[key], dest)
            copied += 1
            index[key] = dest
            continue

        if use_ffmpeg and extract_frame(mp4, dest):
            extracted += 1
            index[key] = dest
            continue

        print(f"  No thumb: {mp4.name}")

    print(f"Done — copied {copied}, extracted {extracted}, already had {skipped}")
    print(f"Thumbnails in {THUMB_OUT}: {len(list(THUMB_OUT.glob('*.jpg')))}")
    print("Run: python3 generate-media-catalog.py")


if __name__ == "__main__":
    main()