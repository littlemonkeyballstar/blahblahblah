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

EXCLUDED_LECTURES = {
    "abu ghazi",
    "abu mutassim",
}


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
    "The Sealed Nector (Series)": "The Sealed Nectar",
    "Prophets_Seerah": "Prophets & Seerah",
    "Tawheed": "Tawheed",
    "Aqeedah": "Aqeedah",
    "Fiqh_Worship": "Fiqh & Worship",
    "Jihad": "Jihad",
    "Khilafah": "Khilafah",
    "Refutation": "Refutations",
    "Jokers in the pack": "Jokers in the Pack",
    "The Devils Deception": "The Devil's Deception",
    "Wicked_Scholars": "Wicked Scholars",
    "Science in the quran": "Science in the Quran",
    "Nikah_Divorce": "Nikah & Divorce",
    "Ramadan": "Ramadan",
    "Diseases_of_the_Heart": "Diseases of the Heart",
    "Personality Disorders (Series)": "Personality Disorders",
    "Who Are You?": "Who Are You?",
    "Radio_Show": "Radio Show",
    "Character_Dawah": "Character & Dawah",
    "Ummah_Affairs": "Ummah & Contemporary Issues",
    "The 5 Desperate Zindeeq": "The 5 Desperate Zindeeq",
}

# Fold small / sect-specific folders into broader categories
CATEGORY_MERGE = {
    "Madkhali": "Refutation",
    "Shia": "Refutation",
    "Conference": "Ummah_Affairs",
}

SUB_DISPLAY = {
    "rules_of_divorce": "Rules of Divorce",
    "rules_of_nikah": "Rules of Nikah",
    "types_to_avoid": "Types to Avoid Marrying",
    "fiqh_of_divorce": "Fiqh of Divorce",
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

# Sub-series display order within a category (overrides A–Z by label).
CATEGORY_SUB_ORDER: dict[str, list[str]] = {
    "Nikah_Divorce": [
        "rules_of_divorce",
        "rules_of_nikah",
        "types_to_avoid",
        "fiqh_of_divorce",
    ],
}

NIKAH_DIVORCE_SUB_PATTERNS: list[tuple[str, str]] = [
    (r"rules of divorce", "rules_of_divorce"),
    (r"rules of nikah", "rules_of_nikah"),
    (r"types of (women|men) you should not marry", "types_to_avoid"),
    (r"fiqh of divorce", "fiqh_of_divorce"),
]

CAT_ORDER = [
    "Tafseer",
    "The Sealed Nector (Series)",
    "Prophets_Seerah",
    "Tawheed",
    "Aqeedah",
    "Fiqh_Worship",
    "Jihad",
    "Khilafah",
    "Refutation",
    "Jokers in the pack",
    "The 5 Desperate Zindeeq",
    "The Devils Deception",
    "Wicked_Scholars",
    "Science in the quran",
    "Nikah_Divorce",
    "Ramadan",
    "Diseases_of_the_Heart",
    "Personality Disorders (Series)",
    "Who Are You?",
    "Radio_Show",
    "Character_Dawah",
    "Ummah_Affairs",
    "General",
]

# Re-home root-level lectures into named series when the title matches
TITLE_SERIES_PATTERNS: list[tuple[str, str, str | None]] = [
    (r"sealed nectar", "The Sealed Nector (Series)", None),
    (r"jokers in the pack", "Jokers in the pack", None),
    (r"devil'?s deception|devils deception", "The Devils Deception", None),
    (r"science of quran", "Science in the quran", None),
    (r"who are you", "Who Are You?", None),
    (r"personality disorders", "Personality Disorders (Series)", None),
    (r"^radio show", "Radio_Show", None),
    (r"rules of nikah|rules of divorce|types of (women|men) you should not marry", "Nikah_Divorce", None),
    (r"wicked scholar", "Wicked_Scholars", None),
    (r"5 desperate zindeeq|five desperate zindeeq", "The 5 Desperate Zindeeq", None),
    (r"diseases of the heart", "Diseases_of_the_Heart", None),
    (r"at conference", "Ummah_Affairs", None),
    (r"refut|refuting", "Refutation", None),
    (r"\bshia\b", "Refutation", None),
    (r"madkhali", "Refutation", None),
    (r"khilaf|caliphate", "Khilafah", None),
    (r"ramadan|ramadhan|laylatul qadr|virtues of ramadan", "Ramadan", None),
    (r"\bjihad\b", "Jihad", None),
    (r"tawheed|tauheed|branches of tauheed", "Tawheed", None),
]

# Thematic buckets for miscellaneous root-level lectures
TITLE_THEME_PATTERNS: list[tuple[str, str]] = [
    (
        r"takfir|kufr|kafir|kaafir|shirk|democracy|munafiq|hypocrite|wala.?wal.?bara|al.?wala|"
        r"impediment|excuse of ignorance|kufr doona|dismantle the sharia|meltdown of democracy|"
        r"are you a takfiri|what makes you a kafir|25 things.*kaafir|shirk in perspective|"
        r"invalidation of your actions|let.?s call a spade",
        "Aqeedah",
    ),
    (
        r"salah|prayer|fasting|hajj|fiqh|paradise \[part|rules of |description of paradise|"
        r"description of the prophet|merits of salah|how to make hajj|fiqhul waaqi|menses|clothing|"
        r"qadr|pillars of qadr|lailatul qadr explained",
        "Fiqh_Worship",
    ),
    (
        r"\badam |\bmusa |\bibrahim|prophet muhammad|miracles of the prophet|israa|mi.?raaj|"
        r"isra wal|boy and the king|pharoah|khidr|qaroon|islam of umar|signs of musa",
        "Prophets_Seerah",
    ),
    (
        r"sincere|brotherhood|sisterhood|etiquette|dawah|manhood|priorities|balanced nation|"
        r"etiquettes of dawah|merits and etiquettes|foundations of the islamic brotherhood",
        "Character_Dawah",
    ),
    (
        r"cancers in the body|challenges facing|ideological warfare|human rights|muslim character|"
        r"natural instinct|signs before the day|unity|the jinn\b|\btawba\b|black magic|\bmagic\b|"
        r"dreams|judgment day|leadership in islam|changing the goalpost|mad dogs|sheikh abdullah faisal -",
        "Ummah_Affairs",
    ),
]

TAFSIR_SUB_PATTERNS: list[tuple[str, str]] = [
    (r"baqarah|baqara", "Tafsir baqarah"),
    (r"taubah|tawbah", "Tafseer surah Taubah"),
    (r"ta.?ha|taha", "tafseer TaHa"),
    (r"furqan", "Tafseer Al Furqan"),
    (r"kahf", "tafseer al kahf"),
    (r"naml", "Tafseer an-naml"),
    (r"ankabut", "Tafseer Al - ankabut"),
    (r"ahzab", "tafseer surah al ahzab"),
    (r"luqman", "Tafseer surah luqman"),
    (r"yasin|ya.?sin", "tafseer surah yasin"),
]


def norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s*_thumb$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_tafsir_subcategory(title: str) -> str | None:
    for pattern, sub_id in TAFSIR_SUB_PATTERNS:
        if re.search(pattern, title, re.I):
            return sub_id
    return None


def detect_nikah_divorce_subcategory(title: str) -> str | None:
    for pattern, sub_id in NIKAH_DIVORCE_SUB_PATTERNS:
        if re.search(pattern, title, re.I):
            return sub_id
    return None


def resolve_category(title: str, folder_category: str, folder_subcategory: str | None) -> tuple[str, str | None]:
    """Apply merges, series detection, and thematic grouping."""
    category = CATEGORY_MERGE.get(folder_category, folder_category)
    subcategory = folder_subcategory

    if category == "General":
        for pattern, series_cat, series_sub in TITLE_SERIES_PATTERNS:
            if re.search(pattern, title, re.I):
                category = series_cat
                subcategory = series_sub or subcategory
                break
        else:
            for pattern, theme_cat in TITLE_THEME_PATTERNS:
                if re.search(pattern, title, re.I):
                    category = theme_cat
                    break

    if category == "General" and re.search(r"tafseer|tafsir", title, re.I):
        category = "Tafseer"
        subcategory = detect_tafsir_subcategory(title) or subcategory

    if category == "Tafseer" and not subcategory:
        subcategory = detect_tafsir_subcategory(title)

    if category == "Nikah_Divorce":
        subcategory = detect_nikah_divorce_subcategory(title) or subcategory

    return category, subcategory


def lecture_sort_key(lecture: dict) -> str:
    return lecture["title"].lower()


def lecture_dedupe_rank(lecture: dict) -> tuple[int, int]:
    """Prefer category-folder copies over root-level duplicates."""
    archive = lecture["archive"]
    return (1 if "/" in archive else 0, len(archive))


def dedupe_lectures(lectures: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for lecture in lectures:
        key = (lecture["category"], norm(lecture["title"]))
        existing = best.get(key)
        if existing is None or lecture_dedupe_rank(lecture) > lecture_dedupe_rank(existing):
            best[key] = lecture
    return list(best.values())


def label_for_category(category: str) -> str:
    return DISPLAY_NAMES.get(category, category.replace("_", " "))


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


def display_title(filename_stem: str) -> str:
    """Strip leading episode numbers from lecture display titles."""
    return strip_number_prefix(filename_stem).strip()


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

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.lower().endswith(".mp3"):
                continue
            if norm(filename[:-4]) in EXCLUDED_LECTURES:
                continue
            full = Path(dirpath) / filename
            rel = full.relative_to(ROOT)
            folder = rel.parent.as_posix() if rel.parent != Path(".") else ""
            if folder:
                parts = folder.split("/")
                folder_category = parts[0]
                folder_subcategory = "/".join(parts[1:]) if len(parts) > 1 else None
            else:
                folder_category, folder_subcategory = "General", None

            title = display_title(filename[:-4])
            category, subcategory = resolve_category(title, folder_category, folder_subcategory)
            thumb = resolver.resolve(full, title, folder)

            lectures.append({
                "title": title,
                "category": category,
                "categoryLabel": label_for_category(category),
                "subcategory": subcategory,
                "subcategoryLabel": SUB_DISPLAY.get(subcategory, subcategory) if subcategory else None,
                "archive": archive_path(folder, filename, by_path, by_name),
                "thumb": thumb,
            })

    lectures = dedupe_lectures(lectures)
    lectures.sort(key=lecture_sort_key)
    for index, lecture in enumerate(lectures):
        lecture["id"] = index

    categories: dict[str, dict] = {}
    for lecture in lectures:
        cat = lecture["category"]
        categories.setdefault(cat, {"label": label_for_category(cat), "subs": {}})
        sub = lecture.get("subcategory")
        if sub:
            categories[cat]["subs"][sub] = SUB_DISPLAY.get(sub, sub)

    cat_meta = []
    for cat_id in sorted(categories, key=lambda c: label_for_category(c).lower()):
        sub_order = CATEGORY_SUB_ORDER.get(cat_id)
        if sub_order:
            rank = {sub_id: index for index, sub_id in enumerate(sub_order)}
            subs = sorted(
                categories[cat_id]["subs"].items(),
                key=lambda x: (rank.get(x[0], len(sub_order)), x[1]),
            )
        else:
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