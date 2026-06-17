#!/usr/bin/env python3
"""
Scan SheikhFaisalAudioLectures, resolve thumbnails, and regenerate lectures-data.js.

Thumbnail resolution order:
  1. Image in same folder as the MP3 (exact / fuzzy name match)
  2. Series cover (cover.png / COVER.jpg) in the lecture folder or a parent folder
  3. Category thumb/ subfolder (exact / fuzzy match)
  4. Root thumb/ folder (exact / fuzzy match)
  5. Embedded album art extracted from the MP3 ID3 tags

Run after adding lectures or thumbnails:
    python3 generate-catalog.py
"""
import hashlib
import json
import os
import re
import shutil
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

try:
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

ROOT = Path(__file__).resolve().parent.parent / "www" / "SheikhFaisalAudioLectures"
WEBSITE = Path(__file__).resolve().parent
WEB_THUMB = WEBSITE / "thumb"
SRC_CACHE = WEB_THUMB / "_src"
ASSETS_OUT = WEB_THUMB / "assets"  # GitHub Pages-safe copy (no _src underscore folder)
EXTRACTED = WEB_THUMB / "extracted"
ARCHIVE_URL = "https://archive.org/metadata/FaisalAudios"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
COVER_NAMES = {"cover.png", "cover.jpg", "cover.jpeg", "cover.webp",
                "COVER.png", "COVER.jpg", "COVER.jpeg", "COVER.webp"}
# Never use these as lecture thumbnails (generic fallbacks / spectrograms)
THUMB_BLOCKLIST = {"__ia_thumb.jpg", "__ia_thumb.png"}


def is_blocked_thumb(path: Path) -> bool:
    name = path.name
    if name in THUMB_BLOCKLIST:
        return True
    if name.startswith("__"):
        return True
    if "spectrogram" in name.lower():
        return True
    return False


def is_low_quality_thumb(path: Path) -> bool:
    """Skip *_thumb.jpg variants in Website/thumb/ — prefer full-quality images."""
    return bool(re.search(r"_thumb$", path.stem, re.I))

DISPLAY_NAMES = {
    "General": "General Lectures",
    "Tafseer": "Tafseer",
    "Jihad": "Jihad",
    "Tawheed": "Tawheed",
    "Ramadan": "Ramadan",
    "Refutation": "Refutations",
    "Conference": "Conference",
    "Diseases_of_the_Heart": "Diseases of the Heart",
    "Jokers in the pack": "Jokers in the Pack",
    "Khilafah": "Khilafah",
    "Madkhali": "Madkhali",
    "Nikah_Divorce": "Nikah & Divorce",
    "Personality Disorders (Series)": "Personality Disorders",
    "Radio_Show": "Radio Show",
    "Science in the quran": "Science in the Quran",
    "Shia": "Shia",
    "The 5 Desperate Zindeeq": "The 5 Desperate Zindeeq",
    "The Devils Deception": "The Devil's Deception",
    "The Sealed Nector (Series)": "The Sealed Nectar",
    "Who Are You?": "Who Are You?",
    "Wicked_Scholars": "Wicked Scholars",
}

SUB_DISPLAY = {
    "Tafsir baqarah": "Tafsir Al-Baqarah",
    "Tafseer surah Taubah": "Tafsir At-Tawbah",
    "tafseer TaHa": "Tafsir Ta-Ha",
    "Tafseer Al Furqan": "Tafsir Al-Furqan",
    "tafseer al kahf": "Tafsir Al-Kahf",
    "Tafseer an-naml": "Tafsir An-Naml",
    "Tafseer Al - ankabut": "Tafsir Al-Ankabut",
    "tafseer surah al ahzab": "Tafsir Al-Ahzab",
    "Tafseer surah luqman": "Tafsir Luqman",
    "tafseer surah yasin": "Tafsir Ya-Sin",
}

CAT_ORDER = [
    "Tafseer", "Tawheed", "Jihad", "Ramadan", "Refutation", "Khilafah", "Shia",
    "Wicked_Scholars", "Diseases_of_the_Heart", "The Sealed Nector (Series)",
    "The Devils Deception", "Science in the quran", "Nikah_Divorce", "Conference",
    "Radio_Show", "Madkhali", "Jokers in the pack", "The 5 Desperate Zindeeq",
    "Who Are You?", "Personality Disorders (Series)", "General",
]


def norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s*_thumb$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def web_path(path: Path) -> str:
    return path.relative_to(WEBSITE).as_posix()


def publish_asset(cached: Path) -> str:
    """Mirror thumb/_src/... → thumb/assets/... for GitHub Pages (Jekyll ignores _folders)."""
    rel = cached.relative_to(SRC_CACHE)
    dest = ASSETS_OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size != cached.stat().st_size:
        shutil.copy2(cached, dest)
    return web_path(dest)


def strip_number_prefix(name: str) -> str:
    """16.Sheikh Abdullah Faisal - X.mp3 → Sheikh Abdullah Faisal - X.mp3"""
    return re.sub(r"^\d+\.", "", name)


def load_archive_index():
    with urllib.request.urlopen(ARCHIVE_URL, timeout=30) as resp:
        data = json.load(resp)
    by_path, by_name = {}, {}
    for item in data.get("files", []):
        name = item.get("name", "")
        if name.endswith(".mp3"):
            by_path[name.lower()] = name
            base = os.path.basename(name)
            by_name.setdefault(base.lower(), name)
            # While IA renames are processing, map stripped local names → old numbered files
            stripped = strip_number_prefix(base)
            if stripped.lower() != base.lower():
                by_name.setdefault(stripped.lower(), name)
                if "/" in name:
                    folder, sfile = name.rsplit("/", 1)
                    by_path.setdefault(f"{folder}/{stripped}".lower(), name)
    return by_path, by_name


def archive_path(folder, filename, by_path, by_name):
    local = f"{folder}/{filename}" if folder else filename
    if local.lower() in by_path:
        return by_path[local.lower()]
    hit = by_name.get(filename.lower())
    if hit:
        return hit
    stripped = strip_number_prefix(filename)
    if stripped != filename:
        if folder:
            alt = f"{folder}/{stripped}"
            if alt.lower() in by_path:
                return by_path[alt.lower()]
        hit = by_name.get(stripped.lower())
        if hit:
            return hit
    return local


def mirror_source_images():
    """Copy every image from the source tree into thumb/_src/ (preserving paths)."""
    copied = 0
    if not ROOT.exists():
        return copied
    SRC_CACHE.mkdir(parents=True, exist_ok=True)
    for src in ROOT.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in IMAGE_EXTS:
            continue
        rel = src.relative_to(ROOT)
        dest = SRC_CACHE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
            copied += 1
    return copied


def sync_flat_thumbs():
    """Copy category thumb/ images into the flat thumb/ folder when missing."""
    copied = 0
    WEB_THUMB.mkdir(parents=True, exist_ok=True)
    for thumb_dir in ROOT.rglob("thumb"):
        if not thumb_dir.is_dir():
            continue
        for src in thumb_dir.iterdir():
            if src.suffix.lower() not in IMAGE_EXTS:
                continue
            dest = WEB_THUMB / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
                copied += 1
    return copied


def extract_embedded_art(mp3_path: Path, rel_key: str) -> str | None:
    """Extract ID3 embedded cover art to thumb/extracted/."""
    if not HAS_MUTAGEN:
        return None
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    digest = hashlib.md5(rel_key.encode()).hexdigest()[:14]
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if not audio.tags:
            return None
        for key in audio.tags.keys():
            if not key.startswith("APIC"):
                continue
            frame = audio.tags[key]
            mime = getattr(frame, "mime", "image/jpeg") or "image/jpeg"
            ext = ".png" if "png" in mime.lower() else ".jpg"
            dest = EXTRACTED / f"{digest}{ext}"
            if not dest.exists():
                dest.write_bytes(frame.data)
            return web_path(dest)
    except Exception:
        return None
    return None


class ThumbResolver:
    def __init__(self):
        self.audio_flat: list[tuple[str, str]] = []  # images in Website/thumb/ root only
        self.src_images: list[tuple[str, str]] = []
        self.covers: dict[str, str] = {}
        self._build_indexes()

    def _build_indexes(self):
        if WEB_THUMB.exists():
            by_key: dict[str, str] = {}
            for path in sorted(WEB_THUMB.iterdir()):
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                    continue
                if is_blocked_thumb(path) or is_low_quality_thumb(path):
                    continue
                key = norm(path.stem)
                if not key or len(key) < 4:
                    continue
                by_key[key] = web_path(path)
            self.audio_flat = [(key, rel) for key, rel in sorted(by_key.items())]

        if SRC_CACHE.exists():
            for path in SRC_CACHE.rglob("*"):
                if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                    if is_blocked_thumb(path):
                        continue
                    rel = web_path(path)
                    self.src_images.append((norm(path.stem), rel))

        for folder in [ROOT, *ROOT.rglob("*")]:
            if not folder.is_dir():
                continue
            for cover_name in COVER_NAMES:
                cover = folder / cover_name
                if cover.is_file():
                    cached = SRC_CACHE / cover.relative_to(ROOT)
                    if cached.is_file():
                        self.covers[str(folder.relative_to(ROOT))] = publish_asset(cached)

    def _best_fuzzy(self, target: str, candidates: list[tuple[str, str]], threshold=0.82):
        if len(target) < 10:
            return None
        best_rel = None
        best_score = 0.0
        for stem, rel in candidates:
            if "__ia_thumb" in rel or len(stem) < 10:
                continue
            score = similarity(target, stem)
            if score > best_score and score >= threshold:
                best_score = score
                best_rel = rel
        return best_rel

    def _images_in_dir(self, directory: Path) -> list[tuple[str, str]]:
        """Images stored inline next to the MP3 (not category thumb/ subfolders)."""
        results = []
        if not directory.is_dir():
            return results
        for item in directory.iterdir():
            if not item.is_file() or item.suffix.lower() not in IMAGE_EXTS:
                continue
            if item.name in COVER_NAMES or is_blocked_thumb(item):
                continue
            cached = SRC_CACHE / item.relative_to(ROOT)
            if cached.is_file():
                results.append((norm(item.stem), publish_asset(cached)))
        return results

    def resolve(self, mp3_path: Path, title: str, rel_folder: str) -> str | None:
        filename = mp3_path.name
        stem = Path(filename).stem
        target = norm(stem)
        mp3_dir = mp3_path.parent

        # 1. Same folder as MP3
        local_images = self._images_in_dir(mp3_dir)
        for s, rel in local_images:
            if s == target or norm(title) == s:
                return rel
        fuzzy = self._best_fuzzy(target, local_images, threshold=0.88)
        if fuzzy:
            return fuzzy

        # 2. Website/thumb/ root artwork (featured slideshow + site-wide priority)
        for key in (target, norm(title)):
            for s, rel in self.audio_flat:
                if s == key:
                    return rel
        fuzzy = self._best_fuzzy(target, self.audio_flat, threshold=0.85)
        if fuzzy:
            return fuzzy

        # 3. Series cover — walk up from mp3 folder to category root
        current = mp3_dir
        while True:
            try:
                rel_dir = str(current.relative_to(ROOT))
            except ValueError:
                break
            if rel_dir in self.covers:
                return self.covers[rel_dir]
            if current == ROOT:
                break
            current = current.parent

        # 4. Category thumb/ folder
        if rel_folder:
            cat = rel_folder.split("/")[0]
            cat_thumb = ROOT / cat / "thumb"
            cat_images = self._images_in_dir(cat_thumb) if cat_thumb.is_dir() else []
            for s, rel in cat_images:
                if s == target:
                    return rel
            fuzzy = self._best_fuzzy(target, cat_images, threshold=0.85)
            if fuzzy:
                return fuzzy

        # 5. Embedded album art
        rel_key = f"{rel_folder}/{filename}" if rel_folder else filename
        return extract_embedded_art(mp3_path, rel_key)


def main():
    if not HAS_MUTAGEN:
        print("Warning: install mutagen for embedded cover extraction (pip install mutagen)")

    mirrored = mirror_source_images()
    copied = sync_flat_thumbs()
    by_path, by_name = load_archive_index()
    resolver = ThumbResolver()

    lectures = []
    categories = {}
    stats = {"file": 0, "cover": 0, "category": 0, "flat": 0, "embedded": 0, "none": 0}

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.lower().endswith(".mp3"):
                continue
            full = Path(dirpath) / filename
            rel = full.relative_to(ROOT)
            folder = rel.parent.as_posix() if rel.parent != Path(".") else ""
            if folder:
                parts = folder.split("/")
                category = parts[0]
                subcategory = "/".join(parts[1:]) if len(parts) > 1 else None
            else:
                category, subcategory = "General", None

            title = filename[:-4]
            thumb = resolver.resolve(full, title, folder)

            lectures.append({
                "id": len(lectures),
                "title": title,
                "category": category,
                "categoryLabel": DISPLAY_NAMES.get(category, category),
                "subcategory": subcategory,
                "subcategoryLabel": SUB_DISPLAY.get(subcategory, subcategory) if subcategory else None,
                "archive": archive_path(folder, filename, by_path, by_name),
                "thumb": thumb,
            })

            categories.setdefault(category, {"label": DISPLAY_NAMES.get(category, category), "subs": {}})
            if subcategory:
                categories[category]["subs"][subcategory] = SUB_DISPLAY.get(subcategory, subcategory)

    cat_meta = []
    for cat_id in CAT_ORDER:
        if cat_id not in categories:
            continue
        subs = sorted(categories[cat_id]["subs"].items(), key=lambda x: x[1])
        cat_meta.append({
            "id": cat_id,
            "label": categories[cat_id]["label"],
            "count": sum(1 for lec in lectures if lec["category"] == cat_id),
            "subcategories": [
                {
                    "id": sub_id,
                    "label": sub_label,
                    "count": sum(
                        1 for lec in lectures
                        if lec["category"] == cat_id and lec["subcategory"] == sub_id
                    ),
                }
                for sub_id, sub_label in subs
            ],
        })

    out = WEBSITE / "lectures-data.js"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-catalog.py to refresh */\n")
        handle.write('const ARCHIVE_BASE = "https://archive.org/download/FaisalAudios/";\n')
        handle.write('const THUMB_FALLBACK = "thumb/__ia_thumb.jpg";\n\n')
        handle.write("const LECTURE_CATEGORIES = ")
        json.dump(cat_meta, handle, ensure_ascii=False, indent=2)
        handle.write(";\n\nconst LECTURES = ")
        json.dump(lectures, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")

    with_thumb = sum(1 for lec in lectures if lec["thumb"])
    from_embedded = sum(1 for lec in lectures if lec["thumb"] and "/extracted/" in lec["thumb"])
    from_assets = sum(1 for lec in lectures if lec["thumb"] and "/assets/" in lec["thumb"])
    from_flat = sum(
        1 for lec in lectures
        if lec["thumb"] and lec["thumb"].startswith("thumb/")
        and "/" not in lec["thumb"][len("thumb/"):]
    )

    print(f"Mirrored {mirrored} source images to thumb/_src/")
    print(f"Copied {copied} images to flat thumb/")
    print(f"Generated {len(lectures)} lectures across {len(cat_meta)} categories")
    print(f"Thumbnails resolved: {with_thumb} / {len(lectures)} ({100*with_thumb/len(lectures):.1f}%)")
    print(f"  - flat thumb/: {from_flat}")
    print(f"  - thumb/assets/ (series covers, inline): {from_assets}")
    print(f"  - thumb/extracted/ (embedded MP3 art): {from_embedded}")
    print(f"  - no thumbnail: {len(lectures) - with_thumb}")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()