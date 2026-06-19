#!/usr/bin/env python3
"""Build small WebP card thumbnails for audio lecture images."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

WEBSITE = Path(__file__).resolve().parent
LECTURE_GLOBS = [
    WEBSITE / "data" / "lectures" / "*.js",
    WEBSITE / "lectures-data.js",
    WEBSITE / "lectures-home.js",
    WEBSITE / "lectures-meta.js",
    WEBSITE / "home-previews-pool.js",
]

CARD_MAX_PX = 320
WEBP_QUALITY = 80


def collect_thumb_paths() -> set[str]:
    paths: set[str] = set()
    for pattern in LECTURE_GLOBS:
        for file in WEBSITE.glob(str(pattern.relative_to(WEBSITE))):
            text = file.read_text(encoding="utf-8")
            for match in re.finditer(r'"thumb":\s*"([^"]+)"', text):
                src = match.group(1)
                if src.startswith("thumb/") and not src.startswith("thumb/cards/"):
                    paths.add(src)
    return paths


def card_rel(src: str) -> str:
    inner = src[len("thumb/") :]
    stem = Path(inner).stem
    parent = Path(inner).parent
    if str(parent) == ".":
        return f"thumb/cards/{stem}.webp"
    return f"thumb/cards/{parent.as_posix()}/{stem}.webp"


def optimize_one(src_rel: str) -> tuple[bool, int, int]:
    src = WEBSITE / src_rel
    if not src.is_file():
        return False, 0, 0

    dest = WEBSITE / card_rel(src_rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        with Image.open(dest) as existing:
            if max(existing.size) <= CARD_MAX_PX + 2:
                return False, src.stat().st_size, dest.stat().st_size

    with Image.open(src) as img:
        img = img.convert("RGB")
        img.thumbnail((CARD_MAX_PX, CARD_MAX_PX), Image.Resampling.LANCZOS)
        img.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)

    return True, src.stat().st_size, dest.stat().st_size


def main() -> None:
    paths = sorted(collect_thumb_paths())
    created = 0
    before = 0
    after = 0
    missing = []

    for src_rel in paths:
        src = WEBSITE / src_rel
        if not src.is_file():
            missing.append(src_rel)
            continue
        changed, src_size, dest_size = optimize_one(src_rel)
        before += src_size
        after += dest_size
        if changed:
            created += 1

    print(f"Card thumbs: {len(paths)} sources, {created} regenerated, {len(missing)} missing")
    if paths:
        print(f"Size: {before / 1024 / 1024:.1f} MB source -> {after / 1024 / 1024:.1f} MB cards")


if __name__ == "__main__":
    main()