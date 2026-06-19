#!/usr/bin/env python3
"""
Extract clip thumbnail frames with ffmpeg from local short-form MP4s.

Sources (in order):
  1. Existing JPG in Shaykh Faisal clips/shorts/thumb/ (if present)
  2. ffmpeg frame grab at 3s into the local .mp4

Output: Website/thumb/clips/{clip-filename-stem}.jpg

Requires: ffmpeg

    python3 extract-clip-thumbs.py
    python3 generate-media-catalog.py   # prefers thumb/clips/ over IA URLs
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
CLIP_SRC = WEBSITE.parent / "www" / "Shaykh Faisal cllips⁄shorts"
THUMB_OUT = WEBSITE / "thumb" / "clips"
SRC_THUMB = CLIP_SRC / "thumb"
BLOCKED = {"__ia_thumb.jpg", "__ia_thumb.png"}


def norm_key(name: str) -> str:
    text = name.lower().strip()
    text = re.sub(r"\.(mp4|m4v|webm|jpg|jpeg|png|webp)$", "", text, flags=re.I)
    text = re.sub(r"\.ia$", "", text, flags=re.I)
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
        "-ss", "3", "-i", str(mp4),
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
    if not CLIP_SRC.is_dir():
        print(f"Clip folder not found: {CLIP_SRC}")
        sys.exit(1)

    THUMB_OUT.mkdir(parents=True, exist_ok=True)
    use_ffmpeg = has_ffmpeg()
    if not use_ffmpeg:
        print("Warning: ffmpeg not found — will only copy existing thumb/ images")

    copied = extracted = skipped = failed = 0

    src_by_key: dict[str, Path] = {}
    if SRC_THUMB.is_dir():
        for img in SRC_THUMB.iterdir():
            if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            if img.name in BLOCKED:
                continue
            src_by_key[norm_key(img.stem)] = img

    mp4_files = sorted(set(CLIP_SRC.glob("*.mp4")) | set(CLIP_SRC.glob("*.MP4")))
    print(f"Processing {len(mp4_files)} local clip files…")

    for mp4 in mp4_files:
        key = norm_key(mp4.stem)
        dest = THUMB_OUT / f"{mp4.stem}.jpg"

        if dest.exists() and dest.stat().st_size > 500:
            skipped += 1
            continue

        if key in src_by_key:
            shutil.copy2(src_by_key[key], dest)
            copied += 1
            continue

        if use_ffmpeg and extract_frame(mp4, dest):
            extracted += 1
            continue

        failed += 1
        print(f"  No thumb: {mp4.name}")

    stream_extracted = extract_stream_thumbs(use_ffmpeg)

    print(
        f"Done — copied {copied}, extracted {extracted}, stream {stream_extracted}, "
        f"already had {skipped}, failed {failed}"
    )
    print(f"Thumbnails in {THUMB_OUT}: {len(list(THUMB_OUT.glob('*.jpg')))}")
    print("Run: python3 generate-media-catalog.py")


def extract_stream_thumbs(use_ffmpeg: bool) -> int:
    """Grab frames from IA streams for catalog clips still missing a local thumb."""
    if not use_ffmpeg:
        return 0

    import importlib.util
    import json
    import re
    import urllib.parse

    clips_path = WEBSITE / "clips-data.js"
    if not clips_path.is_file():
        return 0

    spec = importlib.util.spec_from_file_location("gmc", WEBSITE / "generate-media-catalog.py")
    gmc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gmc)

    clips_text = clips_path.read_text(encoding="utf-8")
    match = re.search(r"const CLIPS = (\[.*\]);", clips_text, re.S)
    if not match:
        return 0

    clips = json.loads(match.group(1))
    local_index = gmc.build_clip_thumb_index()
    extracted = 0

    for clip in clips:
        archive = clip.get("archive") or clip.get("file", "")
        stem = Path(archive).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        if gmc.find_clip_thumb(stem + ".mp4", local_index, {}):
            continue

        dest = THUMB_OUT / f"{stem}.jpg"
        if dest.exists() and dest.stat().st_size > 500:
            continue

        stream = clip.get("stream")
        if not stream:
            continue

        if extract_frame_from_url(stream, dest):
            extracted += 1
            print(f"  Stream thumb: {stem}")

    return extracted


def extract_frame_from_url(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "3", "-i", url,
        "-vframes", "1", "-q:v", "3",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=180)
        return dest.exists() and dest.stat().st_size > 500
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


if __name__ == "__main__":
    main()